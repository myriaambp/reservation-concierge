"""Unified LLM client — runs Gemini through Vertex AI by default, billed
against GCP credits (zero out-of-pocket for the build week).

Key design decision: the rest of the codebase consumes a provider-agnostic
`LLMResponse` (text + tool_uses + usage). The Anthropic ↔ Gemini schema and
message-format differences are isolated to this module.

Auth: gcloud Application Default Credentials. Run once on the dev machine:
    gcloud auth application-default login
On Cloud Run, the runtime service account works automatically.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from backend.config import get_settings


# Per-1M token pricing for cost tracking (input, output) USD.
# Gemini 2.5 prices as of late 2025; update if Vertex pricing moves.
_PRICING = {
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.0-flash-001": (0.15, 0.60),
    "gemini-2.0-flash": (0.15, 0.60),
}


# ---------------- Provider-agnostic response shape ----------------

@dataclass
class ToolUse:
    """A single tool invocation requested by the model."""
    id: str  # synthesized; Gemini doesn't expose tool-use IDs
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str
    tool_uses: list[ToolUse]
    input_tokens: int
    output_tokens: int
    raw: Any = None  # provider-native response, for debugging


# ---------------- Cost tracking ----------------

@dataclass
class CostLedger:
    total_usd: float = 0.0
    by_model: dict[str, float] = field(default_factory=dict)
    by_agent: dict[str, float] = field(default_factory=dict)
    call_count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, model: str, agent: str, in_tok: int, out_tok: int) -> float:
        # Strip suffixes like "-001" so the price table can match.
        key = model
        if key not in _PRICING:
            for k in _PRICING:
                if model.startswith(k):
                    key = k
                    break
        in_rate, out_rate = _PRICING.get(key, (0.30, 2.50))
        cost = (in_tok / 1_000_000) * in_rate + (out_tok / 1_000_000) * out_rate
        with self._lock:
            self.total_usd += cost
            self.by_model[model] = self.by_model.get(model, 0.0) + cost
            self.by_agent[agent] = self.by_agent.get(agent, 0.0) + cost
            self.call_count += 1
        return cost


_ledger = CostLedger()


def get_ledger() -> CostLedger:
    return _ledger


# ---------------- Genai client ----------------

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        settings = get_settings()
        _client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id or None,
            location=settings.gcp_region or "us-central1",
        )
    return _client


# ---------------- Schema converter (Pydantic -> Gemini-compatible) ----------------

def _clean_schema(schema: dict) -> dict:
    """Strip Pydantic JSON Schema features Gemini doesn't accept.

    - Unwrap `anyOf: [{type: X}, {type: null}]` → just `{type: X}` (optionality
      is conveyed by absence from `required`).
    - Drop `title`, `default` keys (Gemini ignores or rejects).
    - Recurse into properties.
    """
    if not isinstance(schema, dict):
        return schema

    # anyOf with null = Optional. Take the non-null branch.
    if "anyOf" in schema:
        non_null = [b for b in schema["anyOf"] if b.get("type") != "null"]
        if len(non_null) == 1:
            inner = _clean_schema(non_null[0])
            # Preserve description from outer.
            for k in ("description", "enum"):
                if k in schema and k not in inner:
                    inner[k] = schema[k]
            return inner

    out: dict = {}
    for k, v in schema.items():
        if k in ("title", "default", "$defs"):
            continue
        if k == "properties" and isinstance(v, dict):
            out[k] = {pk: _clean_schema(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            out[k] = _clean_schema(v)
        else:
            out[k] = v
    return out


def _convert_tools(anthropic_tools: list[dict]) -> list[types.Tool]:
    """Convert our Anthropic-format tool list into a single Gemini Tool.

    Gemini expects `Tool(function_declarations=[FunctionDeclaration(...)])`.
    """
    declarations: list[types.FunctionDeclaration] = []
    for t in anthropic_tools:
        params = _clean_schema(t.get("input_schema", {"type": "object", "properties": {}}))
        declarations.append(
            types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=params,
            )
        )
    return [types.Tool(function_declarations=declarations)]


# ---------------- Message converter (Anthropic-shape -> Gemini Content list) ----------------

def _convert_messages(messages: list[dict]) -> list[types.Content]:
    """Translate our internal Anthropic-shape messages into Gemini Contents.

    Input (Anthropic-shape) supports:
      - {"role": "user"|"assistant", "content": str}
      - {"role": "assistant", "content": [{"type":"tool_use", "id", "name", "input"}, ...]}
      - {"role": "user", "content": [{"type":"tool_result", "tool_use_id", "content"}, ...]}
    """
    out: list[types.Content] = []
    for m in messages:
        role = m.get("role", "user")
        gemini_role = "model" if role == "assistant" else "user"
        content = m.get("content", "")

        if isinstance(content, str):
            out.append(
                types.Content(role=gemini_role, parts=[types.Part.from_text(text=content)])
            )
            continue

        # List of blocks. Tool_use blocks emitted by the model become
        # function_call parts. Tool_result blocks become function_response parts.
        parts: list[types.Part] = []
        for block in content:
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                parts.append(types.Part.from_text(text=block["text"]))
            elif btype == "tool_use":
                parts.append(
                    types.Part.from_function_call(
                        name=block["name"],
                        args=block.get("input", {}) or {},
                    )
                )
            elif btype == "tool_result":
                # Gemini wants the tool name in function_response. We don't
                # have it on the result block, so we pull it from the matching
                # function_call earlier in the conversation. Kept simple for
                # our use case: most loops have a single tool call per turn.
                tool_name = block.get("name") or _find_tool_name_for_id(
                    out, block.get("tool_use_id", "")
                ) or "tool"
                payload_raw = block.get("content", "")
                if isinstance(payload_raw, str):
                    payload = {"output": payload_raw}
                elif isinstance(payload_raw, dict):
                    payload = payload_raw
                else:
                    payload = {"output": str(payload_raw)}
                parts.append(
                    types.Part.from_function_response(
                        name=tool_name, response=payload
                    )
                )
        if parts:
            out.append(types.Content(role=gemini_role, parts=parts))
    return out


def _find_tool_name_for_id(prior: list[types.Content], _id: str) -> str | None:
    """Best-effort: scan prior model turns for a function_call whose name we
    can pair with this tool_result. We don't track IDs cross-turn so we fall
    back to the most recent function_call's name."""
    last_name: str | None = None
    for c in prior:
        if c.role != "model":
            continue
        for p in c.parts or []:
            fc = getattr(p, "function_call", None)
            if fc and fc.name:
                last_name = fc.name
    return last_name


