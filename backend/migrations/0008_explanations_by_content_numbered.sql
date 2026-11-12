-- 0008 — name options by content in sets 12 and 34, then shuffle their options again.
--
-- 0007 turned option shuffle off for set 12 and set 34 because their explanations number
-- their options ("Option 2 inverts the two; option 3 is wrong ..."); with options shuffled
-- those numbers would point at the wrong option. This rewrites each such explanation (25 in
-- set 12, 2 in set 34) to name the option by its content instead, keeping the rest of the text
-- as it was, then turns option shuffle back on for those two sets. It also rewrites one
-- sentence in set 19, which already shuffles its options ("the second distractor").
--
-- Each rewrite is keyed by question id and set id and guarded by the exact current text, so
-- on any other database, or if an author has since edited the text, it changes nothing.
-- Each switch applies only where that set's rewrites landed (a new text is present) and none
-- of the replaced numbered phrases is left in any of the set's explanations (instr() is
-- case-sensitive).
--
-- Only questions.explanation and quiz_sets.shuffle_options change. Past attempts keep their
-- papers (attempt_questions.explanation) as they were served.

-- Set 12 "RAG · Grounding and Citations (M12)": 25 explanations.

-- Q2
UPDATE questions SET explanation =
  'Attribution only asks whether a source exists that the claim points at — and here the source really exists, so attribution held. Faithfulness asks whether that source entails the claim — it does not, so faithfulness failed. The ''faithfulness held, but attribution failed'' option inverts the two; the ''both failed'' option is wrong because attribution genuinely held; the retrieval-latency option is a red herring, since latency is unrelated to whether the cited source supports the answer.'
WHERE id = 360 AND set_id = 12 AND explanation =
  'Attribution only asks whether a source exists that the claim points at — and here the source really exists, so attribution held. Faithfulness asks whether that source entails the claim — it does not, so faithfulness failed. Option 2 inverts the two; option 3 is wrong because attribution genuinely held; option 4 is a red herring, since latency is unrelated to whether the cited source supports the answer.';

-- Q4
UPDATE questions SET explanation =
  'Attributability-to-identified-sources is about the relationship between a statement and the source it points at, and is silent on whether that source (or the statement) is actually correct. The ''measures truth about the world'' option states the opposite; the ''only when the cited source is already verified correct'' option is wrong because the framework is precisely used when source correctness is not assumed; the ''cannot be applied to any real system'' option is false — it is a practical, widely used framing.'
WHERE id = 362 AND set_id = 12 AND explanation =
  'Attributability-to-identified-sources is about the relationship between a statement and the source it points at, and is silent on whether that source (or the statement) is actually correct. Option 2 states the opposite; option 3 is wrong because the framework is precisely used when source correctness is not assumed; option 4 is false — it is a practical, widely used framing.';

-- Q5
UPDATE questions SET explanation =
  'Citing everything trivially maximizes recall (every claim carries a citation) while precision collapses because most attached citations do not actually support the claim they sit next to. The ''precision improved'' option mistakes quantity for support; the ''recall collapsed'' option has the direction of recall backwards; the ''both improved together'' option describes the opposite of what happens.'
WHERE id = 363 AND set_id = 12 AND explanation =
  'Citing everything trivially maximizes recall (every claim carries a citation) while precision collapses because most attached citations do not actually support the claim they sit next to. Option 2 mistakes quantity for support; option 3 has the direction of recall backwards; option 4 describes the opposite of what happens.';

-- Q6
UPDATE questions SET explanation =
  'Precision is the fraction of emitted citations that actually support their claim (irrelevant citations lower it); recall is the fraction of supportable claims that carry any citation (uncited load-bearing claims lower it). The ''citation recall; citation precision'' option swaps them; the ''citation precision; citation precision'' and ''citation recall; citation recall'' options collapse the two distinct metrics into one.'
WHERE id = 364 AND set_id = 12 AND explanation =
  'Precision is the fraction of emitted citations that actually support their claim (irrelevant citations lower it); recall is the fraction of supportable claims that carry any citation (uncited load-bearing claims lower it). Option 2 swaps them; options 3 and 4 collapse the two distinct metrics into one.';

-- Q8
UPDATE questions SET explanation =
  'Finer citations make a claim checkable at a glance (higher verifiability) but cost more: document-level citations cost almost nothing, while per-claim attribution requires an extraction step and one attribution call per claim. The ''cost stays flat'' and ''verifiability falls'' options get the cost or the direction wrong; the ''verifiability is unchanged'' option wrongly claims verifiability does not improve.'
