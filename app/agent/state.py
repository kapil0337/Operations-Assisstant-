"""LangGraph state: short-term memory of the conversation + tool results."""
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    tenant_id: str          # for tenant-scoped tool queries and memory
    user_id: str            # for RBAC decisions on writes
    step_count: int
    escalated: bool
    # Transient scratch slot written by specialist nodes, consumed by observe.
    last_tool_result: dict[str, Any] | None
    # Which specialist node just ran (for tracing / routing back to supervisor).
    active_specialist: str | None
