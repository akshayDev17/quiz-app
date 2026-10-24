---
name: quiz-create
description: Author a quiz-set JSON for the quiz app — varied difficulty, hidden multi-correct counts, plausible distractors, questions solvable cold by the intended audience — then self-audit, run a fresh critic pass, and validate before upload. Use when asked to create, write, or author a quiz or quiz set.
---

# quiz-create — author a quiz set, then check it

Write a quiz-set JSON, run `<scripts>/validate.py` until it prints `OK`, and hand
the file over for review. Do **not** upload — that is `quiz-upload`'s job.

## Steps

1. **Get the inputs the invocation didn't give.** Ask the user once
   (`ask_user_question`, all questions together):
   - *Where should the file go?* Default `~/quiz-sets/` — scratch, outside this
     repo. If they pick a path inside the repo, confirm once before using it.
   - *Who must be able to solve it?* Options in "The audience"; default
     `domain`.
   - *How many questions?* Default 10.
   - *Time pressure?* Seconds per question — default 45 (range 30–45), or
     "untimed". Set `time_limit_minutes = ceil(count × seconds / 60)`.
   Skip any question the invocation already answered; if the user says "doesn't
   matter", take the defaults.
   Completion: destination, audience, count, and time limit known.
2. **Read the source material.** Extract the ideas worth quizzing — the
   concepts a reader must retain — not the document's own examples or layout.
   Completion: the ideas to quiz are identified.
3. **Write the set** to the chosen destination, and alongside it the
   justification sidecar — `<basename>.justification.md`, one entry per question
   as in "The justification sidecar". Completion: a `.json` file exists there
   with the asked count, and the sidecar has one entry per question.
4. **Self-audit — the craft gate.** Run every rule's check in "The rules"
   against every question; rewrite each violation. The validator in step 6
   checks only the schema, never the craft — this step is where craft is
   enforced.
   Completion: every check passes for every question.
5. **Critic pass — a fresh pair of eyes, then revise.** Spawn a fresh subagent
   (the `subagent` tool) that has not seen this generation conversation. Give it
   the source material, "The rules", the quiz JSON, and the justification
   sidecar. It judges each question: does its justification hold — not
   source-locked and self-explanatory? It returns a per-question verdict
   (pass, or fail with a one-line reason) and must not edit. Rewrite only the
   failing questions and their sidecar entries, then re-run the critic. Stop
   early when a pass comes back clean; if a question is still failing after 2
   critic rounds, stop and hand that question to the user for a call — do not
   loop a third time.
   Completion: a clean critic pass, or 2 rounds run and any stragglers reported.
6. **Validate** the mechanics: `python3 <scripts>/validate.py <file>`.
   Resolve `<scripts>` as the `scripts/` directory beside this SKILL.md — in Claude Code that is `${CLAUDE_PLUGIN_ROOT}/skills/quiz-create/scripts`, never a path relative to the project you happen to be in.
   Completion: it prints `OK — N question(s) …`. If it prints `invalid: …`,
   fix everything listed and re-run.
7. **Hand the file over**: report the path, the audience, and the settings
   (difficulty, time limit, scoring). Done.

## The audience

Every question must be solvable **cold**: a solver who meets the audience and
has not read this source can answer from the question text alone.

- `domain` (default) — knows the topic's working concepts; the source's own
  vocabulary is private to its author and must be glossed (rule 3).
- `studied` — has studied this exact material; its vocabulary is allowed, but
  gloss option labels anyway (rule 3).
- `general` — no assumed background; prompts teach what they test.

Vocabulary is the only thing the audience widens. The source's scaffolding
(rule 1) and exact figures (rule 2) are off-limits for every audience.

## The justification sidecar

Alongside the quiz, write `<basename>.justification.md` — one entry per
question, two lines:

```markdown
## Q2 — <one-line title>
- **Not source-locked:** why the answer is derivable — no private vocabulary,
  no scaffolding, no document figure, and no recall of the source's own
  list/criterion/prescription.
- **Self-explanatory:** why the prompt gives enough to reason from, and every
  option defines what it names — no bare labels, no slogan the solver must
  already know.
```

A question whose first line cannot be written honestly fails rule 1 — it is a
recall of the source, not a quiz of the idea.

## The rules — each rule is also its check

1. **Quiz the idea, not the document.** Test definitions, mechanisms,
   distinctions, tradeoffs. Name concepts by what they mean, never by where the
   source filed them — no "class 7", "M12", section numbers. The answer must be
   derivable, not a recall of the source's own list, checklist, or criterion.
   Check: prompt and answer speak in meanings, not the source's scaffolding;
   the answer is derivable from the question, not recited from the source.
2. **Paraphrase.** A question whose only correct answer is an exact figure,
   percentage, or verbatim phrase tests recitation, not understanding. For
   "roughly 80% of failures are harness problems", quiz the claim — its
   direction, mechanism, consequence — not the number.
   Check: the correct answer is still correct reworded; no exact figure is the
   answer.
3. **Solvable cold.** Prompt and every option must be decidable from their own
   text under the audience. A concept the source names privately gets a gloss:
   "Sycophancy — the verdict flips when a preference is asserted first".
   Check: a solver meeting the audience answers from the question text alone.
4. **Fresh scenarios.** The source supplies ideas; the quiz re-instantiates
   them in scenarios of its own.
   Check: no prompt is a transcription of a source example.
5. **Traps, not giveaways.** A wrong option is a neighboring concept, a common
   misconception, or a half-truth — eliminable only by knowing the material.
   Check: eliminating any wrong option requires knowing the material.
6. **Varied difficulty.** Recall (name the class/mechanism/definition — a
   concept, never a figure), identification (scenario → "which is this?"),
   distinction (tell two neighboring concepts apart). All three bands appear.
   Check: all three bands present; recall questions name concepts only.
7. **Varied, hidden correct count.** Some questions have 1 correct, some 2,
   some 3; the prompt never reveals how many ("Select all that apply" stays
   honest). Prefer multi-correct for "which classes/layers/signatures does X
   involve" — real incidents are combinations.
   Check: counts vary across the set; no prompt tips the count.
8. **Teach in the explanation.** Why the right answer is right, and why each
   wrong option is wrong (or what it actually is).
   Check: the explanation covers the right answer and every wrong option.
9. **Right-size.** The asked count (default 10; 8–12 if no count was asked).
   Check: the count matches.
10. **Score fair.** Any multi-correct question ⇒ `scoring_policy: "partial"`
    (`all_or_nothing` zeroes a partially-correct multi-select).
    Check: multi-correct questions and `partial` agree.
11. **Justify every question.** Each question has its two-line sidecar entry,
    and the "not source-locked" line is true — a question only the source's
    author could justify fails here.
    Check: every question has both lines; the first line holds.

## The shape

The validator (`<scripts>/validate.py`, via `quiz_validation.py` at the plugin root) mirrors
`backend/quiz_app/validation.py`, so a file that passes here cannot fail
validation on upload.

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
