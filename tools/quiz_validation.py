# Self-contained copy of backend/quiz_app/validation.py.
# Kept standalone so the quiz-tools plugin validates without reaching into the
# quiz-app repo (the installed plugin lives under ~/.dsh). When the import schema
# changes, update backend/quiz_app/validation.py first, then re-copy this file.
"""``QuizValidator``: a JSON import payload (spec §4) becomes a ``SetImport``.

``parse`` collects every problem and raises one ``Invalid`` joining them with
``"; "``, so an author fixes the whole file in one pass. ``parse_update`` validates
an in-place edit: the set already owns its topic, so only the body is checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

class Invalid(Exception):
    """A validation problem; ``message`` is the human-readable reason."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


SCORING_POLICIES = ("all_or_nothing", "partial")

DIFFICULTIES = ("easy", "medium", "hard")
STYLES = ("standard", "scenario")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class QuestionImport:
    prompt: str
    explanation: str | None = None
    points: float = 1
    options: tuple[tuple[str, bool], ...] = ()  # (body, correct)


@dataclass(frozen=True)
class SetImport:
    topic: tuple[str, str]                          # (slug, name)
    subtopic: tuple[str, str] | None = None         # (slug, name)
    difficulty: str | None = None
    style: str = "standard"
    title: str | None = None
    description: str | None = None
    time_limit_minutes: int | None = None
    scoring_policy: str = "all_or_nothing"
    shuffle_questions: bool = False
    shuffle_options: bool = False
    reveal_answers: bool = True
    max_attempts: int | None = None
    questions: tuple[QuestionImport, ...] = ()


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_fields(payload: dict, errors: list[str]) -> dict:
    """Everything except topic/subtopic — shared by import and edit."""
    difficulty = payload.get("difficulty")
    if difficulty is not None and difficulty not in DIFFICULTIES:
        errors.append(f"difficulty must be one of {', '.join(DIFFICULTIES)}")
    style = payload.get("style", "standard")
    if style not in STYLES:
        errors.append(f"style must be one of {', '.join(STYLES)}")
    policy = payload.get("scoring_policy", "all_or_nothing")
    if not (isinstance(policy, str) and policy in SCORING_POLICIES):
        errors.append(f"scoring_policy must be one of {', '.join(sorted(SCORING_POLICIES))}")

    time_limit = payload.get("time_limit_minutes")
    if time_limit is not None and not (_is_int(time_limit) and time_limit > 0):
        errors.append("time_limit_minutes must be a positive whole number or null")
    max_attempts = payload.get("max_attempts")
    if max_attempts is not None and not (_is_int(max_attempts) and max_attempts > 0):
        errors.append("max_attempts must be a positive whole number or null")

    flags = {}
    for key, default in (("shuffle_questions", False), ("shuffle_options", False), ("reveal_answers", True)):
        value = payload.get(key, default)
        if not isinstance(value, bool):
            errors.append(f"{key} must be true or false")
        flags[key] = value

    title = _optional_text(payload.get("title"), "title", errors)
    description = _optional_text(payload.get("description"), "description", errors)

    raw_questions = payload.get("questions")
    questions: list[QuestionImport] = []
    if not isinstance(raw_questions, list) or not raw_questions:
        errors.append("a set needs at least 1 question")
    else:
        for number, raw in enumerate(raw_questions, start=1):
            question = _parse_question(raw, number, errors)
            if question is not None:
                questions.append(question)

    return {
        "difficulty": difficulty,
        "style": style,
        "title": title,
        "description": description,
        "time_limit_minutes": time_limit,
        "scoring_policy": policy,
        "max_attempts": max_attempts,
        "questions": tuple(questions),
        **flags,
    }


class QuizValidator:
    @staticmethod
    def parse(payload: dict) -> SetImport:
        if not isinstance(payload, dict):
            raise Invalid("payload must be a JSON object")
        errors: list[str] = []
        topic = _parse_named(payload.get("topic"), "topic", errors, required=True)
        subtopic = _parse_named(payload.get("subtopic"), "subtopic", errors, required=False)
        fields = _parse_fields(payload, errors)
        if errors:
            raise Invalid("; ".join(errors))
        return SetImport(topic=topic, subtopic=subtopic, **fields)

    @staticmethod
    def parse_update(payload: dict) -> SetImport:
        """Validate an in-place edit. The set keeps its topic, so the payload has no
        topic/subtopic; the returned ``SetImport`` carries an empty topic."""
        if not isinstance(payload, dict):
            raise Invalid("payload must be a JSON object")
        errors: list[str] = []
        fields = _parse_fields(payload, errors)
        if errors:
            raise Invalid("; ".join(errors))
        return SetImport(topic=("", ""), subtopic=None, **fields)


def _optional_text(value, label: str, errors: list[str]) -> str | None:
    """Blank text is no text: whitespace-only becomes ``None``."""
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"{label} must be text")
        return None
    value = value.strip()
    return value or None


def _parse_named(raw, label: str, errors: list[str], required: bool) -> tuple[str, str] | None:
    if raw is None:
        if required:
            errors.append(f"{label} is required")
        return None
    if not isinstance(raw, dict):
        errors.append(f"{label} must be an object with slug and name")
        return None
    slug, name = raw.get("slug"), raw.get("name")
    ok = True
    if not isinstance(slug, str) or not _SLUG.match(slug):
        errors.append(f"{label} slug must be lowercase letters, digits and hyphens")
        ok = False
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{label} name must not be empty")
        ok = False
    return (slug, name.strip()) if ok else None


def _parse_question(raw, number: int, errors: list[str]) -> QuestionImport | None:
    where = f"question {number}"
    if not isinstance(raw, dict):
        errors.append(f"{where} must be an object")
        return None
    before = len(errors)

    prompt = raw.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append(f"{where}: empty prompt")
    explanation = _optional_text(raw.get("explanation"), f"{where}: explanation", errors)
    points = raw.get("points", 1)
    if not (_is_number(points) and points > 0):
        errors.append(f"{where}: points must be a positive number")

    raw_options = raw.get("options")
    options: list[tuple[str, bool]] = []
    if not isinstance(raw_options, list) or len(raw_options) < 2:
        errors.append(f"{where}: needs at least 2 options")
    else:
        for index, option in enumerate(raw_options, start=1):
            body = option.get("body") if isinstance(option, dict) else None
            correct = option.get("correct") if isinstance(option, dict) else None
            if not isinstance(body, str) or not body.strip():
                errors.append(f"{where}: option {index} has an empty body")
            if not isinstance(correct, bool):
                errors.append(f"{where}: option {index} needs correct true or false")
            if isinstance(body, str) and isinstance(correct, bool):
                options.append((body, correct))
        if len(options) == len(raw_options) and not any(correct for _, correct in options):
            errors.append(f"{where}: needs at least 1 correct option")

    if len(errors) > before:
        return None
    return QuestionImport(prompt=prompt, explanation=explanation, points=points, options=tuple(options))