# ---------------- Public chat() ----------------

def chat(
    *,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict] | None = None,
    max_tokens: int = 1024,
    agent_name: str = "unknown",
    temperature: float = 0.0,
    disable_thinking: bool = False,
) -> LLMResponse:
    """Single chokepoint for every Gemini call. Tracks cost + agent attribution.
    Returns provider-agnostic LLMResponse.

    `disable_thinking=True` zeroes the Gemini 2.5 thinking budget — useful for
    formatter tasks (ranker, notifier) where reasoning tokens just eat into
    the output budget without adding quality.
    """
    client = _get_client()

    contents = _convert_messages(messages)
    config_kwargs: dict[str, Any] = {
        "system_instruction": system,
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if disable_thinking:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    if tools:
        config_kwargs["tools"] = _convert_tools(tools)
        # When tools are present, allow auto function calling off — we want to
        # see the function_call in the response and dispatch ourselves.
        config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
            disable=True
        )

    config = types.GenerateContentConfig(**config_kwargs)

    t0 = time.perf_counter()
    resp = client.models.generate_content(
        model=model, contents=contents, config=config
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Extract text + tool_uses from candidate parts.
    text_parts: list[str] = []
    tool_uses: list[ToolUse] = []
    for cand in resp.candidates or []:
        if not cand.content or not cand.content.parts:
            continue
        for part in cand.content.parts:
            if getattr(part, "text", None):
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc:
                tool_uses.append(
                    ToolUse(
                        id=f"tu-{secrets.token_hex(4)}",
                        name=fc.name,
                        input=dict(fc.args) if fc.args else {},
                    )
                )

    in_tok = (
        resp.usage_metadata.prompt_token_count if resp.usage_metadata else 0
    )
    out_tok = (
        resp.usage_metadata.candidates_token_count if resp.usage_metadata else 0
    )
    cost = _ledger.add(model, agent_name, in_tok or 0, out_tok or 0)

    try:
        from rich import print as rprint
        rprint(
            f"[dim]LLM[/dim] [bold]{agent_name}[/bold] "
            f"{model.split('-')[-1]} {in_tok}↑/{out_tok}↓ "
            f"${cost:.4f} {elapsed_ms:.0f}ms"
        )
    except Exception:
        pass

    return LLMResponse(
        text="".join(text_parts).strip(),
        tool_uses=tool_uses,
        input_tokens=in_tok or 0,
        output_tokens=out_tok or 0,
        raw=resp,
    )
