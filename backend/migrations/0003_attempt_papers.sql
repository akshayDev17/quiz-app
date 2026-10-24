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
-- Written for D1, which will not run an explicit BEGIN/COMMIT from SQL ("use
-- state.storage.transaction() instead") and always enforces foreign keys. So
-- there is no transaction and no `PRAGMA foreign_keys = OFF` here; instead every
-- step is ordered so that nothing references a table at the moment it is dropped:
--
--   1. copy the two child tables into FK-free scratch tables,
--   2. drop the children (nothing references `attempts` any more),
--   3. rebuild `attempts` with a nullable set_id plus the frozen label and policy,
--   4. create the paper,
--   5. recreate the children against the paper,
--   6. backfill the paper from the live set,
--   7. restore the answers and the grades, mapping source ids onto paper ids.
--
-- If a statement fails part-way the scratch tables hold the only copy of the
-- answers; nothing before step 2 is destructive.

-- 1. Set aside what the solver ticked and what they were graded, without FKs ----

CREATE TABLE _attempt_selections_backup (
  attempt_id  TEXT NOT NULL,
  question_id INTEGER NOT NULL,
  option_id   INTEGER NOT NULL
);
INSERT INTO _attempt_selections_backup (attempt_id, question_id, option_id)
SELECT attempt_id, question_id, option_id FROM attempt_selections;

CREATE TABLE _attempt_results_backup (
  attempt_id      TEXT NOT NULL,
  question_id     INTEGER NOT NULL,
  awarded_points  REAL NOT NULL,
  is_correct      INTEGER NOT NULL
);
INSERT INTO _attempt_results_backup (attempt_id, question_id, awarded_points, is_correct)
SELECT attempt_id, question_id, awarded_points, is_correct FROM attempt_results;

-- 2. Drop the children so `attempts` can be replaced ---------------------------

DROP TABLE attempt_selections;
DROP TABLE attempt_results;

-- 3. attempts: nullable set_id + the frozen name/policy it is shown and graded by
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

-- 4. The paper ----------------------------------------------------------------

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

-- 5. The children, now pointing at the paper ----------------------------------

CREATE TABLE attempt_selections (
  attempt_id          TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  attempt_question_id INTEGER NOT NULL REFERENCES attempt_questions(id) ON DELETE CASCADE,
  attempt_option_id   INTEGER NOT NULL REFERENCES attempt_options(id) ON DELETE CASCADE,
  PRIMARY KEY (attempt_id, attempt_question_id, attempt_option_id)
);

CREATE TABLE attempt_results (
  attempt_id          TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  attempt_question_id INTEGER NOT NULL REFERENCES attempt_questions(id) ON DELETE CASCADE,
  awarded_points      REAL NOT NULL,
  is_correct          INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
  PRIMARY KEY (attempt_id, attempt_question_id)
);

-- 6. A paper for every attempt that already exists ----------------------------
--
-- Read from the live set because it is still what those attempts were served: the
-- old guard meant a set with attempts could never be edited. Served order = authored
-- order, since a shuffle was only ever applied at read time and every stored
-- selection is by id, not by position.

INSERT INTO attempt_questions (attempt_id, source_question_id, position, prompt, explanation, points)
SELECT a.id, q.id, q.position, q.prompt, q.explanation, q.points
FROM attempts a
JOIN questions q ON q.set_id = a.set_id;

INSERT INTO attempt_options (attempt_question_id, source_option_id, position, body, is_correct)
SELECT aq.id, o.id, o.position, o.body, o.is_correct
FROM attempt_questions aq
JOIN options o ON o.question_id = aq.source_question_id;

-- 7. Put the answers and the grades back, on paper ids -------------------------

INSERT INTO attempt_selections (attempt_id, attempt_question_id, attempt_option_id)
SELECT b.attempt_id, aq.id, ao.id
FROM _attempt_selections_backup b
JOIN attempt_questions aq
  ON aq.attempt_id = b.attempt_id AND aq.source_question_id = b.question_id
JOIN attempt_options ao
  ON ao.attempt_question_id = aq.id AND ao.source_option_id = b.option_id;

INSERT INTO attempt_results (attempt_id, attempt_question_id, awarded_points, is_correct)
SELECT b.attempt_id, aq.id, b.awarded_points, b.is_correct
FROM _attempt_results_backup b
JOIN attempt_questions aq
  ON aq.attempt_id = b.attempt_id AND aq.source_question_id = b.question_id;

DROP TABLE _attempt_selections_backup;
DROP TABLE _attempt_results_backup;

-- Verified by test/test_migration.py, which applies 0001–0002, seeds attempts, then
-- applies this file with foreign keys ON and no wrapping transaction — the same
-- constraints D1 runs under.
