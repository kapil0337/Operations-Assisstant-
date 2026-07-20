"""Structured JSON logging for every plan/tool/generation step.

Each call to `log_event` emits one JSON line with a consistent envelope so logs
can be grepped/ingested without a schema migration: timestamp, event name,
session id, node/tool name, latency, and (when available) token usage.
"""
from __future__ import annotations

import contextlib
import json
import logging
import sys
import time
from typing import Any, Iterator

_LOGGER_NAME = "ops_assistant"


def configure_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return  # already configured
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def log_event(event: str, **fields: Any) -> None:
    logger = logging.getLogger(_LOGGER_NAME)
    payload = {"ts": time.time(), "event": event, **fields}
    logger.info(json.dumps(payload, default=str))


@contextlib.contextmanager
def log_step(event: str, **fields: Any) -> Iterator[dict[str, Any]]:
    """Context manager that times a step and logs start/end (+ exceptions).

    Yields a mutable dict the caller can stuff extra result fields into
    (e.g. token counts) before the `end` event is emitted.
    """
    start = time.perf_counter()
    log_event(f"{event}.start", **fields)
    result: dict[str, Any] = {}
    try:
        yield result
    except Exception as exc:  # noqa: BLE001 - we want to log and re-raise
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(f"{event}.error", latency_ms=latency_ms, error=str(exc), **fields)
        raise
    else:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(f"{event}.end", latency_ms=latency_ms, **fields, **result)
