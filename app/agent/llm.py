"""NVIDIA NIM chat model factory with automatic fallback if the primary model
is unavailable (e.g. quota, deprecation).  NVIDIA NIM exposes an
OpenAI-compatible API so tool-binding works identically to any other
LangChain chat model."""
from __future__ import annotations

import threading
from typing import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from app.config import get_settings
from app.logging_conf import log_event

_lock = threading.Lock()
_active_model: str | None = None


def _build(model: str) -> ChatNVIDIA:
    settings = get_settings()
    return ChatNVIDIA(
        model=model,
        api_key=settings.nvidia_api_key,
        temperature=0,
        max_tokens=1024,
        timeout=60,  # seconds — fail fast rather than hanging until ARQ job_timeout
    )


def _current_model() -> str:
    return _active_model or get_settings().nvidia_model


def _is_unavailable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(k in text for k in ("decommission", "model_not_found", "does not exist", "not found", "404"))


async def invoke_with_fallback(
    messages: Sequence[BaseMessage],
    tools: Sequence[BaseTool] | None = None,
    callbacks: list | None = None,
) -> BaseMessage:
    """Invoke ChatNVIDIA, swapping to the fallback model exactly once if the
    primary model is unavailable."""
    settings = get_settings()
    global _active_model

    model = _current_model()
    llm: BaseChatModel = _build(model)
    bound = llm.bind_tools(tools) if tools else llm
    invoke_config = {"callbacks": callbacks} if callbacks else None

    try:
        return await bound.ainvoke(list(messages), config=invoke_config)
    except Exception as exc:  # noqa: BLE001
        if _is_unavailable_error(exc) and model != settings.nvidia_fallback_model:
            log_event(
                "llm.fallback",
                from_model=model,
                to_model=settings.nvidia_fallback_model,
                error=str(exc),
            )
            with _lock:
                _active_model = settings.nvidia_fallback_model
            fallback_llm = _build(_active_model)
            fallback_bound = fallback_llm.bind_tools(tools) if tools else fallback_llm
            return await fallback_bound.ainvoke(list(messages), config=invoke_config)
        raise
