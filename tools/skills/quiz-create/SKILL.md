---
name: quiz-create
description: Author a quiz-set JSON for the quiz app — from prose or code material — varied difficulty, hidden multi-correct counts, plausible distractors, about one written (AI-marked) question in five, questions solvable cold by the intended audience — then self-audit, run a fresh critic pass, and validate before upload. Use when asked to create, write, or author a quiz or quiz set.
---

# quiz-create — author a quiz set, then check it

Write a quiz-set JSON, run `<scripts>/validate.py` until it prints `OK`, and hand
the file over for review. Do **not** upload — that is `quiz-upload`'s job.

The material is either **prose** (notes, papers, docs — follow the rules below)
or **code** (a repo, a folder, or one flow/sub-flow within it — follow
`CODE-MATERIAL.md` instead of the prose rules).

## Steps

1. **Get the inputs the invocation didn't give.** Ask the user once
   (`ask_user_question`, all questions together):
   - *Where should the file go?* Default `~/quiz-sets/` — scratch, outside this
     repo. If they pick a path inside the repo, confirm once before using it.
   - *Prose or code material?* Infer from the invocation (a repo URL, a
     directory of code files, "quiz this repo/flow" → code); ask only when
     unclear. Default prose.
   - *Who must be able to solve it?* Options in "The audience"; default
     `domain`.
   - *How many questions?* Default 10.
   - *How many written answers?* Do not ask: by default about one question in
     five is written (subjective, AI-marked), rounded, at least 1 — 2 in a
     10-question set, 1 in a 5-question set. Use another share, or none, only
     when the invocation asks for it.
   - *Time pressure?* Seconds per question — default 45 (range 30–45), or
     "untimed". Set `time_limit_minutes = ceil(count × seconds / 60)`.
   Skip any question the invocation already answered; if the user says "doesn't
   matter", take the defaults.
   Completion: destination, material kind, audience, count, written share, and time limit known.
2. **Read the source material.**
   - Prose: extract the ideas worth quizzing — the concepts a reader must
     retain — not the document's own examples or layout.
   - Code: trace the code and build the flow map; follow `CODE-MATERIAL.md`.
   Completion: the ideas (or the flow) to quiz are identified.
3. **Write the set** to the chosen destination, and alongside it the
   justification sidecar — `<basename>.justification.md`, one entry per question
   as in "The justification sidecar". Mix the written questions in by rule 13.
   Completion: a `.json` file exists there with the asked count and written
   share, and the sidecar has one entry per question.
4. **Self-audit — the craft gate.** Run every rule's check in "The rules"
   (prose) or `CODE-MATERIAL.md` (code) against every question; rewrite each
   violation. The validator in step 6 checks only the schema, never the craft —
   this step is where craft is enforced.
   Completion: every check passes for every question.
5. **Critic pass — a fresh pair of eyes, then revise.** Spawn a fresh subagent
   (the `subagent` tool) that has not seen this generation conversation. Give it
   the source material, the governing rules ("The rules" for prose,
   `CODE-MATERIAL.md` for code), the quiz JSON, and the justification sidecar.
   It judges each question: does its justification hold — not source-locked (or
   load-bearing, for code) and self-explanatory? For a written question it also
   checks the three things the AI evaluator depends on: the prompt bounds the
   answer (how much, and of what), the model answer alone fully answers it, and
   the key points are the model answer's essentials with nothing extra, so a
   level-4 answer is one that makes every key point ("Written questions"). It
   returns a per-question verdict (pass, or fail with a one-line reason) and
   must not edit. Rewrite
   only the failing questions and their sidecar entries, then re-run the critic.
   Stop early when a pass comes back clean; if a question is still failing after
   2 critic rounds, stop and hand that question to the user for a call — do not
   loop a third time.
   Completion: a clean critic pass, or 2 rounds run and any stragglers reported.
6. **Validate** the mechanics: `python3 <scripts>/validate.py <file>`.
   Resolve `<scripts>` as the `scripts/` directory beside this SKILL.md — in Claude Code that is `${CLAUDE_PLUGIN_ROOT}/skills/quiz-create/scripts`, never a path relative to the project you happen to be in.
   Completion: it prints `OK — N question(s), W written …` and no `warning:`
   line. If it prints `invalid: …`, fix everything listed and re-run; a
   `warning:` (a written question without key points, or written questions
   bunched at the end with shuffle off) is house style, so fix it too.
7. **Hand the file over**: report the path, the audience, the settings
   (difficulty, time limit, scoring), and how many questions are written. Done.

## The audience

Every question must be solvable **cold**: a solver who meets the audience and
has not read this source can answer from the question text alone.

- `domain` (default) — knows the topic's working concepts; the source's own
  vocabulary is private to its author and must be glossed (rule 3).
- `studied` — has studied this exact material; its vocabulary is allowed, but
  gloss option labels anyway (rule 3).
- `general` — no assumed background; prompts teach what they test.
- `drill` — the learner drilling exact recall of a codebase's structure; bare
  symbols, exact outputs, and exact lines are the point. Code only; see
  `CODE-MATERIAL.md` for the rules it swaps in.

Vocabulary is the only thing the audience widens — for prose. The source's
scaffolding (rule 1) and exact figures (rule 2) are off-limits for every prose
audience. For code under `drill`, the system's own structure is the answer key.

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
recall of the source, not a quiz of the idea. For code quizzes the first line is
reworded to *why is this hop/answer load-bearing?* — see `CODE-MATERIAL.md`.

## The rules — each rule is also its check (prose)

Prose material. For code, follow `CODE-MATERIAL.md` instead of rules 1–8;
rules 9–13 (right-size, scoring, justification, order, written mix) apply to both.

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
9. **Right-size.** The asked count (default 10; 8–12 if no count was asked),
   about one in five of them written unless the invocation set another share.
   Check: the count matches, and so does the written share.
