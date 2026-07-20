"""Optional Langfuse tracing. No-op (empty callback list) if keys are unset,
so the agent runs fine without a Langfuse account -- structured JSON logs
(app/logging_conf.py) are the always-on observability layer.
"""
from __future__ import annotations

from app.config import get_settings

_handler = None
_attempted = False


def get_callbacks() -> list:
    global _handler, _attempted
    settings = get_settings()
    if not settings.langfuse_enabled:
        return []
    if not _attempted:
        _attempted = True
        try:
            from langfuse.callback import CallbackHandler

            _handler = CallbackHandler(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        except Exception:  # noqa: BLE001 - tracing must never break the agent
            _handler = None
    return [_handler] if _handler else []
