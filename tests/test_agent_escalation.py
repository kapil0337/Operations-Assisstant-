"""Escalation scenario: out-of-scope request must escalate, not hallucinate."""
from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage

from app.agent.runner import handle_message


@pytest.mark.asyncio
async def test_out_of_scope_request_escalates(fake_pool, monkeypatch):
    scripted = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "escalate_to_human",
                    "args": {"reason": "out_of_scope", "summary": "User asked about the weather."},
                    "id": "c1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="I've escalated this to a human agent who can help."),
    ]
    idx = {"i": 0}

    async def fake_llm(messages, tools=None, callbacks=None):
        msg = scripted[idx["i"]]
        idx["i"] += 1
        return msg

    monkeypatch.setattr("app.agent.nodes.invoke_with_fallback", fake_llm)

    sid = f"test-{uuid.uuid4()}"
    result = await handle_message("What's the weather like in Paris today?", session_id=sid)

    assert result.escalated is True
    assert result.awaiting_confirmation is False
    assert "escalate_to_human" in result.tool_calls
    assert "take_action" not in result.tool_calls
    assert "lookup_order" not in result.tool_calls
    assert len(fake_pool.inserted_escalations) == 1
    assert idx["i"] == 2
