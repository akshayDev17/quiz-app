"""Deterministic, attempt-seeded display order.

``random.Random`` seeded with a str is stable across processes (SHA-512).
"""

from __future__ import annotations

import dataclasses
import random

from .models import QuestionForSolver


def display_order(
    attempt_id: str,
    questions: list[QuestionForSolver],
    shuffle_questions: bool,
    shuffle_options: bool,
) -> list[QuestionForSolver]:
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