WHERE id = 366 AND set_id = 12 AND explanation =
  'Finer citations make a claim checkable at a glance (higher verifiability) but cost more: document-level citations cost almost nothing, while per-claim attribution requires an extraction step and one attribution call per claim. Options 2 and 3 get the cost or the direction wrong; option 4 wrongly claims verifiability does not improve.';

-- Q9
UPDATE questions SET explanation =
  'Recall bought by lowering the bar is not real recall: when citations always exist but rarely help, readers stop trusting them, and even the correct ones lose value. The ''trust rises'' option assumes help where there is none; the ''recall is the only number that matters'' option ignores precision entirely; the ''still strictly better than no citation'' option is the trap this module warns against — a citation that points at a whole document rarely lets anyone verify a claim.'
WHERE id = 367 AND set_id = 12 AND explanation =
  'Recall bought by lowering the bar is not real recall: when citations always exist but rarely help, readers stop trusting them, and even the correct ones lose value. Option 2 assumes help where there is none; option 3 ignores precision entirely; option 4 is the trap this module warns against — a citation that points at a whole document rarely lets anyone verify a claim.';

-- Q10
UPDATE questions SET explanation =
  'Granularity is capped by the index: the engine re-splits existing nodes, so it can only produce smaller (finer) citation nodes, and a requested size larger than the original chunk has no effect. The ''arbitrarily coarse or fine'' option ignores the cap; the ''only coarser, never finer'' option inverts the direction; the ''no effect on citation size'' option is wrong because the parameter does change node size, just only in the finer direction.'
WHERE id = 368 AND set_id = 12 AND explanation =
  'Granularity is capped by the index: the engine re-splits existing nodes, so it can only produce smaller (finer) citation nodes, and a requested size larger than the original chunk has no effect. Option 2 ignores the cap; option 3 inverts the direction; option 4 is wrong because the parameter does change node size, just only in the finer direction.';

-- Q12
UPDATE questions SET explanation =
  'If removing the cited node changes nothing, the claim never depended on that node — it came from the model''s weights (parametric memory), so the citation only decorates it. Retrieval and formatting both worked fine; the ''citation formatting is broken'' option confuses a generation problem with a formatting problem, and the ''definitely correct because it was stable'' option mistakes stability for correctness.'
WHERE id = 370 AND set_id = 12 AND explanation =
  'If removing the cited node changes nothing, the claim never depended on that node — it came from the model''s weights (parametric memory), so the citation only decorates it. Retrieval and formatting both worked fine; option 3 confuses a generation problem with a formatting problem, and option 4 mistakes stability for correctness.';

-- Q13
UPDATE questions SET explanation =
  '"If any" means the output space explicitly includes "no supporting part," which is precisely the diagnosis a citation cannot express. The ''single most supportive span'' and ''guaranteed to find at least one supporting span'' options assume a supporting span always exists; the ''cannot tell a grounded statement from a fabricated one'' option is wrong because distinguishing grounded from misinterpreted from fabricated is exactly what the method is designed to do.'
WHERE id = 371 AND set_id = 12 AND explanation =
  '"If any" means the output space explicitly includes "no supporting part," which is precisely the diagnosis a citation cannot express. Options 2 and 3 assume a supporting span always exists; option 4 is wrong because distinguishing grounded from misinterpreted from fabricated is exactly what the method is designed to do.';

-- Q14
UPDATE questions SET explanation =
  'Ablation removes the cited node and checks whether the answer still reproduces; perturbation edits the cited span and checks whether the answer tracks the edit. The option calling span editing ablation and node removal perturbation swaps the names; the ''both are forms of ablation'' option collapses two distinct instruments; the ''trustworthy LLM judge'' option is wrong because both produce a diff (changed vs unchanged), not a judge''s score.'
WHERE id = 372 AND set_id = 12 AND explanation =
  'Ablation removes the cited node and checks whether the answer still reproduces; perturbation edits the cited span and checks whether the answer tracks the edit. Option 2 swaps the names; option 3 collapses two distinct instruments; option 4 is wrong because both produce a diff (changed vs unchanged), not a judge''s score.';

