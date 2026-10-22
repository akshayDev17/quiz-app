-- quiz-app — initial schema (Cloudflare D1 / SQLite).
--
-- Shape:  topic 1─* quiz_set 1─* question 1─* option
--         quiz_set 1─* attempt 1─* attempt_selection   (what the solver ticked)
--                          attempt 1─* attempt_result  (written once, at grading)
--
-- Times are INTEGER unix epoch milliseconds: the deadline arithmetic is then
-- plain integer comparison, with no timezone parsing on either side.

PRAGMA foreign_keys = ON;

-- Who may sign in is decided by the Cloudflare Access policy, not by this table.
-- A row is created on a user's first authenticated request; `role` only decides
-- who may author quizzes.
CREATE TABLE users (
  email         TEXT PRIMARY KEY,                       -- normalized (lowercased)
  display_name  TEXT,
  role          TEXT NOT NULL DEFAULT 'solver'
                CHECK (role IN ('solver', 'admin')),
  created_at    INTEGER NOT NULL
);

CREATE TABLE topics (
  id            INTEGER PRIMARY KEY,
  slug          TEXT NOT NULL UNIQUE,                   -- 'python', 'system-design'
  name          TEXT NOT NULL,
  description   TEXT,
  created_at    INTEGER NOT NULL
);

-- A set is the unit a solver takes: it carries the time limit and the rules.
CREATE TABLE quiz_sets (
  id                   INTEGER PRIMARY KEY,
  topic_id             INTEGER NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
  slug                 TEXT NOT NULL,
  title                TEXT NOT NULL,
  description          TEXT,
  -- NULL = untimed. Whole minutes, as authored.
  time_limit_minutes   INTEGER CHECK (time_limit_minutes IS NULL OR time_limit_minutes > 0),
  -- How a multi-answer question is marked (see ScoringPolicyFactory).
  scoring_policy       TEXT NOT NULL DEFAULT 'all_or_nothing'
                       CHECK (scoring_policy IN ('all_or_nothing', 'partial')),
  shuffle_questions    INTEGER NOT NULL DEFAULT 0 CHECK (shuffle_questions IN (0, 1)),
  shuffle_options      INTEGER NOT NULL DEFAULT 0 CHECK (shuffle_options IN (0, 1)),
  -- After grading, may the solver see the correct options and explanations?
  reveal_answers       INTEGER NOT NULL DEFAULT 1 CHECK (reveal_answers IN (0, 1)),
  max_attempts         INTEGER CHECK (max_attempts IS NULL OR max_attempts > 0), -- NULL = unlimited
  status               TEXT NOT NULL DEFAULT 'draft'
                       CHECK (status IN ('draft', 'published', 'archived')),
  created_by           TEXT NOT NULL REFERENCES users(email),
  created_at           INTEGER NOT NULL,
  updated_at           INTEGER NOT NULL,
  UNIQUE (topic_id, slug)
);
CREATE INDEX idx_quiz_sets_topic_status ON quiz_sets(topic_id, status);

CREATE TABLE questions (
  id            INTEGER PRIMARY KEY,
  set_id        INTEGER NOT NULL REFERENCES quiz_sets(id) ON DELETE CASCADE,
  position      INTEGER NOT NULL,                       -- authored order, 0-based
  prompt        TEXT NOT NULL,                          -- markdown (code blocks allowed)
  explanation   TEXT,                                   -- shown on the scores page only
  points        REAL NOT NULL DEFAULT 1 CHECK (points > 0),
  UNIQUE (set_id, position)
);

-- N options per question; any number of them may be correct (at least one — that
-- cross-row rule is enforced by QuizValidator on publish, since SQLite CHECKs
-- cannot see other rows). Letters A, B, C… are NOT stored: they are derived from
-- display order, which may be shuffled per attempt.
CREATE TABLE options (
  id            INTEGER PRIMARY KEY,
  question_id   INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  position      INTEGER NOT NULL,
  body          TEXT NOT NULL,                          -- markdown
  is_correct    INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
  UNIQUE (question_id, position)
);
CREATE INDEX idx_options_question ON options(question_id);

CREATE TABLE attempts (
  id            TEXT PRIMARY KEY,                       -- uuid; also the shuffle seed
  set_id        INTEGER NOT NULL REFERENCES quiz_sets(id) ON DELETE RESTRICT,
  user_email    TEXT NOT NULL REFERENCES users(email),
  started_at    INTEGER NOT NULL,
  -- started_at + time_limit, fixed at start. NULL = untimed. The server's copy is
  -- the only one that counts; the browser's countdown is a display of it.
  deadline_at   INTEGER,
  finished_at   INTEGER,
  status        TEXT NOT NULL DEFAULT 'in_progress'
                CHECK (status IN ('in_progress', 'submitted', 'expired')),
  score         REAL,                                   -- NULL until graded
  max_score     REAL,
  CHECK ((status = 'in_progress') = (finished_at IS NULL)),
  CHECK (status <> 'expired' OR deadline_at IS NOT NULL)
);
-- At most one open attempt per person per set: "Start" twice resumes, never forks.
CREATE UNIQUE INDEX uq_attempts_one_open
  ON attempts(set_id, user_email) WHERE status = 'in_progress';
CREATE INDEX idx_attempts_user ON attempts(user_email, started_at DESC);

-- One row per ticked option. Saving an answer replaces the question's rows.
CREATE TABLE attempt_selections (
  attempt_id    TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  question_id   INTEGER NOT NULL REFERENCES questions(id),
  option_id     INTEGER NOT NULL REFERENCES options(id),
  PRIMARY KEY (attempt_id, question_id, option_id)
);

-- Written once, when the attempt is graded, so a score never moves afterwards.
CREATE TABLE attempt_results (
  attempt_id      TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  question_id     INTEGER NOT NULL REFERENCES questions(id),
  awarded_points  REAL NOT NULL,
  is_correct      INTEGER NOT NULL CHECK (is_correct IN (0, 1)),  -- exact match
  PRIMARY KEY (attempt_id, question_id)
);
