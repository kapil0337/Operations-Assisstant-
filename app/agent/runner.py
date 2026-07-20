"""Bridges /chat (and the worker) to the compiled LangGraph agent.

Detects whether a session is mid-interrupt (awaiting take_action confirmation)
and resumes it with Command(resume=...) or starts a fresh turn.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from app.agent.graph import get_graph
from app.config import get_settings


@dataclass
class AgentTurnResult:
    session_id: str
    reply: str
    escalated: bool = False
    awaiting_confirmation: bool = False
    tool_calls: list[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""


def _config(session_id: str) -> dict:
    return {
        "configurable": {"thread_id": session_id},
        "recursion_limit": get_settings().recursion_limit,
    }


async def handle_message(
    message: str,
    session_id: str | None = None,
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> AgentTurnResult:
    session_id = session_id or str(uuid.uuid4())
    graph = get_graph()
    config = _config(session_id)

    snapshot = await graph.aget_state(config)
    prior_count = len(snapshot.values.get("messages", [])) if snapshot.values else 0

    if snapshot.next:
        # Graph is paused at an interrupt — this message is the resume value.
        await graph.ainvoke(Command(resume=message), config=config)
    else:
        await graph.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "session_id": session_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "step_count": 0,
                "escalated": False,
                "last_tool_result": None,
                "active_specialist": None,
            },
            config=config,
        )

    snapshot = await graph.aget_state(config)
    values = snapshot.values
    messages = values.get("messages", [])
    new_messages = messages[prior_count:]
    # Compute tool_calls BEFORE early-return on awaiting_confirmation so the
    # caller always sees which tools fired even when we pause mid-turn.
    tool_calls = [m.name for m in new_messages if isinstance(m, ToolMessage)]

    if snapshot.next:
        prompt = "Please confirm to proceed (yes/no)."
        for task in snapshot.tasks:
            if task.interrupts:
                value = task.interrupts[0].value
                if isinstance(value, dict) and "prompt" in value:
                    prompt = value["prompt"]
                break
        return AgentTurnResult(
            session_id=session_id,
            reply=prompt,
            awaiting_confirmation=True,
            tool_calls=tool_calls,
        )

    last_ai = next((m for m in reversed(new_messages) if isinstance(m, AIMessage)), None)
    reply = (
        last_ai.content
        if last_ai and last_ai.content
        else "I'm not sure how to help with that — could you rephrase?"
    )

    return AgentTurnResult(
        session_id=session_id,
        reply=reply,
        escalated=values.get("escalated", False),
        tool_calls=tool_calls,
    )
