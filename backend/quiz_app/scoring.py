"""Scoring policies, looked up by name through a factory."""

from __future__ import annotations

from typing import Protocol

from .errors import Invalid


class ScoringPolicy(Protocol):
    def award(self, points: float, correct: frozenset[int], selected: frozenset[int]) -> float: ...


class AllOrNothing:
    """Full points for an exact match, otherwise zero."""

    def award(self, points: float, correct: frozenset[int], selected: frozenset[int]) -> float:
        return points if selected == correct else 0


class PartialCredit:
    """``points * max(0, (|S∩C| - |S∖C|) / |C|)``."""

    def award(self, points: float, correct: frozenset[int], selected: frozenset[int]) -> float:
        if not correct:
            return 0
        hits = len(selected & correct)
        misses = len(selected - correct)
        return points * max(0, (hits - misses) / len(correct))


_REGISTRY: dict[str, type] = {
    "all_or_nothing": AllOrNothing,
    "partial": PartialCredit,
}


class ScoringPolicyFactory:
    @staticmethod
    def for_name(name: str) -> ScoringPolicy:
        try:
            return _REGISTRY[name]()
        except KeyError:
            raise Invalid(f"unknown scoring policy: {name}") from None

    @staticmethod
    def names() -> frozenset[str]:
        return frozenset(_REGISTRY)
