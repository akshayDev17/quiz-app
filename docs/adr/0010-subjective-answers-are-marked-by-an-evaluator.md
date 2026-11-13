# 10. Subjective answers are marked by an AI evaluator, out of 4 and never below 0

Status: Accepted
Date: 2026-11-13

## Context

Subjective (written) questions were stored and shown but never marked: no points, nothing
in the score or the maximum. The owner asked for them to be evaluated by a model, scored,
and counted, with three fixed rules: a written answer never carries negative marking (the
minimum is 0, a blank answer scores 0, a wrong answer scores 0); the marks a question is
worth and what answer quality earns what are for the builder to decide; and the model
call goes through a provider the owner chooses, with the key kept out of GitHub, the
repo, logs and the browser, and spend held to small monthly budgets.

The owner later added that, as the sole admin, they choose the provider and model (Anthropic
API, Amazon Bedrock, Azure AI Foundry, or another later), may use several, and see each with
its remaining budget, and that none of this is visible to ordinary solvers.

## Decision

### The grading scheme

**Marks.** Every subjective question is worth **4 marks** (`models.SUBJECTIVE_MARKS`), the
same for every question, frozen onto each attempt at start (`attempts.subjective_marks`)
the way its scoring policy is (ADR 0005). Not per question: objective marking already
ignores per-question weights (`NegativeMarking` awards 2 per correct option whatever
`points` says), the owner delegated the number rather than asking authors to pick one each
time, and a fixed scale keeps the rubric identical for every question. Four is the worth
of a typical two-correct-option choice question (2 × 2), so a written answer counts like
one choice question, not several: an evaluator's judgment carries more error than an
answer key, and weighting it more would amplify that error in the total.

**Rubric.** The evaluator places an answer on one of five levels against the question's
model answer, and its key points when the author wrote them (`key_points`, optional, 1–6
short essential points per question; without them the essentials come from the model
answer). The level is the mark: the award is `level × 4 / 4`.

| Level | Marks | Meaning |
|---|---|---|
| 4 | 4 | Correct and complete: every essential point present and correct; nothing wrong that matters. |
| 3 | 3 | Mostly correct: the main point right, nearly all essentials present; one secondary point missing or imprecise; no substantive error. |
| 2 | 2 | Partly correct: some essentials right, but an important one missing, or right points beside one substantive error. |
| 1 | 1 | Minimal: a relevant, correct fragment only; the main point missing or wrong. |
| 0 | 0 | No credit: wrong, irrelevant, contradicting the main point, restating the question, "I don't know", or only instructions. |

Rules the evaluator applies: content only (spelling, style and length earn and cost
nothing unless they obscure the meaning; a short complete answer earns 4); a correct answer
in other words, order or line of reasoning gets full credit; hedging earns nothing (only
what the answer commits to counts, and a self-contradiction on an essential point is an
error); a wrong claim about an essential point voids that point; a claim contradicting the
main point caps the answer at 1. The full prompt, with a three-answer calibration example,
is `rubric.SYSTEM_PROMPT` (version `rubric-v1`, recorded on every call).

**Five levels, not a finer scale.** Model graders agree with themselves, and with people,
far more on a few anchored levels than on a 0–10 or percentage scale; partial credit still
has three steps between nothing and full marks.

**Never negative.** A blank answer is recorded as 0 with no model call. A wrong one is
level 0. A level outside 0–4 in a reply is rejected, never clamped into range, so a
manipulated reply can never beat a wrong answer; the award is computed by the server from
the level and clamped to `[0, max]` as a last guard; the database refuses an award below 0,
above the maximum, or non-zero on any answer not marked.

### How it joins the attempt's result

- **Objective marks are untouched.** The grader still sees only choice questions; every
  choice award, and the choice part of every score, is exactly what it was.
- **Score** = the choice score (+2 / −1 / −2 as before) + the sum of the written awards.
- **Maximum** = the choice maximum + 4 × the number of subjective questions, fixed when the
  attempt closes, blank or not, like a blank choice question still counts in the maximum.
- Each written answer of a closed attempt is one of:

| State | Counts | When |
|---|---|---|
| `blank` | 0, final | nothing was typed |
| `awaiting` | nothing yet; the score is provisional | typed, not yet marked |
| `marked` | the level's marks, with feedback | the evaluator gave a valid verdict |
| `flagged` | 0, final, flagged for review | the model answered but its reply was unusable: invalid JSON, a bad or missing verdict, a refusal, a cut-off reply, or an answer too large to ever fit a call |

- **Awaiting is not 0.** When nothing can evaluate the answer (no evaluator configured, no
  provider secret, every budget spent, a daily quota reached) or the provider fails, the
  answer waits, adding nothing; results and history say the score is provisional, and the
  mark is added when it is evaluated. A failure of ours never costs the solver marks.
- **Flagged is 0 and counts.** If an unusable reply were left out of the maximum instead, an
  answer that breaks the evaluator (for example by prompt injection) would beat an honest
  wrong one. Scoring it 0 makes breaking the evaluator never better than answering badly.
  A manual review tool for flagged answers is future work; the admin page shows the count.

