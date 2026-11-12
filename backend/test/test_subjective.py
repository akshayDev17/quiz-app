"""Subjective questions, end to end through the API: imported, served, typed, paused,
edited, never marked.

Most tests store a subjective question as a ``SetImport`` handed straight to the authoring
repository; ``ImportTest`` and ``EditRoundTripTest`` go through the admin routes.

Run:  python3 test/test_subjective.py
"""

from __future__ import annotations

import dataclasses
import json
import unittest

import helpers  # noqa: F401  (sys.path)

from helpers import fresh_db, sample_import

from quiz_app.auth import Identity
from quiz_app.clock import FakeClock
from quiz_app.composition import build_api
from quiz_app.d1.attempts import D1AttemptRepository
from quiz_app.d1.authoring import D1QuizAuthoring
from quiz_app.errors import Invalid
from quiz_app.validation import QuestionImport, QuizValidator

ADMIN = Identity("admin@example.com")
ALICE = Identity("alice@example.com")
START = 1_700_000_000_000
P = "/quiz/api"

WRITTEN = QuestionImport(
    kind="subjective",
    prompt="Why does swapping the embedding model force a full re-index?",
    explanation="Same dimension is a storage coincidence, not compatibility.",
    model_answer="Each model learns its own vector space, so old and new vectors are not comparable.",
)

#: sample_import's three choice questions have 3, 2 and 1 correct options: +2 each.
CHOICE_MAX = 2 * (3 + 2 + 1)
CHOICE_COUNT = 3


def with_written(position: int = 1, **overrides):
    """sample_import with ``WRITTEN`` inserted at ``position``, as a SetImport."""
    imp = QuizValidator.parse(sample_import(**overrides))
    questions = list(imp.questions)
    questions.insert(position, WRITTEN)
    return dataclasses.replace(imp, questions=tuple(questions))


class SubjectiveCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = fresh_db()
        self.clock = FakeClock(START)
        self.api = build_api(self.db, [ADMIN.email], self.clock)
        self.authoring = D1QuizAuthoring(self.db, self.clock)
        await self.call("GET", "/me", ident=ADMIN)  # the importer's user row
        self.sid = await self.publish(with_written())

    async def call(self, method, path, body=None, ident=ALICE):
        return await self.api.handle(method, P + path, body, ident)

    async def ok(self, method, path, body=None, ident=ALICE, status=200):
        got, payload = await self.call(method, path, body, ident)
        self.assertEqual(got, status, payload)
        return payload

    async def publish(self, imp) -> int:
        sid = await self.authoring.create_set(imp, ADMIN.email, START)
        await self.ok("POST", f"/admin/sets/{sid}/publish", None, ADMIN)
        return sid

    async def start(self, sid=None) -> dict:
        return await self.ok("POST", f"/sets/{sid or self.sid}/attempts", None, ALICE, 201)

    @staticmethod
    def written_id(session: dict) -> int:
        [q] = [q for q in session["questions"] if q["kind"] == "subjective"]
        return q["id"]

    async def type(self, aid, qid, text):
        return await self.call("PUT", f"/attempts/{aid}/answers/{qid}", {"text": text})

    async def tick_every_correct_option(self, aid):
        for key in await D1AttemptRepository(self.db).answer_key(aid):
            got, body = await self.call(
                "PUT", f"/attempts/{aid}/answers/{key.question_id}", {"option_ids": sorted(key.correct)}
            )
            self.assertEqual(got, 204, body)