-- Q15
UPDATE questions SET explanation =
  'Each test produces a diff (unchanged vs changed answer), which is interpretable without trusting a judge''s score. The ''no model calls at all'' option is false — both re-run generation; the ''only the retrieval stage'' option is false — they exercise generation on purpose; the ''numeric confidence value'' option is false — the whole point is that a diff is not a numeric score.'
WHERE id = 373 AND set_id = 12 AND explanation =
  'Each test produces a diff (unchanged vs changed answer), which is interpretable without trusting a judge''s score. Option 2 is false — both re-run generation; option 3 is false — they exercise generation on purpose; option 4 is false — the whole point is that a diff is not a numeric score.';

-- Q16
UPDATE questions SET explanation =
  'If most sentences really are supported, a claim- or answer-level score looks mostly faithful, and a single wrong number in one clause disappears into the average; word-level annotation localizes it. The ''every word into a separate citation'' option misreads annotation as citation; the ''claim-level scores are always more precise'' option inverts the precision claim; the ''ignore the citation entirely'' option is wrong — the evaluator still checks citations, just at finer granularity.'
WHERE id = 374 AND set_id = 12 AND explanation =
  'If most sentences really are supported, a claim- or answer-level score looks mostly faithful, and a single wrong number in one clause disappears into the average; word-level annotation localizes it. Option 2 misreads annotation as citation; option 3 inverts the precision claim; option 4 is wrong — the evaluator still checks citations, just at finer granularity.';

-- Q19
UPDATE questions SET explanation =
  'A formatting bug lives in the response synthesizer and is fixed by changing how citations are rendered. Parametric recall is a property of the model''s weights — the claim was never in the context — so it cannot be formatted away; it can only be detected (e.g., by ablation). The ''same formatting change'' option collapses two different fixes; the ''parametric recall is fixed by formatting'' option inverts the pair; the ''neither can ever be detected'' option wrongly claims detection is impossible.'
WHERE id = 377 AND set_id = 12 AND explanation =
  'A formatting bug lives in the response synthesizer and is fixed by changing how citations are rendered. Parametric recall is a property of the model''s weights — the claim was never in the context — so it cannot be formatted away; it can only be detected (e.g., by ablation). Option 2 collapses two different fixes; option 3 inverts the pair; option 4 wrongly claims detection is impossible.';

-- Q21
UPDATE questions SET explanation =
  'If the displayed text and the fed text are produced by different templates, the reader and the model look at different material, so the reader cannot verify what the model actually used. The ''fewer tokens, improving latency'' and ''more precise'' options are non-sequiturs — the template adds content rather than removing it, and precision is unaffected; the ''no consequence'' option ignores the mismatch entirely.'
WHERE id = 379 AND set_id = 12 AND explanation =
  'If the displayed text and the fed text are produced by different templates, the reader and the model look at different material, so the reader cannot verify what the model actually used. Options 2 and 3 are non-sequiturs — the template adds content rather than removing it, and precision is unaffected; option 4 ignores the mismatch entirely.';

-- Q23
UPDATE questions SET explanation =
  'The two audiences (embedder and generator) can be decoupled: a key can be excluded from the model''s view while remaining available to the embedder. Deleting it throws away the embedding benefit; including it for the LLM and excluding it from embeddings inverts the case in the scenario; the ''no mechanism'' option is false — decoupling is exactly what the metadata modes provide.'
WHERE id = 381 AND set_id = 12 AND explanation =
  'The two audiences (embedder and generator) can be decoupled: a key can be excluded from the model''s view while remaining available to the embedder. Deleting it throws away the embedding benefit; option 3 inverts the case in the scenario; option 4 is false — decoupling is exactly what the metadata modes provide.';

-- Q26
UPDATE questions SET explanation =
  'The design treats abstention as a legitimate, logged success (a bounded cost: the user re-checks the source) and forbids the ungrounded-answer state entirely. The ''error path to be driven to zero'' option demotes abstention to an error; the ''acceptable as long as they are fast'' option is the exact failure the design prevents; the ''same thing'' option conflates two outcomes with opposite costs.'
WHERE id = 384 AND set_id = 12 AND explanation =
  'The design treats abstention as a legitimate, logged success (a bounded cost: the user re-checks the source) and forbids the ungrounded-answer state entirely. Option 2 demotes abstention to an error; option 3 is the exact failure the design prevents; option 4 conflates two outcomes with opposite costs.';

