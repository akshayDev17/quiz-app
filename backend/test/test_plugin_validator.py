"""The quiz-tools plugin's validator is a copy of the backend's, so a file the plugin
passes cannot fail on upload. This runs the same payloads through both and requires the
same result from each: the same parsed set, or the same error message.

Run:  python3 test/test_plugin_validator.py
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
import unittest

import helpers  # noqa: F401  (sys.path)

from helpers import BACKEND, sample_import
from quiz_app import validation as backend_validation

PLUGIN_COPY = BACKEND.parent / "tools" / "quiz_validation.py"


def load_plugin_validator():
    spec = importlib.util.spec_from_file_location("plugin_quiz_validation", PLUGIN_COPY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


plugin_validation = load_plugin_validator()


def outcome(module, payload, update: bool = False):
    parse = module.QuizValidator.parse_update if update else module.QuizValidator.parse
    try:
        return "ok", dataclasses.asdict(parse(payload))
    except module.Invalid as e:
        return "invalid", str(e)


def subjective(**extra) -> dict:
    question = {
        "type": "subjective",
        "prompt": "Why re-embed every stored vector after swapping the embedding model?",
        "model_answer": "Vectors from different models live in different spaces, so they are not comparable.",
    }
    question.update(extra)
    return question


def with_questions(*questions) -> dict:
    return sample_import(questions=sample_import()["questions"] + list(questions))


def body_of(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k not in ("topic", "subtopic")}


CHOICE = sample_import()["questions"][0]
CASES = {
    "a valid set with a subjective question and key points": (
        with_questions(subjective(key_points=["different vector spaces", " not comparable "])), "ok"),
    "a subjective question without key points": (with_questions(subjective()), "ok"),
    "key points on a choice question": (with_questions({**CHOICE, "key_points": ["a point"]}), "invalid"),
    "no key points in the list": (with_questions(subjective(key_points=[])), "invalid"),
    "seven key points": (with_questions(subjective(key_points=[f"point {i}" for i in range(7)])), "invalid"),
    "an over-long key point": (with_questions(subjective(key_points=["x" * 301])), "invalid"),
    "a blank key point": (with_questions(subjective(key_points=["fine", "  "])), "invalid"),
    "points on a subjective question": (with_questions(subjective(points=2)), "invalid"),
    "options on a subjective question": (with_questions(subjective(options=CHOICE["options"])), "invalid"),
    "a subjective question with no model answer": (with_questions(subjective(model_answer="  ")), "invalid"),
    "a model answer on a choice question": (with_questions({**CHOICE, "model_answer": "x"}), "invalid"),
    "an unknown question type": (with_questions(subjective(type="essay")), "invalid"),
}


class PluginValidatorTest(unittest.TestCase):
    def test_the_plugin_and_the_backend_agree_on_every_payload(self):
        for name, (payload, expected) in CASES.items():
            with self.subTest(case=name):
                backend = outcome(backend_validation, payload)
                self.assertEqual(backend[0], expected, backend[1])
                self.assertEqual(outcome(plugin_validation, payload), backend)

    def test_they_agree_on_an_in_place_edit_too(self):
        for name, (payload, expected) in CASES.items():
            with self.subTest(case=name):
                backend = outcome(backend_validation, body_of(payload), update=True)
                self.assertEqual(backend[0], expected, backend[1])
                self.assertEqual(outcome(plugin_validation, body_of(payload), update=True), backend)


if __name__ == "__main__":
    unittest.main()
