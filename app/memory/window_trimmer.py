"""History window trimmer.

Keeps the last `window` messages in the active context.  Older messages are
summarised with a cheap LLM call and prepended as a SystemMessage so the
supervisor always has the essential thread context without hitting the model's
context limit.
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, SystemMessage

from app.config import get_settings


def trim_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Return at most `history_window` messages, prepending a note if older
    messages were dropped.  A future upgrade can add an LLM summarisation pass
    here — for now the note is a placeholder that documents the truncation."""
    settings = get_settings()
    window = settings.history_window
    if len(messages) <= window:
        return messages

    dropped = len(messages) - window
    note = SystemMessage(
        content=(
            f"[Context note: {dropped} earlier message(s) are omitted from the "
            "active window. The conversation has been ongoing — use the tool "
            "results visible here as ground truth for the current request.]"
        )
    )
    return [note, *messages[-window:]]
