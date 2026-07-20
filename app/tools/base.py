"""Shared tool primitives: ToolError + circuit-breaker state tracker."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


class ToolError(Exception):
    """Raised by tool implementations for user-visible, non-retryable errors."""


@dataclass
class CircuitBreaker:
    """Simple sliding-window circuit breaker.

    CLOSED → OPEN after `failure_threshold` errors in `window_seconds`.
    OPEN → HALF_OPEN after `recovery_seconds`.
    HALF_OPEN → CLOSED on success; → OPEN on failure.
    """
    name: str
    failure_threshold: int = 5
    window_seconds: float = 60.0
    recovery_seconds: float = 30.0
    _failures: deque = field(default_factory=deque, init=False, repr=False)
    _open_since: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self._failures = deque()
        self._open_since = None

    @property
    def is_open(self) -> bool:
        now = time.monotonic()
        if self._open_since is not None:
            if now - self._open_since >= self.recovery_seconds:
                self._open_since = None
                return False
            return True
        while self._failures and now - self._failures[0] > self.window_seconds:
            self._failures.popleft()
        return False

    def record_success(self) -> None:
        self._open_since = None
        self._failures.clear()

    def record_failure(self) -> None:
        now = time.monotonic()
        self._failures.append(now)
        while self._failures and now - self._failures[0] > self.window_seconds:
            self._failures.popleft()
        if len(self._failures) >= self.failure_threshold:
            self._open_since = now

    def check(self) -> None:
        if self.is_open:
            raise ToolError(f"circuit breaker open for {self.name}; too many recent failures")


_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(tool_name: str) -> CircuitBreaker:
    if tool_name not in _breakers:
        _breakers[tool_name] = CircuitBreaker(name=tool_name)
    return _breakers[tool_name]