10. **Score fair.** Every choice question is marked +2 per correct option ticked,
    −1 per wrong one, −2 for a blank question, so its worth is 2 × its correct
    options. Keep wrong options plausible, not traps that only punish. A written
    question is worth 4: the AI evaluator marks the typed answer 0–4 against its
    model answer and key points, with partial credit, and it never goes below 0
    (blank or wrong scores 0). Both count toward the score and the maximum.
    Check: no question has a wrong option that is wrong only on a technicality,
    and every written question can be marked fairly from its model answer and
    key points alone.
11. **Justify every question.** Each question has its two-line sidecar entry,
    and the "not source-locked" line is true — a question only the source's
    author could justify fails here.
    Check: every question has both lines; the first line holds.
12. **Order-free, or say so.** By default every attempt serves the questions in
    a fresh random order and shuffles the options inside each question. So
    prefer options that read correctly anywhere — no "All of the above", "None
    of the above", "Both A and B", "A and C", "the option above" — and
    explanations that name options by what they say, never "the first option"
    or "option B". Prefer questions that stand alone, never "the previous
    question" or "Question 3". If a set truly needs either, set
    `"shuffle_options": false` (position-dependent options or explanations) or
    `"shuffle_questions": false` (cross-question references) in its JSON.
    Check: every option and explanation reads correctly in any option order,
    and every question in any question order — or the matching switch is false.
13. **Sprinkle the written questions in.** With `shuffle_questions` on (the
    default), every attempt serves the questions in a fresh order, so placement
    in the file does not matter. With it off, place the written questions spread
    through the set — for 2 in 10, around positions 4 and 8 — never bunched at
    the end. Pick for them the ideas best tested by explaining (a mechanism, a
    tradeoff, a "why"), and keep the rest choice questions.
    Check: the written share holds; with shuffle off, no run of written
    questions sits at the end.

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
     "options": [{"body": "…", "correct": true}, {"body": "…", "correct": false}]},
    {"type": "subjective", "prompt": "…", "model_answer": "…",
     "key_points": ["…", "…"], "explanation": "…"}
  ]
}
```

- `topic` required — `slug` is lowercase letters/digits/hyphens, `name` non-empty.
- `subtopic` optional; omitted means a whole-topic set.
- `difficulty`: `easy` | `medium` | `hard`; `style`: `standard` (default) | `scenario`.
- `scoring_policy`: `all_or_nothing` (default) | `partial`. Accepted for older files but
  ignored: every attempt is marked +2 / −1 / −2 blank.
- `time_limit_minutes`, `max_attempts`: positive whole number, or omit (untimed / unlimited).
- `title`, `description`: optional text.
- `shuffle_questions`, `shuffle_options`, `reveal_answers`: booleans (defaults true, true, true).
  Turn a shuffle switch off only for the reason in rule 12.
- `visibility`: `public` (default: signed-out visitors can View it, signed-in solvers can take it)
  | `private` (only admins see and take it). Changeable later in the admin editor.
- `questions`: at least 1. Each has a `type`: `choice` (the default, may be omitted) or
  `subjective`.
  - **choice**: non-empty `prompt`, `points > 0` (default 1; stored but no longer weights
    marking), at least 2 `options`, at least 1 option with `correct: true`. `explanation`
    optional. No `model_answer`.
  - **subjective**: the solver types the answer into a text box (up to 10,000 characters).
    Non-empty `prompt` and a required, non-empty `model_answer`; `key_points` optional
    for the upload (1–6 short texts, each at most 300 characters) but always written by
    this skill; `explanation` optional. No `options` and no `points`: it is always worth
    4, marked 0–4 by the AI evaluator against the model answer and key points, never
    below 0. `model_answer` is Markdown, shown on results and View when `reveal_answers`
    is true; the key points are the evaluator's rubric, never shown to solvers.

### Written questions

About one question in five is written (rule 9), chosen from the ideas best tested by
having the solver explain them. The prose rules still apply to the prompt: quiz the idea,
solvable cold, a fresh scenario, no exact figure as the answer. Rules 5 and 7 (traps,
hidden correct count) are about options, so they do not apply.

The AI evaluator marks a typed answer on five levels, and the level is the mark: **4**
every essential point present and correct; **3** the main point right, one secondary point
missing or loose; **2** some essentials right, an important one missing or one real error;
**1** a correct fragment only; **0** wrong, irrelevant, contradicting the main point, or
blank. It credits correct answers in other words or by another valid route, ignores
spelling and length, and gives nothing for hedging. Write each question so that scale is
easy to apply:

- **Ask for a bounded answer.** Say how much is wanted, and of what ("In two or three
  sentences: why …, and what it costs"), so the solver, the model answer and the key
  points aim at the same size. One question, not two hidden in one.
- **The model answer is the answer a strong solver would write**, complete enough to
  mark against: every point a full answer must make, in plain prose, nothing the prompt
  did not ask for. Never a stub ("see explanation").
- **Key points: 2 to 4 of them, the model answer's essentials.** Each is one checkable
  claim in plain words ("Each model learns its own vector space"), not a keyword or a
  topic ("vector spaces"). Together they are exactly a level-4 answer: drop one and the
  answer is a 3 or a 2. No point the prompt did not ask for, no example dressed as an
  essential, no two points that say the same thing.
- **The explanation**, if any, says why that answer is right or names the common wrong
  answer; it does not repeat the model answer.
- Check: the prompt bounds the answer; the model answer alone fully answers it; the key
  points are its essentials, each one checkable, and making all of them earns 4.
