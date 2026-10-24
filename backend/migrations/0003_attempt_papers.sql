-- 0003 — an attempt owns its paper.
--
-- Until now an attempt referenced the *live* quiz: attempt_selections.question_id
-- pointed at questions(id), so editing or deleting a played set either orphaned
-- history or was forbidden outright. This migration freezes, per attempt, the
-- content it was served and the rules it was graded by, so the live set can be
-- edited or deleted without touching any attempt.
--
-- Shape after this:
--   attempt 1─* attempt_question 1─* attempt_option   (the paper; immutable)
--   attempt 1─* attempt_selection                     (→ attempt_question/option)
--   attempt 1─* attempt_result                        (→ attempt_question)
--   attempt.set_id → quiz_sets ON DELETE SET NULL     (NULL once the set is gone)
--
-- The paper carries the served order (shuffle happens once, at start), and
-- `source_*_id` is provenance only — deliberately NOT a foreign key, because the
-- whole point is that the source may be deleted.
--
-- Table rebuilds are needed for the nullable FK and the rewired child FKs.
-- `foreign_keys = OFF` is the documented SQLite procedure; `defer_foreign_keys`
-- covers D1, which does not allow turning enforcement off. Either way the end
-- state is checked by `PRAGMA foreign_key_check` (see the note at the bottom).

PRAGMA foreign_keys = OFF;
BEGIN;
PRAGMA defer_foreign_keys = true;

-- 1. The paper ------------------------------------------------------------------

CREATE TABLE attempt_questions (
  id                  INTEGER PRIMARY KEY,
  attempt_id          TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  source_question_id  INTEGER,                          -- provenance only; no FK on purpose
  position            INTEGER NOT NULL,                 -- served order, 0-based
  prompt              TEXT NOT NULL,
  explanation         TEXT,
  points              REAL NOT NULL CHECK (points > 0),
  UNIQUE (attempt_id, position)
);
CREATE INDEX idx_attempt_questions_attempt ON attempt_questions(attempt_id);

CREATE TABLE attempt_options (
  id                  INTEGER PRIMARY KEY,
  attempt_question_id INTEGER NOT NULL REFERENCES attempt_questions(id) ON DELETE CASCADE,
  source_option_id    INTEGER,                          -- provenance only; no FK on purpose
  position            INTEGER NOT NULL,                 -- served order, 0-based
  body                TEXT NOT NULL,
  is_correct          INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
  UNIQUE (attempt_question_id, position)
);
CREATE INDEX idx_attempt_options_question ON attempt_options(attempt_question_id);

-- 2. attempts: nullable set_id + the frozen name/policy it is shown and graded by -
--
-- The name ingredients (topic, subtopic, difficulty, style, seq, title) are copied
-- rather than the computed string, so `models.set_name` stays the single place that
-- decides how a set is displayed and history cannot drift from it.

CREATE TABLE attempts_new (
  id             TEXT PRIMARY KEY,                      -- uuid; also the shuffle seed
  set_id         INTEGER REFERENCES quiz_sets(id) ON DELETE SET NULL,
  user_email     TEXT NOT NULL REFERENCES users(email),
  topic_name     TEXT NOT NULL,
  subtopic_name  TEXT,
  difficulty     TEXT,
  style          TEXT NOT NULL DEFAULT 'standard',
  seq            INTEGER NOT NULL DEFAULT 1,
  title          TEXT,
  scoring_policy TEXT NOT NULL DEFAULT 'all_or_nothing',
  reveal_answers INTEGER NOT NULL DEFAULT 1 CHECK (reveal_answers IN (0, 1)),
  started_at     INTEGER NOT NULL,
  deadline_at    INTEGER,
  finished_at    INTEGER,
  status         TEXT NOT NULL DEFAULT 'in_progress'
                 CHECK (status IN ('in_progress', 'submitted', 'expired')),
  score          REAL,
  max_score      REAL,
  paused_at      INTEGER,
  CHECK ((status = 'in_progress') = (finished_at IS NULL)),
  CHECK (status <> 'expired' OR deadline_at IS NOT NULL)
);

