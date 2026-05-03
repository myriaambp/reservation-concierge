"""Eval harness — the **evaluation** class concept artifact.

Three eval suites, all run in one script:
  1. intent_cases  : did the supervisor call the right tool with reasonable args?
  2. ranker_cases  : did the ranker produce a 1-2-sentence rationale that
                     matches a per-case judge_criteria?
  3. notifier_cases: did the notifier emit valid JSON matching the schema?

Suites 2 + 3 use LLM-as-judge (Opus). Suite 1 uses programmatic checks since
the answer is a tool name + key args, no semantic interpretation needed.

Run:
    python -m backend.evals.run_evals [--cases-only intent|ranker|notifier]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from backend.agents.prompts import NOTIFIER_PROMPT, RANKER_PROMPT, SUPERVISOR_PROMPT
from backend.config import get_settings
from backend.llm.client import chat
from backend.tools.reservation_tools import ANTHROPIC_TOOLS

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CASES_PATH = Path(__file__).parent / "cases.json"
_OUTPUT_DIR = Path(__file__).parent / "output"


JUDGE_PROMPT = """You are a strict pass/fail judge. Given a target output and a criteria,
respond with JSON: {"pass": <bool>, "reason": "<one short sentence>"}.

Be unforgiving. If criteria says '1-2 sentences', three sentences fails. If it
says 'no exclamation marks', one fails.

Output ONLY valid JSON."""


@dataclass
class Result:
    suite: str
    case_id: str
    passed: bool
    reason: str = ""
    raw: str = ""


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def by_suite(self) -> dict[str, tuple[int, int]]:
        out: dict[str, list[int]] = {}
        for r in self.results:
            out.setdefault(r.suite, [0, 0])
            out[r.suite][1] += 1
            if r.passed:
                out[r.suite][0] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}

    def overall(self) -> tuple[int, int]:
        return (
            sum(1 for r in self.results if r.passed),
            len(self.results),
        )


def _load_cases() -> dict:
    return json.loads(_CASES_PATH.read_text())


def _strip_code_fence(s: str) -> str:
    """Gemini sometimes wraps JSON in ```json ... ``` fences."""
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()


def _judge(target: str, criteria: str) -> tuple[bool, str]:
    settings = get_settings()
    resp = chat(
        model=settings.judge_model,
        system=JUDGE_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"OUTPUT:\n{target}\n\nCRITERIA:\n{criteria}",
            }
        ],
        max_tokens=1024,
        agent_name="judge",
        temperature=0.0,
    )
    text = _strip_code_fence(resp.text)
    try:
        parsed = json.loads(text)
        return bool(parsed.get("pass", False)), parsed.get("reason", "")
    except json.JSONDecodeError:
        # If the judge returns malformed JSON, fail closed.
        return False, f"judge returned non-JSON: {text[:120]}"


# ---------------- Suite 1: intent ----------------

def run_intent(cases: list[dict]) -> list[Result]:
    settings = get_settings()
    out: list[Result] = []
    for case in cases:
        # Single Claude call with tools bound; expect a tool_use block.
        resp = chat(
            model=settings.supervisor_model,
            system=SUPERVISOR_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"[user_id=eval-user] {case['input']}",
                }
            ],
            tools=ANTHROPIC_TOOLS,
            max_tokens=2048,
            agent_name="eval-supervisor",
            temperature=0.0,
        )
        if not resp.tool_uses:
            out.append(
                Result("intent", case["id"], False, "no tool call", raw=resp.text[:200])
            )
            continue

        first = resp.tool_uses[0]
        if first.name != case["expected_tool"]:
            out.append(
                Result(
                    "intent",
                    case["id"],
                    False,
                    f"expected {case['expected_tool']}, got {first.name}",
                )
            )
            continue

        # Spot-check expected args (substring/equality on keys).
        ok = True
        for k, v in case.get("expected_args", {}).items():
            actual = first.input.get(k)
            if isinstance(v, str):
                if actual is None or v.lower() not in str(actual).lower():
                    ok = False
                    break
            else:
                if actual != v:
                    ok = False
                    break
        out.append(
            Result(
                "intent",
                case["id"],
                ok,
                "" if ok else f"args mismatch on {case['expected_args']} vs {first.input}",
            )
        )
    return out


# ---------------- Suite 2: ranker ----------------

def run_ranker(cases: list[dict]) -> list[Result]:
    settings = get_settings()
    out: list[Result] = []
    for case in cases:
        prompt_input = (
            f"Slot: {json.dumps(case['slot'])}\n"
            f"User prefs: {json.dumps(case['user_prefs'])}\n"
            f"Restaurant context: (use the slot details)"
        )
        resp = chat(
            model=settings.worker_model,
            system=RANKER_PROMPT,
            messages=[{"role": "user", "content": prompt_input}],
            max_tokens=200,
            agent_name="eval-ranker",
            temperature=0.3,
        )
        text = resp.text
        passed, reason = _judge(text, case["judge_criteria"])
        out.append(Result("ranker", case["id"], passed, reason, raw=text))
    return out


# ---------------- Suite 3: notifier ----------------

def run_notifier(cases: list[dict]) -> list[Result]:
    settings = get_settings()
    out: list[Result] = []
    for case in cases:
        prompt_input = (
            f"Slot: {json.dumps(case['slot'])}\nRationale: {case['rationale']}"
        )
        resp = chat(
            model=settings.worker_model,
            system=NOTIFIER_PROMPT,
            messages=[{"role": "user", "content": prompt_input}],
            max_tokens=200,
            agent_name="eval-notifier",
            temperature=0.2,
        )
        text = _strip_code_fence(resp.text)
        # Programmatic check first: must be valid JSON with subject + body.
        try:
            parsed = json.loads(text)
            assert "subject" in parsed and "body" in parsed
            assert len(parsed["subject"]) <= 65
        except Exception as exc:
            out.append(
                Result(
                    "notifier", case["id"], False, f"format check failed: {exc}", raw=text
                )
            )
            continue

        passed, reason = _judge(text, case["judge_criteria"])
        out.append(Result("notifier", case["id"], passed, reason, raw=text))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-only", choices=["intent", "ranker", "notifier"])
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    cases = _load_cases()
    report = Report()

    if args.cases_only in (None, "intent"):
        report.results.extend(run_intent(cases["intent_cases"]))
    if args.cases_only in (None, "ranker"):
        report.results.extend(run_ranker(cases["ranker_cases"]))
    if args.cases_only in (None, "notifier"):
        report.results.extend(run_notifier(cases["notifier_cases"]))

    _OUTPUT_DIR.mkdir(exist_ok=True)
    out_file = _OUTPUT_DIR / "latest.json"
    out_file.write_text(
        json.dumps(
            [r.__dict__ for r in report.results], indent=2, default=str
        )
    )

    print()
    print("=" * 60)
    print("EVAL REPORT")
    print("=" * 60)
    for suite, (passed, total) in report.by_suite().items():
        print(f"  {suite:10s}  {passed}/{total}  ({passed / total:.0%})")
    p, t = report.overall()
    print(f"  {'OVERALL':10s}  {p}/{t}  ({p / t:.0%})")
    print(f"\nDetails: {out_file}")
    print()

    return 0 if (p / t) >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