-- Q29
UPDATE questions SET explanation =
  'An abstention costs the user a second look — bounded. An ungrounded answer can become a compliance incident — unbounded. Trading abstentions for answers therefore trades a bounded cost for an unbounded one. The ''no downside'', ''no effect on correctness'' and ''only latency'' options all deny this asymmetry, which is the entire reason the acceptance threshold is calibrated on the ungrounded rate rather than on coverage.'
WHERE id = 387 AND set_id = 12 AND explanation =
  'An abstention costs the user a second look — bounded. An ungrounded answer can become a compliance incident — unbounded. Trading abstentions for answers therefore trades a bounded cost for an unbounded one. Options 2–4 all deny this asymmetry, which is the entire reason the acceptance threshold is calibrated on the ungrounded rate rather than on coverage.';

-- Q31
UPDATE questions SET explanation =
  'Showing a source only proves the answer when the source actually entails the claim; attaching a real, relevant source to an unsupported answer is exactly the conflation. The empty-answer option is an abstention-like outcome, the option citing a source that does not exist is a broken attribution (nonexistent source), and the option citing a fully supporting source is the correct behavior — none illustrate the conflation.'
WHERE id = 389 AND set_id = 12 AND explanation =
  'Showing a source only proves the answer when the source actually entails the claim; attaching a real, relevant source to an unsupported answer is exactly the conflation. Option 2 is an abstention-like outcome, option 3 is a broken attribution (nonexistent source), and option 4 is the correct behavior — none illustrate the conflation.';

-- Q32
UPDATE questions SET explanation =
  'A citation converts a quality bug the user would catch into a compliance incident nobody catches, because the citation signals verification. The ''minor UX issue'' and ''fluent answer is necessarily correct'' options deny the severity or assume fluency implies correctness; the ''purely an embedding problem'' option misattributes a generation/grounding problem to the embedding stage.'
WHERE id = 390 AND set_id = 12 AND explanation =
  'A citation converts a quality bug the user would catch into a compliance incident nobody catches, because the citation signals verification. Options 2 and 4 deny the severity or assume fluency implies correctness; option 3 misattributes a generation/grounding problem to the embedding stage.';

-- Q33
UPDATE questions SET explanation =
  'Attribution establishes a relationship between answer and source, not between answer and reality; a source can be wrong or outdated. The ''it is stronger'' and ''identical in strength'' options overstate or equate the guarantees; the ''correctness is weaker'' option is false because correctness is the stronger, harder-to-establish claim.'
WHERE id = 391 AND set_id = 12 AND explanation =
  'Attribution establishes a relationship between answer and source, not between answer and reality; a source can be wrong or outdated. Options 2 and 3 overstate or equate the guarantees; option 4 is false because correctness is the stronger, harder-to-establish claim.';

-- Q34
UPDATE questions SET explanation =
  'The engine re-splits retrieved nodes into smaller citation nodes at query time, so finer citations are a parameter change, not a re-index. The ''only after a full re-index'' option misses that no re-index is needed; the ''coarser citations only'' option inverts the direction; the ''only in ranking'' option ignores the mechanism entirely.'
WHERE id = 392 AND set_id = 12 AND explanation =
  'The engine re-splits retrieved nodes into smaller citation nodes at query time, so finer citations are a parameter change, not a re-index. Option 2 misses that no re-index is needed; option 3 inverts the direction; option 4 ignores the mechanism entirely.';

-- Q38
UPDATE questions SET explanation =
  'An uncited answer carries no evidence of support, so downstream no one can tell it from a hallucination — which is why it is a failure, not formatting. The ''formatting issues are always trivial'' option is a non-sequitur; the ''improve embedding quality'' option confuses citations with embedding; the ''always hallucinates without citations'' option overstates — citations do not cause or prevent hallucination.'
WHERE id = 396 AND set_id = 12 AND explanation =
  'An uncited answer carries no evidence of support, so downstream no one can tell it from a hallucination — which is why it is a failure, not formatting. Option 2 is a non-sequitur; option 3 confuses citations with embedding; option 4 overstates — citations do not cause or prevent hallucination.';

-- Q39
UPDATE questions SET explanation =
  'If the answer does not change when the span changes, the answer was not derived from the span — it came from parametric memory. The ''faithfully follows the span'' and ''correctly supporting the answer'' options claim the opposite of the observed signal, and the ''retrieval stage failed'' option has nothing to do with the span-edit result.'
