# quiz-create — code-material support: gap analysis and proposal

Status: **implemented** in `tools/skills/quiz-create/SKILL.md` (router + prose
path) and `tools/skills/quiz-create/CODE-MATERIAL.md` (the code/flow branch).
This document remains the design record: the ask, the gaps, and each suggestion
named alongside the problem it mitigates.

## The ask

Generate quizzes from **code**: a GitHub repo, or a folder within one, with
questions whose answers are 1–2 lines of code knowledge. Four question families
were named:

1. **Name-the-symbol** — "which tool from ADK enables the agent with tools that
   have a certain I/O boundedness?" → answer `LongRunningFunctionTool`.
2. **Snippet → output** — a 1–2 line Python snippet in the prompt, the output
   in the answer.
3. **Complete-the-code** — 2–3 contiguous lines blanked from the start, middle,
   or end of a snippet; pick the correct completion from 4–5 confusingly
   similar options.
4. **Flow** — quiz the system's control/data flow: which component handles which
   case, what happens next after a branch, who hands off to whom. Scopable to a
   single **sub-flow** (e.g. an orchestrator agent's interaction with one
   sub-agent and its tools), not only the whole system.

Stated goal: the user drills their own recall of a codebase's flows — whole or
sub-flow — until the exact calls, handoffs and outputs stick. Rote learning as
the intended, legitimate use.

## What already works (no change needed)

- **The app can carry code.** `backend/quiz_app/validation.py` requires only
  non-empty strings for prompt/option bodies; JSON strings legally contain
  newlines, so fenced code blocks pass validation today.
