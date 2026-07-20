"""Happy-path: double-charge refund with HITL confirmation (LLM scripted)."""
from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage

from app.agent.runner import handle_message


@pytest.mark.asyncio
async def test_double_charge_refund_happy_path(fake_pool, monkeypatch):
    scripted = [
        # Supervisor decides to call lookup_order
        AIMessage(
            content="",
            tool_calls=[{"name": "lookup_order", "args": {"order_id": "1042"}, "id": "c1", "type": "tool_call"}],
        ),
        # Supervisor decides to call take_action (order is now verified in history)
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "take_action",
                    "args": {"action_type": "flag_refund", "order_id": "1042", "reason": "duplicate charge", "idempotency_key": ""},
                    "id": "c2",
                    "type": "tool_call",
                }
            ],
        ),
        # Supervisor produces final answer after confirmation
        AIMessage(content="I've flagged a refund for the duplicate charge on order 1042."),
    ]
    idx = {"i": 0}

    async def fake_llm(messages, tools=None, callbacks=None):
        msg = scripted[idx["i"]]
        idx["i"] += 1
        return msg

    monkeypatch.setattr("app.agent.nodes.invoke_with_fallback", fake_llm)

    sid = f"test-{uuid.uuid4()}"

    turn1 = await handle_message("I was double-charged for order #1042, please help", session_id=sid)
    assert turn1.awaiting_confirmation is True, "should pause for confirmation"
    assert turn1.escalated is False
    assert "1042" in turn1.reply

    turn2 = await handle_message("yes", session_id=sid)
    assert turn2.awaiting_confirmation is False
    assert turn2.escalated is False
    assert "take_action" in turn2.tool_calls
    assert "refund" in turn2.reply.lower()

    # DB assertion: one refund ticket inserted
    assert len(fake_pool.inserted_tickets) == 1
    assert fake_pool.inserted_tickets[0]["order_id"] == 1042
    assert fake_pool.inserted_tickets[0]["type"] == "refund"
    assert idx["i"] == 3
