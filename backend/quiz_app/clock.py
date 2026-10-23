"""The server clock decides time. Injected so tests control it."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod


class Clock(ABC):
    @abstractmethod
    def now_ms(self) -> int:
        """Current time as integer epoch milliseconds."""


class SystemClock(Clock):
    def now_ms(self) -> int:
        return time.time_ns() // 1_000_000


class FakeClock(Clock):
    """Test double: time only moves when told to."""

    def __init__(self, start_ms: int):
        self._now = start_ms

    def now_ms(self) -> int:
        return self._now

    def advance(self, ms: int) -> None:
        self._now += ms