WHERE id = 397 AND set_id = 12 AND explanation =
  'If the answer does not change when the span changes, the answer was not derived from the span — it came from parametric memory. Options 2 and 4 claim the opposite of the observed signal, and option 3 has nothing to do with the span-edit result.';

-- Q43
UPDATE questions SET explanation =
  'A dangling inline citation (an attribution pointing at nothing) is fatal and reported as a hard failure, while a Sources entry no claim cites is an unused-source recall gap and reported as a warning. The option making the uncited entry the hard failure and the ''both are warnings'' option swap or flatten this asymmetry; the ''both are hard failures'' option treats an uncited source as fatal when the code does not.'
WHERE id = 401 AND set_id = 12 AND explanation =
  'A dangling inline citation (an attribution pointing at nothing) is fatal and reported as a hard failure, while a Sources entry no claim cites is an unused-source recall gap and reported as a warning. Options 2 and 4 swap or flatten this asymmetry; option 3 treats an uncited source as fatal when the code does not.';

-- Q49
UPDATE questions SET explanation =
  'The `.md` file holds content without metadata and the manifest holds metadata without content, so a pipeline that cites a document must re-join them (typically keyed on `doc_id`). The ''metadata is embedded inside the `.md` file'' and ''manifest contains the full document text'' options invert where each part lives, and the ''no way to recover'' option is false because `doc_id` is the join key that recovers the pairing.'
