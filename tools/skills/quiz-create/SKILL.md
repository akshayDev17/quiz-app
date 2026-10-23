---
name: quiz-create
description: Author a quiz-set JSON for the quiz app — varied difficulty, single- and multi-correct questions, plausible distractors — and validate it before upload. Use when asked to create, write, or author a quiz or quiz set.
---

# quiz-create — author a quiz set, then check it

Write a quiz-set JSON, then run `scripts/validate.py` so the file is clean before
it goes anywhere near the server. Do **not** upload — that is `quiz-upload`'s job.

## Authoring principles — the craft (read before writing)

The schema below is the *mechanics*; this section is the *craft*. A quiz that
merely passes validation but is flat is a failure of this skill, not of the schema.

1. **Quiz the core, not the trivia.** Read the source material and extract the
   ideas the author would insist a reader retain — definitions, mechanisms,
   distinctions, tradeoffs — not dates, filenames, or incidental facts.

2. **Vary the difficulty across three bands:**
   - *recall* — name the class / mechanism / definition;
   - *identification* — a short scenario, then "which class is this?";
   - *distinction* — tell two neighboring classes apart (e.g. reasoning
     degradation vs instruction drift; hallucination vs overlooked constraints).

3. **Vary the correct-count, and never reveal it.** The UI always renders
   checkboxes with "Select all that apply" — it never tells the solver how many
   are right. Use that deliberately: some questions have 1 correct, some 2, some 3.
   The uncertainty *is* the difficulty (JEE-Advanced-style). For "which classes /
   layers / signatures does X involve", prefer multi-correct — real incidents are
   combinations.

4. **Make every distractor a believable trap.** A wrong option should be a
   neighboring class, a common misconception, or a half-truth — never a
   self-evidently absurd answer. If a distractor can be eliminated without knowing
   the material, it is not earning its place.

5. **Teach in the explanation.** The explanation should say why the right answer is
   right *and* why each wrong option is wrong (or what it actually is). A solver
   who gets it wrong should learn from the review.

6. **Right-size the set.** 8–12 questions is a good quiz; fewer feels thin, more
   becomes a grind.

7. **Scoring.** If any question has more than one correct option, set
   `scoring_policy` to `partial` (`all_or_nothing` would zero any partially-correct
   multi-select). Single-correct-only sets may keep `all_or_nothing`.

## The shape

The validator (`scripts/validate.py`, via `quiz_validation.py`) mirrors
`backend/quiz_app/validation.py`, so a file that passes here cannot fail validation
on upload.

```json
{
  "topic": {"slug": "rag", "name": "RAG"},
  "subtopic": {"slug": "embeddings", "name": "Embeddings and vector space"},
  "difficulty": "medium",
  "style": "standard",
  "time_limit_minutes": 15,
  "scoring_policy": "all_or_nothing",
  "questions": [
    {"prompt": "…", "explanation": "…", "points": 1,
     "options": [{"body": "…", "correct": true}, {"body": "…", "correct": false}]}
  ]
}
```

- `topic` required — `slug` is lowercase letters/digits/hyphens, `name` non-empty.
- `subtopic` optional; omitted means a whole-topic set.
- `difficulty`: `easy` | `medium` | `hard`; `style`: `standard` (default) | `scenario`.
- `scoring_policy`: `all_or_nothing` (default) | `partial`.
- `time_limit_minutes`, `max_attempts`: positive whole number, or omit (untimed / unlimited).
- `title`, `description`: optional text.
- `shuffle_questions`, `shuffle_options`, `reveal_answers`: booleans (defaults false, false, true).
- `questions`: at least 1. Each: non-empty `prompt`, `points > 0` (default 1), at least
  2 `options`, at least 1 option with `correct: true`. `explanation` optional.

## Steps

1. Read the source material, then write the set to a `.json` file under
   `~/quiz-sets/` — scratch, never inside or committed to the quiz-app repo.
   Completion: the authoring principles above are applied (varied difficulty,
   mixed single/multi-correct with the count hidden, plausible distractors,
   teaching explanations, 8–12 questions), each question has ≥2 options and ≥1 correct.
2. Run `python3 scripts/validate.py <file>`. Completion: it prints `OK — N question(s) …`.
3. If it prints `invalid: …`, fix every listed problem and re-run until `OK`.
   Hand the clean file to the user for review.
