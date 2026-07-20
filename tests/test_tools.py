"""Unit tests for the four tools, against the FakePool (no real Postgres)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.tools.base import ToolError
from app.tools.escalate_to_human import EscalateInput, escalate_to_human
from app.tools.knowledge_search import KnowledgeSearchInput, knowledge_search
from app.tools.lookup_order import LookupOrderInput, lookup_order
from app.tools.take_action import TakeActionInput, take_action


async def test_lookup_order_found(fake_pool):
    result = await lookup_order.coroutine(order_id="#1042")
    assert result["status"] == "found"
    assert result["order"]["order_id"] == 1042
    assert result["order"]["charge_count"] == 2


async def test_lookup_order_not_found(fake_pool):
    result = await lookup_order.coroutine(order_id="9999")
    assert result["status"] == "not_found"
    assert result["order_id"] == 9999


def test_lookup_order_input_rejects_non_numeric():
    with pytest.raises(ValidationError):
        LookupOrderInput(order_id="abc")


async def test_take_action_creates_ticket(fake_pool):
    result = await take_action.coroutine(action_type="flag_refund", order_id="1042", reason="duplicate charge")
    assert result["status"] == "completed"
    assert fake_pool.inserted_tickets[0]["type"] == "refund"


async def test_take_action_unknown_order_raises(fake_pool):
    with pytest.raises(ToolError):
        await take_action.coroutine(action_type="create_ticket", order_id="424242", reason="damaged item")


def test_take_action_input_rejects_bad_action_type():
    with pytest.raises(ValidationError):
        TakeActionInput(action_type="delete_account", order_id="1042", reason="not a real action")


async def test_escalate_to_human(fake_pool):
    result = await escalate_to_human.coroutine(reason="out_of_scope", summary="weather question", session_id="s1")
    assert result["status"] == "escalated"
    assert fake_pool.inserted_escalations[0]["session_id"] == "s1"


async def test_knowledge_search_returns_results(fake_pool):
    result = await knowledge_search.coroutine(query="how long does shipping take", top_k=3)
    assert len(result["results"]) == 1
    assert result["results"][0]["source"] == "refund_policy.md"


def test_escalate_input_requires_summary():
    with pytest.raises(ValidationError):
        EscalateInput(reason="x", summary="")


def test_knowledge_search_input_bounds_top_k():
    with pytest.raises(ValidationError):
        KnowledgeSearchInput(query="test", top_k=0)
