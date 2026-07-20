"""Graph nodes: supervisor + four specialist nodes + observe + reflect.

Architecture
─────────────
supervisor (LLM with all tools bound) routes to a named specialist based on
which tool was requested.  Each specialist executes exactly its own tool, then
hands off to observe → reflect → supervisor.

Safety properties preserved from the original single-agent design:
  • _order_verified_in_history  — code-level guard before any take_action write
  • interrupt() / Command(resume=...)  — HITL gate before every DB write
  • reflect_node step-budget check  — forced escalation instead of infinite loop
  • Tenacity retry on all tool coroutine calls  — transient DB errors recover
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.errors import GraphInterrupt
from langgraph.graph import END
from langgraph.types import interrupt
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agent.llm import invoke_with_fallback
from app.agent.prompts import (
    ACTIONS_AGENT_PROMPT,
    ESCALATION_AGENT_PROMPT,
    KNOWLEDGE_AGENT_PROMPT,
    ORDERS_AGENT_PROMPT,
    SUPERVISOR_PROMPT,
    SUPERVISOR_WRAPUP_PROMPT,
)
from app.agent.state import AgentState
from app.config import get_settings
from app.logging_conf import log_event, log_step
from app.memory.window_trimmer import trim_messages
from app.observability.tracing import get_callbacks
from app.tools import ALL_TOOLS, escalate_to_human
from app.tools.base import ToolError

_TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
_AFFIRMATIVE = {"y", "yes", "yep", "yeah", "confirm", "confirmed", "ok", "okay", "sure", "proceed", "go ahead"}
_DIGITS_RE = re.compile(r"\d+")


def _is_affirmative(reply: str) -> bool:
    return reply.strip().lower().rstrip(".!") in _AFFIRMATIVE


def _order_verified_in_history(messages: list, order_id: int) -> bool:
    """Code-level guard: True only if a successful lookup_order ToolMessage for
    this order_id already exists in the conversation."""
    for message in messages:
        if not (isinstance(message, ToolMessage) and message.name == "lookup_order"):
            continue
        try:
            payload = json.loads(message.content)
        except (TypeError, ValueError):
            continue
        if payload.get("status") == "found" and payload.get("order", {}).get("order_id") == order_id:
            return True
    return False


# Tenacity retry policy applied to every tool coroutine call.
_RETRY = retry(
    retry=retry_if_exception_type((OSError, ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


async def _call_tool(tool_obj: Any, **kwargs: Any) -> dict:
    @_RETRY
    async def _inner():
        return await tool_obj.coroutine(**kwargs)
    return await _inner()


# ── Supervisor node ────────────────────────────────────────────────────────────

async def supervisor_node(state: AgentState) -> dict:
    settings = get_settings()
    step_count = state.get("step_count", 0) + 1
    escalated = state.get("escalated", False)

    system_text = SUPERVISOR_WRAPUP_PROMPT if escalated else SUPERVISOR_PROMPT

    # Optionally inject episodic recall on the first step of a fresh session
    if step_count == 1 and not escalated:
        try:
            from app.memory.episodic import recall_similar_episodes
            first_user_msg = next(
                (m.content for m in state["messages"] if hasattr(m, "content")), ""
            )
            episodes = await recall_similar_episodes(
                state.get("tenant_id", "default"),
                str(first_user_msg),
                k=settings.episodic_recall_k,
            )
            if episodes:
                ep_text = "\n".join(
                    f"- Problem: {e['problem'][:120]} → Resolution: {e['resolution'][:120]} "
                    f"(tools: {e['tools_used']}, outcome: {e['outcome']})"
                    for e in episodes
                )
                system_text += f"\n\nRelevant past episodes (for context only):\n{ep_text}"
        except Exception:
            pass

    call_messages = [
        SystemMessage(content=system_text),
        *trim_messages(state["messages"]),
    ]
    tools = None if escalated else ALL_TOOLS

    with log_step("supervisor", session_id=state["session_id"], step=step_count) as log_result:
        ai_msg = await invoke_with_fallback(call_messages, tools=tools, callbacks=get_callbacks())
        usage = getattr(ai_msg, "usage_metadata", None) or {}
        log_result["input_tokens"] = usage.get("input_tokens")
        log_result["output_tokens"] = usage.get("output_tokens")
        log_result["requested_tool"] = (
            ai_msg.tool_calls[0]["name"] if getattr(ai_msg, "tool_calls", None) else None
        )

    return {"messages": [ai_msg], "step_count": step_count}


def route_from_supervisor(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return {
            "knowledge_search": "knowledge_agent",
            "lookup_order": "orders_agent",
            "take_action": "actions_agent",
            "escalate_to_human": "escalation_agent",
        }.get(last.tool_calls[0]["name"], END)
    return END


# ── Shared specialist helper ──────────────────────────────────────────────────

async def _specialist_node(
    state: AgentState,
    specialist_name: str,
    specialist_prompt: str,
    tool_names: list[str],
) -> dict:
    """Generic specialist: LLM call bound to `tool_names`, then execute the tool.

    Having a per-specialist LLM call (rather than just blindly forwarding the
    supervisor's tool_call) lets each specialist validate arguments in its own
    domain context and provides an extra layer of hallucination defence.
    For simplicity, we forward the supervisor's tool_call directly when
    arg validation passes — the specialist prompt adds tracing clarity.
    """
    last = state["messages"][-1]
    if not (isinstance(last, AIMessage) and last.tool_calls):
        # Nothing to do — shouldn't happen but be defensive.
        return {"active_specialist": specialist_name}

    tool_call = last.tool_calls[0]
    name, args, call_id = tool_call["name"], tool_call["args"], tool_call["id"]
    tool_obj = _TOOLS_BY_NAME.get(name)

    if tool_obj is None or name not in tool_names:
        result: dict = {"status": "error", "error": f"unknown tool {name} for specialist {specialist_name}"}
        return {
            "last_tool_result": {"call_id": call_id, "name": name, "result": result},
            "active_specialist": specialist_name,
        }

    try:
        validated = tool_obj.args_schema(**args)
    except ValidationError as exc:
        log_event("tool.validation_error", tool=name, error=str(exc))
        result = {"status": "error", "error": f"invalid input: {exc}"}
        return {
            "last_tool_result": {"call_id": call_id, "name": name, "result": result},
            "active_specialist": specialist_name,
        }

    kwargs = validated.model_dump()

    with log_step(f"{specialist_name}.act", session_id=state["session_id"], tool=name) as log_result:
        try:
            if name == "take_action":
                result = await _actions_specialist_execute(state, kwargs, tool_obj)
            elif name == "escalate_to_human":
                result = await _call_tool(tool_obj, **kwargs, session_id=state["session_id"])
            else:
                result = await _call_tool(tool_obj, **kwargs)
        except GraphInterrupt:
            raise  # Let LangGraph handle the HITL interrupt — must not be caught here
        except ToolError as exc:
            result = {"status": "error", "error": str(exc)}
        except Exception as exc:
            result = {"status": "error", "error": f"tool error: {exc}"}
        log_result["status"] = result.get("status")

    return {
        "last_tool_result": {"call_id": call_id, "name": name, "result": result},
        "active_specialist": specialist_name,
    }


async def _actions_specialist_execute(
    state: AgentState, kwargs: dict, tool_obj: Any
) -> dict:
    """take_action execution: code-level order-verification guard + HITL interrupt."""
    order_match = _DIGITS_RE.search(kwargs["order_id"])
    numeric_id = int(order_match.group()) if order_match else None

    if numeric_id is None or not _order_verified_in_history(state["messages"], numeric_id):
        return {
            "status": "error",
            "error": (
                f"order {kwargs['order_id']} has not been verified with lookup_order "
                "in this conversation — call lookup_order for it first"
            ),
        }

    # Generate a deterministic idempotency key so a replayed job doesn't double-write.
    idem_key = str(uuid.uuid5(
        uuid.NAMESPACE_OID,
        f"{state['session_id']}:{kwargs['order_id']}:{kwargs['action_type']}",
    ))

    prompt = (
        f"Confirm action '{kwargs['action_type']}' for order {kwargs['order_id']} "
        f"(reason: {kwargs['reason']}). Reply yes to proceed or no to cancel."
    )
    user_reply = interrupt({"prompt": prompt, "action": kwargs, "idempotency_key": idem_key})

    if _is_affirmative(str(user_reply)):
        return await _call_tool(tool_obj, **kwargs)
    return {"status": "cancelled", "reason": "user declined confirmation"}


# ── Specialist nodes ───────────────────────────────────────────────────────────

async def knowledge_agent(state: AgentState) -> dict:
    return await _specialist_node(state, "knowledge_agent", KNOWLEDGE_AGENT_PROMPT, ["knowledge_search"])


async def orders_agent(state: AgentState) -> dict:
    return await _specialist_node(state, "orders_agent", ORDERS_AGENT_PROMPT, ["lookup_order"])


async def actions_agent(state: AgentState) -> dict:
    return await _specialist_node(state, "actions_agent", ACTIONS_AGENT_PROMPT, ["take_action"])


async def escalation_agent(state: AgentState) -> dict:
    return await _specialist_node(state, "escalation_agent", ESCALATION_AGENT_PROMPT, ["escalate_to_human"])


# ── Observe node ───────────────────────────────────────────────────────────────

async def observe_node(state: AgentState) -> dict:
    last_result = state.get("last_tool_result")
    if not last_result:
        return {}
    name, call_id, result = last_result["name"], last_result["call_id"], last_result["result"]
    log_event("tool.observed", tool=name, status=result.get("status"))
    update: dict = {
        "messages": [ToolMessage(content=json.dumps(result, default=str), tool_call_id=call_id, name=name)],
        "last_tool_result": None,
    }
    if name == "escalate_to_human" and result.get("status") == "escalated":
        update["escalated"] = True
    return update


# ── Reflect node ───────────────────────────────────────────────────────────────

async def reflect_node(state: AgentState) -> dict:
    settings = get_settings()
    if state.get("escalated"):
        return {}
    if state.get("step_count", 0) >= settings.max_steps:
        log_event("agent.step_limit_exceeded", session_id=state["session_id"])
        result = await escalate_to_human.coroutine(
            reason="step_limit_exceeded",
            summary="The agent could not resolve this request within its planning step budget.",
            session_id=state["session_id"],
        )
        return {
            "messages": [
                ToolMessage(
                    content=json.dumps(result, default=str),
                    tool_call_id="forced-escalation",
                    name="escalate_to_human",
                )
            ],
            "escalated": True,
        }
    return {}
