# CODE-MATERIAL — quiz code, not just its README

Follow this instead of SKILL.md's prose rules when the material is **code**: a
repo, a folder, or one flow/sub-flow within it. SKILL.md's steps, the
justification sidecar, and rules 9–10 (right-size, scoring) still apply; this
file replaces rules 1–8 and the sidecar's "not source-locked" line.

## Navigate the code

1. **Get the code.** Shallow-clone remote repos into a scratch directory
   (outside the quiz-app repo); use the local checkout if it exists.
2. **Find the flow.** Read the README, then the entry point, then trace the
   main flow(s) across files. The quiz targets load-bearing calls, handoffs and
   branches, not file inventory.
3. **Honor the scope.** The user may scope to a sub-flow — a sub-agent, an
   endpoint, an action, or "the flow that serves X". Trace from that entry down
   to its leaves; questions stay inside the boundary. If the scope is
   ambiguous, render the flow map (below) and ask the user to pick the entry
   node.
4. **Skip noise.** Vendored code, lockfiles, generated artifacts, and tests —
   unless the user explicitly wants them.
5. **Size guard.** Too large to trace in one pass → ask the user to narrow,
   never silently sample.

## Build the flow map first (ground truth)

Before writing any flow question, write an explicit **flow map** to
`<name>.flow-map.md`: nodes (agents, tools, stages, endpoints), edges (calls,
handoffs, data, with branch conditions). Generate questions *from the map*; the
critic verifies every answer *against the map*. Ground truth lives in the map,
not in memory. The map doubles as the user's study aid.

## Question shapes

- **Trace-the-flow** — given an input or scenario, the sequence of components
  invoked, in order. Often multi-correct ("which of these happen, in order?").
- **Routing / attribution** — "given this user question, which agent or tool
  answers it?"
- **Next-hop / branch** — "after the intent is classified as X, what happens
  next?"
- **Handoff** — "what does the caller pass to the sub-agent, and what comes
  back?"
- **Data-flow** — "which artefact does stage A hand to stage B?"
- **Name-the-symbol** — "which tool/function/class does X" for the codebase's
  own vocabulary.
- **Trace-the-output** — a short, self-contained snippet (≤ ~15 lines) in the
  prompt; the correct option is the exact output. Resolvable by reading alone
  (no hidden state, no stdin, no network); state the language.
- **Complete-the-code** — 2–3 contiguous lines blanked (start, middle, or end).
  The blank must be load-bearing: removing it must be the only thing that
  distinguishes the correct option from the rest, and every wrong option must
  be compile-plausible (right shape, wrong behavior).

## Distractors (the trap, every time)

Draw every wrong option from an adjacent-but-real node or near-miss:

- **Flow:** a node that exists but is in the wrong order, the wrong branch, or
  a neighbouring sub-flow — never a node that does not exist.
- **Routing:** a sibling agent/tool in the same routing table.
- **Output:** mutation vs copy, shallow vs deep, integer vs float division,
  off-by-one, type coercion, exception vs return, empty vs singleton.
- **Completion:** wrong argument order, adjacent API name, missing
  `await`/`return`/`yield`, swapped variable, inverted condition, right call on
  the wrong object.
- **Symbol:** sibling symbol in the same module, deprecated alias, the inverse
  operation.

## The rule swap (drill)

For code under the `drill` audience, the prose rules' "derivable, not recited"
test is replaced by **load-bearing, not incidental**: quiz the hops, handoffs
and branches a solver must know to reason about the system — never filenames,
constants, or line counts. Under `domain`/`studied`, keep the glossing habit
(gloss any symbol you use) but exact outputs and exact lines remain legal — the
exact answer is the point of code, not a recited document figure.

## Formatting

- Fence all code in the prompt and every code-bearing option, with a language
  tag.
- Preserve indentation through JSON escaping; never re-indent to "save space".
- Keep the blank region contiguous; never blank more than ~3 lines; never put
  the deciding clue only in a comment.
- Single-correct for trace/completion questions; multi-correct for "which of
  these happen, in order?" and "which stages are involved".

## Justification sidecar (code reword)

The two lines stay; the first is reworded:

```markdown
## Q3 — <one-line title>
- **Load-bearing:** why this hop/handoff/branch/answer is something the solver
  must know to reason about the system — not a filename, constant, or line count.
- **Self-explanatory:** why the prompt gives enough to reason from, and every
  option defines what it names.
```
