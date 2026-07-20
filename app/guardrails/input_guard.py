"""Input guardrail — runs before the agent sees the user message.

Three checks (all regex-based; swap Presidio in by replacing the PII section):

1. Prompt-injection: detect common jailbreak / instruction-override patterns.
2. PII detection: flag messages containing email, phone, SSN, or credit-card
   numbers so they can be redacted or logged with care.
3. Scope check: if the message is clearly unrelated to customer support, block
   it with a friendly out-of-scope reply rather than burning LLM tokens.

Architecture note: the guardrail is intentionally a CODE layer, not a prompt.
The model never sees messages that fail injection or scope checks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ── Patterns ───────────────────────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|rules?)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"disregard\s+(your|the)\s+(system\s+)?prompt", re.I),
    re.compile(r"act\s+as\s+(if\s+you\s+(are|were)\s+)?(a\s+)?", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN\s+mode", re.I),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.I),
    re.compile(r"(system|hidden|secret)\s+prompt", re.I),
]

# Regex PII detectors — swap the body of _detect_pii for Presidio if installed.
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ \-]?){13,19}\b")

# Support-domain keywords — at least one must be present for the scope check to pass.
_SCOPE_KEYWORDS = re.compile(
    r"\b(order|ticket|refund|charge|shipped|shipping|delivery|item|account|payment|invoice|"
    r"support|help|issue|problem|return|damaged|broken|missing|track|status|cancel|cancell?ation|"
    r"discount|policy|warranty|replace|replacement|complaint|billing|purchase|product|"
    r"package|parcel|defect|defective|lost|delay|delayed|double|duplicate|receipt|invoice)\b",
    re.I,
)
# Short / greeting messages bypass the scope check (e.g. "hello", "hi").
_GREETING_RE = re.compile(r"^\s*(hi|hello|hey|thanks?|thank\s+you|ok|okay|yes|no|sure)\W*$", re.I)


@dataclass
class InputGuardResult:
    allowed: bool
    block_reason: str = ""
    pii_detected: bool = False
    pii_types: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.pii_types is None:
            self.pii_types = []


def _detect_pii(text: str) -> list[str]:
    found: list[str] = []
    if _EMAIL_RE.search(text):
        found.append("email")
    if _PHONE_RE.search(text):
        found.append("phone")
    if _SSN_RE.search(text):
        found.append("ssn")
    if _CARD_RE.search(text):
        found.append("credit_card")
    return found


class InputGuard:
    """Stateless guard; call check() before every agent invocation."""

    def check(self, message: str) -> InputGuardResult:
        # 1. Injection check
        for pat in _INJECTION_PATTERNS:
            if pat.search(message):
                return InputGuardResult(
                    allowed=False,
                    block_reason=f"prompt_injection: matched pattern '{pat.pattern[:40]}'",
                )

        # 2. PII detection (advisory — logged but not blocked by default)
        pii = _detect_pii(message)

        # 3. Scope check (skip for short greetings)
        if len(message.strip()) > 30 and not _GREETING_RE.match(message):
            if not _SCOPE_KEYWORDS.search(message):
                return InputGuardResult(
                    allowed=False,
                    block_reason="out_of_scope: message does not appear to be a customer-support request",
                    pii_detected=bool(pii),
                    pii_types=pii,
                )

        return InputGuardResult(allowed=True, pii_detected=bool(pii), pii_types=pii)
