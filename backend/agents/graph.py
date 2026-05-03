"""LangGraph wiring — the **multi-agent orchestration** class concept artifact.

Two graphs:

CHAT_GRAPH (user-triggered):
    START → supervisor → [booker | END]
    Booker is conditionally entered when scratchpad has a confirmation_token.

TICK_GRAPH (cron-triggered):
    START → scout → [ranker → notifier → END | END]
    Ranker only runs if scout produced pending_slots.

Both share the same AgentState schema and run on an in-memory checkpointer
since per-conversation state is short-lived (persistent state is in Firestore).
"""
from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from backend.agents.booker import booker_node
from backend.agents.notifier import notifier_node
from backend.agents.ranker import ranker_node
from backend.agents.scout import scout_node
from backend.agents.supervisor import supervisor_node
from backend.memory.state import AgentState


def _route_after_supervisor(state: AgentState) -> str:
    scratchpad = state.get("scratchpad", {}) or {}
    if scratchpad.get("confirmation_token"):
        return "booker"
    return END


def _route_after_scout(state: AgentState) -> str:
    return "ranker" if state.get("pending_slots") else END


def build_chat_graph() -> "CompiledGraph":
    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("booker", booker_node)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"booker": "booker", END: END},
    )
    g.add_edge("booker", END)
    return g.compile()


def build_tick_graph() -> "CompiledGraph":
    g = StateGraph(AgentState)
    g.add_node("scout", scout_node)
    g.add_node("ranker", ranker_node)
    g.add_node("notifier", notifier_node)
    g.add_edge(START, "scout")
    g.add_conditional_edges(
        "scout",
        _route_after_scout,
        {"ranker": "ranker", END: END},
    )
    g.add_edge("ranker", "notifier")
    g.add_edge("notifier", END)
    return g.compile()


# Module-level singletons; cheap to compile, expensive to do per-request.
chat_graph = build_chat_graph()
tick_graph = build_tick_graph()


def render_diagrams(out_dir: Path | None = None) -> None:
    """Render both graphs as Mermaid PNGs for the README. Run once at build time:
        python -c "from backend.agents.graph import render_diagrams; render_diagrams()"
    """
    out_dir = out_dir or Path(__file__).resolve().parents[2] / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, graph in [("chat_graph", chat_graph), ("tick_graph", tick_graph)]:
        try:
            png = graph.get_graph().draw_mermaid_png()
            (out_dir / f"{name}.png").write_bytes(png)
        except Exception as exc:
            # Mermaid rendering needs internet; ok to skip locally.
            print(f"[skip] {name}.png: {exc}")
