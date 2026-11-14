-- 0009 — subjective answers are marked by an AI evaluator, out of 4, never below 0.
--
-- The grading scheme is ADR 0010 (docs/adr/0010-subjective-answers-are-marked-by-an-evaluator.md).
-- In short: every subjective question of a new attempt is worth `subjective_marks`
-- (4 today), frozen on the attempt at start like its scoring policy (ADR 0005). An
-- evaluator model places the typed answer on a 0–4 rubric level against the authored
-- model answer and key points; the level times subjective_marks / 4 is the award. A
-- blank answer scores 0 without any call. Nothing here can go below 0.
--
-- Only columns and tables are added, so there is no rebuild:
--   * every existing attempt keeps subjective_marks NULL, which means "started before
--     written answers were marked": its written answers stay unmarked and outside its
--     score and maximum, exactly as before, and its stored score never moves;
--   * every existing question keeps key_points NULL, which the evaluator reads as
--     "no authored key points: take the essentials from the model answer".

ALTER TABLE attempts ADD COLUMN subjective_marks REAL CHECK (subjective_marks IS NULL OR subjective_marks > 0);

-- Authored rubric for a subjective question: a JSON array of 1–6 short strings, each one
-- essential point a full answer makes. Optional; validated by QuizValidator. The paper
-- copies it, so a later edit never changes how a running attempt is marked (ADR 0005).
ALTER TABLE questions ADD COLUMN key_points TEXT;
ALTER TABLE attempt_questions ADD COLUMN key_points TEXT;

-- One row per subjective question of a marked attempt, written in the same transaction
-- that closes the attempt:
--   blank     nothing typed: 0, final, no evaluator call;
--   awaiting  typed, not yet marked (no evaluator could take it, the daily quota was
--             reached, or the provider failed): counts nothing yet, waits for the next
--             submit of this attempt or an admin re-run;
--   marked    the evaluator's level, award and feedback: final;
--   flagged   the evaluator answered but its reply was unusable (invalid, refused, or
--             the item could never fit a call): 0, final, flagged for review.
-- `claim`/`claimed_at` mark an awaiting row taken by one request, so no two requests
-- ever send the same answer. `reason`, `provider` and `model` are for admins only.
CREATE TABLE attempt_text_marks (
  attempt_id          TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  attempt_question_id INTEGER NOT NULL REFERENCES attempt_questions(id) ON DELETE CASCADE,
  status              TEXT NOT NULL CHECK (status IN ('blank', 'awaiting', 'marked', 'flagged')),
  max_marks           REAL NOT NULL CHECK (max_marks > 0),
  awarded             REAL NOT NULL DEFAULT 0 CHECK (awarded >= 0 AND awarded <= max_marks),
  level               INTEGER CHECK (level IS NULL OR level BETWEEN 0 AND 4),
  feedback            TEXT CHECK (feedback IS NULL OR length(feedback) <= 400),
  reason              TEXT,
  provider            TEXT,
  model               TEXT,
  claim               TEXT,
  claimed_at          INTEGER,
  marked_at           INTEGER,
  CHECK (status = 'marked' OR awarded = 0),
  PRIMARY KEY (attempt_id, attempt_question_id)
);
CREATE INDEX idx_attempt_text_marks_status ON attempt_text_marks(status);

