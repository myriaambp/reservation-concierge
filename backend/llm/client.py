"""Anthropic client wrapper.

Two responsibilities:
1. Single chokepoint for Claude calls — easier observability, cost tracking,
   and prompt caching wins.
2. Cost tracking — the unit-economics story is real because we measure it. The
   `cost_usd` field is surfaced in the UI so the panel can see the live margin.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic
from anthropic.types import Message

from backend.config import get_settings

# Per-1M token pricing (input, output) — keep current to your contract.
# Sonnet 4.6: $3 / $15. Opus 4.7: $15 / $75. Update if pricing changes.
_PRICING = {
    "claude-opus-4-7": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
}


@dataclass
class CostLedger:
    total_usd: float = 0.0
    by_model: dict[str, float] = field(default_factory=dict)
    by_agent: dict[str, float] = field(default_factory=dict)
    call_count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, model: str, agent: str, in_tok: int, out_tok: int) -> float:
        in_rate, out_rate = _PRICING.get(model, (3.0, 15.0))
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


_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Anthropic(api_key=settings.anthropic_api_key or None)
    return _client


def chat(
    *,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict] | None = None,
    max_tokens: int = 1024,
    agent_name: str = "unknown",
    temperature: float = 0.0,
) -> Message:
    """Single chokepoint for every Claude call. Tracks cost + agent attribution."""
    client = _get_client()
    kwargs: dict[str, Any] = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools

    t0 = time.perf_counter()
    resp = client.messages.create(**kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    in_tok = resp.usage.input_tokens
    out_tok = resp.usage.output_tokens
    cost = _ledger.add(model, agent_name, in_tok, out_tok)

    # Best-effort logging; never fail the call on logging.
    try:
        from rich import print as rprint
        rprint(
            f"[dim]LLM[/dim] [bold]{agent_name}[/bold] "
            f"{model.split('-')[1]} {in_tok}↑/{out_tok}↓ "
            f"${cost:.4f} {elapsed_ms:.0f}ms"
        )
    except Exception:
        pass

    return resp
