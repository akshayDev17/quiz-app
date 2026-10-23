"""Domain errors. The API layer maps each subclass to an HTTP status."""

from __future__ import annotations


class QuizError(Exception):
    """Base class; ``message`` is what goes in the ``{"error": ...}`` body."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(QuizError):
    """404"""


class Conflict(QuizError):
    """409"""


class Invalid(QuizError):
    """422"""


class Forbidden(QuizError):
    """403"""