- **The UI renders code.** `frontend/app/play/page.tsx` renders prompts and
  option bodies through `frontend/app/components/Markdown.tsx`
  (`react-markdown` + `remark-gfm`), so ` ```python ` fences render as code.
  (No `rehype-raw`, so code blocks cannot smuggle HTML — safe.)
- **The interaction scaffold fits.** Step 1 already asks the user for save
  location and audience; a material-kind input rides the same question cheaply.

## Problems (gaps in the current instructions)

| # | Problem | Consequence if left alone |
|---|---------|---------------------------|
| P1 | No procedure for repo/folder input. Step 2 says "read the source material" and every rule speaks in document metaphors ("scaffolding", "figures"). | Agent improvises: reads the README and a few files, then produces the same failure we just fixed for notes — a quiz about the README, not about the flow. No scoping to a subtree, no size guard, no guidance on cloning/auth. |
| P2 | No code question shapes. The difficulty bands (recall / identification / distinction) are prose-shaped only. | Trace-the-output and complete-the-code have no sanctioned shape; the agent either refuses or invents one inconsistently. |
| P3 | Rule 2 (paraphrase; "no exact figure is the answer") misfires on code. It bans *recited document figures* but as written cannot tell those from *computed results* (`print(x)` → `3`) or *exact completion lines*. | A literal agent may refuse or mangle the exact-answer questions that are the entire point of the ask. |
| P4 | Rule 3 (solvable cold; gloss private vocabulary) fights bare-symbol recall. Under the default `domain` audience, `LongRunningFunctionTool` is "the source's private vocabulary" and must be glossed. | The agent hedges, glosses, or rewrites name-the-symbol questions instead of asking them bare — wrong behavior for drill. |
| P5 | No code distractor taxonomy. Rule 5 (traps, not giveaways) is stated abstractly. | The agent must invent believable code near-misses each run; most plausible inventions (sibling symbol names, wrong arg order, off-by-one) are exactly the traps wanted, but nothing guarantees them. |
| P6 | No formatting rules for code in prompts/options. | Fences omitted, language tags missing, indentation mangled by JSON escaping, snippets longer than comfortable, or blanks placed so the question is unsolvable or trivially guessable. |
| P7 | No audience band for drill. `studied` is the closest existing setting, but the skill never says exact-recall drilling is a legitimate intent where the exact symbol/output/line *is* the answer. | The rote-learning goal fights the skill's concept-first philosophy instead of being a named, first-class mode. |
| P8 | No flow representation. "What happens when X" questions need a model of the flow (components, calls, handoffs, branches); the instructions only say "read the source". | Generator and critic both hallucinate sequences: questions assert a wrong order, and the critic cannot verify the answer's sequence, so flow quizzes are unreliable end to end. |
| P9 | No sub-flow scoping. A large system (an orchestrator plus many sub-agents) cannot be quizzed whole without drowning, and there is no way to say "only the orchestrator→PeopleAgent sub-flow". | Flow questions become a whole-system grind or an arbitrary sample, neither of which tests the one flow the user actually wants. |
| P10 | Flow recall contradicts the anti-source-lock philosophy. Rules 1–3 are built to forbid exactly what flow drilling wants: recalling the system's own structure. | The agent is told to drill, then rules 1–3 tell it "derivable, not recited", so it fights itself — the flow feature needs the value system flipped explicitly. |

## Proposed changes

### S1 — Material kind: `prose` | `code`

Add a material-kind input to the step-1 question set (or infer it from the
invocation: a repo URL, a directory of code files, or explicit "quiz this code"
wording selects `code`).

- **Mitigates P1, P2** — the kind selects the navigation procedure (S2) and the
  allowed question shapes (S3), so prose runs keep today's rules untouched.

### S2 — Repo navigation procedure (step 2, `code` branch)

When the material is a repo or a folder of one:

1. Shallow-clone remote repos into a scratch directory (outside the quiz-app
   repo); use the local checkout if it exists.
2. Read the README, then the entry point, then trace the main flow(s) across
   files — the quiz targets *load-bearing calls and their contracts*, not file
   inventory.
3. Honor the user's subtree scope; when none is given, ask or default to the
   entry point's package rather than the whole repo.
4. Skip vendored code, lockfiles, generated artifacts, and tests by default
   (tests only when the user explicitly wants them quizzed).
5. Size guard: repos too large to trace in one pass → ask the user to narrow
   the folder, never silently sample.

- **Mitigates P1** — replaces improvisation with a trace-the-flow procedure and
  scoping rules.

### S3 — Code question shapes (`code` branch)

Three sanctioned shapes, each with its own constraints:

- **Trace-the-output** — a short, self-contained snippet (≤ ~15 lines) in the
  prompt; the correct option is the exact output. The snippet must be resolvable
  by reading alone (no hidden state, no stdin, no network); state the language.
- **Complete-the-code** — 2–3 contiguous lines blanked (start, middle, or end).
  The blank must be *load-bearing*: removing it must be the only thing that
  distinguishes the correct option from the others, and every wrong option must
  compile-plausible (right shape, wrong behavior).
- **Name-the-symbol** — "which tool/function/class does X" for the codebase's
  own vocabulary; options are sibling symbols from the same module/package.

- **Mitigates P2, P6** — gives each family a sanctioned shape and solvability
  rules; no per-run invention.

### S4 — Rule 2 carve-out

Amend the paraphrase rule to target *recited document figures and verbatim
prose*, and to exempt **computed results** (a snippet's output) and **drilled
symbols/lines** under the `drill` audience. The exact output or exact line is a
legitimate answer for code; a README's "~80%" is not.

- **Mitigates P3** — keeps the prose guardrail while legalizing exact code
  answers where they are the point.

### S5 — `drill` audience band

Add a fourth audience: `drill` — the solver is the learner drilling exact
recall; bare symbols, exact outputs, and exact lines are the goal, not a bug.
Gloss-pressure from rule 3 is off for this band; explanations still teach (rule
8 unchanged).

- **Mitigates P4, P7** — names the rote-learning intent as first-class instead
  of leaving it to fight `domain`/`studied` defaults.

### S6 — Code distractor taxonomy

State the near-miss families rule 5 should draw from for code:

- **Output questions:** mutation vs copy, shallow vs deep, integer vs float
  division, off-by-one, type coercion, exception vs return, empty vs singleton.
- **Completion questions:** wrong argument order, adjacent API name, missing
  `await`/`return`/`yield`, swapped variable, inverted condition, right call on
  wrong object.
- **Symbol questions:** sibling symbols in the same module, deprecated alias,
  the inverse operation.

- **Mitigates P5** — turns the abstract trap principle into the specific trap
  families code quizzes actually need.

### S7 — Formatting rules for code in prompts/options

- Fence all code in the prompt and every code-bearing option, with a language
  tag.
- Preserve indentation through JSON escaping; never re-indent to "save space".
- Keep the blank region contiguous; never blank more than ~3 lines; never put
  the deciding clue only in a comment.
- Single-correct for trace/completion questions (rule 7's hidden-count play
  stays for the multi-correct "which of these calls…" shapes).

- **Mitigates P6** — removes the mangle/unsolvable failure modes.

### S8 — Flow question shapes (a fourth family)

Flow questions test that the solver *understands and remembers* the sequence of
hops. Sub-shapes, each with its distractor family:

- **Trace-the-flow** — given an input or scenario, the sequence of components
  invoked, in order. Often multi-correct ("which of these happen, in order?").
- **Routing / attribution** — "given this user question, which agent or tool
  answers it?" Distractors: sibling agents/tools in the same routing table.
- **Next-hop / branch** — "after the intent is classified as X, what happens
  next?" Distractors: a real stage that belongs to a *different* branch.
- **Handoff** — "what does the caller pass to the sub-agent, and what comes
  back?" Distractors: the inverse handoff, or the right payload in the wrong
  direction.
- **Data-flow** — "which artefact does stage A hand to stage B?"

The trap in every case is an adjacent-but-real node in the flow — wrong only
because it is in the wrong order, the wrong branch, or a neighbouring sub-flow —
never a node that does not exist.

- **Mitigates P2, P8** — adds the shape family the prose bands cannot express.

### S9 — Flow map before questions (ground truth)

Before writing any flow question, extract an explicit **flow map**: nodes
(agents, tools, stages, endpoints), edges (calls, handoffs, data, with branch
conditions). Write it to a companion file (`<name>.flow-map.md`). Generate
questions *from the map*, and have the critic verify every answer *against the
map* — ground truth lives in the map, not in the generator's memory.

- **Mitigates P8** — a shared ground truth kills sequence hallucination in both
  generation and evaluation, and doubles as the user's study aid.

### S10 — Sub-flow scoping

Ask (or infer) the scope as a named entry point: a sub-agent, an endpoint, an
action, or "the flow that serves X". Trace from that entry down to its leaves;
questions stay inside the boundary, and options that cross it — nodes that
belong to a *different* sub-flow — are the natural distractors.

Worked example (ADK): scope = the orchestrator→PeopleAgent sub-flow. The map
starts at the orchestrator's intent branch that routes employee-detail
questions, follows the handoff to PeopleAgent, its tools (`get_employee`,
`update_employee`, …), and the workflows those serve. Questions: "which tool
answers 'update Priya's title'?", "after PeopleAgent returns, what does the
orchestrator do next?", "which of these does *not* belong to this sub-flow (it
belongs to OrdersAgent)?".

- **Mitigates P9** — makes the quiz target one flow instead of the whole system.

### S11 — Drill-mode philosophy flip (flow)

For flow quizzes under the `drill` audience the value system inverts: the
system's own structure *is* the answer key, so "source-locked" is not a defect.
Rules 1–3's test ("derivable, not recited") is replaced by **load-bearing, not
incidental**: quiz the hops, handoffs and branches a solver must know to reason
about the system — never filenames, constants, or line counts. The sidecar's
"not source-locked" line is reworded for flow to *why is this hop load-bearing?*

- **Mitigates P10** — removes the self-contradiction so the agent can drill
  without rules 1–3 fighting the flow feature.

## Mapping: suggestion → problem

| Suggestion | Mitigates |
|------------|-----------|
| S1 material kind `prose`/`code` | P1, P2 |
| S2 repo navigation procedure | P1 |
| S3 code question shapes | P2, P6 |
| S4 rule 2 carve-out | P3 |
| S5 `drill` audience band | P4, P7 |
| S6 code distractor taxonomy | P5 |
| S7 formatting rules | P6 |
| S8 flow question shapes | P2, P8 |
| S9 flow-map artifact | P8 |
| S10 sub-flow scoping | P9 |
| S11 drill-mode philosophy flip | P10 |

## Open decisions

1. **Material kind: ask or infer?** Asking adds a third question to step 1;
   inferring from invocation wording ("quiz this repo", a `.py`/`.ts` directory)
   is cheaper but occasionally wrong. Suggest: infer, and let the step-1 ask
   confirm when uncertain.
2. **`drill` as audience vs a separate knob.** `drill` is about intent, not
   prior knowledge, so it sits oddly next to `domain`/`studied`/`general`.
   Alternative: keep three audiences and add `intent: assess | drill`. Suggest
   the two-knob form for honesty, `drill` band for simplicity.
3. **Schema `style`.** The app schema has `style: standard | scenario`. Code
   quizzes would be stored as `standard` — acceptable, but if the UI ever wants
   to render code quizzes differently, a backend enum change is a separate,
   schema-level decision this skill cannot make alone.
4. **Where the code taxonomy lives.** S3/S6/S7 are reference, not steps; keep
   them in-file under a "Code material" section or disclose to a sibling file
   loaded only on the `code` branch (progressive disclosure, per
   `writing-for-agents`).
5. **Sub-flow scope UX.** How does the user name the sub-flow — an entry symbol
   ("quiz PeopleAgent"), a natural-language action ("the flow that updates
   employee details"), or a pick from the rendered flow map? Suggest: accept
   any; if ambiguous, render the flow map and ask them to pick the entry node.
6. **Flow-map artifact location.** Separate file (`<name>.flow-map.md`) vs a
   section of the justification sidecar. Suggest: separate — it is ground truth
   for generation *and* the critic, and it is independently useful to the user
   as a study aid while drilling the flow.

## Verification evidence (this document's claims)

- `backend/quiz_app/validation.py` — option bodies checked only for non-empty
  strings (no length caps; newlines legal).
- `frontend/app/play/page.tsx` (lines ~329–348) — prompt and option bodies
  rendered through `Markdown`.
- `frontend/app/components/Markdown.tsx` — `react-markdown` + `remark-gfm`, no
  `rehype-raw`.
- `tools/skills/quiz-create/SKILL.md` — rules 2, 3, 5 and the audience bands
  referenced above.
