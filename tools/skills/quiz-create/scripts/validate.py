#!/usr/bin/env python3
"""Validate a quiz-set JSON against the app's schema — no network.

Uses quiz_validation.py, a self-contained copy of the backend validator, so a
file that passes here cannot fail validation on upload.
"""
import json
import sys
from pathlib import Path

def _plugin_root() -> Path:
    """The quiz-tools plugin root, found by walking up to quiz_validation.py."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "quiz_validation.py").exists():
            return parent
    raise SystemExit("could not locate the quiz-tools plugin root (quiz_validation.py)")


sys.path.insert(0, str(_plugin_root()))

from quiz_validation import Invalid, QuizValidator  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: python3 {sys.argv[0]} <quiz.json>")
    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"not valid JSON: {e}")
    except OSError as e:
        sys.exit(f"cannot read {path}: {e}")

    try:
        parsed = QuizValidator.parse(payload)
    except Invalid as e:
        sys.exit(f"invalid: {e.message}")

    nq = len(parsed.questions)
    no = sum(len(q.options) for q in parsed.questions)
    print(f"OK — {nq} question(s), {no} option(s) total")


if __name__ == "__main__":
    main()
