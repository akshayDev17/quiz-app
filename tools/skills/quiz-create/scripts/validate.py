#!/usr/bin/env python3
"""Validate a quiz-set JSON against the app's own validator — no network.

Single source of truth: imports backend/quiz_app/validation.py, the same module
the server runs on upload, so a file that passes here cannot fail validation there.
"""
import json
import sys
from pathlib import Path

def _repo_root() -> Path:
    """quiz-app/, found by walking up to backend/quiz_app/validation.py."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "backend" / "quiz_app" / "validation.py").exists():
            return parent
    raise SystemExit("could not locate quiz-app (backend/quiz_app/validation.py)")


sys.path.insert(0, str(_repo_root() / "backend"))

from quiz_app.errors import Invalid  # noqa: E402
from quiz_app.validation import QuizValidator  # noqa: E402


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