WHERE id = 407 AND set_id = 12 AND explanation =
  'The `.md` file holds content without metadata and the manifest holds metadata without content, so a pipeline that cites a document must re-join them (typically keyed on `doc_id`). Options 2 and 3 invert where each part lives, and option 4 is false because `doc_id` is the join key that recovers the pairing.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 12
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'Attribution only asks whether a source exists that the claim points at — and here the source really exists, so attribution held. Faithfulness asks whether that source entails the claim — it does not, so faithfulness failed. The ''faithfulness held, but attribution failed'' option inverts the two; the ''both failed'' option is wrong because attribution genuinely held; the retrieval-latency option is a red herring, since latency is unrelated to whether the cited source supports the answer.',
    'Attributability-to-identified-sources is about the relationship between a statement and the source it points at, and is silent on whether that source (or the statement) is actually correct. The ''measures truth about the world'' option states the opposite; the ''only when the cited source is already verified correct'' option is wrong because the framework is precisely used when source correctness is not assumed; the ''cannot be applied to any real system'' option is false — it is a practical, widely used framing.',
    'Citing everything trivially maximizes recall (every claim carries a citation) while precision collapses because most attached citations do not actually support the claim they sit next to. The ''precision improved'' option mistakes quantity for support; the ''recall collapsed'' option has the direction of recall backwards; the ''both improved together'' option describes the opposite of what happens.',
    'Precision is the fraction of emitted citations that actually support their claim (irrelevant citations lower it); recall is the fraction of supportable claims that carry any citation (uncited load-bearing claims lower it). The ''citation recall; citation precision'' option swaps them; the ''citation precision; citation precision'' and ''citation recall; citation recall'' options collapse the two distinct metrics into one.',
    'Finer citations make a claim checkable at a glance (higher verifiability) but cost more: document-level citations cost almost nothing, while per-claim attribution requires an extraction step and one attribution call per claim. The ''cost stays flat'' and ''verifiability falls'' options get the cost or the direction wrong; the ''verifiability is unchanged'' option wrongly claims verifiability does not improve.',
    'Recall bought by lowering the bar is not real recall: when citations always exist but rarely help, readers stop trusting them, and even the correct ones lose value. The ''trust rises'' option assumes help where there is none; the ''recall is the only number that matters'' option ignores precision entirely; the ''still strictly better than no citation'' option is the trap this module warns against — a citation that points at a whole document rarely lets anyone verify a claim.',
    'Granularity is capped by the index: the engine re-splits existing nodes, so it can only produce smaller (finer) citation nodes, and a requested size larger than the original chunk has no effect. The ''arbitrarily coarse or fine'' option ignores the cap; the ''only coarser, never finer'' option inverts the direction; the ''no effect on citation size'' option is wrong because the parameter does change node size, just only in the finer direction.',
    'If removing the cited node changes nothing, the claim never depended on that node — it came from the model''s weights (parametric memory), so the citation only decorates it. Retrieval and formatting both worked fine; the ''citation formatting is broken'' option confuses a generation problem with a formatting problem, and the ''definitely correct because it was stable'' option mistakes stability for correctness.',
    '"If any" means the output space explicitly includes "no supporting part," which is precisely the diagnosis a citation cannot express. The ''single most supportive span'' and ''guaranteed to find at least one supporting span'' options assume a supporting span always exists; the ''cannot tell a grounded statement from a fabricated one'' option is wrong because distinguishing grounded from misinterpreted from fabricated is exactly what the method is designed to do.',
    'Ablation removes the cited node and checks whether the answer still reproduces; perturbation edits the cited span and checks whether the answer tracks the edit. The option calling span editing ablation and node removal perturbation swaps the names; the ''both are forms of ablation'' option collapses two distinct instruments; the ''trustworthy LLM judge'' option is wrong because both produce a diff (changed vs unchanged), not a judge''s score.',
    'Each test produces a diff (unchanged vs changed answer), which is interpretable without trusting a judge''s score. The ''no model calls at all'' option is false — both re-run generation; the ''only the retrieval stage'' option is false — they exercise generation on purpose; the ''numeric confidence value'' option is false — the whole point is that a diff is not a numeric score.',
    'If most sentences really are supported, a claim- or answer-level score looks mostly faithful, and a single wrong number in one clause disappears into the average; word-level annotation localizes it. The ''every word into a separate citation'' option misreads annotation as citation; the ''claim-level scores are always more precise'' option inverts the precision claim; the ''ignore the citation entirely'' option is wrong — the evaluator still checks citations, just at finer granularity.',
    'A formatting bug lives in the response synthesizer and is fixed by changing how citations are rendered. Parametric recall is a property of the model''s weights — the claim was never in the context — so it cannot be formatted away; it can only be detected (e.g., by ablation). The ''same formatting change'' option collapses two different fixes; the ''parametric recall is fixed by formatting'' option inverts the pair; the ''neither can ever be detected'' option wrongly claims detection is impossible.',
    'If the displayed text and the fed text are produced by different templates, the reader and the model look at different material, so the reader cannot verify what the model actually used. The ''fewer tokens, improving latency'' and ''more precise'' options are non-sequiturs — the template adds content rather than removing it, and precision is unaffected; the ''no consequence'' option ignores the mismatch entirely.',
    'The two audiences (embedder and generator) can be decoupled: a key can be excluded from the model''s view while remaining available to the embedder. Deleting it throws away the embedding benefit; including it for the LLM and excluding it from embeddings inverts the case in the scenario; the ''no mechanism'' option is false — decoupling is exactly what the metadata modes provide.',
    'The design treats abstention as a legitimate, logged success (a bounded cost: the user re-checks the source) and forbids the ungrounded-answer state entirely. The ''error path to be driven to zero'' option demotes abstention to an error; the ''acceptable as long as they are fast'' option is the exact failure the design prevents; the ''same thing'' option conflates two outcomes with opposite costs.',
    'An abstention costs the user a second look — bounded. An ungrounded answer can become a compliance incident — unbounded. Trading abstentions for answers therefore trades a bounded cost for an unbounded one. The ''no downside'', ''no effect on correctness'' and ''only latency'' options all deny this asymmetry, which is the entire reason the acceptance threshold is calibrated on the ungrounded rate rather than on coverage.',
    'Showing a source only proves the answer when the source actually entails the claim; attaching a real, relevant source to an unsupported answer is exactly the conflation. The empty-answer option is an abstention-like outcome, the option citing a source that does not exist is a broken attribution (nonexistent source), and the option citing a fully supporting source is the correct behavior — none illustrate the conflation.',
    'A citation converts a quality bug the user would catch into a compliance incident nobody catches, because the citation signals verification. The ''minor UX issue'' and ''fluent answer is necessarily correct'' options deny the severity or assume fluency implies correctness; the ''purely an embedding problem'' option misattributes a generation/grounding problem to the embedding stage.',
    'Attribution establishes a relationship between answer and source, not between answer and reality; a source can be wrong or outdated. The ''it is stronger'' and ''identical in strength'' options overstate or equate the guarantees; the ''correctness is weaker'' option is false because correctness is the stronger, harder-to-establish claim.',
    'The engine re-splits retrieved nodes into smaller citation nodes at query time, so finer citations are a parameter change, not a re-index. The ''only after a full re-index'' option misses that no re-index is needed; the ''coarser citations only'' option inverts the direction; the ''only in ranking'' option ignores the mechanism entirely.',
    'An uncited answer carries no evidence of support, so downstream no one can tell it from a hallucination — which is why it is a failure, not formatting. The ''formatting issues are always trivial'' option is a non-sequitur; the ''improve embedding quality'' option confuses citations with embedding; the ''always hallucinates without citations'' option overstates — citations do not cause or prevent hallucination.',
    'If the answer does not change when the span changes, the answer was not derived from the span — it came from parametric memory. The ''faithfully follows the span'' and ''correctly supporting the answer'' options claim the opposite of the observed signal, and the ''retrieval stage failed'' option has nothing to do with the span-edit result.',
    'A dangling inline citation (an attribution pointing at nothing) is fatal and reported as a hard failure, while a Sources entry no claim cites is an unused-source recall gap and reported as a warning. The option making the uncited entry the hard failure and the ''both are warnings'' option swap or flatten this asymmetry; the ''both are hard failures'' option treats an uncited source as fatal when the code does not.',
    'The `.md` file holds content without metadata and the manifest holds metadata without content, so a pipeline that cites a document must re-join them (typically keyed on `doc_id`). The ''metadata is embedded inside the `.md` file'' and ''manifest contains the full document text'' options invert where each part lives, and the ''no way to recover'' option is false because `doc_id` is the join key that recovers the pairing.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, 'Option 2 assumes help where there is none; option 3 ignores precision entirely; option 4 is the trap') > 0
      OR instr(q.explanation, 'Option 2 collapses two different fixes; option 3 inverts the pair; option 4 wrongly claims') > 0
      OR instr(q.explanation, 'Option 2 demotes abstention to an error; option 3 is the exact failure the design prevents; option 4 conflates') > 0
      OR instr(q.explanation, 'Option 2 ignores the cap; option 3 inverts the direction; option 4 is wrong because') > 0
      OR instr(q.explanation, 'Option 2 inverts the two; option 3 is wrong because attribution genuinely held; option 4 is a red herring') > 0
      OR instr(q.explanation, 'Option 2 is a non-sequitur; option 3 confuses citations with embedding; option 4 overstates —') > 0
      OR instr(q.explanation, 'Option 2 is an abstention-like outcome, option 3 is a broken attribution (nonexistent source), and option 4 is the correct behavior') > 0
      OR instr(q.explanation, 'Option 2 is false — both re-run generation; option 3 is false — they exercise generation on purpose; option 4 is false —') > 0
      OR instr(q.explanation, 'Option 2 misreads annotation as citation; option 3 inverts the precision claim; option 4 is wrong —') > 0
      OR instr(q.explanation, 'Option 2 misses that no re-index is needed; option 3 inverts the direction; option 4 ignores') > 0
      OR instr(q.explanation, 'Option 2 mistakes quantity for support; option 3 has the direction of recall backwards; option 4 describes the opposite') > 0
      OR instr(q.explanation, 'Option 2 states the opposite; option 3 is wrong because') > 0
      OR instr(q.explanation, 'Option 2 swaps the names; option 3 collapses two distinct instruments; option 4 is wrong because') > 0
      OR instr(q.explanation, 'Option 2 swaps them; options 3 and 4 collapse') > 0
      OR instr(q.explanation, 'Options 2 and 3 are non-sequiturs —') > 0
      OR instr(q.explanation, 'Options 2 and 3 assume a supporting span always exists; option 4 is wrong because') > 0
      OR instr(q.explanation, 'Options 2 and 3 get the cost or the direction wrong; option 4 wrongly claims') > 0
      OR instr(q.explanation, 'Options 2 and 3 invert where each part lives, and option 4 is false because') > 0
      OR instr(q.explanation, 'Options 2 and 3 overstate or equate the guarantees; option 4 is false because') > 0
      OR instr(q.explanation, 'Options 2 and 4 claim the opposite of the observed signal, and option 3 has nothing to do with') > 0
      OR instr(q.explanation, 'Options 2 and 4 deny the severity or assume fluency implies correctness; option 3 misattributes') > 0
      OR instr(q.explanation, 'Options 2 and 4 swap or flatten this asymmetry; option 3 treats') > 0
      OR instr(q.explanation, 'Options 2–4 all deny this asymmetry') > 0
      OR instr(q.explanation, 'option 3 confuses a generation problem with a formatting problem, and option 4 mistakes') > 0
      OR instr(q.explanation, 'option 3 inverts the case in the scenario; option 4 is false —') > 0
      OR instr(q.explanation, 'option 4 ignores the mismatch') > 0
      OR instr(q.explanation, 'option 4 is false — it is a practical') > 0));

