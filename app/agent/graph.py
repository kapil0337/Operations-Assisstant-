"""Builds and compiles the multi-agent supervisor → specialist StateGraph.

Graph structure:
  supervisor → {knowledge_agent, orders_agent, actions_agent, escalation_agent, END}
  knowledge_agent → observe → reflect → supervisor
  orders_agent    → observe → reflect → supervisor
  actions_agent   → observe → reflect → supervisor  (may pause at interrupt)
  escalation_agent→ observe → reflect → supervisor

The compiled graph is stored in a module-level variable initialised at app
startup by init_graph(checkpointer).  Workers call init_graph() in their own
startup hook so each process has its own compiled instance backed by the
shared Postgres checkpointer.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    actions_agent,
    escalation_agent,
    knowledge_agent,
    observe_node,
    orders_agent,
    reflect_node,
    route_from_supervisor,
    supervisor_node,
)
from app.agent.state import AgentState

_graph = None


def build_graph(checkpointer) -> object:
    g = StateGraph(AgentState)

    # Nodes
    g.add_node("supervisor", supervisor_node)
    g.add_node("knowledge_agent", knowledge_agent)
    g.add_node("orders_agent", orders_agent)
    g.add_node("actions_agent", actions_agent)
    g.add_node("escalation_agent", escalation_agent)
    g.add_node("observe", observe_node)
    g.add_node("reflect", reflect_node)

    # Entry point
    g.set_entry_point("supervisor")

    # Supervisor routes to a specialist or ends
    g.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "knowledge_agent": "knowledge_agent",
            "orders_agent": "orders_agent",
            "actions_agent": "actions_agent",
            "escalation_agent": "escalation_agent",
            END: END,
        },
    )

    # All specialists feed into the same observe → reflect → supervisor loop
    for specialist in ("knowledge_agent", "orders_agent", "actions_agent", "escalation_agent"):
        g.add_edge(specialist, "observe")
    g.add_edge("observe", "reflect")
    g.add_edge("reflect", "supervisor")

    return g.compile(checkpointer=checkpointer)


def init_graph(checkpointer) -> None:
    """Called once at startup (API server or worker) to compile the graph."""
    global _graph
    _graph = build_graph(checkpointer)


def get_graph():
    if _graph is None:
        raise RuntimeError(
            "Graph not initialised; call init_graph(checkpointer) during app startup"
        )
    return _graph