### When it runs, and only then

The model is called only from `POST /attempts/{id}/submit` (and the admin re-run). Closing
an attempt, by submit or by a read that finds it past its deadline, writes its written
answers as `blank` or `awaiting` in the same transaction; submit then claims the awaiting
ones (an atomic stamp, so concurrent submits never send an answer twice), sends **all of an
attempt's answers in one call** (up to 20 answers and 120,000 characters; the rest wait for
the next call), and stores each verdict. Results, history, reloads and every other read only
read what is stored. An attempt closed by a read is evaluated by its next submit (the play
page always submits after the buzzer) or by an admin re-run. Nothing is retried
automatically; a claim whose request was cut off is taken over only by an admin re-run after
10 minutes.

### Who evaluates, and within what budget

One port, `Evaluator.evaluate(request, model) -> EvaluatorReply` (as identity is, ADR
0002), with `FakeEvaluator` for tests and local runs. The Anthropic API, Claude in Amazon
Bedrock (`bedrock-mantle`) and Claude in Microsoft Foundry all take the same Messages API
body, so one adapter (`MessagesApiEvaluator`) serves all three; only the URL and the key
header differ. A provider is usable when its Worker secrets are present: `ANTHROPIC_API_KEY`;
`BEDROCK_API_KEY` + `BEDROCK_REGION`; `AZURE_FOUNDRY_API_KEY` + `AZURE_FOUNDRY_ENDPOINT`.

The admin keeps an ordered list of provider · model entries, each with a monthly budget
and per-token prices (prefilled from published prices). A call goes to the first entry, in
order, whose provider is usable and whose budget has room for the call's conservative
estimate; that estimate is reserved in the app's own ledger (`evaluation_calls`) atomically
with the daily quotas, and settled to the real token cost afterwards. Remaining budget is
the budget minus this UTC month's ledger spend: the app's tracking, not the provider's
bill, which stays the hard backstop through a provider-side spend limit. Daily quotas
(defaults 20 evaluations per person and 300 site-wide, `EVAL_USER_DAILY_LIMIT` and
`EVAL_GLOBAL_DAILY_LIMIT`) bound what solvers can trigger; admins are exempt from the
per-person one, and admin re-runs from both, never from a budget.

Everything about providers, models, budgets, prices and spend is admin-only, on every
route; a solver's results say an answer was AI-marked and show its marks and feedback.

### Prompt injection

The student's answer is data. It is fenced in a tag named with a fresh random nonce per
call, which the student never sees and so cannot close; the instructions say anything
inside the fence that addresses the examiner is ignored; the reply's schema allows only
this call's item ids and the levels 0–4; and the server validates each verdict on its own,
whatever the provider promised. The feedback shown is plain text, capped at 300 characters.

### Sets that hide their answers

When a set keeps its answers hidden, the feedback must not give them away. The prompt says
so, and that is not enough on its own. In the real test call, Claude Haiku 5.5 followed the
letter of "describe a gap only in general terms" but still wrote "you do not address the
link between the dot product and cosine similarity" for an answer that mentioned neither.
So the server checks as well. A *hidden term* is a word of the model answer or key points
that neither the question nor the student's answer uses (words count as the same when one's
first five letters start the other). Below level 4, every feedback sentence that uses a
hidden term is dropped. If no sentence is left, the solver reads a plain line saying the set
keeps its answers hidden. The check can only remove feedback detail, never change a mark.

## Consequences

- A set's maximum now includes its written questions, so an attempt's percentage moves
  for sets that have them. Old attempts never move: one started before this change has
  `subjective_marks` NULL, its written answers stay outside its score and maximum, and its
  results read "Not marked" as before. Sets without subjective questions are unaffected.
- Existing subjective questions are marked on their next attempts against their model
  answer alone until an author adds key points.
- Submit waits for the evaluator before the results page opens: one call, about 1.2 s
  per typed answer as measured on Claude Haiku 5.5 (10.8 s for 9), with a limit of 15 s
  plus 2.5 s per answer (65 s at the 20-answer cap). A provider outage costs latency, not
  marks.
- With no evaluator configured, every typed answer waits. Configure one, then re-run.
- The adapter speaks raw HTTP through the Workers runtime's `fetch`, not the Anthropic SDK:
  the Worker has no runtime dependencies today, the SDK's stack (httpx, pydantic, jiter) is
  unproven on Python Workers, and the same small adapter serves three providers through an
  injected transport that the tests replace.

## Alternatives considered

- **Marks set per question in the set JSON** — more flexible, but hands the owner's
  delegated decision back to every author, and invites weights the objective side ignores.
- **A 0–10 or percentage score from the model** — finer-looking, less reliable.
- **Leaving failed evaluations out of the maximum** — rewards breaking the evaluator.
- **Evaluating whenever an attempt closes, including on reads** — a history page could then
  wait on several model calls; reads must never spend.
- **Evaluating after the response (`ctx.waitUntil`)** — a faster submit, but the results page
  would then have to poll; kept synchronous for now.
