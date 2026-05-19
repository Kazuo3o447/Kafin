from __future__ import annotations

from typing import Any

from pipeline.state import PipelineState


def build_langgraph() -> Any:
    """Build the minimal LangGraph skeleton when langgraph is installed."""

    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise RuntimeError("langgraph is not installed; install project dependencies first") from exc

    graph = StateGraph(PipelineState)
    graph.add_node("load_data", _dummy_load_data)
    graph.add_node("research_agent", _dummy_research_agent)
    graph.set_entry_point("load_data")
    graph.add_edge("load_data", "research_agent")
    graph.add_edge("research_agent", END)
    return graph.compile()


def _dummy_load_data(state: PipelineState) -> PipelineState:
    state["data_snapshot"] = {"ticker": state["ticker"], "metrics": {}, "sources": []}
    return state


def _dummy_research_agent(state: PipelineState) -> PipelineState:
    state["card"] = {"ticker": state["ticker"], "status": "research_complete"}
    state["status"] = "research_complete"
    return state