-- Set 34 "The Long Way Down": 2 explanations.

-- Q27
UPDATE questions SET explanation =
  'The passthrough key itself is still camelCased (`runtimeVarOverrides`); only its value''s keys are preserved. `extra_info` is not a passthrough field, so `POD_NAME` → `"POD" + "Name"` = `PODName`, because `capitalize()` lowercases everything after the first letter. That mangling is exactly why SLX var names need the passthrough set. The option with `''ISSUETitle''` and `''appName''` has no passthrough. The option keeping `''runtime_var_overrides''` wrongly preserves the outer key. The option with `''runtimeVarOverrides''` but `{''POD_NAME'': ''p''}` wrongly treats `POD_NAME` as preserved.'
WHERE id = 1597 AND set_id = 34 AND explanation =
  'The passthrough key itself is still camelCased (`runtimeVarOverrides`); only its value''s keys are preserved. `extra_info` is not a passthrough field, so `POD_NAME` → `"POD" + "Name"` = `PODName`, because `capitalize()` lowercases everything after the first letter. That mangling is exactly why SLX var names need the passthrough set. Option 2 has no passthrough. Option 3 wrongly preserves the outer key. Option 4 wrongly treats `POD_NAME` as preserved.';

-- Q32
UPDATE questions SET explanation =
  'Narrowing on the literal `type` removes the handled members. Whatever remains in `default` must be `never`, or assigning it is a compile error. That turns ''BE added a widget the FE doesn''t handle'' into a red build. The option where TodoWidget renders via GenericWidget describes today''s untyped behaviour. Assignability to `never` doesn''t depend on `strict`. The check is purely static; nothing is thrown at runtime.'
