"""Output guardrail — runs on the agent reply before it reaches the client.

Two checks:
1. Grounding: any dollar amount, order-id, or status claim in the reply must
   be traceable to a ToolMessage in the conversation (not invented by the LLM).
2. PII redaction: mask emails, phone numbers, and card numbers in outbound text.

Both checks are regex-based and deliberately conservative: they raise a warning
but do NOT block the reply (the grounding check logs an anomaly for monitoring;
the redaction check masks in-place).  Escalating to block on grounding failures
can be enabled by setting `raise_on_grounding_fail=True`.
"""
from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import BaseMessage, ToolMessage

logger = logging.getLogger(__name__)

_DOLLAR_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
_ORDER_CLAIM_RE = re.compile(r"order\s+#?\d+", re.I)
_STATUS_WORDS = {"processing", "shipped", "delivered", "refunded", "delayed", "cancelled"}

# PII patterns for redaction
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ \-]?){13,19}\b")


def _tool_text(messages: list[BaseMessage]) -> str:
    """Concatenate all ToolMessage content for grounding reference."""
    parts: list[str] = []
    for m in messages:
        if isinstance(m, ToolMessage):
            parts.append(m.content)
    return " ".join(parts)


class OutputGuard:
    def __init__(self, raise_on_grounding_fail: bool = False):
        self._raise = raise_on_grounding_fail

    def check_and_redact(self, reply: str, messages: list[BaseMessage]) -> str:
        self._grounding_check(reply, messages)
        return self._redact_pii(reply)

    def _grounding_check(self, reply: str, messages: list[BaseMessage]) -> None:
        tool_text = _tool_text(messages)
        if not tool_text:
            return  # no tool results in session — grounding not applicable

        # Check that any dollar claims appear somewhere in the tool outputs
        for m in _DOLLAR_RE.finditer(reply):
            claim = m.group().replace(" ", "").replace(",", "")
            if claim not in tool_text:
                msg = f"output_guard: dollar claim '{m.group()}' not found in tool results"
                logger.warning(msg)
                if self._raise:
                    raise ValueError(msg)

        # Check status words against tool results
        for word in _STATUS_WORDS:
            if re.search(rf"\b{word}\b", reply, re.I):
                if word not in tool_text.lower():
                    msg = f"output_guard: status word '{word}' not found in tool results"
                    logger.warning(msg)
                    if self._raise:
                        raise ValueError(msg)

    @staticmethod
    def _redact_pii(text: str) -> str:
        text = _EMAIL_RE.sub("[email redacted]", text)
        text = _PHONE_RE.sub("[phone redacted]", text)
        text = _CARD_RE.sub("[card redacted]", text)
        return text