INSERT INTO attempts_new (
  id, set_id, user_email, topic_name, subtopic_name, difficulty, style, seq, title,
  scoring_policy, reveal_answers, started_at, deadline_at, finished_at, status,
  score, max_score, paused_at
)
SELECT
  a.id, a.set_id, a.user_email,
  COALESCE(t.name, ''), st.name, s.difficulty, COALESCE(s.style, 'standard'),
  COALESCE(s.seq, 1), s.title,
  COALESCE(s.scoring_policy, 'all_or_nothing'), COALESCE(s.reveal_answers, 1),
  a.started_at, a.deadline_at, a.finished_at, a.status, a.score, a.max_score, a.paused_at
FROM attempts a
LEFT JOIN quiz_sets s  ON s.id  = a.set_id
LEFT JOIN topics t     ON t.id  = s.topic_id
LEFT JOIN subtopics st ON st.id = s.subtopic_id;

DROP TABLE attempts;
ALTER TABLE attempts_new RENAME TO attempts;

CREATE UNIQUE INDEX uq_attempts_one_open
  ON attempts(set_id, user_email) WHERE status = 'in_progress';
CREATE INDEX idx_attempts_user ON attempts(user_email, started_at DESC);

-- 3. Backfill a paper for every attempt that already exists -----------------------
--
-- Safe because the live set could never have been edited after an attempt (that was
-- exactly the restriction this migration removes), so live questions still are what
-- each attempt was served. Served order = authored order: shuffle is applied at read
-- time today and is not recoverable, and every stored selection is by id, not order.

INSERT INTO attempt_questions (attempt_id, source_question_id, position, prompt, explanation, points)
SELECT a.id, q.id, q.position, q.prompt, q.explanation, q.points
FROM attempts a
JOIN questions q ON q.set_id = a.set_id;

INSERT INTO attempt_options (attempt_question_id, source_option_id, position, body, is_correct)
SELECT aq.id, o.id, o.position, o.body, o.is_correct
FROM attempt_questions aq
JOIN options o ON o.question_id = aq.source_question_id;

-- 4. Rewire what the solver ticked and what was graded onto the paper -------------

CREATE TABLE attempt_selections_new (
  attempt_id          TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  attempt_question_id INTEGER NOT NULL REFERENCES attempt_questions(id) ON DELETE CASCADE,
  attempt_option_id   INTEGER NOT NULL REFERENCES attempt_options(id) ON DELETE CASCADE,
  PRIMARY KEY (attempt_id, attempt_question_id, attempt_option_id)
);

INSERT INTO attempt_selections_new (attempt_id, attempt_question_id, attempt_option_id)
SELECT s.attempt_id, aq.id, ao.id
FROM attempt_selections s
JOIN attempt_questions aq
  ON aq.attempt_id = s.attempt_id AND aq.source_question_id = s.question_id
JOIN attempt_options ao
  ON ao.attempt_question_id = aq.id AND ao.source_option_id = s.option_id;

DROP TABLE attempt_selections;
ALTER TABLE attempt_selections_new RENAME TO attempt_selections;

CREATE TABLE attempt_results_new (
  attempt_id          TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  attempt_question_id INTEGER NOT NULL REFERENCES attempt_questions(id) ON DELETE CASCADE,
  awarded_points      REAL NOT NULL,
  is_correct          INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
  PRIMARY KEY (attempt_id, attempt_question_id)
);

INSERT INTO attempt_results_new (attempt_id, attempt_question_id, awarded_points, is_correct)
SELECT r.attempt_id, aq.id, r.awarded_points, r.is_correct
FROM attempt_results r
JOIN attempt_questions aq
  ON aq.attempt_id = r.attempt_id AND aq.source_question_id = r.question_id;

DROP TABLE attempt_results;
ALTER TABLE attempt_results_new RENAME TO attempt_results;

COMMIT;
PRAGMA foreign_keys = ON;

-- Verified by test/test_migration.py, which applies 0001–0002, seeds attempts, then
-- applies this file and asserts papers, selections, results and labels all survive.