class ValidatorTest(unittest.TestCase):
    """The import rules for ``"type": "subjective"``; choice questions are unchanged."""

    def parse(self, question: dict):
        return QuizValidator.parse(sample_import(questions=[question]))

    def refused(self, question: dict) -> str:
        with self.assertRaises(Invalid) as caught:
            self.parse(question)
        return caught.exception.message

    def test_a_subjective_question_imports_with_its_model_answer(self):
        [parsed] = self.parse({
            "type": "subjective", "prompt": "Explain.", "model_answer": "  Because.  ", "explanation": "Why.",
        }).questions
        self.assertEqual(
            (parsed.kind, parsed.prompt, parsed.model_answer, parsed.explanation, parsed.options),
            ("subjective", "Explain.", "Because.", "Why.", ()),
        )

    def test_a_subjective_question_needs_a_model_answer(self):
        for missing in ({}, {"model_answer": None}, {"model_answer": "   "}):
            self.assertEqual(
                self.refused({"type": "subjective", "prompt": "Explain.", **missing}),
                "question 1: a subjective question needs a model_answer",
            )

    def test_a_model_answer_must_be_text(self):
        self.assertEqual(
            self.refused({"type": "subjective", "prompt": "Explain.", "model_answer": 42}),
            "question 1: model_answer must be text",
        )

    def test_a_subjective_question_takes_no_options_and_no_points(self):
        self.assertEqual(
            self.refused({
                "type": "subjective", "prompt": "Explain.", "model_answer": "Because.",
                "options": [{"body": "a", "correct": True}, {"body": "b", "correct": False}], "points": 1,
            }),
            "question 1: a subjective question has no options; "
            "question 1: a subjective question is not marked, so it takes no points",
        )

    def test_a_choice_question_takes_no_model_answer(self):
        options = [{"body": "a", "correct": True}, {"body": "b", "correct": False}]
        self.assertEqual(
            self.refused({"prompt": "Q", "options": options, "model_answer": "a"}),
            "question 1: model_answer is only for subjective questions",
        )

    def test_a_subjective_question_still_needs_a_prompt(self):
        self.assertEqual(
            self.refused({"type": "subjective", "prompt": " ", "model_answer": "Because."}),
            "question 1: empty prompt",
        )

    def test_an_unknown_type_is_refused(self):
        self.assertEqual(self.refused({"type": "essay", "prompt": "Explain."}),
                         "question 1: type must be one of choice, subjective")

    def test_choice_is_the_default_and_may_be_spelled_out(self):
        options = [{"body": "a", "correct": True}, {"body": "b", "correct": False}]
        for question in ({"prompt": "Q", "options": options}, {"type": "choice", "prompt": "Q", "options": options}):
            [parsed] = self.parse(question).questions
            self.assertEqual((parsed.kind, parsed.model_answer), ("choice", None))


def written_json(**overrides) -> dict:
    """``WRITTEN`` in its import shape."""
    return {
        "type": "subjective", "prompt": WRITTEN.prompt, "explanation": WRITTEN.explanation,
        "model_answer": WRITTEN.model_answer, **overrides,
    }


class ImportTest(SubjectiveCase):
    async def test_an_uploaded_subjective_question_is_served_and_left_unmarked(self):
        payload = sample_import(difficulty="easy")
        payload["questions"].insert(1, written_json())
        made = await self.ok("POST", "/admin/sets", payload, ADMIN, 201)
        await self.ok("POST", f"/admin/sets/{made['id']}/publish", None, ADMIN)
        session = await self.start(made["id"])
        self.assertEqual(sorted(q["kind"] for q in session["questions"]), ["choice"] * 3 + ["subjective"])
        aid = session["attempt"]["id"]
        got, body = await self.type(aid, self.written_id(session), "Typed.")
        self.assertEqual(got, 204, body)
        await self.ok("POST", f"/attempts/{aid}/submit")
        results = await self.ok("GET", f"/attempts/{aid}/results")
        self.assertEqual(results["attempt"]["max_score"], CHOICE_MAX)
        [written] = [q for q in results["questions"] if q["kind"] == "subjective"]
        self.assertEqual((written["text_answer"], written["model_answer"], written["points"]),
                         ("Typed.", WRITTEN.model_answer, None))

    async def test_an_upload_without_a_model_answer_is_refused(self):
        payload = sample_import(difficulty="easy")
        payload["questions"].append(written_json(model_answer=""))
        got, body = await self.call("POST", "/admin/sets", payload, ADMIN)
        self.assertEqual((got, body), (422, {"error": "question 4: a subjective question needs a model_answer"}))


class EditRoundTripTest(SubjectiveCase):
    """The editor reads a set and sends its questions straight back; a subjective one must survive."""

    def editable(self, detail: dict) -> dict:
        keep = ("title", "description", "difficulty", "style", "scoring_policy", "time_limit_minutes",
                "max_attempts", "shuffle_questions", "shuffle_options", "reveal_answers", "visibility")
        return {**{k: detail[k] for k in keep}, "questions": detail["questions"]}

    async def test_saving_a_set_with_a_subjective_question_unchanged_keeps_it(self):
        before = await self.ok("GET", f"/admin/sets/{self.sid}", ident=ADMIN)
        await self.ok("PUT", f"/admin/sets/{self.sid}", self.editable(before), ADMIN)
        after = await self.ok("GET", f"/admin/sets/{self.sid}", ident=ADMIN)
        self.assertEqual(after["questions"], before["questions"])

    async def test_switching_a_question_between_choice_and_subjective(self):
        detail = await self.ok("GET", f"/admin/sets/{self.sid}", ident=ADMIN)
        body = self.editable(detail)
        first = body["questions"][0]
        body["questions"][0] = written_json(prompt=first["prompt"], model_answer="Re-embed; re-tune.")
        body["questions"][1] = {
            "type": "choice", "prompt": WRITTEN.prompt, "explanation": None, "points": 1,
            "options": [{"body": "Spaces differ", "correct": True}, {"body": "Nothing", "correct": False}],
        }
        await self.ok("PUT", f"/admin/sets/{self.sid}", body, ADMIN)
        after = await self.ok("GET", f"/admin/sets/{self.sid}", ident=ADMIN)
        self.assertEqual([q["type"] for q in after["questions"]], ["subjective", "choice", "choice", "choice"])
        self.assertEqual(after["questions"][0]["model_answer"], "Re-embed; re-tune.")
        self.assertNotIn("options", after["questions"][0])
        self.assertEqual(len(after["questions"][1]["options"]), 2)