-- Evaluator keys, entered by the admin on the admin page (ADR 0011). A key's values are
-- stored only sealed with AES-256-GCM under the KEY_ENCRYPTION_KEY Worker secret:
-- `sealed_key`, and `sealed_billing` for its optional read-only billing credential. The
-- non-secret fields (a region, an endpoint, an account id, a budget name) are JSON in
-- `settings` and `billing_settings`. `hint` is the key's last four characters, the only
-- part ever shown again.
--   unusable/unusable_at  the provider refused this key's calls for credit ('out_of_credit')
--                         or refused the key ('key_refused'): marking skips it until a
--                         retry is due, and a working call or a "check now" clears it;
--   checked_at/check_result  the last "check now";
--   balance_*             the last reading of the provider's own budget figures.
CREATE TABLE evaluator_keys (
  id                    INTEGER PRIMARY KEY,
  provider              TEXT NOT NULL,
  label                 TEXT NOT NULL UNIQUE CHECK (length(label) BETWEEN 1 AND 60),
  sealed_key            TEXT NOT NULL,
  hint                  TEXT NOT NULL DEFAULT '',
  settings              TEXT NOT NULL DEFAULT '{}',
  sealed_billing        TEXT,
  billing_settings      TEXT,
  unusable              TEXT CHECK (unusable IS NULL OR unusable IN ('out_of_credit', 'key_refused')),
  unusable_at           INTEGER,
  checked_at            INTEGER,
  check_result          TEXT,
  balance_limit_micros  INTEGER,
  balance_spent_micros  INTEGER,
  balance_currency      TEXT,
  balance_source        TEXT,
  balance_at            INTEGER,
  balance_error         TEXT,
  created_at            INTEGER NOT NULL,
  updated_at            INTEGER NOT NULL
);

-- The admin's ordered list: each entry is one key and one model. Marking takes the first
-- entry, in `position` order, that can take the call, and falls down the list. Money is
-- integer micro-dollars; prices are USD per million tokens, so a call costs
-- input_tokens × input_price + output_tokens × output_price micro-dollars.
-- `monthly_cap_micros` is an optional app-side cap on the entry's tracked spend in a UTC
-- month (NULL: no cap); at the cap, marking stops using the entry.
CREATE TABLE evaluator_entries (
  id                     INTEGER PRIMARY KEY,
  key_id                 INTEGER NOT NULL,
  model                  TEXT NOT NULL CHECK (length(model) BETWEEN 1 AND 120),
  position               INTEGER NOT NULL,
  monthly_cap_micros     INTEGER CHECK (monthly_cap_micros IS NULL OR monthly_cap_micros >= 0),
  input_price_per_mtok   REAL NOT NULL CHECK (input_price_per_mtok >= 0),
  output_price_per_mtok  REAL NOT NULL CHECK (output_price_per_mtok >= 0),
  created_at             INTEGER NOT NULL,
  updated_at             INTEGER NOT NULL,
  UNIQUE (key_id, model)
);

-- The app's own spend ledger: one row per evaluator call, reserved before the call at a
-- conservative estimate and settled to its real token cost after. An entry's spend this
-- month is the sum of its rows (settled cost, else the reservation): the app's tracking,
-- not the provider's bill. A "check now" probe is a row too (trigger 'check'), on the
-- entry it probed or, for a key no entry uses yet, on the key alone. Daily quotas count
-- only marking calls. No foreign keys: the ledger outlives keys, entries and attempts.
CREATE TABLE evaluation_calls (
  id               INTEGER PRIMARY KEY,
  token            TEXT NOT NULL UNIQUE,
  entry_id         INTEGER,
  key_id           INTEGER NOT NULL,
  provider         TEXT NOT NULL,
  model            TEXT NOT NULL,
  attempt_id       TEXT,
  user_email       TEXT NOT NULL,
  trigger          TEXT NOT NULL CHECK (trigger IN ('submit', 'rerun', 'check')),
  day              TEXT NOT NULL,    -- UTC 'YYYY-MM-DD'
  month            TEXT NOT NULL,    -- UTC 'YYYY-MM'
  reserved_micros  INTEGER NOT NULL CHECK (reserved_micros >= 0),
  cost_micros      INTEGER CHECK (cost_micros IS NULL OR cost_micros >= 0),
  input_tokens     INTEGER,
  output_tokens    INTEGER,
  latency_ms       INTEGER,
  http_status      INTEGER,
  request_id       TEXT,
  outcome          TEXT,
  rubric           TEXT NOT NULL,
  created_at       INTEGER NOT NULL,
  CHECK (trigger = 'check' OR (attempt_id IS NOT NULL AND entry_id IS NOT NULL))
);
CREATE INDEX idx_evaluation_calls_day ON evaluation_calls(day, user_email);
CREATE INDEX idx_evaluation_calls_entry ON evaluation_calls(entry_id, month);
