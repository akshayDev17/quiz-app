---
name: quiz-create
description: Author a quiz-set JSON for the quiz app and validate it before upload. Use when asked to create, write, or author a quiz or quiz set.
---

# quiz-create — author a quiz set, then check it

Write a quiz-set JSON in the import shape, then run `scripts/validate.py` so the
file is clean before it goes anywhere near the server. Do **not** upload — that is
`quiz-upload`'s job.

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

1. Write the set to a `.json` file under `~/quiz-sets/` — scratch, never inside
   or committed to the quiz-app repo. Completion: every field is present or
   deliberately omitted, each question has ≥2 options and ≥1 correct.
2. Run `python3 scripts/validate.py <file>`. Completion: it prints `OK — N question(s) …`.
3. If it prints `invalid: …`, fix every listed problem and re-run until `OK`.
   Hand the clean file to the user for review.
