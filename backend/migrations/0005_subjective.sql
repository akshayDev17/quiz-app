-- 0005 — subjective questions: answered in a text box, never marked.
--
-- A question is now one of two kinds:
--   'choice'      today's question: options, an answer key, marked;
--   'subjective'  no options; the solver types an answer; an authored model
--                 answer is shown on review. It earns no marks, costs nothing
--                 when left blank, and counts toward neither score nor maximum.
--
-- Only columns and a table are added, so there is no rebuild: every existing
-- question and paper row defaults to 'choice', and stored attempts, scores and
-- results are untouched.

ALTER TABLE questions ADD COLUMN kind TEXT NOT NULL DEFAULT 'choice'
  CHECK (kind IN ('choice', 'subjective'));
ALTER TABLE questions ADD COLUMN model_answer TEXT;

-- The paper copies both, so a later edit never rewrites what an attempt shows (ADR 0005).
ALTER TABLE attempt_questions ADD COLUMN kind TEXT NOT NULL DEFAULT 'choice'
  CHECK (kind IN ('choice', 'subjective'));
ALTER TABLE attempt_questions ADD COLUMN model_answer TEXT;

-- What the solver typed: one row per answered subjective question, replaced on
-- save and deleted when the answer is cleared. Not attempt_selections, whose keys
-- and foreign keys are option-shaped.
CREATE TABLE attempt_text_answers (
  attempt_id          TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  attempt_question_id INTEGER NOT NULL REFERENCES attempt_questions(id) ON DELETE CASCADE,
  body                TEXT NOT NULL CHECK (length(body) <= 10000),
  saved_at            INTEGER NOT NULL,
  PRIMARY KEY (attempt_id, attempt_question_id)
);