WHERE id = 1602 AND set_id = 34 AND explanation =
  'Narrowing on the literal `type` removes the handled members. Whatever remains in `default` must be `never`, or assigning it is a compile error. That turns ''BE added a widget the FE doesn''t handle'' into a red build. Option 2 describes today''s untyped behaviour. Assignability to `never` doesn''t depend on `strict`. The check is purely static; nothing is thrown at runtime.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 34
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'The passthrough key itself is still camelCased (`runtimeVarOverrides`); only its value''s keys are preserved. `extra_info` is not a passthrough field, so `POD_NAME` → `"POD" + "Name"` = `PODName`, because `capitalize()` lowercases everything after the first letter. That mangling is exactly why SLX var names need the passthrough set. The option with `''ISSUETitle''` and `''appName''` has no passthrough. The option keeping `''runtime_var_overrides''` wrongly preserves the outer key. The option with `''runtimeVarOverrides''` but `{''POD_NAME'': ''p''}` wrongly treats `POD_NAME` as preserved.',
    'Narrowing on the literal `type` removes the handled members. Whatever remains in `default` must be `never`, or assigning it is a compile error. That turns ''BE added a widget the FE doesn''t handle'' into a red build. The option where TodoWidget renders via GenericWidget describes today''s untyped behaviour. Assignability to `never` doesn''t depend on `strict`. The check is purely static; nothing is thrown at runtime.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, 'Option 2 describes today''s untyped behaviour.') > 0
      OR instr(q.explanation, 'Option 2 has no passthrough. Option 3 wrongly preserves the outer key. Option 4 wrongly treats `POD_NAME` as preserved.') > 0));

-- Set 19 "RAG — Context Assembly, Prompting, and the Temperature Dial": 1 explanation.

-- Q27
UPDATE questions SET explanation =
  'Temperature scaling fits T to fix miscalibration; sampling temperature sets T and treats the entropy as the product — same function, opposite goals. They''re not interchangeable, the effects are reversed in the option where the calibration use makes output more varied, and both involve a scalar.'
WHERE id = 765 AND set_id = 19 AND explanation =
  'Temperature scaling fits T to fix miscalibration; sampling temperature sets T and treats the entropy as the product — same function, opposite goals. They''re not interchangeable, the effects are reversed in the second distractor, and both involve a scalar.';
