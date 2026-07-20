"""Lightweight token/cost/latency metrics collector.

Emits structured log lines via the existing logging_conf pipeline.  If OTel
is configured, also records values as span attributes on the current span.

Usage:
    from app.observability.metrics import record_llm_call

    record_llm_call(
        model="openai/gpt-oss-120b",
        input_tokens=512,
        output_tokens=128,
        latency_ms=1430,
        session_id="...",
    )
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from app.logging_conf import log_event

# Approximate cost per 1K tokens (update as Groq pricing changes).
_COST_PER_1K_IN = 0.0004   # USD
_COST_PER_1K_OUT = 0.0012  # USD


def record_llm_call(
    *,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    latency_ms: float,
    session_id: str = "",
    node: str = "",
) -> None:
    cost = None
    if input_tokens is not None and output_tokens is not None:
        cost = (input_tokens / 1000 * _COST_PER_1K_IN) + (output_tokens / 1000 * _COST_PER_1K_OUT)

    log_event(
        "metrics.llm_call",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 6) if cost else None,
        latency_ms=round(latency_ms, 1),
        session_id=session_id,
        node=node,
    )

    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.input_tokens", input_tokens or 0)
            span.set_attribute("llm.output_tokens", output_tokens or 0)
            span.set_attribute("llm.latency_ms", round(latency_ms, 1))
    except Exception:
        pass


def record_tool_call(
    *,
    tool: str,
    status: str,
    latency_ms: float,
    session_id: str = "",
) -> None:
    log_event(
        "metrics.tool_call",
        tool=tool,
        status=status,
        latency_ms=round(latency_ms, 1),
        session_id=session_id,
    )


@contextmanager
def timed():
    """Yield a dict that will have 'elapsed_ms' set on exit."""
    result: dict = {}
    t0 = time.perf_counter()
    try:
        yield result
    finally:
        result["elapsed_ms"] = (time.perf_counter() - t0) * 1000