class ServedTest(SubjectiveCase):
    async def test_starting_an_attempt_serves_every_question(self):
        info = await self.ok("GET", f"/sets/{self.sid}")
        self.assertEqual(info["question_count"], CHOICE_COUNT + 1)
        self.assertEqual(info["subjective_count"], 1)
        session = await self.start()
        self.assertEqual(len(session["questions"]), CHOICE_COUNT + 1)
        self.assertEqual(sorted(q["kind"] for q in session["questions"]), ["choice"] * 3 + ["subjective"])
        [written] = [q for q in session["questions"] if q["kind"] == "subjective"]
        self.assertEqual((written["prompt"], written["options"]), (WRITTEN.prompt, []))

    async def test_a_set_of_only_subjective_questions_is_served_whole(self):
        imp = dataclasses.replace(QuizValidator.parse(sample_import(difficulty="easy")), questions=(WRITTEN, WRITTEN))
        sid = await self.publish(imp)
        info = await self.ok("GET", f"/sets/{sid}")
        self.assertEqual((info["question_count"], info["subjective_count"]), (2, 2))
        session = await self.start(sid)
        self.assertEqual([q["kind"] for q in session["questions"]], ["subjective", "subjective"])

    async def test_shuffling_keeps_the_subjective_question_whole(self):
        sid = await self.publish(with_written(difficulty="medium"))
        session = await self.start(sid)
        self.assertEqual(sorted(q["kind"] for q in session["questions"]), ["choice"] * 3 + ["subjective"])
        review = await D1AttemptRepository(self.db).review(session["attempt"]["id"])
        [written] = [q for q in review if q.kind == "subjective"]
        self.assertEqual((written.model_answer, written.options), (WRITTEN.model_answer, ()))

    async def test_the_open_attempt_never_carries_the_model_answer(self):
        session = await self.start()
        aid = session["attempt"]["id"]
        await self.type(aid, self.written_id(session), "My answer.")
        wire = json.dumps(await self.ok("GET", f"/attempts/{aid}"))
        self.assertNotIn("model_answer", wire)
        self.assertNotIn(WRITTEN.model_answer, wire)
        self.assertNotIn(WRITTEN.explanation, wire)

    async def test_the_question_is_copied_onto_the_paper(self):
        aid = (await self.start())["attempt"]["id"]
        rows = (await self.db.prepare(
            "SELECT kind, model_answer FROM attempt_questions WHERE attempt_id = ? ORDER BY source_question_id"
        ).bind(aid).all()).results
        self.assertEqual(
            [(r["kind"], r["model_answer"]) for r in rows],
            [("choice", None), ("subjective", WRITTEN.model_answer), ("choice", None), ("choice", None)],
        )
        options = await self.db.prepare(
            "SELECT COUNT(*) AS n FROM attempt_options ao JOIN attempt_questions aq "
            "ON aq.id = ao.attempt_question_id WHERE aq.attempt_id = ? AND aq.kind = 'subjective'"
        ).bind(aid).first()
        self.assertEqual(options["n"], 0)

    async def test_editing_the_model_answer_later_leaves_the_attempt_alone(self):
        aid = (await self.start())["attempt"]["id"]
        edited = dataclasses.replace(WRITTEN, model_answer="Rewritten after the attempt started.")
        imp = with_written()
        await self.authoring.update(
            self.sid, dataclasses.replace(imp, questions=imp.questions[:1] + (edited,) + imp.questions[2:]), START,
        )
        await self.ok("POST", f"/attempts/{aid}/submit")
        results = await self.ok("GET", f"/attempts/{aid}/results")
        [written] = [q for q in results["questions"] if q["kind"] == "subjective"]
        self.assertEqual(written["model_answer"], WRITTEN.model_answer)


