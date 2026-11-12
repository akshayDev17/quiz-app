"""Scoring policies, looked up by name through a factory.

Every attempt started now is marked by ``MARKING`` (``NegativeMarking``). The older
policies stay registered only so an attempt that started under one of them is
still graded and displayed by the rule it started under: the policy name is frozen
onto the attempt at start.
"""

from __future__ import annotations

from typing import Protocol

from .errors import Invalid


class ScoringPolicy(Protocol):
    def award(self, points: float, correct: frozenset[int], selected: frozenset[int]) -> float: ...

    def max_award(self, points: float, correct: frozenset[int]) -> float: ...


class AllOrNothing:
    """Full points for an exact match, otherwise zero."""

    def award(self, points: float, correct: frozenset[int], selected: frozenset[int]) -> float:
        return points if selected and selected == correct else 0

    def max_award(self, points: float, correct: frozenset[int]) -> float:
        return points


class PartialCredit:
    """``points * max(0, (|S∩C| - |S∖C|) / |C|)``."""

    def award(self, points: float, correct: frozenset[int], selected: frozenset[int]) -> float:
        if not correct:
            return 0
        hits = len(selected & correct)
        misses = len(selected - correct)
        return points * max(0, (hits - misses) / len(correct))

    def max_award(self, points: float, correct: frozenset[int]) -> float:
        return points


class NegativeMarking:
    """+2 per correct option ticked, -1 per wrong option ticked, -2 for a blank question.

    A correct option left unticked costs nothing, and a question (or a whole quiz)
    may score below zero. The question's ``points`` weight plays no part.
    """

    PER_CORRECT = 2
    PER_WRONG = -1
    BLANK = -2

    def award(self, points: float, correct: frozenset[int], selected: frozenset[int]) -> float:
        if not selected:
            return self.BLANK
        return self.PER_CORRECT * len(selected & correct) + self.PER_WRONG * len(selected - correct)

    def max_award(self, points: float, correct: frozenset[int]) -> float:
        return self.PER_CORRECT * len(correct)


MARKING = "negative_marking"
"""The policy every new attempt is frozen with, whatever its set's own column says."""

_REGISTRY: dict[str, type] = {
    "all_or_nothing": AllOrNothing,
    "partial": PartialCredit,
    MARKING: NegativeMarking,
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
