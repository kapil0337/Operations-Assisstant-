"""Action guardrail — enforces write preconditions in code, not prompt text.

verify_order_for_write() is the authoritative gate used by actions_agent.
It mirrors the old _order_verified_in_history() but lives in a dedicated
module so it can be imported independently (e.g. by tests).
"""
from __future__ import annotations

import json
import re

from langchain_core.messages import BaseMessage, ToolMessage

_DIGITS_RE = re.compile(r"\d+")


def verify_order_for_write(messages: list[BaseMessage], order_id_str: str) -> tuple[bool, str]:
    """Return (ok, reason).

    ok=True   order was verified in this session → write may proceed to interrupt gate.
    ok=False  reason explains why the write was blocked.
    """
    m = _DIGITS_RE.search(order_id_str)
    if not m:
        return False, f"could not parse a numeric order_id from '{order_id_str}'"

    numeric_id = int(m.group())
    for msg in messages:
        if not (isinstance(msg, ToolMessage) and msg.name == "lookup_order"):
            continue
        try:
            payload = json.loads(msg.content)
        except (TypeError, ValueError):
            continue
        if (
            payload.get("status") == "found"
            and payload.get("order", {}).get("order_id") == numeric_id
        ):
            return True, ""

    return (
        False,
        f"order {numeric_id} has not been verified with lookup_order in this conversation "
        "— call lookup_order first before taking action",
    )