class TextAnswerTest(SubjectiveCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        session = await self.start()
        self.aid = session["attempt"]["id"]
        self.qid = self.written_id(session)
        self.choice_qid = next(q["id"] for q in session["questions"] if q["kind"] == "choice")

    async def texts(self) -> dict:
        return (await self.ok("GET", f"/attempts/{self.aid}"))["texts"]

    async def test_a_typed_answer_is_saved_exactly_and_replaced(self):
        self.assertEqual(await self.texts(), {})
        self.assertEqual((await self.type(self.aid, self.qid, "  First draft.\n"))[0], 204)
        self.assertEqual(await self.texts(), {str(self.qid): "  First draft.\n"})
        self.assertEqual((await self.type(self.aid, self.qid, "Second draft."))[0], 204)
        self.assertEqual(await self.texts(), {str(self.qid): "Second draft."})

    async def test_blank_text_clears_the_answer(self):
        await self.type(self.aid, self.qid, "Something.")
        self.assertEqual((await self.type(self.aid, self.qid, " \n\t"))[0], 204)
        self.assertEqual(await self.texts(), {})
        count = await self.db.prepare("SELECT COUNT(*) AS n FROM attempt_text_answers").first()
        self.assertEqual(count["n"], 0)

    async def test_text_is_capped_at_10000_characters(self):
        self.assertEqual((await self.type(self.aid, self.qid, "é" * 10_000))[0], 204)
        status, body = await self.type(self.aid, self.qid, "x" * 10_001)
        self.assertEqual((status, body), (422, {"error": "a text answer is at most 10,000 characters"}))
        self.assertEqual(await self.texts(), {str(self.qid): "é" * 10_000})

    async def test_an_answer_must_suit_its_question(self):
        for qid, body, error in (
            (self.qid, {"option_ids": []}, "a subjective question takes a text answer, not options"),
            (self.choice_qid, {"text": "words"}, "only a subjective question takes a text answer"),
            (self.qid, {"text": "a", "option_ids": []}, "an answer has option_ids or text, not both"),
            (self.qid, {"text": None}, "text must be a string"),
            (self.qid, {"text": 5}, "text must be a string"),
        ):
            got = await self.call("PUT", f"/attempts/{self.aid}/answers/{qid}", body)
            self.assertEqual(got, (422, {"error": error}), body)
        self.assertEqual(await self.texts(), {})

    async def test_text_for_a_question_not_on_the_paper_is_refused(self):
        status, _ = await self.type(self.aid, 999_999, "words")
        self.assertEqual(status, 422)

    async def test_no_text_is_taken_after_the_attempt_finishes(self):
        await self.ok("POST", f"/attempts/{self.aid}/submit")
        status, body = await self.type(self.aid, self.qid, "Too late.")
        self.assertEqual((status, body), (409, {"error": "attempt finished"}))

    async def test_pause_stores_typed_answers_with_the_freeze_and_resume_returns_them(self):
        body = {"answers": [
            {"question_id": self.qid, "text": "Typed just before pausing."},
            {"question_id": self.choice_qid, "option_ids": []},
        ]}
        paused = await self.ok("POST", f"/attempts/{self.aid}/pause", body)
        self.assertIsNotNone(paused["attempt"]["paused_at"])
        self.assertEqual(paused["texts"], {str(self.qid): "Typed just before pausing."})

        status, _ = await self.type(self.aid, self.qid, "While paused.")
        self.assertEqual(status, 409)

        resumed = await self.ok("POST", f"/attempts/{self.aid}/resume")
        self.assertIsNone(resumed["attempt"]["paused_at"])
        self.assertEqual(resumed["texts"], {str(self.qid): "Typed just before pausing."})

    async def test_a_refused_pause_answer_leaves_the_attempt_unpaused_and_unwritten(self):
        body = {"answers": [
            {"question_id": self.qid, "text": "Fine."},
            {"question_id": self.choice_qid, "text": "Not for a choice question."},
        ]}
        status, _ = await self.call("POST", f"/attempts/{self.aid}/pause", body)
        self.assertEqual(status, 422)
        session = await self.ok("GET", f"/attempts/{self.aid}")
        self.assertIsNone(session["attempt"]["paused_at"])
        self.assertEqual(session["texts"], {})


class NotMarkedTest(SubjectiveCase):
    async def finish(self, typed: str | None, tick: bool) -> tuple[str, dict]:
        session = await self.start()
        aid = session["attempt"]["id"]
        if typed is not None:
            await self.type(aid, self.written_id(session), typed)
        if tick:
            await self.tick_every_correct_option(aid)
        await self.ok("POST", f"/attempts/{aid}/submit")
        return aid, await self.ok("GET", f"/attempts/{aid}/results")

    async def test_a_blank_subjective_question_costs_nothing(self):
        _, results = await self.finish(typed=None, tick=False)
        # Only the three choice questions are charged the -2 for a blank.
        self.assertEqual((results["attempt"]["score"], results["attempt"]["max_score"]),
                         (-2 * CHOICE_COUNT, CHOICE_MAX))

    async def test_a_written_answer_earns_nothing(self):
        aid, results = await self.finish(typed="A thoughtful answer.", tick=True)
        self.assertEqual((results["attempt"]["score"], results["attempt"]["max_score"]), (CHOICE_MAX, CHOICE_MAX))
        rows = await self.db.prepare(
            "SELECT COUNT(*) AS n FROM attempt_results WHERE attempt_id = ?"
        ).bind(aid).first()
        self.assertEqual(rows["n"], CHOICE_COUNT)

    async def test_results_show_the_typed_answer_and_the_model_answer_unmarked(self):
        _, results = await self.finish(typed="  Mine, as typed.\n", tick=True)
        [written] = [q for q in results["questions"] if q["kind"] == "subjective"]
        self.assertEqual(written, {
            "id": written["id"],
            "kind": "subjective",
            "prompt": WRITTEN.prompt,
            "points": None,
            "awarded_points": None,
            "is_correct": None,
            "explanation": WRITTEN.explanation,
            "options": [],
            "text_answer": "  Mine, as typed.\n",
            "model_answer": WRITTEN.model_answer,
        })
        self.assertTrue(all(q["kind"] == "choice" for q in results["questions"] if q is not written))
        self.assertEqual(len(results["questions"]), CHOICE_COUNT + 1)

    async def test_a_blank_answer_reads_as_none(self):
        _, results = await self.finish(typed=None, tick=True)
        [written] = [q for q in results["questions"] if q["kind"] == "subjective"]
        self.assertIsNone(written["text_answer"])

    async def test_hidden_answers_hide_the_model_answer_but_not_your_own(self):
        self.sid = await self.publish(with_written(reveal_answers=False, difficulty="hard"))
        _, results = await self.finish(typed="Mine.", tick=False)
        [written] = [q for q in results["questions"] if q["kind"] == "subjective"]
        self.assertEqual((written["text_answer"], written["model_answer"], written["explanation"]),
                         ("Mine.", None, None))


class PublicViewTest(SubjectiveCase):
    async def written(self, sid) -> dict:
        view = await self.ok("GET", f"/public/sets/{sid}", ident=None)
        self.assertEqual([q["kind"] for q in view["questions"]], ["choice", "subjective", "choice", "choice"])
        return view["questions"][1]

    async def test_view_shows_the_subjective_question_with_its_model_answer(self):
        written = await self.written(self.sid)
        self.assertEqual(written, {
            "id": written["id"],
            "kind": "subjective",
            "prompt": WRITTEN.prompt,
            "explanation": WRITTEN.explanation,
            "model_answer": WRITTEN.model_answer,
            "options": [],
        })

    async def test_hidden_answers_hide_the_model_answer_on_view(self):
        sid = await self.publish(with_written(reveal_answers=False, difficulty="hard"))
        written = await self.written(sid)
        self.assertEqual((written["kind"], written["options"], written["model_answer"], written["explanation"]),
                         ("subjective", [], None, None))


class AuthoringTest(SubjectiveCase):
    async def test_the_editor_gets_every_question_in_its_import_shape(self):
        detail = await self.ok("GET", f"/admin/sets/{self.sid}", ident=ADMIN)
        self.assertEqual([q["type"] for q in detail["questions"]], ["choice", "subjective", "choice", "choice"])
        self.assertEqual(detail["questions"][1], {
            "type": "subjective",
            "prompt": WRITTEN.prompt,
            "explanation": WRITTEN.explanation,
            "model_answer": WRITTEN.model_answer,
        })
        self.assertEqual(len(detail["questions"][0]["options"]), 4)

    async def test_clone_copies_the_subjective_question(self):
        clone = await self.ok("POST", f"/admin/sets/{self.sid}/clone", None, ADMIN)
        source = await self.ok("GET", f"/admin/sets/{self.sid}", ident=ADMIN)
        copied = await self.ok("GET", f"/admin/sets/{clone['id']}", ident=ADMIN)
        self.assertEqual(copied["questions"], source["questions"])


if __name__ == "__main__":
    unittest.main()
