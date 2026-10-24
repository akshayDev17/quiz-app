"""Deterministic, attempt-seeded display order.

``random.Random`` seeded with a str is stable across processes (SHA-512).
"""

from __future__ import annotations

import dataclasses
import random
from typing import Protocol, TypeVar


class _Orderable(Protocol):
    """A question-shaped value: an id and an ordered tuple of options, each with an id."""

    id: int
    options: tuple


Q = TypeVar("Q", bound=_Orderable)


def display_order(
    attempt_id: str,
    questions: list[Q],
    shuffle_questions: bool,
    shuffle_options: bool,
) -> list[Q]:
    out = list(questions)
    if shuffle_questions:
        random.Random(attempt_id).shuffle(out)
    if shuffle_options:
        reordered = []
        for q in out:
            opts = list(q.options)
            random.Random(f"{attempt_id}:{q.id}").shuffle(opts)
            reordered.append(dataclasses.replace(q, options=tuple(opts)))
        out = reordered
    return out
