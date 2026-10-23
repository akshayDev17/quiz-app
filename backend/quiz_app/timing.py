"""Time limits. A set is either timed (fixed minutes) or untimed."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

# Server-side leniency for network latency on the final autosave/submit.
GRACE_MS = 10_000


class TimeLimit(ABC):
    @staticmethod
    def of(minutes: int | None) -> "TimeLimit":
        if minutes is None:
            return NoTimeLimit()
        if minutes <= 0:
            raise ValueError("time limit must be a positive number of minutes")
        return FixedTimeLimit(minutes)

    @abstractmethod
    def deadline(self, started_at_ms: int) -> int | None:
        """Epoch ms at which an attempt started at ``started_at_ms`` is due."""


@dataclass(frozen=True)
class FixedTimeLimit(TimeLimit):
    minutes: int

    def deadline(self, started_at_ms: int) -> int | None:
        return started_at_ms + self.minutes * 60_000


@dataclass(frozen=True)
class NoTimeLimit(TimeLimit):
    def deadline(self, started_at_ms: int) -> int | None:
        return None
