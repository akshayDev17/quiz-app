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
    written = [i for i, q in enumerate(parsed.questions, start=1) if q.kind == "subjective"]
    print(f"OK — {nq} question(s), {len(written)} written, {no} option(s) total")
    # House style, not schema: the upload accepts these, the skill's rules do not.
    for number in written:
        if not parsed.questions[number - 1].key_points:
            print(f"warning: question {number} is written but has no key_points for the AI evaluator")
    if written and not parsed.shuffle_questions:
        last = written[-1]
        if written == list(range(nq - len(written) + 1, nq + 1)) and len(written) < nq:
            print(f"warning: with shuffle_questions false, the written questions are bunched at the end "
                  f"(questions {written[0]}–{last}); spread them through the set")


if __name__ == "__main__":
    main()
