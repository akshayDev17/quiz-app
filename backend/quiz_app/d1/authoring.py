"""D1-backed authoring: create (import), status changes, clone, admin listing."""

from __future__ import annotations

from ..clock import Clock
from ..errors import Conflict, NotFound
from ..models import QuizSetInfo
from ..ports import QuizAuthoring
from ..validation import SetImport
from ._rows import QUIZ_SET_COLUMNS, QUIZ_SET_FROM, QUIZ_SET_SELECT, quiz_set_from_row

_NEXT_SEQ = (
    "SELECT COALESCE(MAX(seq), 0) + 1 AS seq FROM quiz_sets "
    "WHERE topic_id = ? AND COALESCE(subtopic_id, 0) = COALESCE(?, 0) "
    "AND COALESCE(difficulty, '') = COALESCE(?, '') AND style = ?"
)


class D1QuizAuthoring(QuizAuthoring):
    def __init__(self, db, clock: Clock):
        self._db = db
        self._clock = clock  # stamps updated_at on status changes (the port carries no time)

    async def create_set(self, imp: SetImport, created_by: str, now_ms: int) -> int:
        topic_slug, topic_name = imp.topic
        await self._db.prepare(
            "INSERT INTO topics (slug, name, created_at) VALUES (?, ?, ?) ON CONFLICT(slug) DO NOTHING"
        ).bind(topic_slug, topic_name, now_ms).run()
        topic_id = (await self._db.prepare("SELECT id FROM topics WHERE slug = ?").bind(topic_slug).first())["id"]

        subtopic_id = None
        if imp.subtopic is not None:
            sub_slug, sub_name = imp.subtopic
            await self._db.prepare(
                "INSERT INTO subtopics (topic_id, slug, name, created_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(topic_id, slug) DO NOTHING"
            ).bind(topic_id, sub_slug, sub_name, now_ms).run()
            subtopic_id = (await self._db.prepare(
                "SELECT id FROM subtopics WHERE topic_id = ? AND slug = ?"
            ).bind(topic_id, sub_slug).first())["id"]

        seq = (await self._db.prepare(_NEXT_SEQ).bind(topic_id, subtopic_id, imp.difficulty, imp.style).first())["seq"]
        set_id = (await self._db.prepare(
            "INSERT INTO quiz_sets (topic_id, subtopic_id, difficulty, style, seq, title, description, "
            "time_limit_minutes, scoring_policy, shuffle_questions, shuffle_options, reveal_answers, "
            "max_attempts, status, created_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?) RETURNING id"
        ).bind(
            topic_id, subtopic_id, imp.difficulty, imp.style, seq, imp.title, imp.description,
            imp.time_limit_minutes, imp.scoring_policy, int(imp.shuffle_questions),
            int(imp.shuffle_options), int(imp.reveal_answers), imp.max_attempts,
            created_by, now_ms, now_ms,
        ).first())["id"]

        try:
            for position, question in enumerate(imp.questions):
                question_id = (await self._db.prepare(
                    "INSERT INTO questions (set_id, position, prompt, explanation, points) "
                    "VALUES (?, ?, ?, ?, ?) RETURNING id"
                ).bind(set_id, position, question.prompt, question.explanation, question.points).first())["id"]
                await self._db.batch([
                    self._db.prepare(
                        "INSERT INTO options (question_id, position, body, is_correct) VALUES (?, ?, ?, ?)"
                    ).bind(question_id, index, body, int(correct))
                    for index, (body, correct) in enumerate(question.options)
                ])
        except BaseException:
            # Questions are inserted one by one (we need each id), so a failure part-way
            # would leave a half-built draft. Remove it; questions and options cascade.
            await self._db.prepare("DELETE FROM quiz_sets WHERE id = ?").bind(set_id).run()
            raise
        return set_id

    async def set_status(self, set_id: int, status: str) -> None:
        await self._db.prepare(
            "UPDATE quiz_sets SET status = ?, updated_at = ? WHERE id = ?"
        ).bind(status, self._clock.now_ms(), set_id).run()

    async def clone(self, set_id: int, created_by: str, now_ms: int) -> int:
        source = await self._db.prepare("SELECT * FROM quiz_sets WHERE id = ?").bind(set_id).first()
        if source is None:
            raise NotFound("quiz set not found")
        seq = (await self._db.prepare(_NEXT_SEQ).bind(
            source["topic_id"], source["subtopic_id"], source["difficulty"], source["style"]
        ).first())["seq"]
        new_id = (await self._db.prepare(
            "INSERT INTO quiz_sets (topic_id, subtopic_id, difficulty, style, seq, title, description, "
            "time_limit_minutes, scoring_policy, shuffle_questions, shuffle_options, reveal_answers, "
            "max_attempts, status, created_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?) RETURNING id"
        ).bind(
            source["topic_id"], source["subtopic_id"], source["difficulty"], source["style"], seq,
            source["title"], source["description"], source["time_limit_minutes"],
            source["scoring_policy"], source["shuffle_questions"], source["shuffle_options"],
            source["reveal_answers"], source["max_attempts"], created_by, now_ms, now_ms,
        ).first())["id"]

        try:
            questions = (await self._db.prepare(
                "SELECT id, position, prompt, explanation, points FROM questions WHERE set_id = ? ORDER BY position"
            ).bind(set_id).all()).results
            for question in questions:
                new_question_id = (await self._db.prepare(
                    "INSERT INTO questions (set_id, position, prompt, explanation, points) "
                    "VALUES (?, ?, ?, ?, ?) RETURNING id"
                ).bind(new_id, question["position"], question["prompt"], question["explanation"],
                       question["points"]).first())["id"]
                await self._db.prepare(
                    "INSERT INTO options (question_id, position, body, is_correct) "
                    "SELECT ?, position, body, is_correct FROM options WHERE question_id = ?"
                ).bind(new_question_id, question["id"]).run()
        except BaseException:
            await self._db.prepare("DELETE FROM quiz_sets WHERE id = ?").bind(new_id).run()
            raise
        return new_id

    async def list_all(self) -> list[tuple[QuizSetInfo, int]]:
        rows = (await self._db.prepare(
            f"SELECT {QUIZ_SET_COLUMNS}, "
            "(SELECT COUNT(*) FROM attempts a WHERE a.set_id = s.id) AS attempt_count "
            f"{QUIZ_SET_FROM} ORDER BY s.created_at DESC, s.id DESC"
        ).all()).results
        return [(quiz_set_from_row(row), row["attempt_count"]) for row in rows]

    async def get(self, set_id: int) -> QuizSetInfo | None:
        row = await self._db.prepare(f"{QUIZ_SET_SELECT} WHERE s.id = ?").bind(set_id).first()
        return quiz_set_from_row(row) if row else None

    async def delete(self, set_id: int) -> None:
        # A set with attempts can't be hard-deleted: attempts.set_id → quiz_sets is
        # ON DELETE RESTRICT. Refuse cleanly instead of surfacing a D1 FK error.
        attempts = (await self._db.prepare(
            "SELECT COUNT(*) AS n FROM attempts WHERE set_id = ?"
        ).bind(set_id).first())["n"]
        if attempts:
            raise Conflict("set has attempts — archive it instead of deleting")
        # questions and options cascade; no attempts means nothing else references them.
        await self._db.prepare("DELETE FROM quiz_sets WHERE id = ?").bind(set_id).run()
