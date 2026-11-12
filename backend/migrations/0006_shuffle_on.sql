-- 0006 — shuffle questions and options by default.
--
-- New sets now import with shuffle_questions and shuffle_options on (the importer's
-- default; the editor keeps both switches so an author can turn either off). Every
-- existing set had them off only because that was the old default, not because an
-- author chose it, so this turns both on for every set.
--
-- Some live sets explain their answers by option position or letter ("the first
-- option is right", "Option B describes …"). The results page labels options A, B, C
-- in served order, so with options shuffled those explanations would point at the
-- wrong option. Those sets keep shuffle_options off. Each exception is keyed by the
-- set's id and guarded by the offending text, so on any other database (where the
-- id may name a different set) it changes nothing. No live set has an option whose
-- meaning depends on its position ("All of the above", "Both A and B", …) or a
-- question that points at another question, so no set keeps shuffle_questions off.
--
-- Running attempts are untouched: each reads its own paper, written in the order it
-- was served.
--
-- The column DEFAULTs (0 in 0001) are left as they are: SQLite can only change a
-- default by rebuilding quiz_sets, and every insert the app makes names both columns.

UPDATE quiz_sets SET shuffle_questions = 1, shuffle_options = 1;

-- Set 6 "Context Engineering: Assembly, Budgets and Grounding", Q10:
--   "Wrong: the first option inverts that, …"
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 6 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND q.explanation LIKE '%the first option inverts that%');

-- Set 8 "Why RAG Exists — Concepts, Tradeoffs, and the Decision Procedure", Q11 and 9 more:
--   "… which is exactly the first option."
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 8 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND q.explanation LIKE '%which is exactly the first option%');

-- Set 9 "RAG Observability, Tracing, and Online Evaluation", Q1:
--   "… the last option wrongly assigns each side to a single pipeline stage …"
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 9 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND q.explanation LIKE '%the last option wrongly assigns each side%');

-- Set 13 "RAG pipeline, end to end", Q18 and 6 more:
--   "The second option misattributes both …"
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 13 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND q.explanation LIKE '%The second option misattributes both%');

-- Set 22 "Multi-tenant, permissioned, and regulated RAG", Q31:
--   "Options C and D are inside the boundary …"
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 22 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND q.explanation LIKE '%Options C and D are inside the boundary%');

-- Set 23 "M3 — Parsing and the Chunking Decision", Q39:
--   "The last option (embedding model) is an additional irreversible choice …"
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 23 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND q.explanation LIKE '%The last option (embedding model)%');

-- Set 24 "Sparse, Dense, and Hybrid Retrieval (M7)", Q4 and 27 more:
--   "Option B describes the b parameter (length normalization), option C …"
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 24 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND q.explanation LIKE '%Option B describes the b parameter%');

-- Set 31 "RAG M8 - Index Structures Beyond Flat Vectors", Q35 and 6 more:
--   "The second option swaps the two models' roles …"
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 31 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND q.explanation LIKE '%The second option swaps the two models%');
