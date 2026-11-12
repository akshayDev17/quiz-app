-- 0007 — name options by content in the explanations 0006 left alone, then shuffle their options.
--
-- 0006 kept shuffle_options off for 8 live sets (6, 8, 9, 13, 22, 23, 24, 31) because their
-- explanations named options by position or letter ("the first option is right", "Option B
-- is wrong ..."). With options shuffled those would point at the wrong option. This rewrites
-- each such explanation (123 in all) to name the option by its content instead, keeping the
-- rest of the text as it was, then turns option shuffle on for those sets. It also turns
-- option shuffle back off for two sets whose explanations number their options (see the end).
--
-- Each rewrite is keyed by question id and set id and guarded by the exact current text, so
-- on any other database, or if an author has since edited the text, it changes nothing.
-- Each switch applies only where that set's rewrites landed (a new text is present) and none
-- of the replaced position phrases is left in any of the set's explanations (instr() is
-- case-sensitive, so "Option B" does not match "option based").
--
-- Only questions.explanation and quiz_sets.shuffle_options change. Past attempts keep their
-- papers (attempt_questions.explanation): they were served in authored order, so their
-- position references still match.

-- Set 6 "Context Engineering: Assembly, Budgets and Grounding": 1 explanation.

-- Q10
UPDATE questions SET explanation =
  'Correct: it generalizes away dates, times and quantities while keeping the narrative, the topic and the named entities -- a summary keeps what the story was about and abstracts away the exact values, which is why the useful compactor rule is specific (''preserve dates, times and quantities verbatim'') rather than vague (''keep the important bits''). Wrong: the option keeping dates, times and quantities exactly inverts that, claiming exact quantities survive while the narrative goes. The option losing the relational structure claims the relational structure linking events is lost, but relational and event structure is exactly what a summary preserves. And the option keeping every date and quantity claims numbers survive because they are short, which confuses token cost with what a summary chooses to keep.'
WHERE id = 64 AND set_id = 6 AND explanation =
  'Correct: it generalizes away dates, times and quantities while keeping the narrative, the topic and the named entities -- a summary keeps what the story was about and abstracts away the exact values, which is why the useful compactor rule is specific (''preserve dates, times and quantities verbatim'') rather than vague (''keep the important bits''). Wrong: the first option inverts that, claiming exact quantities survive while the narrative goes. The third claims the relational structure linking events is lost, but relational and event structure is exactly what a summary preserves. And the fourth claims numbers survive because they are short, which confuses token cost with what a summary chooses to keep.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 6
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'Correct: it generalizes away dates, times and quantities while keeping the narrative, the topic and the named entities -- a summary keeps what the story was about and abstracts away the exact values, which is why the useful compactor rule is specific (''preserve dates, times and quantities verbatim'') rather than vague (''keep the important bits''). Wrong: the option keeping dates, times and quantities exactly inverts that, claiming exact quantities survive while the narrative goes. The option losing the relational structure claims the relational structure linking events is lost, but relational and event structure is exactly what a summary preserves. And the option keeping every date and quantity claims numbers survive because they are short, which confuses token cost with what a summary chooses to keep.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, 'And the fourth claims numbers survive') > 0
      OR instr(q.explanation, 'The third claims the relational structure') > 0
      OR instr(q.explanation, 'Wrong: the first option inverts that') > 0));

-- Set 8 "Why RAG Exists — Concepts, Tradeoffs, and the Decision Procedure": 11 explanations.

-- Q11
UPDATE questions SET explanation =
  'An attribution failure is a claim that is true but unverifiable, which is exactly the option ''The claim is factually true but no source is available to verify it''. A false-but-fluent claim is hallucination. Mixing a real figure with an invented unit is a hallucination (the content is false). Repeating an older document word for word is a freshness or citation problem of a different kind, but the phrase ''older document'' signals staleness, not missing provenance.'
WHERE id = 144 AND set_id = 8 AND explanation =
  'An attribution failure is a claim that is true but unverifiable, which is exactly the first option. A false-but-fluent claim is hallucination. Mixing a real figure with an invented unit is a hallucination (the content is false). Repeating an older document word for word is a freshness or citation problem of a different kind, but the phrase ''older document'' signals staleness, not missing provenance.';

-- Q15
UPDATE questions SET explanation =
  'The ''lost in the middle'' finding is that evidence placed in the middle of a long context is used less reliably than evidence at the beginning or end, so the middle is correct. The beginning and end are the positions that tend to be used most reliably. The option ''Position has no effect'' is simply false — position measurably affects how reliably evidence is used.'
WHERE id = 148 AND set_id = 8 AND explanation =
  'The ''lost in the middle'' finding is that evidence placed in the middle of a long context is used less reliably than evidence at the beginning or end, so the middle is correct. The beginning and end are the positions that tend to be used most reliably. The final option is simply false — position measurably affects how reliably evidence is used.';

-- Q17
UPDATE questions SET explanation =
  'Cost scales with what you put in the prompt, and repeating a large slice on every one of thousands of daily queries multiplies that cost, so the option saying cost scales with what you put in the prompt is right. Long contexts are not free once accepted — the tokens still bill. A model does not refuse long prompts just because volume is high. Longer prompts do not shrink the answer; input and output tokens are both costs.'
WHERE id = 150 AND set_id = 8 AND explanation =
  'Cost scales with what you put in the prompt, and repeating a large slice on every one of thousands of daily queries multiplies that cost, so the first option is right. Long contexts are not free once accepted — the tokens still bill. A model does not refuse long prompts just because volume is high. Longer prompts do not shrink the answer; input and output tokens are both costs.';

-- Q22
UPDATE questions SET explanation =
  'A fine-tuned-facts system fails by confidently misremembering the old value, leaving no trace of where it came from. The option about failing to find the new value describes the retrieval system''s failure (it fails to find the new value but leaves a trace showing evidence was missing) — that is the other system, not this one. Refusing all factual questions and returning the correct value without citation are not the characteristic failure of a fine-tuned-facts system.'
WHERE id = 155 AND set_id = 8 AND explanation =
  'A fine-tuned-facts system fails by confidently misremembering the old value, leaving no trace of where it came from. The second option describes the retrieval system''s failure (it fails to find the new value but leaves a trace showing evidence was missing) — that is the other system, not this one. Refusing all factual questions and returning the correct value without citation are not the characteristic failure of a fine-tuned-facts system.';

-- Q25
UPDATE questions SET explanation =
  'An average can hide entire classes of query that score near zero but matter most, so the option about hiding entire classes of query is right. The average is not always too high, and it is trivial to compute for many queries; those options misstate the problem. An aggregate retrieval score measures quality, not latency, so that option is simply wrong.'
WHERE id = 158 AND set_id = 8 AND explanation =
  'An average can hide entire classes of query that score near zero but matter most, so the first option is right. The average is not always too high, and it is trivial to compute for many queries; those options misstate the problem. An aggregate retrieval score measures quality, not latency, so that option is simply wrong.';

-- Q28
UPDATE questions SET explanation =
  'The error was introduced at chunking time, when the boundary fell inside the answer — before generation ever ran, which is why a faithful generator still quoted a wrong sentence. The generator did not misquote (the ''at generation time'' option). The evaluation metric was not the source of error, and the embeddings were not miscomputed; the split happened earlier, at chunking.'
WHERE id = 161 AND set_id = 8 AND explanation =
  'The error was introduced at chunking time, when the boundary fell inside the answer — before generation ever ran, which is why a faithful generator still quoted a wrong sentence. The generator did not misquote (the second option). The evaluation metric was not the source of error, and the embeddings were not miscomputed; the split happened earlier, at chunking.';

-- Q30
UPDATE questions SET explanation =
  'With no abstention path, the system reports the same confidence for evidence it has and for evidence it does not have, so the option about reporting the same confidence is right. It does not keep searching indefinitely — it just answers. It cannot return the correct answer for an out-of-corpus question, and it does not refuse questions it could actually answer; those options invert the situation.'
WHERE id = 163 AND set_id = 8 AND explanation =
  'With no abstention path, the system reports the same confidence for evidence it has and for evidence it does not have, so the first option is right. It does not keep searching indefinitely — it just answers. It cannot return the correct answer for an out-of-corpus question, and it does not refuse questions it could actually answer; those options invert the situation.';

-- Q33
UPDATE questions SET explanation =
  'Updating a fact in the weights means re-training or fine-tuning, which is rare and expensive, whereas updating an external store is a quick upsert of one document in minutes — so the option pairing re-training for parametric memory with a one-document upsert for the external store is right. The option giving parametric memory a quick in-place edit and the external store a full re-train inverts the two. Both re-train and neither-can-update are false: an external store is updated in place, and weights can be updated (just expensively).'
WHERE id = 166 AND set_id = 8 AND explanation =
  'Updating a fact in the weights means re-training or fine-tuning, which is rare and expensive, whereas updating an external store is a quick upsert of one document in minutes — so the first option is right. The second option inverts the two. Both re-train and neither-can-update are false: an external store is updated in place, and weights can be updated (just expensively).';

-- Q37
UPDATE questions SET explanation =
  'Retrieval changes the cost of being wrong: an error becomes a claim that contradicts a cited span, which a reviewer can catch quickly. It does not drop the probability of error to zero. It does not enlarge the model''s vocabulary. Longer answers are not more accurate, so the option claiming the answer is always longer and therefore more accurate is wrong.'
WHERE id = 170 AND set_id = 8 AND explanation =
  'Retrieval changes the cost of being wrong: an error becomes a claim that contradicts a cited span, which a reviewer can catch quickly. It does not drop the probability of error to zero. It does not enlarge the model''s vocabulary. Longer answers are not more accurate, so the final option is wrong.';

-- Q42
UPDATE questions SET explanation =
  'The spread shows failure is stratified, not uniform: a single average hides which query classes are actually broken, so the option saying failure is stratified, not uniform, is right. The average is not meaningless — it is just insufficient on its own. Not all classes are equally broken (that is the point of the spread). The spread does not mean the system is fine; some classes are doing badly.'
WHERE id = 175 AND set_id = 8 AND explanation =
  'The spread shows failure is stratified, not uniform: a single average hides which query classes are actually broken, so the first option is right. The average is not meaningless — it is just insufficient on its own. Not all classes are equally broken (that is the point of the spread). The spread does not mean the system is fine; some classes are doing badly.';

-- Q45
UPDATE questions SET explanation =
  'Rapid growth means the corpus will outgrow even a very large window, so something must still select a subset first; and long-context prompting at best replaces the final assembly stage, receiving a pre-selected subset, not retrieval itself — both are correct. The growth does not make long-context the winner (it makes retrieval more necessary), and it plainly does bear on the strategy, so the ''clear winner'' and ''no bearing'' options are wrong.'
WHERE id = 178 AND set_id = 8 AND explanation =
  'Rapid growth means the corpus will outgrow even a very large window, so something must still select a subset first; and long-context prompting at best replaces the final assembly stage, receiving a pre-selected subset, not retrieval itself — both are correct. The growth does not make long-context the winner (it makes retrieval more necessary), and it plainly does bear on the strategy, so the last two are wrong.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 8
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'An attribution failure is a claim that is true but unverifiable, which is exactly the option ''The claim is factually true but no source is available to verify it''. A false-but-fluent claim is hallucination. Mixing a real figure with an invented unit is a hallucination (the content is false). Repeating an older document word for word is a freshness or citation problem of a different kind, but the phrase ''older document'' signals staleness, not missing provenance.',
    'The ''lost in the middle'' finding is that evidence placed in the middle of a long context is used less reliably than evidence at the beginning or end, so the middle is correct. The beginning and end are the positions that tend to be used most reliably. The option ''Position has no effect'' is simply false — position measurably affects how reliably evidence is used.',
    'Cost scales with what you put in the prompt, and repeating a large slice on every one of thousands of daily queries multiplies that cost, so the option saying cost scales with what you put in the prompt is right. Long contexts are not free once accepted — the tokens still bill. A model does not refuse long prompts just because volume is high. Longer prompts do not shrink the answer; input and output tokens are both costs.',
    'A fine-tuned-facts system fails by confidently misremembering the old value, leaving no trace of where it came from. The option about failing to find the new value describes the retrieval system''s failure (it fails to find the new value but leaves a trace showing evidence was missing) — that is the other system, not this one. Refusing all factual questions and returning the correct value without citation are not the characteristic failure of a fine-tuned-facts system.',
    'An average can hide entire classes of query that score near zero but matter most, so the option about hiding entire classes of query is right. The average is not always too high, and it is trivial to compute for many queries; those options misstate the problem. An aggregate retrieval score measures quality, not latency, so that option is simply wrong.',
    'The error was introduced at chunking time, when the boundary fell inside the answer — before generation ever ran, which is why a faithful generator still quoted a wrong sentence. The generator did not misquote (the ''at generation time'' option). The evaluation metric was not the source of error, and the embeddings were not miscomputed; the split happened earlier, at chunking.',
    'With no abstention path, the system reports the same confidence for evidence it has and for evidence it does not have, so the option about reporting the same confidence is right. It does not keep searching indefinitely — it just answers. It cannot return the correct answer for an out-of-corpus question, and it does not refuse questions it could actually answer; those options invert the situation.',
    'Updating a fact in the weights means re-training or fine-tuning, which is rare and expensive, whereas updating an external store is a quick upsert of one document in minutes — so the option pairing re-training for parametric memory with a one-document upsert for the external store is right. The option giving parametric memory a quick in-place edit and the external store a full re-train inverts the two. Both re-train and neither-can-update are false: an external store is updated in place, and weights can be updated (just expensively).',
    'Retrieval changes the cost of being wrong: an error becomes a claim that contradicts a cited span, which a reviewer can catch quickly. It does not drop the probability of error to zero. It does not enlarge the model''s vocabulary. Longer answers are not more accurate, so the option claiming the answer is always longer and therefore more accurate is wrong.',
    'The spread shows failure is stratified, not uniform: a single average hides which query classes are actually broken, so the option saying failure is stratified, not uniform, is right. The average is not meaningless — it is just insufficient on its own. Not all classes are equally broken (that is the point of the spread). The spread does not mean the system is fine; some classes are doing badly.',
    'Rapid growth means the corpus will outgrow even a very large window, so something must still select a subset first; and long-context prompting at best replaces the final assembly stage, receiving a pre-selected subset, not retrieval itself — both are correct. The growth does not make long-context the winner (it makes retrieval more necessary), and it plainly does bear on the strategy, so the ''clear winner'' and ''no bearing'' options are wrong.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, '(the second option)') > 0
      OR instr(q.explanation, 'The final option is simply false') > 0
      OR instr(q.explanation, 'The second option describes the retrieval system''s failure') > 0
      OR instr(q.explanation, 'so the final option is wrong.') > 0
      OR instr(q.explanation, 'so the first option is right.') > 0
      OR instr(q.explanation, 'so the first option is right. The second option inverts the two.') > 0
      OR instr(q.explanation, 'so the last two are wrong.') > 0
      OR instr(q.explanation, 'which is exactly the first option.') > 0));

-- Set 9 "RAG Observability, Tracing, and Online Evaluation": 1 explanation.

-- Q1
UPDATE questions SET explanation =
  'Health answers ''is the service up, fast, and cheap''; quality answers ''is it still answering correctly''. They must be tracked separately because a change can leave every health metric flat or better while destroying retrieval quality. The ''inverted'' option swaps the two definitions; the ''synonym'' option collapses a real distinction; the option measuring health only on the query path and quality only at ingest wrongly assigns each side to a single pipeline stage when quality spans both ingest and query.'
WHERE id = 189 AND set_id = 9 AND explanation =
  'Health answers ''is the service up, fast, and cheap''; quality answers ''is it still answering correctly''. They must be tracked separately because a change can leave every health metric flat or better while destroying retrieval quality. The ''inverted'' option swaps the two definitions; the ''synonym'' option collapses a real distinction; the last option wrongly assigns each side to a single pipeline stage when quality spans both ingest and query.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 9
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'Health answers ''is the service up, fast, and cheap''; quality answers ''is it still answering correctly''. They must be tracked separately because a change can leave every health metric flat or better while destroying retrieval quality. The ''inverted'' option swaps the two definitions; the ''synonym'' option collapses a real distinction; the option measuring health only on the query path and quality only at ingest wrongly assigns each side to a single pipeline stage when quality spans both ingest and query.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, 'the last option wrongly assigns') > 0));

-- Set 13 "RAG pipeline, end to end": 7 explanations.

-- Q18
UPDATE questions SET explanation =
  'A miss is about absence: the correct chunk never made the candidate set. Noise is about order: the correct chunk made it in but was buried below plausible wrong ones. The hallucination/stale-index option misattributes both (hallucination is a generation issue, staleness a freshness issue). The latency/cost option reclassifies both as resource problems, which neither is. The too-small/too-large chunk option invents a chunk-size explanation that describes neither failure.'
WHERE id = 426 AND set_id = 13 AND explanation =
  'A miss is about absence: the correct chunk never made the candidate set. Noise is about order: the correct chunk made it in but was buried below plausible wrong ones. The second option misattributes both (hallucination is a generation issue, staleness a freshness issue). The third reclassifies both as resource problems, which neither is. The fourth invents a chunk-size explanation that describes neither failure.';

-- Q19
UPDATE questions SET explanation =
  'Boundary loss leaves part of the answer findable (it was retrieved, just split), whereas representation mismatch means the relevant chunk never matches any query wording, so it is not retrieved at all. The stale-index/truncation option confuses both with other failures (staleness, truncation). The tables/legal-prose option invents a document-type restriction that neither failure has. The ''same phenomenon, differing only in severity'' option collapses two mechanisms with different fixes into one.'
WHERE id = 427 AND set_id = 13 AND explanation =
  'Boundary loss leaves part of the answer findable (it was retrieved, just split), whereas representation mismatch means the relevant chunk never matches any query wording, so it is not retrieved at all. The second option confuses both with other failures (staleness, truncation). The third invents a document-type restriction that neither failure has. The fourth collapses two mechanisms with different fixes into one.';

-- Q20
UPDATE questions SET explanation =
  'Overflow loses the evidence before the model sees it (window too small, or the passage buried mid-context); unfaithful synthesis is the model deviating from evidence it did see. The ingest/storage option misassigns both to ingest/storage, the retriever/chunker option to retriever/chunker — none of which own these failures. The temperature option merges two failures that have different owners and fixes.'
WHERE id = 428 AND set_id = 13 AND explanation =
  'Overflow loses the evidence before the model sees it (window too small, or the passage buried mid-context); unfaithful synthesis is the model deviating from evidence it did see. The second option misassigns both to ingest/storage, the third to retriever/chunker — none of which own these failures. The fourth merges two failures that have different owners and fixes.';

-- Q21
UPDATE questions SET explanation =
  'Staleness is a divergence between index and source (the index serves an old version), while a miss is the correct, current passage not being retrieved at all. The hallucination/truncation option mislabels both (hallucination and truncation are other failures). The cost/latency option reclassifies them as resource problems. The ''interchangeable terms'' option is wrong because the two have different owners (ingest vs retrieve) and different fixes.'
WHERE id = 429 AND set_id = 13 AND explanation =
  'Staleness is a divergence between index and source (the index serves an old version), while a miss is the correct, current passage not being retrieved at all. The second option mislabels both (hallucination and truncation are other failures). The third reclassifies them as resource problems. The fourth is wrong because the two have different owners (ingest vs retrieve) and different fixes.';

-- Q24
UPDATE questions SET explanation =
  'A reranker reorders the candidate set it receives; if the correct passage was never retrieved, it is not in that set, so reranking cannot conjure it. Rerankers do not search the corpus (that is the retriever''s job). No reranker guarantees correctness — it only improves ordering. The ''only changes latency'' option is half-wrong: reranking does not enlarge the candidate set, but it does change quality when the right passage is present, so ''only changes latency'' is false.'
WHERE id = 432 AND set_id = 13 AND explanation =
  'A reranker reorders the candidate set it receives; if the correct passage was never retrieved, it is not in that set, so reranking cannot conjure it. Rerankers do not search the corpus (that is the retriever''s job). No reranker guarantees correctness — it only improves ordering. The last option is half-wrong: reranking does not enlarge the candidate set, but it does change quality when the right passage is present, so ''only changes latency'' is false.';

-- Q31
UPDATE questions SET explanation =
  'The original RAG work jointly trained a pre-trained retriever with a pre-trained seq2seq generator, optimizing the retriever for the generator; modern systems frequently freeze both and compose them, tuning only how they are joined (prompting, reranking, candidate size). The option where the original keeps both frozen and modern practice fine-tunes only the generator reverses the split. The ''no retriever at all'' option is false — the original formulation is built around a retriever. The ''no disagreement'' option ignores a real, documented divergence in approach.'
WHERE id = 439 AND set_id = 13 AND explanation =
  'The original RAG work jointly trained a pre-trained retriever with a pre-trained seq2seq generator, optimizing the retriever for the generator; modern systems frequently freeze both and compose them, tuning only how they are joined (prompting, reranking, candidate size). The second option reverses the split. The third is false — the original formulation is built around a retriever. The fourth ignores a real, documented divergence in approach.';

-- Q32
UPDATE questions SET explanation =
  'Adopting the framework''s seams means each stage can be swapped and each failure attributed, but you are limited to where the framework lets you cut — a stage that wants to span two objects must be built inside one seam. A bespoke chain gives freedom but loses the substitutability/attribution. The ''unlimited flexibility, losing all attributability'' option inverts the costs and benefits. The speed-for-correctness option invents a speed/correctness trade that isn''t the real one. ''Always better'' is false because a bespoke chain is exactly what makes failures unattributable.'
WHERE id = 440 AND set_id = 13 AND explanation =
  'Adopting the framework''s seams means each stage can be swapped and each failure attributed, but you are limited to where the framework lets you cut — a stage that wants to span two objects must be built inside one seam. A bespoke chain gives freedom but loses the substitutability/attribution. The second option inverts the costs and benefits. The third invents a speed/correctness trade that isn''t the real one. ''Always better'' is false because a bespoke chain is exactly what makes failures unattributable.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 13
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'A miss is about absence: the correct chunk never made the candidate set. Noise is about order: the correct chunk made it in but was buried below plausible wrong ones. The hallucination/stale-index option misattributes both (hallucination is a generation issue, staleness a freshness issue). The latency/cost option reclassifies both as resource problems, which neither is. The too-small/too-large chunk option invents a chunk-size explanation that describes neither failure.',
    'Boundary loss leaves part of the answer findable (it was retrieved, just split), whereas representation mismatch means the relevant chunk never matches any query wording, so it is not retrieved at all. The stale-index/truncation option confuses both with other failures (staleness, truncation). The tables/legal-prose option invents a document-type restriction that neither failure has. The ''same phenomenon, differing only in severity'' option collapses two mechanisms with different fixes into one.',
    'Overflow loses the evidence before the model sees it (window too small, or the passage buried mid-context); unfaithful synthesis is the model deviating from evidence it did see. The ingest/storage option misassigns both to ingest/storage, the retriever/chunker option to retriever/chunker — none of which own these failures. The temperature option merges two failures that have different owners and fixes.',
    'Staleness is a divergence between index and source (the index serves an old version), while a miss is the correct, current passage not being retrieved at all. The hallucination/truncation option mislabels both (hallucination and truncation are other failures). The cost/latency option reclassifies them as resource problems. The ''interchangeable terms'' option is wrong because the two have different owners (ingest vs retrieve) and different fixes.',
    'A reranker reorders the candidate set it receives; if the correct passage was never retrieved, it is not in that set, so reranking cannot conjure it. Rerankers do not search the corpus (that is the retriever''s job). No reranker guarantees correctness — it only improves ordering. The ''only changes latency'' option is half-wrong: reranking does not enlarge the candidate set, but it does change quality when the right passage is present, so ''only changes latency'' is false.',
    'The original RAG work jointly trained a pre-trained retriever with a pre-trained seq2seq generator, optimizing the retriever for the generator; modern systems frequently freeze both and compose them, tuning only how they are joined (prompting, reranking, candidate size). The option where the original keeps both frozen and modern practice fine-tunes only the generator reverses the split. The ''no retriever at all'' option is false — the original formulation is built around a retriever. The ''no disagreement'' option ignores a real, documented divergence in approach.',
    'Adopting the framework''s seams means each stage can be swapped and each failure attributed, but you are limited to where the framework lets you cut — a stage that wants to span two objects must be built inside one seam. A bespoke chain gives freedom but loses the substitutability/attribution. The ''unlimited flexibility, losing all attributability'' option inverts the costs and benefits. The speed-for-correctness option invents a speed/correctness trade that isn''t the real one. ''Always better'' is false because a bespoke chain is exactly what makes failures unattributable.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, 'The fourth collapses two mechanisms') > 0
      OR instr(q.explanation, 'The fourth ignores a real') > 0
      OR instr(q.explanation, 'The fourth invents a chunk-size explanation') > 0
      OR instr(q.explanation, 'The fourth is wrong because') > 0
      OR instr(q.explanation, 'The fourth merges two failures') > 0
      OR instr(q.explanation, 'The last option is half-wrong:') > 0
      OR instr(q.explanation, 'The second option confuses both') > 0
      OR instr(q.explanation, 'The second option inverts the costs and benefits. The third invents') > 0
      OR instr(q.explanation, 'The second option misassigns both to ingest/storage, the third to retriever/chunker') > 0
      OR instr(q.explanation, 'The second option misattributes both') > 0
      OR instr(q.explanation, 'The second option mislabels both') > 0
      OR instr(q.explanation, 'The second option reverses the split.') > 0
      OR instr(q.explanation, 'The third invents a document-type restriction') > 0
      OR instr(q.explanation, 'The third is false') > 0
      OR instr(q.explanation, 'The third reclassifies both') > 0
      OR instr(q.explanation, 'The third reclassifies them') > 0));

-- Set 22 "Multi-tenant, permissioned, and regulated RAG": 55 explanations.

-- Q1
UPDATE questions SET explanation =
  'Propagation means getting access-control labels onto documents, nodes, and queries so the pipeline can narrow its work; it is best-effort and may be proposed by a model. Authorization means proving, for every request, that each node reaching the prompt was readable by THIS principal at query time. A filter inferred from a query is a relevance hint, not a permission proof. The ''applied too early in the pipeline'' option is wrong because the defect is not the stage at which the filter runs but the role it was given; the same filter is unsafe no matter where it sits. The ''interchangeable'' option is wrong because the two roles are not interchangeable. The option making propagation the per-request proof reverses the two definitions outright.'
WHERE id = 886 AND set_id = 22 AND explanation =
  'Propagation means getting access-control labels onto documents, nodes, and queries so the pipeline can narrow its work; it is best-effort and may be proposed by a model. Authorization means proving, for every request, that each node reaching the prompt was readable by THIS principal at query time. A filter inferred from a query is a relevance hint, not a permission proof. Option B is wrong because the defect is not the stage at which the filter runs but the role it was given; the same filter is unsafe no matter where it sits. Option C is wrong because the two roles are not interchangeable. Option D reverses the two definitions outright.';

-- Q2
UPDATE questions SET explanation =
  'The post-retrieval authorization backstop is the only deny: it sits after retrieval and before synthesis and drops every node the requesting principal may not read. Everything upstream — the pushed-down metadata filter and the reranker — only reduces or reorders work and removes nothing. The cache is a stored earlier verdict, not a live deny. The metadata-filter, reranker and response-cache options each name a real component that does NOT enforce the "no": the push-down filter is an optimization, the reranker reorders rather than removes, and the cache replays a prior decision instead of making a fresh one.'
WHERE id = 887 AND set_id = 22 AND explanation =
  'The post-retrieval authorization backstop is the only deny: it sits after retrieval and before synthesis and drops every node the requesting principal may not read. Everything upstream — the pushed-down metadata filter and the reranker — only reduces or reorders work and removes nothing. The cache is a stored earlier verdict, not a live deny. Options B, C, and D each name a real component that does NOT enforce the "no": the push-down filter is an optimization, the reranker reorders rather than removes, and the cache replays a prior decision instead of making a fresh one.';

-- Q3
UPDATE questions SET explanation =
  'Propagation''s failure is a quality problem — slower queries, recall loss, or over-retrieval that a later check then removes — never a breach. And propagation MAY be delegated to a model (the LLM may propose filters). Authorization is the opposite on both axes: it never trusts anything upstream, its failure IS a breach, and it may never be delegated. The ''must never be delegated'' option is false because that is authorization''s property, not propagation''s. The ''runs only at query time'' option is false because propagation runs at ingest time and query time, while authorization runs only at query time after retrieval.'
WHERE id = 888 AND set_id = 22 AND explanation =
  'Propagation''s failure is a quality problem — slower queries, recall loss, or over-retrieval that a later check then removes — never a breach. And propagation MAY be delegated to a model (the LLM may propose filters). Authorization is the opposite on both axes: it never trusts anything upstream, its failure IS a breach, and it may never be delegated. Option C is false because that is authorization''s property, not propagation''s. Option D is false because propagation runs at ingest time and query time, while authorization runs only at query time after retrieval.';

-- Q4
UPDATE questions SET explanation =
  'A security control for permissions must be able to say "no" and remove a node. Reranking only changes the ORDER of the candidate set; it removes nothing, so it cannot enforce a deny decision no matter how good its scores are. The ''runs before retrieval'' option is factually wrong: reranking runs after retrieval, on the retrieved set. The ''derived from access-control labels'' option is wrong: reranker scores are relevance scores, not derived from any ACL. The ''weaker security control'' option is wrong: reranking is not a weaker security control — it is not a security control at all, because it has no removal step.'
WHERE id = 889 AND set_id = 22 AND explanation =
  'A security control for permissions must be able to say "no" and remove a node. Reranking only changes the ORDER of the candidate set; it removes nothing, so it cannot enforce a deny decision no matter how good its scores are. Option B is factually wrong: reranking runs after retrieval, on the retrieved set. Option C is wrong: reranker scores are relevance scores, not derived from any ACL. Option D is wrong: reranking is not a weaker security control — it is not a security control at all, because it has no removal step.';

-- Q5
UPDATE questions SET explanation =
  'Placing the authorization backstop AFTER retrieval means a narrow principal''s top-k is diluted by nodes they may not read, so their effective recall is lower than the index-wide figure. That is a cost of the backstop''s placement, and the push-down filter exists to shrink it — the store does the narrowing so the backstop corrects instead of deleting nearly everything. The storage-bug option is wrong: this configuration uses one shared index, not multiplied storage. The ''metadata filters are no longer needed'' option is wrong: the backstop does not remove the need for metadata filters; it is the reason the push-down filter is worth keeping. The latency-regression option is wrong: the penalty is a recall/coverage problem for the principal, not a slower index rebuild.'
WHERE id = 890 AND set_id = 22 AND explanation =
  'Placing the authorization backstop AFTER retrieval means a narrow principal''s top-k is diluted by nodes they may not read, so their effective recall is lower than the index-wide figure. That is a cost of the backstop''s placement, and the push-down filter exists to shrink it — the store does the narrowing so the backstop corrects instead of deleting nearly everything. Option B is wrong: this configuration uses one shared index, not multiplied storage. Option C is wrong: the backstop does not remove the need for metadata filters; it is the reason the push-down filter is worth keeping. Option D is wrong: the penalty is a recall/coverage problem for the principal, not a slower index rebuild.';

-- Q6
UPDATE questions SET explanation =
  'The push-down filter is a cost optimization, not a security control: it makes the store do the narrowing so that, for a narrow principal, the backstop is a correction rather than a near-total deletion, and it reduces the retrieval cost of an over-broad query. The ''actually drops the unreadable nodes'' option is wrong because dropping unreadable nodes is exactly the backstop''s job, not the filter''s. The ''guarantees no cross-tenant leak'' option is wrong because the filter alone never guarantees no scope leak — that is the module''s entire argument.'
WHERE id = 891 AND set_id = 22 AND explanation =
  'The push-down filter is a cost optimization, not a security control: it makes the store do the narrowing so that, for a narrow principal, the backstop is a correction rather than a near-total deletion, and it reduces the retrieval cost of an over-broad query. Option C is wrong because dropping unreadable nodes is exactly the backstop''s job, not the filter''s. Option D is wrong because the filter alone never guarantees no scope leak — that is the module''s entire argument.';

-- Q7
UPDATE questions SET explanation =
  'If a cache entry is a stored authorization verdict, it must be re-validated for the principal presenting it, or keyed so only principals with identical access-control lists can share it: key every entry on (tenant, ACL hash) and invalidate on any ACL change. Never serve one user''s answer to another user with different permissions. The ''semantically similar'' option is wrong for exactly the reason stated — semantic similarity does not imply equal permissions. The ''skip authorization'' option is wrong because serving from cache skips retrieval but must NOT skip authorization. The ''query vector alone'' option is wrong: keying on the query vector alone is the semantic key that ignores the principal and is precisely the defect.'
WHERE id = 892 AND set_id = 22 AND explanation =
  'If a cache entry is a stored authorization verdict, it must be re-validated for the principal presenting it, or keyed so only principals with identical access-control lists can share it: key every entry on (tenant, ACL hash) and invalidate on any ACL change. Never serve one user''s answer to another user with different permissions. Option B is wrong for exactly the reason stated — semantic similarity does not imply equal permissions. Option C is wrong because serving from cache skips retrieval but must NOT skip authorization. Option D is wrong: keying on the query vector alone is the semantic key that ignores the principal and is precisely the defect.';

-- Q8
UPDATE questions SET explanation =
  'This is the semantic response cache: it is keyed on query semantics rather than on the principal, so a second user asking a semantically similar question gets the first user''s answer with every node already filtered for the first user. No retrieval happens, so the post-retrieval backstop never runs. The fix is keying on (tenant, ACL hash) and invalidating on ACL change. The trace/span-log option leaks stored prompts, not replayed answers. The community-summary option leaks aggregated text, not cached responses. The embedding-inversion option recovers words from vectors, unrelated to serving a cached answer.'
WHERE id = 893 AND set_id = 22 AND explanation =
  'This is the semantic response cache: it is keyed on query semantics rather than on the principal, so a second user asking a semantically similar question gets the first user''s answer with every node already filtered for the first user. No retrieval happens, so the post-retrieval backstop never runs. The fix is keying on (tenant, ACL hash) and invalidating on ACL change. Option B (trace/span logs) leaks stored prompts, not replayed answers. Option C (community summaries) leaks aggregated text, not cached responses. Option D (embedding inversion) recovers words from vectors, unrelated to serving a cached answer.';

-- Q9
UPDATE questions SET explanation =
  'A summary is a derived document whose text is the union of what its member entities'' readers may see. If it spans different access-control lists, no single ACL correctly describes who may read all of it, so the safe rule is deny-by-default: the summary inherits the INTERSECTION of its members'' ACLs, and a summary that would span tenants must not be built at all. The union option would grant the most-permissive reader''s access to everyone. The largest-member option is arbitrary and equally unsafe. The no-label option (no ACL because it is derived) treats the derived text as if it had no sensitivity, which is exactly wrong.'
WHERE id = 894 AND set_id = 22 AND explanation =
  'A summary is a derived document whose text is the union of what its member entities'' readers may see. If it spans different access-control lists, no single ACL correctly describes who may read all of it, so the safe rule is deny-by-default: the summary inherits the INTERSECTION of its members'' ACLs, and a summary that would span tenants must not be built at all. Option B (union) would grant the most-permissive reader''s access to everyone. Option C (largest member) is arbitrary and equally unsafe. Option D (no ACL because it is derived) treats the derived text as if it had no sensitivity, which is exactly wrong.';

-- Q10
UPDATE questions SET explanation =
  'The summary''s text is a union of what several principals may read. An access-control list must describe exactly who may read a piece of content, and no single list describes "client A''s brokers AND client B''s brokers" without granting each side the other''s content. So a cross-tenant aggregate has no correct owner label. The ''never persisted'' option is false (summaries are stored nodes). The ''no readable text'' option is false (summaries have real text — that is the problem). The ''recomputed per query'' option is false: the summary is a precomputed stored artifact, not re-derived per query, and even if it were re-derived, the union it produces would still cross the boundary.'
WHERE id = 895 AND set_id = 22 AND explanation =
  'The summary''s text is a union of what several principals may read. An access-control list must describe exactly who may read a piece of content, and no single list describes "client A''s brokers AND client B''s brokers" without granting each side the other''s content. So a cross-tenant aggregate has no correct owner label. Option B is false (summaries are stored nodes). Option C is false (summaries have real text — that is the problem). Option D is false: the summary is a precomputed stored artifact, not re-derived per query, and even if it were re-derived, the union it produces would still cross the boundary.';

-- Q11
UPDATE questions SET explanation =
  'This is the trace/span log leak: observability stores the retrieved node set, scores, prompts, and responses, so it becomes a second copy of every tenant''s evidence. The controls are to tenant-scope the trace store, redact node text at the span boundary, and treat traces as a regulated data store with its own retention. The response-cache option is the cache (replayed answers), the community-summary option is graph summaries (aggregated text), the embedding-vector option is embedding inversion (recovering words from vectors) — none of these is a log of assembled prompts.'
WHERE id = 896 AND set_id = 22 AND explanation =
  'This is the trace/span log leak: observability stores the retrieved node set, scores, prompts, and responses, so it becomes a second copy of every tenant''s evidence. The controls are to tenant-scope the trace store, redact node text at the span boundary, and treat traces as a regulated data store with its own retention. Option B is the cache (replayed answers), Option C is graph summaries (aggregated text), Option D is embedding inversion (recovering words from vectors) — none of these is a log of assembled prompts.';

-- Q12
UPDATE questions SET explanation =
  'The tool call is made by the SYSTEM, not the end user, so the end user''s session permissions do not automatically travel with it. Every tool call must carry the end-user principal and the tool must re-authorize against it, rather than inheriting a session credential. The option making the end user the principal is wrong because it asserts the user is the principal and the tool inherits credentials — the exact confused-deputy error. The ''tools do not need their own authorization'' option is wrong: tools absolutely need authorization. The option making the model the principal is wrong: the model is the mechanism, not the principal whose rights are being exercised.'
WHERE id = 897 AND set_id = 22 AND explanation =
  'The tool call is made by the SYSTEM, not the end user, so the end user''s session permissions do not automatically travel with it. Every tool call must carry the end-user principal and the tool must re-authorize against it, rather than inheriting a session credential. Option B is wrong because it asserts the user is the principal and the tool inherits credentials — the exact confused-deputy error. Option C is wrong: tools absolutely need authorization. Option D is wrong: the model is the mechanism, not the principal whose rights are being exercised.';

-- Q13
UPDATE questions SET explanation =
  'An embedding is a lossy but invertible encoding of its input, not a privacy-preserving summary. So sensitive text must be redacted BEFORE embedding: once the vector exists, the information is already encoded in it. The ''redact the stored text after embedding'' option is wrong because redacting the stored text after embedding leaves the leak in the vector store. The ''keep embeddings internal'' option is wrong because the vectors themselves are the leak, so keeping them internal does not remove the risk. The ''redact at query time'' option is wrong because redaction must happen at ingest, before the vector is ever produced, not at query time.'
WHERE id = 898 AND set_id = 22 AND explanation =
  'An embedding is a lossy but invertible encoding of its input, not a privacy-preserving summary. So sensitive text must be redacted BEFORE embedding: once the vector exists, the information is already encoded in it. Option B is wrong because redacting the stored text after embedding leaves the leak in the vector store. Option C is wrong because the vectors themselves are the leak, so keeping them internal does not remove the risk. Option D is wrong because redaction must happen at ingest, before the vector is ever produced, not at query time.';

-- Q14
UPDATE questions SET explanation =
  'The sensitive information is already inside the vector the moment the embedding is computed. Removing the sensitive spans from the stored TEXT afterward leaves the leak in the VECTOR STORE untouched. Redaction must precede embedding to matter. The lower-quality-vectors option is wrong: the issue is not vector quality but information already encoded. The ''vector stores do not store text'' option is wrong: vector stores do store the vectors, and the vectors carry the information. The ''reversible'' option is wrong for the same reason — the text removal does not undo the vector.'
WHERE id = 899 AND set_id = 22 AND explanation =
  'The sensitive information is already inside the vector the moment the embedding is computed. Removing the sensitive spans from the stored TEXT afterward leaves the leak in the VECTOR STORE untouched. Redaction must precede embedding to matter. Option B is wrong: the issue is not vector quality but information already encoded. Option C is wrong: vector stores do store the vectors, and the vectors carry the information. Option D is wrong for the same reason — the text removal does not undo the vector.';

-- Q15
UPDATE questions SET explanation =
  'Redaction changes retrieval: a redacted document embeds differently, and a query that names the redacted entity retrieves it less well — a cost paid at ingest and invisible unless the eval set contains queries naming the redacted fields. Redaction also does not address concentration risk: a corpus with one document per person leaks by membership even when each document is individually clean. The ''reversible later'' option is wrong: redaction is IRREVERSIBLE — you cannot recover a redacted span without re-ingesting from source. The ''only matters when the store is shared'' option is wrong: the concern applies to any corpus whose vectors could be inverted, not only to a shared vector store.'
WHERE id = 900 AND set_id = 22 AND explanation =
  'Redaction changes retrieval: a redacted document embeds differently, and a query that names the redacted entity retrieves it less well — a cost paid at ingest and invisible unless the eval set contains queries naming the redacted fields. Redaction also does not address concentration risk: a corpus with one document per person leaks by membership even when each document is individually clean. Option C is wrong: redaction is IRREVERSIBLE — you cannot recover a redacted span without re-ingesting from source. Option D is wrong: the concern applies to any corpus whose vectors could be inverted, not only to a shared vector store.';

-- Q16
UPDATE questions SET explanation =
  'Because the inheritance happens at parse time, if the access-control label is added to the parent Document AFTER parsing, no child node ever receives it — the chunks are now unlabeled while the code believes labeling worked. The ''always propagates'' option is wrong (it does not always carry automatically; timing matters). The ''cannot be stored in metadata'' option is wrong (labels can and do live in metadata, which is exactly what inherits). The ''parsing strips metadata'' option is wrong (parsing does not strip metadata; it propagates it).'
WHERE id = 901 AND set_id = 22 AND explanation =
  'Because the inheritance happens at parse time, if the access-control label is added to the parent Document AFTER parsing, no child node ever receives it — the chunks are now unlabeled while the code believes labeling worked. Option B is wrong (it does not always carry automatically; timing matters). Option C is wrong (labels can and do live in metadata, which is exactly what inherits). Option D is wrong (parsing does not strip metadata; it propagates it).';

-- Q17
UPDATE questions SET explanation =
  'If the access-control label is a node metadata field and the cache key is the node+transformation pair, then a change to the ACL alone (same text) may not invalidate the cached node — removing a user''s access would not be reflected. The ACL change must actively re-emit the node with the new label; you cannot assume the cache notices a metadata-only change. The ''automatically detects'' option is wrong: the cache does not auto-detect ACL edits. The ''stored outside the nodes'' option is wrong: the label lives ON the node, not outside it. The ''irrelevant after ingest'' option is wrong: access changes matter after ingest precisely because the cached node is what gets served.'
WHERE id = 902 AND set_id = 22 AND explanation =
  'If the access-control label is a node metadata field and the cache key is the node+transformation pair, then a change to the ACL alone (same text) may not invalidate the cached node — removing a user''s access would not be reflected. The ACL change must actively re-emit the node with the new label; you cannot assume the cache notices a metadata-only change. Option B is wrong: the cache does not auto-detect ACL edits. Option C is wrong: the label lives ON the node, not outside it. Option D is wrong: access changes matter after ingest precisely because the cached node is what gets served.';

-- Q18
UPDATE questions SET explanation =
  'A Transformations stage in the ingestion pipeline that asserts the label is present and raises otherwise turns a silent default-allow into a failed ingest that a human must fix. This is the right place because ingestion is where transformations run and where a missing label can be caught before a node is ever written. The query-time empty-result option defers the problem to query time, after unlabeled nodes already exist. The silent-delete option removes data silently instead of surfacing the defect. The log-a-warning-and-allow option is the exact default-allow failure the rule forbids.'
WHERE id = 903 AND set_id = 22 AND explanation =
  'A Transformations stage in the ingestion pipeline that asserts the label is present and raises otherwise turns a silent default-allow into a failed ingest that a human must fix. This is the right place because ingestion is where transformations run and where a missing label can be caught before a node is ever written. Option B defers the problem to query time, after unlabeled nodes already exist. Option C (delete the node) removes data silently instead of surfacing the defect. Option D (log a warning and default-allow) is the exact default-allow failure the rule forbids.';

-- Q19
UPDATE questions SET explanation =
  'Document-level permission is "cheap and wrong at the margins": one label, one filter, one check, but it fails exactly when a document is internally heterogeneous — the restricted annex and the public clauses share the same label, so granting access to the clauses leaks the annex. The index-level option describes index-level granularity, the span-level option describes span-level, and the field-level option describes field-level redaction — all different granularities, not the one the scenario used.'
WHERE id = 904 AND set_id = 22 AND explanation =
  'Document-level permission is "cheap and wrong at the margins": one label, one filter, one check, but it fails exactly when a document is internally heterogeneous — the restricted annex and the public clauses share the same label, so granting access to the clauses leaks the annex. Option B describes index-level granularity, Option C describes span-level, and Option D describes field-level redaction — all different granularities, not the one the scenario used.';

-- Q20
UPDATE questions SET explanation =
  'The restricted region ends up inside an unrestricted node, so the restricted content ships inside the unrestricted document. This is worse than never claiming span-level because the team''s threat model now contains a hole it has decided it does not need to look at: they believe a boundary is enforced, and it is not. The ''degrades cleanly to document-level'' option is wrong (it is not equivalent to document-level, which would at least be an honest, uniformly-applied label). The ''parsers always locate section boundaries'' option is wrong (parsers do not always find the boundary — that is the premise). The ''equivalent to field-level redaction'' option is wrong (it is not equivalent to field-level redaction, which is irreversible and removes the text outright).'
WHERE id = 905 AND set_id = 22 AND explanation =
  'The restricted region ends up inside an unrestricted node, so the restricted content ships inside the unrestricted document. This is worse than never claiming span-level because the team''s threat model now contains a hole it has decided it does not need to look at: they believe a boundary is enforced, and it is not. Option B is wrong (it is not equivalent to document-level, which would at least be an honest, uniformly-applied label). Option C is wrong (parsers do not always find the boundary — that is the premise). Option D is wrong (it is not equivalent to field-level redaction, which is irreversible and removes the text outright).';

-- Q21
UPDATE questions SET explanation =
  'Span-level is defensible only where a transformation can reliably locate the boundary in the PARSED STRUCTURE — a heading, an annex section, a table region — so the restricted region is actually split out. It must never be an aspiration that silently degrades to document-level. The ''any parser'' option is wrong: any parser will not do; the parser must reliably find the boundary. The ''LLM finds the boundary'' option is wrong: the boundary must be located at ingest/parse time, not by the LLM at query time. The ''never defensible'' option is wrong: span-level is legitimate where the structural boundary is reliable.'
WHERE id = 906 AND set_id = 22 AND explanation =
  'Span-level is defensible only where a transformation can reliably locate the boundary in the PARSED STRUCTURE — a heading, an annex section, a table region — so the restricted region is actually split out. It must never be an aspiration that silently degrades to document-level. Option B is wrong: any parser will not do; the parser must reliably find the boundary. Option C is wrong: the boundary must be located at ingest/parse time, not by the LLM at query time. Option D is wrong: span-level is legitimate where the structural boundary is reliable.';

-- Q22
UPDATE questions SET explanation =
  'Redacted text is what you retrieve and can cite, and the decision is irreversible: you cannot un-redact — recovering a redacted span requires re-ingesting from source. The ''reversible at query time'' option is wrong (it is not reversible at query time). The ''more permission levels'' option is wrong (redaction reduces, not increases, the number of granularity levels for the redacted field). The ''requires no parsing'' option is wrong: redaction still depends on locating the field, which itself can be a parsing/NER problem.'
WHERE id = 907 AND set_id = 22 AND explanation =
  'Redacted text is what you retrieve and can cite, and the decision is irreversible: you cannot un-redact — recovering a redacted span requires re-ingesting from source. Option B is wrong (it is not reversible at query time). Option C is wrong (redaction reduces, not increases, the number of granularity levels for the redacted field). Option D is wrong: redaction still depends on locating the field, which itself can be a parsing/NER problem.';

-- Q23
UPDATE questions SET explanation =
  'Filters constrain READS, not WRITES: a filter cannot stop a document from being stored in the wrong region in the first place, and residency law is about the physical storage location. Only pinning the store and the embedding/generation endpoints to a region satisfies it. The ''too slow'' option is wrong (filters are not too slow; they are the wrong tool). The ''cannot carry region metadata'' option is wrong (filters can carry region metadata — they just cannot enforce physical placement). The ''only read access'' option is wrong (residency is about storage AND processing location, including where text is transmitted).'
WHERE id = 908 AND set_id = 22 AND explanation =
  'Filters constrain READS, not WRITES: a filter cannot stop a document from being stored in the wrong region in the first place, and residency law is about the physical storage location. Only pinning the store and the embedding/generation endpoints to a region satisfies it. Option B is wrong (filters are not too slow; they are the wrong tool). Option C is wrong (filters can carry region metadata — they just cannot enforce physical placement). Option D is wrong (residency is about storage AND processing location, including where text is transmitted).';

-- Q24
UPDATE questions SET explanation =
  'Residency law is about where data is physically stored and where it is transmitted for processing. Tagging documents with a region does not change where they actually live, so a global deployment with region tags still stores data in the wrong places. The ''inherently incorrect'' option is wrong (region metadata is not "always wrong" — it is simply not the same as physical placement). The ''remove all region metadata'' option is wrong (compliance requires controlling physical placement, not avoiding metadata). The query-time region filter option is wrong (filters, again, cannot enforce storage location).'
WHERE id = 909 AND set_id = 22 AND explanation =
  'Residency law is about where data is physically stored and where it is transmitted for processing. Tagging documents with a region does not change where they actually live, so a global deployment with region tags still stores data in the wrong places. Option B is wrong (region metadata is not "always wrong" — it is simply not the same as physical placement). Option C is wrong (compliance requires controlling physical placement, not avoiding metadata). Option D is wrong (filters, again, cannot enforce storage location).';

-- Q25
UPDATE questions SET explanation =
  'Three real surfaces matter: (1) where node text and vectors physically live (the vector/document store); (2) where text is transmitted for embedding (the embedding call); and (3) where prompt text containing retrieved evidence is transmitted (the generation call). The query-time filter option is wrong: a per-region filter applied at query time constrains reads, not where data is stored. The metadata-tag option is wrong: a region metadata tag on each document is a label, not physical placement.'
WHERE id = 910 AND set_id = 22 AND explanation =
  'Three real surfaces matter: (1) where node text and vectors physically live (the vector/document store); (2) where text is transmitted for embedding (the embedding call); and (3) where prompt text containing retrieved evidence is transmitted (the generation call). Option D is wrong: a per-region filter applied at query time constrains reads, not where data is stored. Option E is wrong: a region metadata tag on each document is a label, not physical placement.';

-- Q26
UPDATE questions SET explanation =
  'The backstop''s job is a per-request deny: after retrieval it drops every node this principal may not read, so the guessed clause never reaches synthesis. The pushed-down filter only narrows which documents the store returns; whatever it admits is not re-examined, so it removes nothing. The ''only reorders the candidates'' option describes reordering, which is the reranker''s job and removes nothing. The ''filter does remove the node'' option misplaces the filter''s stage and role — the filter runs at retrieval and never removes nodes at any stage. The ''rewrites the user''s permissions'' option is wrong because the backstop operates on retrieved nodes, not on the user''s permissions.'
WHERE id = 911 AND set_id = 22 AND explanation =
  'The backstop''s job is a per-request deny: after retrieval it drops every node this principal may not read, so the guessed clause never reaches synthesis. The pushed-down filter only narrows which documents the store returns; whatever it admits is not re-examined, so it removes nothing. Option B describes reordering, which is the reranker''s job and removes nothing. Option C misplaces the filter''s stage and role — the filter runs at retrieval and never removes nodes at any stage. Option D is wrong because the backstop operates on retrieved nodes, not on the user''s permissions.';

-- Q27
UPDATE questions SET explanation =
  'On benign queries the filter-only and backstop configurations perform identically, because the model-proposed relevance filters are usually right and the store usually honors them. The two configurations diverge only on adversarial queries, which a quality harness does not contain. So "users never complained about leakage" is not evidence of anything. The ''do not measure retrieval quality'' option is wrong (quality metrics do measure retrieval quality; they just don''t include attacks). The ''differently phrased queries'' option is wrong (the divergence is about benign vs adversarial queries, not different query phrasing). The ''benign queries are rare'' option is wrong (benign queries are the common case, not rare).'
WHERE id = 912 AND set_id = 22 AND explanation =
  'On benign queries the filter-only and backstop configurations perform identically, because the model-proposed relevance filters are usually right and the store usually honors them. The two configurations diverge only on adversarial queries, which a quality harness does not contain. So "users never complained about leakage" is not evidence of anything. Option B is wrong (quality metrics do measure retrieval quality; they just don''t include attacks). Option C is wrong (the divergence is about benign vs adversarial queries, not different query phrasing). Option D is wrong (benign queries are the common case, not rare).';

-- Q28
UPDATE questions SET explanation =
  'The backstop answers exactly one question — "may this principal read this node?" — and this attack abuses a different boundary: the node''s text is itself a set of instructions that can induce an over-broad retrieval or a tool call. "Is this node''s text instructions?" is a prompt-injection control, not a permission control. The ''fully blocks'' option is wrong (the backstop does not block it — the module marks it as only partially mitigated and owned elsewhere). The ''does not actually exist'' option is wrong (injection is real and studied). The cache-keying option is wrong (it is not a cache problem; it is an instruction/data boundary problem).'
WHERE id = 913 AND set_id = 22 AND explanation =
  'The backstop answers exactly one question — "may this principal read this node?" — and this attack abuses a different boundary: the node''s text is itself a set of instructions that can induce an over-broad retrieval or a tool call. "Is this node''s text instructions?" is a prompt-injection control, not a permission control. Option B is wrong (the backstop does not block it — the module marks it as only partially mitigated and owned elsewhere). Option C is wrong (injection is real and studied). Option D is wrong (it is not a cache problem; it is an instruction/data boundary problem).';

-- Q29
UPDATE questions SET explanation =
  'The backstop protects exactly the SET of nodes handed to the synthesizer by dropping unreadable nodes. A cross-tenant summary is a single node whose own text is the union of several tenants'' content: even when the node legitimately passes the querying principal''s permission, its text still contains other tenants'' material. The leak is INSIDE the node''s text, not in whether the node was retrieved or readable. The ''backstop is disabled'' option is wrong (the backstop is not disabled for summaries). The ''never materialized as nodes'' option is wrong (summaries are nodes). The cache-bypass option is wrong (the text is the problem, not a caching artifact).'
WHERE id = 914 AND set_id = 22 AND explanation =
  'The backstop protects exactly the SET of nodes handed to the synthesizer by dropping unreadable nodes. A cross-tenant summary is a single node whose own text is the union of several tenants'' content: even when the node legitimately passes the querying principal''s permission, its text still contains other tenants'' material. The leak is INSIDE the node''s text, not in whether the node was retrieved or readable. Option B is wrong (the backstop is not disabled for summaries). Option C is wrong (summaries are nodes). Option D is wrong (the text is the problem, not a caching artifact).';

-- Q30
UPDATE questions SET explanation =
  'This is the document-existence inference from a "no results" response: it is inherent and only partially mitigated under every configuration, because any honest distinction between "forbidden" and "absent" leaks existence. The mitigation is to make refusals uniform. The ''fully blocked'' option is wrong (the backstop cannot hide the difference if the response reveals it). The semantic-cache option is wrong (it is not a cache leak). The timing-side-channel option is wrong (it is related to but distinct from a timing side channel; the leak here is the response content, not its timing).'
WHERE id = 915 AND set_id = 22 AND explanation =
  'This is the document-existence inference from a "no results" response: it is inherent and only partially mitigated under every configuration, because any honest distinction between "forbidden" and "absent" leaks existence. The mitigation is to make refusals uniform. Option B is wrong (the backstop cannot hide the difference if the response reveals it). Option C is wrong (it is not a cache leak). Option D is wrong (it is related to but distinct from a timing side channel; the leak here is the response content, not its timing).';

-- Q31
UPDATE questions SET explanation =
  'Two of the listed vectors are outside the retrieval boundary: (1) inferring another tenant''s document from a trace or audit record — that store is a compliance artifact, not a retrieval hop; and (2) the timing side channel between permitted and forbidden queries — that is out of scope at the application layer. Asking directly for another client''s rate card and guessing a clause for the system to confirm are inside the boundary: a direct rate-card request and a clause-confirmation query are both stopped by the backstop dropping the node, so engineering in the retrieval path does close them.'
WHERE id = 916 AND set_id = 22 AND explanation =
  'Two of the listed vectors are outside the retrieval boundary: (1) inferring another tenant''s document from a trace or audit record — that store is a compliance artifact, not a retrieval hop; and (2) the timing side channel between permitted and forbidden queries — that is out of scope at the application layer. Options C and D are inside the boundary: a direct rate-card request and a clause-confirmation query are both stopped by the backstop dropping the node, so engineering in the retrieval path does close them.';

-- Q32
UPDATE questions SET explanation =
  'The defect only appears when the evaluation harness is sliced by principal: the index-wide quality number averages over principals, so a narrow principal''s degraded answer rate is hidden inside a healthy aggregate. Measuring it is a new evaluation obligation. The ''narrow principals are rare'' option is wrong (narrow principals are common, not rare). The ''visible in every default quality report'' option is wrong (it is NOT visible in every report — it is invisible unless sliced). The ''does not actually happen'' option is wrong (it happens precisely because the backstop removes nodes the principal may not read).'
WHERE id = 917 AND set_id = 22 AND explanation =
  'The defect only appears when the evaluation harness is sliced by principal: the index-wide quality number averages over principals, so a narrow principal''s degraded answer rate is hidden inside a healthy aggregate. Measuring it is a new evaluation obligation. Option B is wrong (narrow principals are common, not rare). Option C is wrong (it is NOT visible in every report — it is invisible unless sliced). Option D is wrong (it happens precisely because the backstop removes nodes the principal may not read).';

-- Q33
UPDATE questions SET explanation =
  'The three honest mitigations are: rewrite the query against the readable scope; offer a per-principal corpus summary (the tenancy-safe version of a community summary); and TELL the user that results were filtered, so a silent degradation becomes an explainable one. The relax-the-backstop option is wrong: relaxing the backstop trades a recall loss for a breach, which is never the fix. The pre-partition option is wrong: pre-partitioning per tenant is the reversal if the answer rate drops below the abandonment threshold, not a mitigation applied within the shared-index architecture.'
WHERE id = 918 AND set_id = 22 AND explanation =
  'The three honest mitigations are: rewrite the query against the readable scope; offer a per-principal corpus summary (the tenancy-safe version of a community summary); and TELL the user that results were filtered, so a silent degradation becomes an explainable one. Option D is wrong: relaxing the backstop trades a recall loss for a breach, which is never the fix. Option E is wrong: pre-partitioning per tenant is the reversal if the answer rate drops below the abandonment threshold, not a mitigation applied within the shared-index architecture.';

-- Q34
UPDATE questions SET explanation =
  'Even inside a single tenant''s index there are intra-tenant permissions: a client''s own users are not uniformly entitled to that client''s every document (for example, a junior analyst vs a compliance officer). So per-tenant isolation still needs the backstop. The ''cheaper'' option is wrong (per-tenant indexes multiply storage and maintenance cost). The ''do not exist'' option is wrong (intra-tenant permissions are real). The ''remove the need for any access-control labels'' option is wrong (per-tenant indexes do not remove access-control labels; they add an index-identity label while still needing per-node checks).'
WHERE id = 919 AND set_id = 22 AND explanation =
  'Even inside a single tenant''s index there are intra-tenant permissions: a client''s own users are not uniformly entitled to that client''s every document (for example, a junior analyst vs a compliance officer). So per-tenant isolation still needs the backstop. Option B is wrong (per-tenant indexes multiply storage and maintenance cost). Option C is wrong (intra-tenant permissions are real). Option D is wrong (per-tenant indexes do not remove access-control labels; they add an index-identity label while still needing per-node checks).';

-- Q35
UPDATE questions SET explanation =
  'The decision reverses if a contractual term forbids a shared index outright, or if the red-team test surfaces a leak class the backstop cannot see — in either case the isolation level moves, but the backstop does not. The latency, maintenance-cost and modest-recall-drop options are wrong: slower queries, higher cost, or a modest recall regression are costs to manage, not the named reversal conditions.'
WHERE id = 920 AND set_id = 22 AND explanation =
  'The decision reverses if a contractual term forbids a shared index outright, or if the red-team test surfaces a leak class the backstop cannot see — in either case the isolation level moves, but the backstop does not. Options B, C, and D are wrong: slower queries, higher cost, or a modest recall regression are costs to manage, not the named reversal conditions.';

-- Q36
UPDATE questions SET explanation =
  'The answer reconstructed from a rotating log is not an answer: the record must be per-answer, immutable for the retention window, and complete enough to reconstruct the decision without re-running it. It is the record that proves the control ran and permits reconstruction. The ''never stored'' option is wrong (the record is retained precisely because answers are not sufficient on their own). The ''smaller than the full answer'' option is wrong (the record is not valued for being smaller; it is valued for being complete and immutable). The re-running option is wrong (re-running is NOT a valid substitute, for the reasons above).'
WHERE id = 921 AND set_id = 22 AND explanation =
  'The answer reconstructed from a rotating log is not an answer: the record must be per-answer, immutable for the retention window, and complete enough to reconstruct the decision without re-running it. It is the record that proves the control ran and permits reconstruction. Option B is wrong (the record is retained precisely because answers are not sufficient on their own). Option C is wrong (the record is not valued for being smaller; it is valued for being complete and immutable). Option D is wrong (re-running is NOT a valid substitute, for the reasons above).';

-- Q37
UPDATE questions SET explanation =
  'Re-running cannot reproduce the original decision because three things will have changed: the corpus (documents are ingested and deleted over time), the model (a provider may change it beneath a pinned API), and the serving path (the cache may have served the answer with no retrieval at all). The ''always reproduces the exact same answer'' option is wrong: re-running is not deterministic across time — it is exactly the drift that defeats it.'
WHERE id = 922 AND set_id = 22 AND explanation =
  'Re-running cannot reproduce the original decision because three things will have changed: the corpus (documents are ingested and deleted over time), the model (a provider may change it beneath a pinned API), and the serving path (the cache may have served the answer with no retrieval at all). Option D is wrong: re-running is not deterministic across time — it is exactly the drift that defeats it.';

-- Q38
UPDATE questions SET explanation =
  'The record needs the authorized and denied node identifiers with the denial reason — a denial proves the authorization control actually ran — and the access-control-list version / policy snapshot so a later complaint can be judged against the ACL state that was in force. The full-prompt-text option is wrong: the module argues prompt text is retained only for a short debugging window, not the full regulatory window. The sampling-temperature option is wrong: the record carries the model id + version (and hashes), but the sampling temperature is not a required field.'
WHERE id = 923 AND set_id = 22 AND explanation =
  'The record needs the authorized and denied node identifiers with the denial reason — a denial proves the authorization control actually ran — and the access-control-list version / policy snapshot so a later complaint can be judged against the ACL state that was in force. Option C is wrong: the module argues prompt text is retained only for a short debugging window, not the full regulatory window. Option D is wrong: the record carries the model id + version (and hashes), but the sampling temperature is not a required field.';

-- Q39
UPDATE questions SET explanation =
  'A structured record — identifiers, hashes, and access-control decisions — is retained for the full regulatory window, while prompt/response TEXT is retained only for a short debugging window with node text redacted at the trace boundary. The option giving full text the long window and the record the short one reverses the split. The both-short option keeps both short. The both-long option keeps both long (which would convert every debugging convenience into a second unstructured copy of tenant evidence).'
WHERE id = 924 AND set_id = 22 AND explanation =
  'A structured record — identifiers, hashes, and access-control decisions — is retained for the full regulatory window, while prompt/response TEXT is retained only for a short debugging window with node text redacted at the trace boundary. Option B reverses the split. Option C keeps both short. Option D keeps both long (which would convert every debugging convenience into a second unstructured copy of tenant evidence).';

-- Q40
UPDATE questions SET explanation =
  'Two costs follow: (1) reconstructing an old complaint after the short window requires the source documents and the index snapshot, so it takes hours rather than seconds; and (2) a hash alone cannot prove the CONTENT of an answer to a third party without the text. The ''costs nothing'' option is wrong (it costs real reconstruction effort, not nothing). The ''violates legal retention obligations'' option is wrong (the split is chosen to satisfy retention obligations, not to violate them).'
WHERE id = 925 AND set_id = 22 AND explanation =
  'Two costs follow: (1) reconstructing an old complaint after the short window requires the source documents and the index snapshot, so it takes hours rather than seconds; and (2) a hash alone cannot prove the CONTENT of an answer to a third party without the text. Option C is wrong (it costs real reconstruction effort, not nothing). Option D is wrong (the split is chosen to satisfy retention obligations, not to violate them).';

-- Q41
UPDATE questions SET explanation =
  'Derived artifacts include outputs the system itself authored — community summaries, cached answers, and synthesized evaluation references — and these persist independently of the source document. Deleting them requires a derivation/lineage graph that enumerates every copy. The re-run option is wrong: re-running only proves current absence; it deletes nothing. The ''delete only the source document'' option is wrong: derived artifacts are independent copies and are not purged automatically with the source. The blocklist option is wrong: a blocklist hides a document from retrieval but does not erase it, so it cannot satisfy an erasure request.'
WHERE id = 926 AND set_id = 22 AND explanation =
  'Derived artifacts include outputs the system itself authored — community summaries, cached answers, and synthesized evaluation references — and these persist independently of the source document. Deleting them requires a derivation/lineage graph that enumerates every copy. Option B is wrong: re-running only proves current absence; it deletes nothing. Option C is wrong: derived artifacts are independent copies and are not purged automatically with the source. Option D is wrong: a blocklist hides a document from retrieval but does not erase it, so it cannot satisfy an erasure request.';

-- Q42
UPDATE questions SET explanation =
  'Deletion must walk the derivation graph, so a lineage record from document to chunk to summary to cache entry must exist — you have to be able to list every derived copy before you can delete them. The full-text-search-index option is wrong (a full-text search index helps retrieval, not enumeration of derived artifacts). The backup option is wrong (a backup is itself a derived artifact to enumerate, not the enumeration mechanism). The active-users option is wrong (a list of active users is irrelevant to derivation lineage).'
WHERE id = 927 AND set_id = 22 AND explanation =
  'Deletion must walk the derivation graph, so a lineage record from document to chunk to summary to cache entry must exist — you have to be able to list every derived copy before you can delete them. Option B is wrong (a full-text search index helps retrieval, not enumeration of derived artifacts). Option C is wrong (a backup is itself a derived artifact to enumerate, not the enumeration mechanism). Option D is wrong (a list of active users is irrelevant to derivation lineage).';

-- Q43
UPDATE questions SET explanation =
  'Whether a tombstone satisfies erasure depends on the store''s implementation: the vector may remain physically present and influence nothing, or may not. Because erasure law turns on what actually remains, the question must be asked of the store and its semantics, not assumed. The ''always a full physical deletion'' option is wrong (tombstones are not always full deletion — that is the uncertainty). The ''never use tombstones'' option is wrong (ANN structures do use tombstones for removal). The ''inherently illegal'' option is wrong (tombstones are not inherently illegal; their legal status depends on the store).'
WHERE id = 928 AND set_id = 22 AND explanation =
  'Whether a tombstone satisfies erasure depends on the store''s implementation: the vector may remain physically present and influence nothing, or may not. Because erasure law turns on what actually remains, the question must be asked of the store and its semantics, not assumed. Option B is wrong (tombstones are not always full deletion — that is the uncertainty). Option C is wrong (ANN structures do use tombstones for removal). Option D is wrong (tombstones are not inherently illegal; their legal status depends on the store).';

-- Q44
UPDATE questions SET explanation =
  'The model. If the text was ever used for fine-tuning, or shipped to a provider that retains it, deletion from your index is not erasure from the system — which makes provider data-handling terms a compliance control, not a procurement detail. The backup, chunk and embedding options are all reachable by the deletion chain, even if backups only age out over time.'
WHERE id = 929 AND set_id = 22 AND explanation =
  'The model. If the text was ever used for fine-tuning, or shipped to a provider that retains it, deletion from your index is not erasure from the system — which makes provider data-handling terms a compliance control, not a procurement detail. Options B, C, and D (backups, chunks, embeddings) are all reachable by the deletion chain, even if backups only age out over time.';

-- Q45
UPDATE questions SET explanation =
  'The stages transmit different things: the query-embedding stage transmits a query, while the synthesis stage transmits retrieved evidence, which IS the corpus. A deployment can have acceptable terms for embedding and unacceptable terms for generation — and this is only discoverable if you have written down what each call site sends. The ''same text'' option is wrong (stages transmit different content). The single-vendor option is wrong (a single vendor may not have acceptable terms for every stage). The ''providers do not differ'' option is wrong (providers differ on training-on-inputs, retention, subprocessors, and more).'
WHERE id = 930 AND set_id = 22 AND explanation =
  'The stages transmit different things: the query-embedding stage transmits a query, while the synthesis stage transmits retrieved evidence, which IS the corpus. A deployment can have acceptable terms for embedding and unacceptable terms for generation — and this is only discoverable if you have written down what each call site sends. Option B is wrong (stages transmit different content). Option C is wrong (a single vendor may not have acceptable terms for every stage). Option D is wrong (providers differ on training-on-inputs, retention, subprocessors, and more).';

-- Q46
UPDATE questions SET explanation =
  'Three data-handling terms matter: training-on-inputs (whether your corpus becomes someone''s training data); the retention window / zero-retention options (how long prompt and response text live provider-side); and client SDK logging (whether YOUR client writes prompts to disk — the leak nobody audits). The uptime-SLA option is wrong: an uptime SLA is an operational term, not a data-handling term. The programming-languages option is wrong: the provider''s supported programming languages are irrelevant to what happens to your data.'
WHERE id = 931 AND set_id = 22 AND explanation =
  'Three data-handling terms matter: training-on-inputs (whether your corpus becomes someone''s training data); the retention window / zero-retention options (how long prompt and response text live provider-side); and client SDK logging (whether YOUR client writes prompts to disk — the leak nobody audits). Option D is wrong: an uptime SLA is an operational term, not a data-handling term. Option E is wrong: the provider''s supported programming languages are irrelevant to what happens to your data.';

-- Q47
UPDATE questions SET explanation =
  'They solve different problems. Model-level enforcement suits a fine-tuned model over siloed data where retrieval is not in the loop at all; the module assumes a shared index where evidence is retrieved per request. If an architecture has BOTH a fine-tuned model and retrieval, it needs model-level enforcement AND the backstop. The ''Permissioned LLMs are simply wrong'' option is wrong (the module does not dismiss the Permissioned-LLM line outright). The ''module''s position is simply wrong'' option is wrong (the module is not "wrong"; the two positions are reconciled). The ''same thing'' option is wrong (they are not the same thing — they address different architectures).'
WHERE id = 932 AND set_id = 22 AND explanation =
  'They solve different problems. Model-level enforcement suits a fine-tuned model over siloed data where retrieval is not in the loop at all; the module assumes a shared index where evidence is retrieved per request. If an architecture has BOTH a fine-tuned model and retrieval, it needs model-level enforcement AND the backstop. Option B is wrong (the module does not dismiss the Permissioned-LLM line outright). Option C is wrong (the module is not "wrong"; the two positions are reconciled). Option D is wrong (they are not the same thing — they address different architectures).';

-- Q48
UPDATE questions SET explanation =
  'The paper''s instrument is a statistical measure over public datasets, not a per-request deny decision with an audit record — and an audit record is what a regulator asks for. The ''too expensive'' option is wrong (it is not merely too expensive; it is the wrong kind of artifact). The ''not a statistical measure'' option is wrong (it IS statistical — that is the point of the objection). The ''equivalent to the backstop'' option is wrong (it is not the same as the backstop; it measures leakage risk, it does not deny nodes per request).'
WHERE id = 933 AND set_id = 22 AND explanation =
  'The paper''s instrument is a statistical measure over public datasets, not a per-request deny decision with an audit record — and an audit record is what a regulator asks for. Option B is wrong (it is not merely too expensive; it is the wrong kind of artifact). Option C is wrong (it IS statistical — that is the point of the objection). Option D is wrong (it is not the same as the backstop; it measures leakage risk, it does not deny nodes per request).';

-- Q49
UPDATE questions SET explanation =
  'At roughly 80%, about one in five generated policies is partly wrong, and a wrong policy is either a breach (over-permission) or an outage (under-permission). That error rate is fine for a draft, fatal for the enforcement layer. The ''always correct'' option is wrong (it is not always correct). The ''humans make more errors'' option is wrong (humans are not uniformly worse — the point is the error rate, whoever drafts). The ''80% accuracy is sufficient'' option is wrong (80% is not enough to enforce behind a strict flag).'
WHERE id = 934 AND set_id = 22 AND explanation =
  'At roughly 80%, about one in five generated policies is partly wrong, and a wrong policy is either a breach (over-permission) or an outage (under-permission). That error rate is fine for a draft, fatal for the enforcement layer. Option B is wrong (it is not always correct). Option C is wrong (humans are not uniformly worse — the point is the error rate, whoever drafts). Option D is wrong (80% is not enough to enforce behind a strict flag).';

-- Q50
UPDATE questions SET explanation =
  'The backstop answers "may this principal read this node?" It does NOT answer "is this node''s text a set of instructions?" An injected instruction in retrieved content can itself induce an over-broad retrieval or a tool call, so injection and scope leak can be the same incident — but they are two controls, and pretending one covers the other leaves neither in place. The recency, index-membership and length options are all facts the backstop simply does not assess; they are not the injection-relevant boundary.'
WHERE id = 935 AND set_id = 22 AND explanation =
  'The backstop answers "may this principal read this node?" It does NOT answer "is this node''s text a set of instructions?" An injected instruction in retrieved content can itself induce an over-broad retrieval or a tool call, so injection and scope leak can be the same incident — but they are two controls, and pretending one covers the other leaves neither in place. Options B, C, and D are all facts the backstop simply does not assess; they are not the injection-relevant boundary.';

-- Q51
UPDATE questions SET explanation =
  'Two conclusions hold: (1) redaction is necessary but insufficient — the controls that survive the leakage finding are structural (the vector store''s own access control, tenancy-scoped stores, not storing unneeded vectors), with residual leakage recorded as an accepted risk; and (2) "we redacted" is not the end of the argument. The ''can ship behind a strict enforcement flag'' option is wrong: the module explicitly says an 80%-class policy translator cannot ship behind a strict flag. The ''replaces the post-retrieval check'' option is wrong: a Permissioned LLM is not a substitute for the post-retrieval check.'
WHERE id = 936 AND set_id = 22 AND explanation =
  'Two conclusions hold: (1) redaction is necessary but insufficient — the controls that survive the leakage finding are structural (the vector store''s own access control, tenancy-scoped stores, not storing unneeded vectors), with residual leakage recorded as an accepted risk; and (2) "we redacted" is not the end of the argument. Option C is wrong: the module explicitly says an 80%-class policy translator cannot ship behind a strict flag. Option D is wrong: a Permissioned LLM is not a substitute for the post-retrieval check.';

-- Q52
UPDATE questions SET explanation =
  'The number of query engines in a codebase is the number of places the backstop can be forgotten, so query engines should be constructed in exactly one factory function that attaches the backstop everywhere by construction — including the sub-engines inside a sub-question engine and the retrieval tool inside an agent. The remember-to-pass, sub-engines-inherit and README options rely on memory, assumed inheritance, or documentation — each of which fails.'
WHERE id = 937 AND set_id = 22 AND explanation =
  'The number of query engines in a codebase is the number of places the backstop can be forgotten, so query engines should be constructed in exactly one factory function that attaches the backstop everywhere by construction — including the sub-engines inside a sub-question engine and the retrieval tool inside an agent. Options B, C, and D rely on memory, assumed inheritance, or documentation — each of which fails.';

-- Q56
UPDATE questions SET explanation =
  'Each manifest row carries every `Doc` field EXCEPT the full text — so it includes `doc_id`, `source_type`, `title`, `jurisdiction`, `client_id`, `effective_date`, `version`, `supersedes`, and `metadata`. The manifest is a metadata/lineage index of the corpus, not the corpus content itself. The full-text-only, doc_id-and-title and embeddings options each misstate what survives the `text` removal.'
WHERE id = 941 AND set_id = 22 AND explanation =
  'Each manifest row carries every `Doc` field EXCEPT the full text — so it includes `doc_id`, `source_type`, `title`, `jurisdiction`, `client_id`, `effective_date`, `version`, `supersedes`, and `metadata`. The manifest is a metadata/lineage index of the corpus, not the corpus content itself. Options B, C, and D each misstate what survives the `text` removal.';

-- Q58
UPDATE questions SET explanation =
  'Near-duplicate documents whose overlapping text spans jurisdictions: a naive dedup can collapse them, and a naive cross-jurisdiction retrieval can conflate one tenant''s manual with another''s. This is the tenancy + dedup problem, not a size reduction. The ''smaller corpus'' option is wrong (it adds near-duplicates, not smaller size). The ''each manual unique'' option is wrong (it makes manuals more alike, not unique). The ''removes the need for jurisdiction filters'' option is wrong (it creates, rather than removes, the need for jurisdiction filters).'
WHERE id = 943 AND set_id = 22 AND explanation =
  'Near-duplicate documents whose overlapping text spans jurisdictions: a naive dedup can collapse them, and a naive cross-jurisdiction retrieval can conflate one tenant''s manual with another''s. This is the tenancy + dedup problem, not a size reduction. Option B is wrong (it adds near-duplicates, not smaller size). Option C is wrong (it makes manuals more alike, not unique). Option D is wrong (it creates, rather than removes, the need for jurisdiction filters).';

-- Q60
UPDATE questions SET explanation =
  '`"ALL"` means "shared across all clients" — still subject to jurisdiction and any other filters, and still authorized per principal at query time. It is a specific access-control label, not a signal to skip authorization. Treating it as default-allow would let any principal read any shared regulation without a check; treating it as "no one may read" would deny everyone. The ''no owner'' option is wrong because "ALL" is not "no owner". The ''public to everyone'' option is wrong because the shared docs still need per-principal authorization and jurisdiction filtering. The ''readable by no one'' option is wrong because "ALL" denotes shared, not unreadable.'
WHERE id = 945 AND set_id = 22 AND explanation =
  '`"ALL"` means "shared across all clients" — still subject to jurisdiction and any other filters, and still authorized per principal at query time. It is a specific access-control label, not a signal to skip authorization. Treating it as default-allow would let any principal read any shared regulation without a check; treating it as "no one may read" would deny everyone. Option B is wrong because "ALL" is not "no owner". Option C is wrong because the shared docs still need per-principal authorization and jurisdiction filtering. Option D is wrong because "ALL" denotes shared, not unreadable.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 22
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'Propagation means getting access-control labels onto documents, nodes, and queries so the pipeline can narrow its work; it is best-effort and may be proposed by a model. Authorization means proving, for every request, that each node reaching the prompt was readable by THIS principal at query time. A filter inferred from a query is a relevance hint, not a permission proof. The ''applied too early in the pipeline'' option is wrong because the defect is not the stage at which the filter runs but the role it was given; the same filter is unsafe no matter where it sits. The ''interchangeable'' option is wrong because the two roles are not interchangeable. The option making propagation the per-request proof reverses the two definitions outright.',
    'The post-retrieval authorization backstop is the only deny: it sits after retrieval and before synthesis and drops every node the requesting principal may not read. Everything upstream — the pushed-down metadata filter and the reranker — only reduces or reorders work and removes nothing. The cache is a stored earlier verdict, not a live deny. The metadata-filter, reranker and response-cache options each name a real component that does NOT enforce the "no": the push-down filter is an optimization, the reranker reorders rather than removes, and the cache replays a prior decision instead of making a fresh one.',
    'Propagation''s failure is a quality problem — slower queries, recall loss, or over-retrieval that a later check then removes — never a breach. And propagation MAY be delegated to a model (the LLM may propose filters). Authorization is the opposite on both axes: it never trusts anything upstream, its failure IS a breach, and it may never be delegated. The ''must never be delegated'' option is false because that is authorization''s property, not propagation''s. The ''runs only at query time'' option is false because propagation runs at ingest time and query time, while authorization runs only at query time after retrieval.',
    'A security control for permissions must be able to say "no" and remove a node. Reranking only changes the ORDER of the candidate set; it removes nothing, so it cannot enforce a deny decision no matter how good its scores are. The ''runs before retrieval'' option is factually wrong: reranking runs after retrieval, on the retrieved set. The ''derived from access-control labels'' option is wrong: reranker scores are relevance scores, not derived from any ACL. The ''weaker security control'' option is wrong: reranking is not a weaker security control — it is not a security control at all, because it has no removal step.',
    'Placing the authorization backstop AFTER retrieval means a narrow principal''s top-k is diluted by nodes they may not read, so their effective recall is lower than the index-wide figure. That is a cost of the backstop''s placement, and the push-down filter exists to shrink it — the store does the narrowing so the backstop corrects instead of deleting nearly everything. The storage-bug option is wrong: this configuration uses one shared index, not multiplied storage. The ''metadata filters are no longer needed'' option is wrong: the backstop does not remove the need for metadata filters; it is the reason the push-down filter is worth keeping. The latency-regression option is wrong: the penalty is a recall/coverage problem for the principal, not a slower index rebuild.',
    'The push-down filter is a cost optimization, not a security control: it makes the store do the narrowing so that, for a narrow principal, the backstop is a correction rather than a near-total deletion, and it reduces the retrieval cost of an over-broad query. The ''actually drops the unreadable nodes'' option is wrong because dropping unreadable nodes is exactly the backstop''s job, not the filter''s. The ''guarantees no cross-tenant leak'' option is wrong because the filter alone never guarantees no scope leak — that is the module''s entire argument.',
    'If a cache entry is a stored authorization verdict, it must be re-validated for the principal presenting it, or keyed so only principals with identical access-control lists can share it: key every entry on (tenant, ACL hash) and invalidate on any ACL change. Never serve one user''s answer to another user with different permissions. The ''semantically similar'' option is wrong for exactly the reason stated — semantic similarity does not imply equal permissions. The ''skip authorization'' option is wrong because serving from cache skips retrieval but must NOT skip authorization. The ''query vector alone'' option is wrong: keying on the query vector alone is the semantic key that ignores the principal and is precisely the defect.',
    'This is the semantic response cache: it is keyed on query semantics rather than on the principal, so a second user asking a semantically similar question gets the first user''s answer with every node already filtered for the first user. No retrieval happens, so the post-retrieval backstop never runs. The fix is keying on (tenant, ACL hash) and invalidating on ACL change. The trace/span-log option leaks stored prompts, not replayed answers. The community-summary option leaks aggregated text, not cached responses. The embedding-inversion option recovers words from vectors, unrelated to serving a cached answer.',
    'A summary is a derived document whose text is the union of what its member entities'' readers may see. If it spans different access-control lists, no single ACL correctly describes who may read all of it, so the safe rule is deny-by-default: the summary inherits the INTERSECTION of its members'' ACLs, and a summary that would span tenants must not be built at all. The union option would grant the most-permissive reader''s access to everyone. The largest-member option is arbitrary and equally unsafe. The no-label option (no ACL because it is derived) treats the derived text as if it had no sensitivity, which is exactly wrong.',
    'The summary''s text is a union of what several principals may read. An access-control list must describe exactly who may read a piece of content, and no single list describes "client A''s brokers AND client B''s brokers" without granting each side the other''s content. So a cross-tenant aggregate has no correct owner label. The ''never persisted'' option is false (summaries are stored nodes). The ''no readable text'' option is false (summaries have real text — that is the problem). The ''recomputed per query'' option is false: the summary is a precomputed stored artifact, not re-derived per query, and even if it were re-derived, the union it produces would still cross the boundary.',
    'This is the trace/span log leak: observability stores the retrieved node set, scores, prompts, and responses, so it becomes a second copy of every tenant''s evidence. The controls are to tenant-scope the trace store, redact node text at the span boundary, and treat traces as a regulated data store with its own retention. The response-cache option is the cache (replayed answers), the community-summary option is graph summaries (aggregated text), the embedding-vector option is embedding inversion (recovering words from vectors) — none of these is a log of assembled prompts.',
    'The tool call is made by the SYSTEM, not the end user, so the end user''s session permissions do not automatically travel with it. Every tool call must carry the end-user principal and the tool must re-authorize against it, rather than inheriting a session credential. The option making the end user the principal is wrong because it asserts the user is the principal and the tool inherits credentials — the exact confused-deputy error. The ''tools do not need their own authorization'' option is wrong: tools absolutely need authorization. The option making the model the principal is wrong: the model is the mechanism, not the principal whose rights are being exercised.',
    'An embedding is a lossy but invertible encoding of its input, not a privacy-preserving summary. So sensitive text must be redacted BEFORE embedding: once the vector exists, the information is already encoded in it. The ''redact the stored text after embedding'' option is wrong because redacting the stored text after embedding leaves the leak in the vector store. The ''keep embeddings internal'' option is wrong because the vectors themselves are the leak, so keeping them internal does not remove the risk. The ''redact at query time'' option is wrong because redaction must happen at ingest, before the vector is ever produced, not at query time.',
    'The sensitive information is already inside the vector the moment the embedding is computed. Removing the sensitive spans from the stored TEXT afterward leaves the leak in the VECTOR STORE untouched. Redaction must precede embedding to matter. The lower-quality-vectors option is wrong: the issue is not vector quality but information already encoded. The ''vector stores do not store text'' option is wrong: vector stores do store the vectors, and the vectors carry the information. The ''reversible'' option is wrong for the same reason — the text removal does not undo the vector.',
    'Redaction changes retrieval: a redacted document embeds differently, and a query that names the redacted entity retrieves it less well — a cost paid at ingest and invisible unless the eval set contains queries naming the redacted fields. Redaction also does not address concentration risk: a corpus with one document per person leaks by membership even when each document is individually clean. The ''reversible later'' option is wrong: redaction is IRREVERSIBLE — you cannot recover a redacted span without re-ingesting from source. The ''only matters when the store is shared'' option is wrong: the concern applies to any corpus whose vectors could be inverted, not only to a shared vector store.',
    'Because the inheritance happens at parse time, if the access-control label is added to the parent Document AFTER parsing, no child node ever receives it — the chunks are now unlabeled while the code believes labeling worked. The ''always propagates'' option is wrong (it does not always carry automatically; timing matters). The ''cannot be stored in metadata'' option is wrong (labels can and do live in metadata, which is exactly what inherits). The ''parsing strips metadata'' option is wrong (parsing does not strip metadata; it propagates it).',
    'If the access-control label is a node metadata field and the cache key is the node+transformation pair, then a change to the ACL alone (same text) may not invalidate the cached node — removing a user''s access would not be reflected. The ACL change must actively re-emit the node with the new label; you cannot assume the cache notices a metadata-only change. The ''automatically detects'' option is wrong: the cache does not auto-detect ACL edits. The ''stored outside the nodes'' option is wrong: the label lives ON the node, not outside it. The ''irrelevant after ingest'' option is wrong: access changes matter after ingest precisely because the cached node is what gets served.',
    'A Transformations stage in the ingestion pipeline that asserts the label is present and raises otherwise turns a silent default-allow into a failed ingest that a human must fix. This is the right place because ingestion is where transformations run and where a missing label can be caught before a node is ever written. The query-time empty-result option defers the problem to query time, after unlabeled nodes already exist. The silent-delete option removes data silently instead of surfacing the defect. The log-a-warning-and-allow option is the exact default-allow failure the rule forbids.',
    'Document-level permission is "cheap and wrong at the margins": one label, one filter, one check, but it fails exactly when a document is internally heterogeneous — the restricted annex and the public clauses share the same label, so granting access to the clauses leaks the annex. The index-level option describes index-level granularity, the span-level option describes span-level, and the field-level option describes field-level redaction — all different granularities, not the one the scenario used.',
    'The restricted region ends up inside an unrestricted node, so the restricted content ships inside the unrestricted document. This is worse than never claiming span-level because the team''s threat model now contains a hole it has decided it does not need to look at: they believe a boundary is enforced, and it is not. The ''degrades cleanly to document-level'' option is wrong (it is not equivalent to document-level, which would at least be an honest, uniformly-applied label). The ''parsers always locate section boundaries'' option is wrong (parsers do not always find the boundary — that is the premise). The ''equivalent to field-level redaction'' option is wrong (it is not equivalent to field-level redaction, which is irreversible and removes the text outright).',
    'Span-level is defensible only where a transformation can reliably locate the boundary in the PARSED STRUCTURE — a heading, an annex section, a table region — so the restricted region is actually split out. It must never be an aspiration that silently degrades to document-level. The ''any parser'' option is wrong: any parser will not do; the parser must reliably find the boundary. The ''LLM finds the boundary'' option is wrong: the boundary must be located at ingest/parse time, not by the LLM at query time. The ''never defensible'' option is wrong: span-level is legitimate where the structural boundary is reliable.',
    'Redacted text is what you retrieve and can cite, and the decision is irreversible: you cannot un-redact — recovering a redacted span requires re-ingesting from source. The ''reversible at query time'' option is wrong (it is not reversible at query time). The ''more permission levels'' option is wrong (redaction reduces, not increases, the number of granularity levels for the redacted field). The ''requires no parsing'' option is wrong: redaction still depends on locating the field, which itself can be a parsing/NER problem.',
    'Filters constrain READS, not WRITES: a filter cannot stop a document from being stored in the wrong region in the first place, and residency law is about the physical storage location. Only pinning the store and the embedding/generation endpoints to a region satisfies it. The ''too slow'' option is wrong (filters are not too slow; they are the wrong tool). The ''cannot carry region metadata'' option is wrong (filters can carry region metadata — they just cannot enforce physical placement). The ''only read access'' option is wrong (residency is about storage AND processing location, including where text is transmitted).',
    'Residency law is about where data is physically stored and where it is transmitted for processing. Tagging documents with a region does not change where they actually live, so a global deployment with region tags still stores data in the wrong places. The ''inherently incorrect'' option is wrong (region metadata is not "always wrong" — it is simply not the same as physical placement). The ''remove all region metadata'' option is wrong (compliance requires controlling physical placement, not avoiding metadata). The query-time region filter option is wrong (filters, again, cannot enforce storage location).',
    'Three real surfaces matter: (1) where node text and vectors physically live (the vector/document store); (2) where text is transmitted for embedding (the embedding call); and (3) where prompt text containing retrieved evidence is transmitted (the generation call). The query-time filter option is wrong: a per-region filter applied at query time constrains reads, not where data is stored. The metadata-tag option is wrong: a region metadata tag on each document is a label, not physical placement.',
    'The backstop''s job is a per-request deny: after retrieval it drops every node this principal may not read, so the guessed clause never reaches synthesis. The pushed-down filter only narrows which documents the store returns; whatever it admits is not re-examined, so it removes nothing. The ''only reorders the candidates'' option describes reordering, which is the reranker''s job and removes nothing. The ''filter does remove the node'' option misplaces the filter''s stage and role — the filter runs at retrieval and never removes nodes at any stage. The ''rewrites the user''s permissions'' option is wrong because the backstop operates on retrieved nodes, not on the user''s permissions.',
    'On benign queries the filter-only and backstop configurations perform identically, because the model-proposed relevance filters are usually right and the store usually honors them. The two configurations diverge only on adversarial queries, which a quality harness does not contain. So "users never complained about leakage" is not evidence of anything. The ''do not measure retrieval quality'' option is wrong (quality metrics do measure retrieval quality; they just don''t include attacks). The ''differently phrased queries'' option is wrong (the divergence is about benign vs adversarial queries, not different query phrasing). The ''benign queries are rare'' option is wrong (benign queries are the common case, not rare).',
    'The backstop answers exactly one question — "may this principal read this node?" — and this attack abuses a different boundary: the node''s text is itself a set of instructions that can induce an over-broad retrieval or a tool call. "Is this node''s text instructions?" is a prompt-injection control, not a permission control. The ''fully blocks'' option is wrong (the backstop does not block it — the module marks it as only partially mitigated and owned elsewhere). The ''does not actually exist'' option is wrong (injection is real and studied). The cache-keying option is wrong (it is not a cache problem; it is an instruction/data boundary problem).',
    'The backstop protects exactly the SET of nodes handed to the synthesizer by dropping unreadable nodes. A cross-tenant summary is a single node whose own text is the union of several tenants'' content: even when the node legitimately passes the querying principal''s permission, its text still contains other tenants'' material. The leak is INSIDE the node''s text, not in whether the node was retrieved or readable. The ''backstop is disabled'' option is wrong (the backstop is not disabled for summaries). The ''never materialized as nodes'' option is wrong (summaries are nodes). The cache-bypass option is wrong (the text is the problem, not a caching artifact).',
    'This is the document-existence inference from a "no results" response: it is inherent and only partially mitigated under every configuration, because any honest distinction between "forbidden" and "absent" leaks existence. The mitigation is to make refusals uniform. The ''fully blocked'' option is wrong (the backstop cannot hide the difference if the response reveals it). The semantic-cache option is wrong (it is not a cache leak). The timing-side-channel option is wrong (it is related to but distinct from a timing side channel; the leak here is the response content, not its timing).',
    'Two of the listed vectors are outside the retrieval boundary: (1) inferring another tenant''s document from a trace or audit record — that store is a compliance artifact, not a retrieval hop; and (2) the timing side channel between permitted and forbidden queries — that is out of scope at the application layer. Asking directly for another client''s rate card and guessing a clause for the system to confirm are inside the boundary: a direct rate-card request and a clause-confirmation query are both stopped by the backstop dropping the node, so engineering in the retrieval path does close them.',
    'The defect only appears when the evaluation harness is sliced by principal: the index-wide quality number averages over principals, so a narrow principal''s degraded answer rate is hidden inside a healthy aggregate. Measuring it is a new evaluation obligation. The ''narrow principals are rare'' option is wrong (narrow principals are common, not rare). The ''visible in every default quality report'' option is wrong (it is NOT visible in every report — it is invisible unless sliced). The ''does not actually happen'' option is wrong (it happens precisely because the backstop removes nodes the principal may not read).',
    'The three honest mitigations are: rewrite the query against the readable scope; offer a per-principal corpus summary (the tenancy-safe version of a community summary); and TELL the user that results were filtered, so a silent degradation becomes an explainable one. The relax-the-backstop option is wrong: relaxing the backstop trades a recall loss for a breach, which is never the fix. The pre-partition option is wrong: pre-partitioning per tenant is the reversal if the answer rate drops below the abandonment threshold, not a mitigation applied within the shared-index architecture.',
    'Even inside a single tenant''s index there are intra-tenant permissions: a client''s own users are not uniformly entitled to that client''s every document (for example, a junior analyst vs a compliance officer). So per-tenant isolation still needs the backstop. The ''cheaper'' option is wrong (per-tenant indexes multiply storage and maintenance cost). The ''do not exist'' option is wrong (intra-tenant permissions are real). The ''remove the need for any access-control labels'' option is wrong (per-tenant indexes do not remove access-control labels; they add an index-identity label while still needing per-node checks).',
    'The decision reverses if a contractual term forbids a shared index outright, or if the red-team test surfaces a leak class the backstop cannot see — in either case the isolation level moves, but the backstop does not. The latency, maintenance-cost and modest-recall-drop options are wrong: slower queries, higher cost, or a modest recall regression are costs to manage, not the named reversal conditions.',
    'The answer reconstructed from a rotating log is not an answer: the record must be per-answer, immutable for the retention window, and complete enough to reconstruct the decision without re-running it. It is the record that proves the control ran and permits reconstruction. The ''never stored'' option is wrong (the record is retained precisely because answers are not sufficient on their own). The ''smaller than the full answer'' option is wrong (the record is not valued for being smaller; it is valued for being complete and immutable). The re-running option is wrong (re-running is NOT a valid substitute, for the reasons above).',
    'Re-running cannot reproduce the original decision because three things will have changed: the corpus (documents are ingested and deleted over time), the model (a provider may change it beneath a pinned API), and the serving path (the cache may have served the answer with no retrieval at all). The ''always reproduces the exact same answer'' option is wrong: re-running is not deterministic across time — it is exactly the drift that defeats it.',
    'The record needs the authorized and denied node identifiers with the denial reason — a denial proves the authorization control actually ran — and the access-control-list version / policy snapshot so a later complaint can be judged against the ACL state that was in force. The full-prompt-text option is wrong: the module argues prompt text is retained only for a short debugging window, not the full regulatory window. The sampling-temperature option is wrong: the record carries the model id + version (and hashes), but the sampling temperature is not a required field.',
    'A structured record — identifiers, hashes, and access-control decisions — is retained for the full regulatory window, while prompt/response TEXT is retained only for a short debugging window with node text redacted at the trace boundary. The option giving full text the long window and the record the short one reverses the split. The both-short option keeps both short. The both-long option keeps both long (which would convert every debugging convenience into a second unstructured copy of tenant evidence).',
    'Two costs follow: (1) reconstructing an old complaint after the short window requires the source documents and the index snapshot, so it takes hours rather than seconds; and (2) a hash alone cannot prove the CONTENT of an answer to a third party without the text. The ''costs nothing'' option is wrong (it costs real reconstruction effort, not nothing). The ''violates legal retention obligations'' option is wrong (the split is chosen to satisfy retention obligations, not to violate them).',
    'Derived artifacts include outputs the system itself authored — community summaries, cached answers, and synthesized evaluation references — and these persist independently of the source document. Deleting them requires a derivation/lineage graph that enumerates every copy. The re-run option is wrong: re-running only proves current absence; it deletes nothing. The ''delete only the source document'' option is wrong: derived artifacts are independent copies and are not purged automatically with the source. The blocklist option is wrong: a blocklist hides a document from retrieval but does not erase it, so it cannot satisfy an erasure request.',
    'Deletion must walk the derivation graph, so a lineage record from document to chunk to summary to cache entry must exist — you have to be able to list every derived copy before you can delete them. The full-text-search-index option is wrong (a full-text search index helps retrieval, not enumeration of derived artifacts). The backup option is wrong (a backup is itself a derived artifact to enumerate, not the enumeration mechanism). The active-users option is wrong (a list of active users is irrelevant to derivation lineage).',
    'Whether a tombstone satisfies erasure depends on the store''s implementation: the vector may remain physically present and influence nothing, or may not. Because erasure law turns on what actually remains, the question must be asked of the store and its semantics, not assumed. The ''always a full physical deletion'' option is wrong (tombstones are not always full deletion — that is the uncertainty). The ''never use tombstones'' option is wrong (ANN structures do use tombstones for removal). The ''inherently illegal'' option is wrong (tombstones are not inherently illegal; their legal status depends on the store).',
    'The model. If the text was ever used for fine-tuning, or shipped to a provider that retains it, deletion from your index is not erasure from the system — which makes provider data-handling terms a compliance control, not a procurement detail. The backup, chunk and embedding options are all reachable by the deletion chain, even if backups only age out over time.',
    'The stages transmit different things: the query-embedding stage transmits a query, while the synthesis stage transmits retrieved evidence, which IS the corpus. A deployment can have acceptable terms for embedding and unacceptable terms for generation — and this is only discoverable if you have written down what each call site sends. The ''same text'' option is wrong (stages transmit different content). The single-vendor option is wrong (a single vendor may not have acceptable terms for every stage). The ''providers do not differ'' option is wrong (providers differ on training-on-inputs, retention, subprocessors, and more).',
    'Three data-handling terms matter: training-on-inputs (whether your corpus becomes someone''s training data); the retention window / zero-retention options (how long prompt and response text live provider-side); and client SDK logging (whether YOUR client writes prompts to disk — the leak nobody audits). The uptime-SLA option is wrong: an uptime SLA is an operational term, not a data-handling term. The programming-languages option is wrong: the provider''s supported programming languages are irrelevant to what happens to your data.',
    'They solve different problems. Model-level enforcement suits a fine-tuned model over siloed data where retrieval is not in the loop at all; the module assumes a shared index where evidence is retrieved per request. If an architecture has BOTH a fine-tuned model and retrieval, it needs model-level enforcement AND the backstop. The ''Permissioned LLMs are simply wrong'' option is wrong (the module does not dismiss the Permissioned-LLM line outright). The ''module''s position is simply wrong'' option is wrong (the module is not "wrong"; the two positions are reconciled). The ''same thing'' option is wrong (they are not the same thing — they address different architectures).',
    'The paper''s instrument is a statistical measure over public datasets, not a per-request deny decision with an audit record — and an audit record is what a regulator asks for. The ''too expensive'' option is wrong (it is not merely too expensive; it is the wrong kind of artifact). The ''not a statistical measure'' option is wrong (it IS statistical — that is the point of the objection). The ''equivalent to the backstop'' option is wrong (it is not the same as the backstop; it measures leakage risk, it does not deny nodes per request).',
    'At roughly 80%, about one in five generated policies is partly wrong, and a wrong policy is either a breach (over-permission) or an outage (under-permission). That error rate is fine for a draft, fatal for the enforcement layer. The ''always correct'' option is wrong (it is not always correct). The ''humans make more errors'' option is wrong (humans are not uniformly worse — the point is the error rate, whoever drafts). The ''80% accuracy is sufficient'' option is wrong (80% is not enough to enforce behind a strict flag).',
    'The backstop answers "may this principal read this node?" It does NOT answer "is this node''s text a set of instructions?" An injected instruction in retrieved content can itself induce an over-broad retrieval or a tool call, so injection and scope leak can be the same incident — but they are two controls, and pretending one covers the other leaves neither in place. The recency, index-membership and length options are all facts the backstop simply does not assess; they are not the injection-relevant boundary.',
    'Two conclusions hold: (1) redaction is necessary but insufficient — the controls that survive the leakage finding are structural (the vector store''s own access control, tenancy-scoped stores, not storing unneeded vectors), with residual leakage recorded as an accepted risk; and (2) "we redacted" is not the end of the argument. The ''can ship behind a strict enforcement flag'' option is wrong: the module explicitly says an 80%-class policy translator cannot ship behind a strict flag. The ''replaces the post-retrieval check'' option is wrong: a Permissioned LLM is not a substitute for the post-retrieval check.',
    'The number of query engines in a codebase is the number of places the backstop can be forgotten, so query engines should be constructed in exactly one factory function that attaches the backstop everywhere by construction — including the sub-engines inside a sub-question engine and the retrieval tool inside an agent. The remember-to-pass, sub-engines-inherit and README options rely on memory, assumed inheritance, or documentation — each of which fails.',
    'Each manifest row carries every `Doc` field EXCEPT the full text — so it includes `doc_id`, `source_type`, `title`, `jurisdiction`, `client_id`, `effective_date`, `version`, `supersedes`, and `metadata`. The manifest is a metadata/lineage index of the corpus, not the corpus content itself. The full-text-only, doc_id-and-title and embeddings options each misstate what survives the `text` removal.',
    'Near-duplicate documents whose overlapping text spans jurisdictions: a naive dedup can collapse them, and a naive cross-jurisdiction retrieval can conflate one tenant''s manual with another''s. This is the tenancy + dedup problem, not a size reduction. The ''smaller corpus'' option is wrong (it adds near-duplicates, not smaller size). The ''each manual unique'' option is wrong (it makes manuals more alike, not unique). The ''removes the need for jurisdiction filters'' option is wrong (it creates, rather than removes, the need for jurisdiction filters).',
    '`"ALL"` means "shared across all clients" — still subject to jurisdiction and any other filters, and still authorized per principal at query time. It is a specific access-control label, not a signal to skip authorization. Treating it as default-allow would let any principal read any shared regulation without a check; treating it as "no one may read" would deny everyone. The ''no owner'' option is wrong because "ALL" is not "no owner". The ''public to everyone'' option is wrong because the shared docs still need per-principal authorization and jurisdiction filtering. The ''readable by no one'' option is wrong because "ALL" denotes shared, not unreadable.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, 'Option B (trace/span logs) leaks') > 0
      OR instr(q.explanation, 'Option B (union) would') > 0
      OR instr(q.explanation, 'Option B defers') > 0
      OR instr(q.explanation, 'Option B describes index-level granularity, Option C describes span-level, and Option D describes field-level redaction') > 0
      OR instr(q.explanation, 'Option B describes reordering') > 0
      OR instr(q.explanation, 'Option B is factually wrong') > 0
      OR instr(q.explanation, 'Option B is false') > 0
      OR instr(q.explanation, 'Option B is the cache (replayed answers), Option C is graph summaries (aggregated text), Option D is embedding inversion') > 0
      OR instr(q.explanation, 'Option B is wrong') > 0
      OR instr(q.explanation, 'Option B reverses the split. Option C keeps both short. Option D keeps both long') > 0
      OR instr(q.explanation, 'Option C (community summaries) leaks') > 0
      OR instr(q.explanation, 'Option C (delete the node) removes') > 0
      OR instr(q.explanation, 'Option C (largest member) is') > 0
      OR instr(q.explanation, 'Option C is false') > 0
      OR instr(q.explanation, 'Option C is wrong') > 0
      OR instr(q.explanation, 'Option C is wrong:') > 0
      OR instr(q.explanation, 'Option C misplaces') > 0
      OR instr(q.explanation, 'Option D (embedding inversion) recovers') > 0
      OR instr(q.explanation, 'Option D (log a warning and default-allow) is') > 0
      OR instr(q.explanation, 'Option D (no ACL because it is derived) treats') > 0
      OR instr(q.explanation, 'Option D is false') > 0
      OR instr(q.explanation, 'Option D is wrong') > 0
      OR instr(q.explanation, 'Option D is wrong:') > 0
      OR instr(q.explanation, 'Option D is wrong: a per-region filter') > 0
      OR instr(q.explanation, 'Option D is wrong: relaxing') > 0
      OR instr(q.explanation, 'Option D reverses') > 0
      OR instr(q.explanation, 'Option E is wrong:') > 0
      OR instr(q.explanation, 'Option E is wrong: a region metadata tag') > 0
      OR instr(q.explanation, 'Option E is wrong: pre-partitioning') > 0
      OR instr(q.explanation, 'Options B, C, and D (backups, chunks, embeddings) are all reachable') > 0
      OR instr(q.explanation, 'Options B, C, and D are all facts') > 0
      OR instr(q.explanation, 'Options B, C, and D are wrong:') > 0
      OR instr(q.explanation, 'Options B, C, and D each misstate') > 0
      OR instr(q.explanation, 'Options B, C, and D each name') > 0
      OR instr(q.explanation, 'Options B, C, and D rely on') > 0
      OR instr(q.explanation, 'Options C and D are inside the boundary: a direct rate-card request and a clause-confirmation query are both stopped') > 0));

-- Set 23 "M3 — Parsing and the Chunking Decision": 3 explanations.

-- Q7
UPDATE questions SET explanation =
  'The structure-recovery and chunk-size questions decide what unit the index contains at all, so reversing them means re-ingesting everything. Boundary expansion and multi-hop routing are additive: they layer metadata or a second index on top of the existing one, so they can be adopted or dropped without re-ingesting. Generator temperature is a query-time knob, not an ingestion decision at all.'
WHERE id = 952 AND set_id = 23 AND explanation =
  'The first two questions decide what unit the index contains at all, so reversing them means re-ingesting everything. Boundary expansion and multi-hop routing are additive: they layer metadata or a second index on top of the existing one, so they can be adopted or dropped without re-ingesting. Generator temperature is a query-time knob, not an ingestion decision at all.';

-- Q38
UPDATE questions SET explanation =
  'Smaller chunks improve precision (focus), reduce embedding blur (fewer ideas per vector), and — only while the unit is shorter than the chunk — improve recall. They reduce completeness and increase node count, so the completeness and fewer-nodes options state the opposite of the truth.'
WHERE id = 983 AND set_id = 23 AND explanation =
  'Smaller chunks improve precision (focus), reduce embedding blur (fewer ideas per vector), and — only while the unit is shorter than the chunk — improve recall. They reduce completeness and increase node count, so the last two options state the opposite of the truth.';

-- Q39
UPDATE questions SET explanation =
  'Expansion and multi-hop routing are additive — they layer postprocessors or a second index on top of the existing one, so they can be adopted or dropped without re-ingesting. Structure recovery, chunk size, and the embedding model all determine what the index contains, so changing any of them forces a full re-embed. The embedding-model option is an additional irreversible choice the prompt''s ''re-embedding'' criterion catches.'
WHERE id = 984 AND set_id = 23 AND explanation =
  'Expansion and multi-hop routing are additive — they layer postprocessors or a second index on top of the existing one, so they can be adopted or dropped without re-ingesting. Structure recovery, chunk size, and the embedding model all determine what the index contains, so changing any of them forces a full re-embed. The last option (embedding model) is an additional irreversible choice the prompt''s ''re-embedding'' criterion catches.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 23
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'The structure-recovery and chunk-size questions decide what unit the index contains at all, so reversing them means re-ingesting everything. Boundary expansion and multi-hop routing are additive: they layer metadata or a second index on top of the existing one, so they can be adopted or dropped without re-ingesting. Generator temperature is a query-time knob, not an ingestion decision at all.',
    'Smaller chunks improve precision (focus), reduce embedding blur (fewer ideas per vector), and — only while the unit is shorter than the chunk — improve recall. They reduce completeness and increase node count, so the completeness and fewer-nodes options state the opposite of the truth.',
    'Expansion and multi-hop routing are additive — they layer postprocessors or a second index on top of the existing one, so they can be adopted or dropped without re-ingesting. Structure recovery, chunk size, and the embedding model all determine what the index contains, so changing any of them forces a full re-embed. The embedding-model option is an additional irreversible choice the prompt''s ''re-embedding'' criterion catches.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, 'The first two questions decide') > 0
      OR instr(q.explanation, 'The last option (embedding model) is') > 0
      OR instr(q.explanation, 'so the last two options state') > 0));

-- Set 24 "Sparse, Dense, and Hybrid Retrieval (M7)": 38 explanations.

-- Q4
UPDATE questions SET explanation =
  'k1 calibrates term-frequency scaling: a value of 0 gives a binary (present/absent) model, and a large value approaches raw term frequency. The document-length option describes the b parameter (length normalization), the query-term-rarity option describes the IDF component, and the maximum-number-of-documents option is a retrieval top-k setting rather than a BM25 scoring parameter.'
WHERE id = 1014 AND set_id = 24 AND explanation =
  'k1 calibrates term-frequency scaling: a value of 0 gives a binary (present/absent) model, and a large value approaches raw term frequency. Option B describes the b parameter (length normalization), option C describes the IDF component, and option D is a retrieval top-k setting rather than a BM25 scoring parameter.';

-- Q5
UPDATE questions SET explanation =
  'b scales length normalization: b=1 fully scales term weight by document length, and b=0 disables it. The term-frequency-saturation option describes k1 (term-frequency saturation), the rare-versus-common-terms option describes the IDF component, and the stopword-removal option is a preprocessing choice (stopword/stemmer configuration) rather than b.'
WHERE id = 1015 AND set_id = 24 AND explanation =
  'b scales length normalization: b=1 fully scales term weight by document length, and b=0 disables it. Option B describes k1 (term-frequency saturation), option C describes the IDF component, and option D is a preprocessing choice (stopword/stemmer configuration) rather than b.';

-- Q6
UPDATE questions SET explanation =
  'The mechanism is IDF: a rare exact token is the strongest possible lexical signal, while an embedding maps an arbitrary identifier into a learned direction that is an artifact of training data it never had. BM25 has no semantics (so the option claiming BM25 understands what PN-8842 is is false), dimensionality is not the reason the identifier is arbitrary (the lower-dimensional-vectors option), and BM25 is not trained at all (the option claiming BM25 was trained on a corpus that included PN-8842).'
WHERE id = 1016 AND set_id = 24 AND explanation =
  'The mechanism is IDF: a rare exact token is the strongest possible lexical signal, while an embedding maps an arbitrary identifier into a learned direction that is an artifact of training data it never had. BM25 has no semantics (so option B is false), dimensionality is not the reason the identifier is arbitrary (option C), and BM25 is not trained at all (option D).';

-- Q7
UPDATE questions SET explanation =
  'BM25''s weakness is vocabulary: it matches tokens, so it cannot bridge ''ibuprofen'' to ''Advil'' unless the words co-occur. It has no semantic similarity (the semantic-similarity option), matching the word ''painkiller'' does not equal matching ''Advil'' (the ''painkiller'' option), and rarity only helps when the token is actually present (the ''Advil is a rare token'' option).'
WHERE id = 1017 AND set_id = 24 AND explanation =
  'BM25''s weakness is vocabulary: it matches tokens, so it cannot bridge ''ibuprofen'' to ''Advil'' unless the words co-occur. It has no semantic similarity (option B), matching the word ''painkiller'' does not equal matching ''Advil'' (option C), and rarity only helps when the token is actually present (option D).';

-- Q8
UPDATE questions SET explanation =
  'Keeping a sparse instrument means building and maintaining a second index with a per-corpus vocabulary that must stay in sync with the corpus, plus a fusion stage whose failure modes are new. BM25 is not free just because it is old (the ''no additional cost'' option is false), and it does not re-embed documents on every query (the re-embedding option) — that is a dense-retrieval cost.'
WHERE id = 1018 AND set_id = 24 AND explanation =
  'Keeping a sparse instrument means building and maintaining a second index with a per-corpus vocabulary that must stay in sync with the corpus, plus a fusion stage whose failure modes are new. BM25 is not free just because it is old (option B is false), and it does not re-embed documents on every query (option C) — that is a dense-retrieval cost.';

-- Q9
UPDATE questions SET explanation =
  'Stemmer and language settings are applied at ingest AND at query time; a mismatch means query tokens and indexed tokens are normalized differently, so matches that should happen are silently missed. It does not prevent the index from building (the ''fail to build'' option), does not leave results unchanged (the ''identical scores'' option), and performs no translation (the translation option).'
WHERE id = 1019 AND set_id = 24 AND explanation =
  'Stemmer and language settings are applied at ingest AND at query time; a mismatch means query tokens and indexed tokens are normalized differently, so matches that should happen are silently missed. It does not prevent the index from building (option B), does not leave results unchanged (option C), and performs no translation (option D).';

-- Q10
UPDATE questions SET explanation =
  'SPLADE''s contribution is explicit sparsity regularization plus a log-saturation effect on term weights, yielding sparse representations that keep inverted-index compatibility and exact matching while enabling expansion. It keeps the inverted index rather than replacing it with a dense index (the dense-vector-index option); it is a first-stage ranker, not a reranker on top of BM25 (the neural-reranker option); and it expands rather than discards rare terms (the ''discarding rare terms'' option).'
WHERE id = 1020 AND set_id = 24 AND explanation =
  'SPLADE''s contribution is explicit sparsity regularization plus a log-saturation effect on term weights, yielding sparse representations that keep inverted-index compatibility and exact matching while enabling expansion. It keeps the inverted index rather than replacing it with a dense index (option B); it is a first-stage ranker, not a reranker on top of BM25 (option C); and it expands rather than discards rare terms (option D).';

-- Q12
UPDATE questions SET explanation =
  'Expansion means a document or query gains weight on related tokens it does not literally contain, because the model learned the association — so a document about the drug ibuprofen can carry weight on the brand name ''Advil''. It is not about growing the index (the ''number of documents'' option), appending terms verbatim at ingest (the ''appending more terms verbatim'' option), or adding random query tokens (the ''random tokens'' option).'
WHERE id = 1022 AND set_id = 24 AND explanation =
  'Expansion means a document or query gains weight on related tokens it does not literally contain, because the model learned the association — so a document about the drug ibuprofen can carry weight on the brand name ''Advil''. It is not about growing the index (option B), appending terms verbatim at ingest (option C), or adding random query tokens (option D).';

-- Q14
UPDATE questions SET explanation =
  'When an extension point is sparsely documented, the prudent move is to treat its support as backend-dependent and verify it against the chosen store rather than assume uniform behavior or absence. The ''fully supported everywhere'' and ''use it without checking'' options assume uniform support, and the ''unsupported'' option assumes absence — none of which the documentation actually establishes.'
WHERE id = 1024 AND set_id = 24 AND explanation =
  'When an extension point is sparsely documented, the prudent move is to treat its support as backend-dependent and verify it against the chosen store rather than assume uniform behavior or absence. Options B and D assume uniform support, and option C assumes absence — none of which the documentation actually establishes.';

-- Q18
UPDATE questions SET explanation =
  'Relative score fusion applies a MinMax scaler to each retriever''s returned set and then takes a weighted sum with a per-retriever weight (for example 0.6 on the dense retriever and 0.4 on BM25). The mean-and-standard-deviation option describes distribution-based score fusion, the reciprocal-ranks option describes RRF, and the concatenation option is the naive concatenation that produces the boilerplate-filled top-10.'
WHERE id = 1028 AND set_id = 24 AND explanation =
  'Relative score fusion applies a MinMax scaler to each retriever''s returned set and then takes a weighted sum with a per-retriever weight (for example 0.6 on the dense retriever and 0.4 on BM25). Option B describes distribution-based score fusion, option C describes RRF, and option D is the naive concatenation that produces the boilerplate-filled top-10.';

-- Q19
UPDATE questions SET explanation =
  'DBSF normalizes each retriever''s returned set by its own mean and standard deviation, mapping the three-sigma extremes onto a common range so different score magnitudes no longer matter. The MinMax option is relative score fusion (MinMax), the ranks-only option is RRF (rank-based), and the fixed-global-constant option is a made-up fixed-constant approach.'
WHERE id = 1029 AND set_id = 24 AND explanation =
  'DBSF normalizes each retriever''s returned set by its own mean and standard deviation, mapping the three-sigma extremes onto a common range so different score magnitudes no longer matter. Option B is relative score fusion (MinMax), option C is RRF (rank-based), and option D is a made-up fixed-constant approach.';

-- Q20
UPDATE questions SET explanation =
  'Both relative score and DBSF are score-based; the difference is the normalization statistic — relative score uses a MinMax scaler per set, while DBSF uses each set''s mean and standard deviation. The ''relative score discards scores'' option wrongly has relative score discarding scores, the option giving relative score the mean and standard deviation swaps the statistics, and the ''two names for RRF'' option confuses score-based fusion with rank-based RRF.'
WHERE id = 1030 AND set_id = 24 AND explanation =
  'Both relative score and DBSF are score-based; the difference is the normalization statistic — relative score uses a MinMax scaler per set, while DBSF uses each set''s mean and standard deviation. Option B wrongly has relative score discarding scores, option C swaps the statistics, and option D confuses score-based fusion with rank-based RRF.';

-- Q21
UPDATE questions SET explanation =
  'The argument controls query generation, not the retriever count: it runs the original query and generates additional variants, and each generated query is an LLM call. The retriever-count, documents-per-query and parallel-calls options all misread it as a retriever count, a top-k, or a concurrency setting.'
WHERE id = 1031 AND set_id = 24 AND explanation =
  'The argument controls query generation, not the retriever count: it runs the original query and generates additional variants, and each generated query is an LLM call. Options B, C, and D all misread it as a retriever count, a top-k, or a concurrency setting.';

-- Q22
UPDATE questions SET explanation =
  'A learned convex combination needs a small labelled sample to tune its one weight α, producing s = α·dense + (1−α)·lexical, and the literature finds it outperforms RRF in- and out-of-domain. RRF is the one needing no labels and no normalization (the ''no labels and no parameters'' option), and the separate-neural-network and identical-score-ranges options describe mechanisms a convex combination does not use.'
WHERE id = 1032 AND set_id = 24 AND explanation =
  'A learned convex combination needs a small labelled sample to tune its one weight α, producing s = α·dense + (1−α)·lexical, and the literature finds it outperforms RRF in- and out-of-domain. RRF is the one needing no labels and no normalization (option B), and options C and D describe mechanisms a convex combination does not use.';

-- Q23
UPDATE questions SET explanation =
  'The naive raw-score merge is a weighted average of a useful signal and a noise source on an arbitrary scale, so BM25''s boilerplate matches drown the dense results — retrieval noise. Representation mismatch is the dense-only identifier miss, staleness is an ingest problem, and context overflow is a prompt-assembly problem.'
WHERE id = 1033 AND set_id = 24 AND explanation =
  'The naive raw-score merge is a weighted average of a useful signal and a noise source on an arbitrary scale, so BM25''s boilerplate matches drown the dense results — retrieval noise. Representation mismatch (option B) is the dense-only identifier miss, staleness (option C) is an ingest problem, and context overflow (option D) is a prompt-assembly problem.';

-- Q24
UPDATE questions SET explanation =
  'Identifier/exact-token queries are sparse''s home: the token is present verbatim and IDF makes it decisive, while an embedding has no basis for the distinction. The dense retriever is exactly the instrument that misses such queries; section numbers can be indexed (the ''cannot be indexed at all'' option is false); and a reranker reorders an existing candidate set, it does not retrieve.'
WHERE id = 1034 AND set_id = 24 AND explanation =
  'Identifier/exact-token queries are sparse''s home: the token is present verbatim and IDF makes it decisive, while an embedding has no basis for the distinction. Dense (option B) is exactly the instrument that misses such queries; section numbers can be indexed (option C is false); and a reranker (option D) reorders an existing candidate set, it does not retrieve.';

-- Q25
UPDATE questions SET explanation =
  'This is a semantic paraphrase with no shared tokens, which is dense retrieval''s strength. The sparse retriever fails because there is no lexical overlap, and the rate-table and ''Neither instrument'' options misclassify the query as a numeric lookup or an unanswerable question.'
WHERE id = 1035 AND set_id = 24 AND explanation =
  'This is a semantic paraphrase with no shared tokens, which is dense retrieval''s strength. Sparse (option B) fails because there is no lexical overlap, and options C and D misclassify the query as a numeric lookup or an unanswerable question.';

-- Q26
UPDATE questions SET explanation =
  'Numeric/tabular queries need the answer to be a cell, not a passage, so neither lexical nor dense passage retrieval is the right instrument — the query is routed to a structured path. The dense, BM25 and fused top-10 options all force a passage-retrieval instrument onto a problem it cannot solve.'
WHERE id = 1036 AND set_id = 24 AND explanation =
  'Numeric/tabular queries need the answer to be a cell, not a passage, so neither lexical nor dense passage retrieval is the right instrument — the query is routed to a structured path. Options B, C, and D all force a passage-retrieval instrument onto a problem it cannot solve.';

-- Q27
UPDATE questions SET explanation =
  'Cross-reference/multi-hop questions require joining two documents, which a flat top-k over one index cannot do; they need a structured or graph index. The dense, BM25 and fused top-10 options are single-hop passage retrievals that cannot follow the reference.'
WHERE id = 1037 AND set_id = 24 AND explanation =
  'Cross-reference/multi-hop questions require joining two documents, which a flat top-k over one index cannot do; they need a structured or graph index. Options B, C, and D are single-hop passage retrievals that cannot follow the reference.';

-- Q28
UPDATE questions SET explanation =
  'A mixed query has an identifier (sparse''s job) and a semantic intent (dense''s job), so it is the case for fusion. Single-instrument answers (only the dense retriever, only the sparse retriever) each drop half the signal, and rejecting the query is a non-answer.'
WHERE id = 1038 AND set_id = 24 AND explanation =
  'A mixed query has an identifier (sparse''s job) and a semantic intent (dense''s job), so it is the case for fusion. Single-instrument answers (options B and C) each drop half the signal, and option D is a non-answer.';

-- Q29
UPDATE questions SET explanation =
  'The distinction is named-entity/exact-token versus meaning-without-vocabulary-overlap, which is precisely what routes each to sparse versus dense. Query length and numbers-versus-dates are irrelevant surface features, and ''both are answered by the same instrument'' denies the module''s central finding.'
WHERE id = 1039 AND set_id = 24 AND explanation =
  'The distinction is named-entity/exact-token versus meaning-without-vocabulary-overlap, which is precisely what routes each to sparse versus dense. Options B and C are irrelevant surface features, and option D denies the module''s central finding.';

-- Q30
UPDATE questions SET explanation =
  'BEIR found BM25 a robust baseline across datasets, while dense and sparse models were often more efficient but underperformed out of domain — the out-of-domain statement of the asymmetry. The ''dense beats BM25 on every dataset'' and ''BM25 fails on all datasets'' options assert dense dominance or BM25 collapse, and the ''sparse models always more efficient and more accurate'' option asserts sparse dominance, none of which BEIR found.'
WHERE id = 1040 AND set_id = 24 AND explanation =
  'BEIR found BM25 a robust baseline across datasets, while dense and sparse models were often more efficient but underperformed out of domain — the out-of-domain statement of the asymmetry. Options B and D assert dense dominance or BM25 collapse, and option C asserts sparse dominance, none of which BEIR found.';

-- Q31
UPDATE questions SET explanation =
  'DPR showed a dense retriever beating a strong BM25 baseline on its in-domain open-domain QA benchmarks. It does not generalize to every domain (the ''same win on every corpus'' option), and the ''never match BM25'' and ''eliminate the need for any lexical index'' options overclaim in the opposite direction — DPR neither ''never matches BM25'' nor ''eliminates the need for a lexical index in every domain''.'
WHERE id = 1041 AND set_id = 24 AND explanation =
  'DPR showed a dense retriever beating a strong BM25 baseline on its in-domain open-domain QA benchmarks. It does not generalize to every domain (option D), and options B and C overclaim in the opposite direction — DPR neither ''never matches BM25'' nor ''eliminates the need for a lexical index in every domain''.';

-- Q34
UPDATE questions SET explanation =
  'Hybrid-LITE saved a large multiple of memory (13×) at nearly full performance (98%) of a BM25+DPR hybrid and found light hybrids generalize better than individual sparse and dense retrievers — while the authors immediately caveat that robustness still has large room to improve. The ''sacrificing almost all retrieval performance'' option claims the memory savings cost almost all performance, the ''no remaining gaps'' option claims no remaining gaps, and the ''generalize better'' option overstates uniform dominance.'
WHERE id = 1044 AND set_id = 24 AND explanation =
  'Hybrid-LITE saved a large multiple of memory (13×) at nearly full performance (98%) of a BM25+DPR hybrid and found light hybrids generalize better than individual sparse and dense retrievers — while the authors immediately caveat that robustness still has large room to improve. Option C claims the memory savings cost almost all performance, option D claims no remaining gaps, and option B overstates uniform dominance.';

-- Q35
UPDATE questions SET explanation =
  'BRIGHT showed a leaderboard-leading model scoring far below its MTEB headline on reasoning-intensive queries — a ceiling on what retrieval alone fixes. Hybrid helps the lexical half, not the reasoning ability (the ''closes the reasoning gap entirely'' option is false), and the ''as well as ordinary ones'' and ''easier than standard MTEB queries'' options invert the finding.'
WHERE id = 1045 AND set_id = 24 AND explanation =
  'BRIGHT showed a leaderboard-leading model scoring far below its MTEB headline on reasoning-intensive queries — a ceiling on what retrieval alone fixes. Hybrid helps the lexical half, not the reasoning ability (option C is false), and options B and D invert the finding.';

-- Q36
UPDATE questions SET explanation =
  'Near-identical overall averages hide large per-subset differences, so reporting metrics per query shape is what makes the decision visible. The discard-both, ''proves redundant'' and aggregate-winner options all act on the aggregate, which is exactly what hides the complementarity.'
WHERE id = 1046 AND set_id = 24 AND explanation =
  'Near-identical overall averages hide large per-subset differences, so reporting metrics per query shape is what makes the decision visible. Options B, C, and D all act on the aggregate, which is exactly what hides the complementarity.';

-- Q37
UPDATE questions SET explanation =
  'Hybrid is a better prior across a mixed distribution, not a uniform winner: on identifiers the dense half contributes noise and consumes slots. The fix is not to remove fusion globally, use BM25 everywhere, or drop the queries — it is to measure per band and route.'
WHERE id = 1047 AND set_id = 24 AND explanation =
  'Hybrid is a better prior across a mixed distribution, not a uniform winner: on identifiers the dense half contributes noise and consumes slots. The fix is not to remove fusion globally (option B), use BM25 everywhere (option C), or drop the queries (option D) — it is to measure per band and route.';

-- Q39
UPDATE questions SET explanation =
  'Turning on query generation inserts an LLM call inside retrieval and multiplies p99 latency — it is a budget item owned by query transformation, not a free retrieval knob. It does not change the number of retrievers, and it is not free.'
WHERE id = 1049 AND set_id = 24 AND explanation =
  'Turning on query generation inserts an LLM call inside retrieval and multiplies p99 latency — it is a budget item owned by query transformation, not a free retrieval knob. It does not change the number of retrievers (option C), and it is not free (option D).';

-- Q40
UPDATE questions SET explanation =
  'When two query shapes cap out below target under every fusion, the limit is elsewhere (chunking or routing), so the answer is a different index or a routing plan, not more fusion tuning. The tune-fusion-harder, remove-the-queries and replace-both-retrievers options misdiagnose the cause.'
WHERE id = 1050 AND set_id = 24 AND explanation =
  'When two query shapes cap out below target under every fusion, the limit is elsewhere (chunking or routing), so the answer is a different index or a routing plan, not more fusion tuning. Options B, C, and D misdiagnose the cause.';

-- Q41
UPDATE questions SET explanation =
  'The honest claim is ''hybrid is a better prior across a mixed query distribution'', because on identifiers the dense half of fusion adds noise and the fused system can lose recall to BM25 alone. The ''always score identically'', ''never loses'' and ''always loses'' options are all absolute claims the evidence contradicts.'
WHERE id = 1051 AND set_id = 24 AND explanation =
  'The honest claim is ''hybrid is a better prior across a mixed query distribution'', because on identifiers the dense half of fusion adds noise and the fused system can lose recall to BM25 alone. Options B, C, and D are all absolute claims the evidence contradicts.';

-- Q42
UPDATE questions SET explanation =
  'The two claims are directly contradictory, and implementations set the constant differently (one defaults to 2, another leaves it unspecified), so a team should record the constant and the implementation and, if a labelled sample exists, spend it on a learned convex combination rather than trusting ''no tuning''. Ignoring the study and assuming every implementation uses the same constant both ignore the disagreement, and disabling fusion entirely overreacts.'
WHERE id = 1052 AND set_id = 24 AND explanation =
  'The two claims are directly contradictory, and implementations set the constant differently (one defaults to 2, another leaves it unspecified), so a team should record the constant and the implementation and, if a labelled sample exists, spend it on a learned convex combination rather than trusting ''no tuning''. Options B and C ignore the disagreement, and option D overreacts.';

-- Q43
UPDATE questions SET explanation =
  'If the learned combination does not care how you normalize, normalization is hygiene and the weight α is where the gain is. The ''sole lever'', ''neither matters'' and ''try every normalization'' options each misplace or deny the effort.'
WHERE id = 1053 AND set_id = 24 AND explanation =
  'If the learned combination does not care how you normalize, normalization is hygiene and the weight α is where the gain is. Options B, C, and D each misplace or deny the effort.';

-- Q44
UPDATE questions SET explanation =
  'DPR''s in-domain win is real, but it coexists with contrary results on other distributions, so the claim must be scoped per distribution. The universal-law, ''false in every setting'' and ''lexical retrieval is never useful'' options each generalize or dismiss a distribution-dependent result.'
WHERE id = 1054 AND set_id = 24 AND explanation =
  'DPR''s in-domain win is real, but it coexists with contrary results on other distributions, so the claim must be scoped per distribution. Options B, C, and D each generalize or dismiss a distribution-dependent result.';

-- Q45
UPDATE questions SET explanation =
  'A dense-only system missing identifier queries is representation mismatch: an arbitrary identifier has no semantic content for an embedding to capture, so the representation cannot line up with what the query asks. Averaging incompatible raw scores and burying the correct results is retrieval noise. The chunk-boundary-loss option mislabels the identifier miss as chunk-boundary loss (an answer split across chunks), and the staleness option mislabels the scale-mismatch burial as staleness (an index that has diverged from the corpus).'
WHERE id = 1055 AND set_id = 24 AND explanation =
  'A dense-only system missing identifier queries is representation mismatch: an arbitrary identifier has no semantic content for an embedding to capture, so the representation cannot line up with what the query asks. Averaging incompatible raw scores and burying the correct results is retrieval noise. Option C mislabels the identifier miss as chunk-boundary loss (an answer split across chunks), and option D mislabels the scale-mismatch burial as staleness (an index that has diverged from the corpus).';

-- Q51
UPDATE questions SET explanation =
  'The OWNERS map fixes which module surveys each recurring claim; module 7 owns BM25, the original Okapi paper, SPLADE, and RRF, so later modules must cite these keys rather than re-survey them. It does not forbid citing, encode publication years, or assign dense-retrieval keys like DPR/BEIR to module 7 (those belong to module 4).'
WHERE id = 1061 AND set_id = 24 AND explanation =
  'The OWNERS map fixes which module surveys each recurring claim; module 7 owns BM25, the original Okapi paper, SPLADE, and RRF, so later modules must cite these keys rather than re-survey them. It does not forbid citing (option B), encode publication years (option C), or assign dense-retrieval keys like DPR/BEIR to module 7 (those belong to module 4).';

-- Q52
UPDATE questions SET explanation =
  'Re-survey is detected when a non-owner module contains a full bibliographic entry (author list plus arXiv id) for a key it does not own, with no ownership marker — citing is fine, re-surveying is not. Citing the key inline with an ownership note and citing an owned key in its own Sources section describe legitimate citation or ownership, and an empty Sources section is a different check (a missing Sources section).'
WHERE id = 1062 AND set_id = 24 AND explanation =
  'Re-survey is detected when a non-owner module contains a full bibliographic entry (author list plus arXiv id) for a key it does not own, with no ownership marker — citing is fine, re-surveying is not. Options B and C describe legitimate citation or ownership, and option D is a different check (a missing Sources section).';

-- Q53
UPDATE questions SET explanation =
  'The topics dict drives a scan of each module''s ''Where the literature disagrees'' section; when more than one module contests a topic, it is reported for a human to eyeball that the claims do not conflict — an info item, not an error. The lab-check, delete-modules and only-one-module options misread it as a build gate or a restriction.'
WHERE id = 1063 AND set_id = 24 AND explanation =
  'The topics dict drives a scan of each module''s ''Where the literature disagrees'' section; when more than one module contests a topic, it is reported for a human to eyeball that the claims do not conflict — an info item, not an error. Options B, C, and D misread it as a build gate or a restriction.';

-- Q54
UPDATE questions SET explanation =
  'The five-class stratification is exactly the module''s per-shape diagnosis: lexical→sparse, semantic→dense, numeric/multi-hop→neither, and the query set''s design lets each instrument be evaluated per shape. The file-naming, dense-only and sparse-only options misread its purpose.'
WHERE id = 1064 AND set_id = 24 AND explanation =
  'The five-class stratification is exactly the module''s per-shape diagnosis: lexical→sparse, semantic→dense, numeric/multi-hop→neither, and the query set''s design lets each instrument be evaluated per shape. Options B, C, and D misread its purpose.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 24
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'k1 calibrates term-frequency scaling: a value of 0 gives a binary (present/absent) model, and a large value approaches raw term frequency. The document-length option describes the b parameter (length normalization), the query-term-rarity option describes the IDF component, and the maximum-number-of-documents option is a retrieval top-k setting rather than a BM25 scoring parameter.',
    'b scales length normalization: b=1 fully scales term weight by document length, and b=0 disables it. The term-frequency-saturation option describes k1 (term-frequency saturation), the rare-versus-common-terms option describes the IDF component, and the stopword-removal option is a preprocessing choice (stopword/stemmer configuration) rather than b.',
    'The mechanism is IDF: a rare exact token is the strongest possible lexical signal, while an embedding maps an arbitrary identifier into a learned direction that is an artifact of training data it never had. BM25 has no semantics (so the option claiming BM25 understands what PN-8842 is is false), dimensionality is not the reason the identifier is arbitrary (the lower-dimensional-vectors option), and BM25 is not trained at all (the option claiming BM25 was trained on a corpus that included PN-8842).',
    'BM25''s weakness is vocabulary: it matches tokens, so it cannot bridge ''ibuprofen'' to ''Advil'' unless the words co-occur. It has no semantic similarity (the semantic-similarity option), matching the word ''painkiller'' does not equal matching ''Advil'' (the ''painkiller'' option), and rarity only helps when the token is actually present (the ''Advil is a rare token'' option).',
    'Keeping a sparse instrument means building and maintaining a second index with a per-corpus vocabulary that must stay in sync with the corpus, plus a fusion stage whose failure modes are new. BM25 is not free just because it is old (the ''no additional cost'' option is false), and it does not re-embed documents on every query (the re-embedding option) — that is a dense-retrieval cost.',
    'Stemmer and language settings are applied at ingest AND at query time; a mismatch means query tokens and indexed tokens are normalized differently, so matches that should happen are silently missed. It does not prevent the index from building (the ''fail to build'' option), does not leave results unchanged (the ''identical scores'' option), and performs no translation (the translation option).',
    'SPLADE''s contribution is explicit sparsity regularization plus a log-saturation effect on term weights, yielding sparse representations that keep inverted-index compatibility and exact matching while enabling expansion. It keeps the inverted index rather than replacing it with a dense index (the dense-vector-index option); it is a first-stage ranker, not a reranker on top of BM25 (the neural-reranker option); and it expands rather than discards rare terms (the ''discarding rare terms'' option).',
    'Expansion means a document or query gains weight on related tokens it does not literally contain, because the model learned the association — so a document about the drug ibuprofen can carry weight on the brand name ''Advil''. It is not about growing the index (the ''number of documents'' option), appending terms verbatim at ingest (the ''appending more terms verbatim'' option), or adding random query tokens (the ''random tokens'' option).',
    'When an extension point is sparsely documented, the prudent move is to treat its support as backend-dependent and verify it against the chosen store rather than assume uniform behavior or absence. The ''fully supported everywhere'' and ''use it without checking'' options assume uniform support, and the ''unsupported'' option assumes absence — none of which the documentation actually establishes.',
    'Relative score fusion applies a MinMax scaler to each retriever''s returned set and then takes a weighted sum with a per-retriever weight (for example 0.6 on the dense retriever and 0.4 on BM25). The mean-and-standard-deviation option describes distribution-based score fusion, the reciprocal-ranks option describes RRF, and the concatenation option is the naive concatenation that produces the boilerplate-filled top-10.',
    'DBSF normalizes each retriever''s returned set by its own mean and standard deviation, mapping the three-sigma extremes onto a common range so different score magnitudes no longer matter. The MinMax option is relative score fusion (MinMax), the ranks-only option is RRF (rank-based), and the fixed-global-constant option is a made-up fixed-constant approach.',
    'Both relative score and DBSF are score-based; the difference is the normalization statistic — relative score uses a MinMax scaler per set, while DBSF uses each set''s mean and standard deviation. The ''relative score discards scores'' option wrongly has relative score discarding scores, the option giving relative score the mean and standard deviation swaps the statistics, and the ''two names for RRF'' option confuses score-based fusion with rank-based RRF.',
    'The argument controls query generation, not the retriever count: it runs the original query and generates additional variants, and each generated query is an LLM call. The retriever-count, documents-per-query and parallel-calls options all misread it as a retriever count, a top-k, or a concurrency setting.',
    'A learned convex combination needs a small labelled sample to tune its one weight α, producing s = α·dense + (1−α)·lexical, and the literature finds it outperforms RRF in- and out-of-domain. RRF is the one needing no labels and no normalization (the ''no labels and no parameters'' option), and the separate-neural-network and identical-score-ranges options describe mechanisms a convex combination does not use.',
    'The naive raw-score merge is a weighted average of a useful signal and a noise source on an arbitrary scale, so BM25''s boilerplate matches drown the dense results — retrieval noise. Representation mismatch is the dense-only identifier miss, staleness is an ingest problem, and context overflow is a prompt-assembly problem.',
    'Identifier/exact-token queries are sparse''s home: the token is present verbatim and IDF makes it decisive, while an embedding has no basis for the distinction. The dense retriever is exactly the instrument that misses such queries; section numbers can be indexed (the ''cannot be indexed at all'' option is false); and a reranker reorders an existing candidate set, it does not retrieve.',
    'This is a semantic paraphrase with no shared tokens, which is dense retrieval''s strength. The sparse retriever fails because there is no lexical overlap, and the rate-table and ''Neither instrument'' options misclassify the query as a numeric lookup or an unanswerable question.',
    'Numeric/tabular queries need the answer to be a cell, not a passage, so neither lexical nor dense passage retrieval is the right instrument — the query is routed to a structured path. The dense, BM25 and fused top-10 options all force a passage-retrieval instrument onto a problem it cannot solve.',
    'Cross-reference/multi-hop questions require joining two documents, which a flat top-k over one index cannot do; they need a structured or graph index. The dense, BM25 and fused top-10 options are single-hop passage retrievals that cannot follow the reference.',
    'A mixed query has an identifier (sparse''s job) and a semantic intent (dense''s job), so it is the case for fusion. Single-instrument answers (only the dense retriever, only the sparse retriever) each drop half the signal, and rejecting the query is a non-answer.',
    'The distinction is named-entity/exact-token versus meaning-without-vocabulary-overlap, which is precisely what routes each to sparse versus dense. Query length and numbers-versus-dates are irrelevant surface features, and ''both are answered by the same instrument'' denies the module''s central finding.',
    'BEIR found BM25 a robust baseline across datasets, while dense and sparse models were often more efficient but underperformed out of domain — the out-of-domain statement of the asymmetry. The ''dense beats BM25 on every dataset'' and ''BM25 fails on all datasets'' options assert dense dominance or BM25 collapse, and the ''sparse models always more efficient and more accurate'' option asserts sparse dominance, none of which BEIR found.',
    'DPR showed a dense retriever beating a strong BM25 baseline on its in-domain open-domain QA benchmarks. It does not generalize to every domain (the ''same win on every corpus'' option), and the ''never match BM25'' and ''eliminate the need for any lexical index'' options overclaim in the opposite direction — DPR neither ''never matches BM25'' nor ''eliminates the need for a lexical index in every domain''.',
    'Hybrid-LITE saved a large multiple of memory (13×) at nearly full performance (98%) of a BM25+DPR hybrid and found light hybrids generalize better than individual sparse and dense retrievers — while the authors immediately caveat that robustness still has large room to improve. The ''sacrificing almost all retrieval performance'' option claims the memory savings cost almost all performance, the ''no remaining gaps'' option claims no remaining gaps, and the ''generalize better'' option overstates uniform dominance.',
    'BRIGHT showed a leaderboard-leading model scoring far below its MTEB headline on reasoning-intensive queries — a ceiling on what retrieval alone fixes. Hybrid helps the lexical half, not the reasoning ability (the ''closes the reasoning gap entirely'' option is false), and the ''as well as ordinary ones'' and ''easier than standard MTEB queries'' options invert the finding.',
    'Near-identical overall averages hide large per-subset differences, so reporting metrics per query shape is what makes the decision visible. The discard-both, ''proves redundant'' and aggregate-winner options all act on the aggregate, which is exactly what hides the complementarity.',
    'Hybrid is a better prior across a mixed distribution, not a uniform winner: on identifiers the dense half contributes noise and consumes slots. The fix is not to remove fusion globally, use BM25 everywhere, or drop the queries — it is to measure per band and route.',
    'Turning on query generation inserts an LLM call inside retrieval and multiplies p99 latency — it is a budget item owned by query transformation, not a free retrieval knob. It does not change the number of retrievers, and it is not free.',
    'When two query shapes cap out below target under every fusion, the limit is elsewhere (chunking or routing), so the answer is a different index or a routing plan, not more fusion tuning. The tune-fusion-harder, remove-the-queries and replace-both-retrievers options misdiagnose the cause.',
    'The honest claim is ''hybrid is a better prior across a mixed query distribution'', because on identifiers the dense half of fusion adds noise and the fused system can lose recall to BM25 alone. The ''always score identically'', ''never loses'' and ''always loses'' options are all absolute claims the evidence contradicts.',
    'The two claims are directly contradictory, and implementations set the constant differently (one defaults to 2, another leaves it unspecified), so a team should record the constant and the implementation and, if a labelled sample exists, spend it on a learned convex combination rather than trusting ''no tuning''. Ignoring the study and assuming every implementation uses the same constant both ignore the disagreement, and disabling fusion entirely overreacts.',
    'If the learned combination does not care how you normalize, normalization is hygiene and the weight α is where the gain is. The ''sole lever'', ''neither matters'' and ''try every normalization'' options each misplace or deny the effort.',
    'DPR''s in-domain win is real, but it coexists with contrary results on other distributions, so the claim must be scoped per distribution. The universal-law, ''false in every setting'' and ''lexical retrieval is never useful'' options each generalize or dismiss a distribution-dependent result.',
    'A dense-only system missing identifier queries is representation mismatch: an arbitrary identifier has no semantic content for an embedding to capture, so the representation cannot line up with what the query asks. Averaging incompatible raw scores and burying the correct results is retrieval noise. The chunk-boundary-loss option mislabels the identifier miss as chunk-boundary loss (an answer split across chunks), and the staleness option mislabels the scale-mismatch burial as staleness (an index that has diverged from the corpus).',
    'The OWNERS map fixes which module surveys each recurring claim; module 7 owns BM25, the original Okapi paper, SPLADE, and RRF, so later modules must cite these keys rather than re-survey them. It does not forbid citing, encode publication years, or assign dense-retrieval keys like DPR/BEIR to module 7 (those belong to module 4).',
    'Re-survey is detected when a non-owner module contains a full bibliographic entry (author list plus arXiv id) for a key it does not own, with no ownership marker — citing is fine, re-surveying is not. Citing the key inline with an ownership note and citing an owned key in its own Sources section describe legitimate citation or ownership, and an empty Sources section is a different check (a missing Sources section).',
    'The topics dict drives a scan of each module''s ''Where the literature disagrees'' section; when more than one module contests a topic, it is reported for a human to eyeball that the claims do not conflict — an info item, not an error. The lab-check, delete-modules and only-one-module options misread it as a build gate or a restriction.',
    'The five-class stratification is exactly the module''s per-shape diagnosis: lexical→sparse, semantic→dense, numeric/multi-hop→neither, and the query set''s design lets each instrument be evaluated per shape. The file-naming, dense-only and sparse-only options misread its purpose.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, '(option B is false)') > 0
      OR instr(q.explanation, '(option B)') > 0
      OR instr(q.explanation, '(option B), and options C and D describe mechanisms') > 0
      OR instr(q.explanation, '(option C is false)') > 0
      OR instr(q.explanation, '(option C is false), and options B and D invert the finding.') > 0
      OR instr(q.explanation, '(option C)') > 0
      OR instr(q.explanation, '(option D)') > 0
      OR instr(q.explanation, '(option D), and options B and C overclaim') > 0
      OR instr(q.explanation, '(so option B is false)') > 0
      OR instr(q.explanation, 'Dense (option B) is exactly') > 0
      OR instr(q.explanation, 'Option B describes distribution-based score fusion, option C describes RRF, and option D is the naive concatenation') > 0
      OR instr(q.explanation, 'Option B describes k1 (term-frequency saturation), option C describes the IDF component, and option D is a preprocessing choice') > 0
      OR instr(q.explanation, 'Option B describes the b parameter (length normalization), option C describes the IDF component, and option D is a retrieval top-k setting') > 0
      OR instr(q.explanation, 'Option B is relative score fusion (MinMax), option C is RRF (rank-based), and option D is a made-up fixed-constant approach.') > 0
      OR instr(q.explanation, 'Option B wrongly has relative score discarding scores, option C swaps the statistics, and option D confuses') > 0
      OR instr(q.explanation, 'Option C claims the memory savings cost almost all performance, option D claims no remaining gaps, and option B overstates uniform dominance.') > 0
      OR instr(q.explanation, 'Option C mislabels the identifier miss') > 0
      OR instr(q.explanation, 'Options B and C are irrelevant surface features, and option D denies') > 0
      OR instr(q.explanation, 'Options B and C describe legitimate citation or ownership, and option D is a different check') > 0
      OR instr(q.explanation, 'Options B and C ignore the disagreement, and option D overreacts.') > 0
      OR instr(q.explanation, 'Options B and D assert dense dominance or BM25 collapse, and option C asserts sparse dominance') > 0
      OR instr(q.explanation, 'Options B and D assume uniform support, and option C assumes absence') > 0
      OR instr(q.explanation, 'Options B, C, and D all act on the aggregate') > 0
      OR instr(q.explanation, 'Options B, C, and D all force') > 0
      OR instr(q.explanation, 'Options B, C, and D all misread it') > 0
      OR instr(q.explanation, 'Options B, C, and D are all absolute claims') > 0
      OR instr(q.explanation, 'Options B, C, and D are single-hop') > 0
      OR instr(q.explanation, 'Options B, C, and D each generalize') > 0
      OR instr(q.explanation, 'Options B, C, and D each misplace') > 0
      OR instr(q.explanation, 'Options B, C, and D misdiagnose') > 0
      OR instr(q.explanation, 'Options B, C, and D misread it') > 0
      OR instr(q.explanation, 'Options B, C, and D misread its purpose') > 0
      OR instr(q.explanation, 'Representation mismatch (option B) is') > 0
      OR instr(q.explanation, 'Single-instrument answers (options B and C) each drop half the signal, and option D is a non-answer.') > 0
      OR instr(q.explanation, 'Sparse (option B) fails') > 0
      OR instr(q.explanation, 'a reranker (option D) reorders') > 0
      OR instr(q.explanation, 'and option D mislabels the scale-mismatch burial') > 0
      OR instr(q.explanation, 'and options C and D misclassify the query') > 0
      OR instr(q.explanation, 'context overflow (option D) is') > 0
      OR instr(q.explanation, 'forbid citing (option B), encode publication years (option C), or') > 0
      OR instr(q.explanation, 'remove fusion globally (option B), use BM25 everywhere (option C), or drop the queries (option D)') > 0
      OR instr(q.explanation, 'staleness (option C) is') > 0
      OR instr(q.explanation, 'the number of retrievers (option C), and it is not free (option D).') > 0));

-- Set 31 "RAG M8 - Index Structures Beyond Flat Vectors": 7 explanations.

-- Q22
UPDATE questions SET explanation =
  'Metadata filtering constrains which nodes are candidates, using the vector store''s own predicate support - cheap, but you can only express what the store can filter. Metadata replacement moves the constraint into a second index (match a summary or entity, return the source), which costs more to build and redefines the retrieved unit. The cost claim is reversed in the ''filtering is expensive, replacement is cheap'' option; ''both are the same operation'' collapses a real distinction; and ''filtering creates new retrieval signal'' gets the direction backwards - filters can only exclude, while replacement can surface nodes whose own text never matched.'
WHERE id = 1432 AND set_id = 31 AND explanation =
  'Metadata filtering constrains which nodes are candidates, using the vector store''s own predicate support - cheap, but you can only express what the store can filter. Metadata replacement moves the constraint into a second index (match a summary or entity, return the source), which costs more to build and redefines the retrieved unit. The cost claim is reversed in the second option; the third collapses a real distinction; and the fourth gets the direction backwards - filters can only exclude, while replacement can surface nodes whose own text never matched.';

-- Q29
UPDATE questions SET explanation =
  'The keyword table builds a mapping from each keyword to its nodes and goes straight from query terms to that node set - a lookup, not a ranking - trading expressiveness for cost. BM25 scores each term against each document to produce a ranking. The option giving the keyword table BM25''s scoring swaps them; ''both rank all documents'' and ''both return an unordered node set'' collapse a real distinction that matters for cost and behaviour.'
WHERE id = 1439 AND set_id = 31 AND explanation =
  'The keyword table builds a mapping from each keyword to its nodes and goes straight from query terms to that node set - a lookup, not a ranking - trading expressiveness for cost. BM25 scores each term against each document to produce a ranking. The second option swaps them; the third and fourth collapse a real distinction that matters for cost and behaviour.';

-- Q35
UPDATE questions SET explanation =
  'The index extracts a summary per document (an LLM call - the summaries are produced by a response synthesizer) and stores that summary alongside the nodes; the embedding model supports the default embedding-based retrieval path over those summaries. The option where the LLM embeds and the embedder writes the summaries swaps the two models'' roles; deduplication is not their job; and the index demonstrably needs both, as the constructor requires them.'
WHERE id = 1445 AND set_id = 31 AND explanation =
  'The index extracts a summary per document (an LLM call - the summaries are produced by a response synthesizer) and stores that summary alongside the nodes; the embedding model supports the default embedding-based retrieval path over those summaries. The second option swaps the two models'' roles; deduplication is not their job; and the index demonstrably needs both, as the constructor requires them.';

-- Q38
UPDATE questions SET explanation =
  'A node reference is a pointer: the cheap small unit (the reference) is what gets matched for precision, and the expensive large unit (the referent, the parent) is what gets returned - a pointer chase. Matching the parent and returning the child reverses the direction; returning only the child returns no parent at all; and returning the parent with all its siblings over-returns by dragging in siblings, which references do not do.'
WHERE id = 1448 AND set_id = 31 AND explanation =
  'A node reference is a pointer: the cheap small unit (the reference) is what gets matched for precision, and the expensive large unit (the referent, the parent) is what gets returned - a pointer chase. The second option reverses the direction; the third returns no parent at all; and the fourth over-returns by dragging in siblings, which references do not do.';

-- Q41
UPDATE questions SET explanation =
  'Recursive retrieval chases an explicit reference (an IndexNode pointer to a parent). Auto-merging instead looks at the leaf set and recursively merges subsets that reference the same parent beyond a threshold. The option where recursive merges by threshold and auto-merging follows a pointer swaps the two; ''both merge leaf nodes by an embedding-similarity threshold'' describes only auto-merging; and ''both return only the leaf nodes'' contradicts both, since returning the parent is the whole point.'
WHERE id = 1451 AND set_id = 31 AND explanation =
  'Recursive retrieval chases an explicit reference (an IndexNode pointer to a parent). Auto-merging instead looks at the leaf set and recursively merges subsets that reference the same parent beyond a threshold. The second option swaps the two; the third describes only auto-merging; and the fourth contradicts both, since returning the parent is the whole point.';

-- Q43
UPDATE questions SET explanation =
  'The negative result means the hierarchy''s benefit did not show up in whole-document QA over a single long PDF - not that auto-merging is useless. It reappears where the failure is real: a question whose answer straddles a chunk boundary in a document the retriever did find. The option calling whole-document QA the setting where auto-merging shines most inverts the lesson, since whole-document QA is precisely the setting where the benefit is invisible.'
WHERE id = 1453 AND set_id = 31 AND explanation =
  'The negative result means the hierarchy''s benefit did not show up in whole-document QA over a single long PDF - not that auto-merging is useless. It reappears where the failure is real: a question whose answer straddles a chunk boundary in a document the retriever did find. The last option inverts the lesson, since whole-document QA is precisely the setting where the benefit is invisible.';

-- Q46
UPDATE questions SET explanation =
  'DynamicLLMPathExtractor''s allowed types help steer the LLM but do not enforce exactly those types, whereas SchemaLLMPathExtractor uses a pydantic validation schema with strict mode and refuses off-schema triples. The option where Schema guides and Dynamic refuses swaps them; ''both refuse off-schema triples equally'' overstates Dynamic; and ''neither can constrain the LLM''s output'' understates Schema.'
WHERE id = 1456 AND set_id = 31 AND explanation =
  'DynamicLLMPathExtractor''s allowed types help steer the LLM but do not enforce exactly those types, whereas SchemaLLMPathExtractor uses a pydantic validation schema with strict mode and refuses off-schema triples. The second option swaps them; the third overstates Dynamic; and the fourth understates Schema.';

UPDATE quiz_sets SET shuffle_options = 1 WHERE id = 31
  AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND q.explanation IN (
    'Metadata filtering constrains which nodes are candidates, using the vector store''s own predicate support - cheap, but you can only express what the store can filter. Metadata replacement moves the constraint into a second index (match a summary or entity, return the source), which costs more to build and redefines the retrieved unit. The cost claim is reversed in the ''filtering is expensive, replacement is cheap'' option; ''both are the same operation'' collapses a real distinction; and ''filtering creates new retrieval signal'' gets the direction backwards - filters can only exclude, while replacement can surface nodes whose own text never matched.',
    'The keyword table builds a mapping from each keyword to its nodes and goes straight from query terms to that node set - a lookup, not a ranking - trading expressiveness for cost. BM25 scores each term against each document to produce a ranking. The option giving the keyword table BM25''s scoring swaps them; ''both rank all documents'' and ''both return an unordered node set'' collapse a real distinction that matters for cost and behaviour.',
    'The index extracts a summary per document (an LLM call - the summaries are produced by a response synthesizer) and stores that summary alongside the nodes; the embedding model supports the default embedding-based retrieval path over those summaries. The option where the LLM embeds and the embedder writes the summaries swaps the two models'' roles; deduplication is not their job; and the index demonstrably needs both, as the constructor requires them.',
    'A node reference is a pointer: the cheap small unit (the reference) is what gets matched for precision, and the expensive large unit (the referent, the parent) is what gets returned - a pointer chase. Matching the parent and returning the child reverses the direction; returning only the child returns no parent at all; and returning the parent with all its siblings over-returns by dragging in siblings, which references do not do.',
    'Recursive retrieval chases an explicit reference (an IndexNode pointer to a parent). Auto-merging instead looks at the leaf set and recursively merges subsets that reference the same parent beyond a threshold. The option where recursive merges by threshold and auto-merging follows a pointer swaps the two; ''both merge leaf nodes by an embedding-similarity threshold'' describes only auto-merging; and ''both return only the leaf nodes'' contradicts both, since returning the parent is the whole point.',
    'The negative result means the hierarchy''s benefit did not show up in whole-document QA over a single long PDF - not that auto-merging is useless. It reappears where the failure is real: a question whose answer straddles a chunk boundary in a document the retriever did find. The option calling whole-document QA the setting where auto-merging shines most inverts the lesson, since whole-document QA is precisely the setting where the benefit is invisible.',
    'DynamicLLMPathExtractor''s allowed types help steer the LLM but do not enforce exactly those types, whereas SchemaLLMPathExtractor uses a pydantic validation schema with strict mode and refuses off-schema triples. The option where Schema guides and Dynamic refuses swaps them; ''both refuse off-schema triples equally'' overstates Dynamic; and ''neither can constrain the LLM''s output'' understates Schema.'))
  AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id AND (
      instr(q.explanation, 'The last option inverts the lesson') > 0
      OR instr(q.explanation, 'The second option reverses the direction; the third returns no parent at all; and the fourth over-returns') > 0
      OR instr(q.explanation, 'The second option swaps the two models'' roles') > 0
      OR instr(q.explanation, 'The second option swaps the two; the third describes only auto-merging; and the fourth contradicts both') > 0
      OR instr(q.explanation, 'The second option swaps them; the third and fourth collapse') > 0
      OR instr(q.explanation, 'The second option swaps them; the third overstates Dynamic; and the fourth understates Schema.') > 0
      OR instr(q.explanation, 'reversed in the second option; the third collapses a real distinction; and the fourth gets the direction backwards') > 0));

-- Two more sets number their options in their explanations ("Option 2 inverts the two;
-- option 3 is wrong ..."), which 0006's check missed, so 0006 turned their option shuffle on.
-- Their explanations are not rewritten here; they keep option order, as 0006 did for the 8
-- sets above. shuffle_questions stays on. Each is keyed by id and guarded by one exact phrase.

-- Set 12 "RAG · Grounding and Citations (M12)", 25 explanations, e.g. question id 360:
--   "Option 2 inverts the two; option 3 is wrong because attribution genuinely held"
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 12 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND instr(q.explanation, 'Option 2 inverts the two; option 3 is wrong because attribution genuinely held') > 0);

-- Set 34 "The Long Way Down", 2 explanations, e.g. question id 1597:
--   "Option 2 has no passthrough. Option 3 wrongly preserves the outer key."
UPDATE quiz_sets SET shuffle_options = 0 WHERE id = 34 AND EXISTS (
  SELECT 1 FROM questions q WHERE q.set_id = quiz_sets.id
    AND instr(q.explanation, 'Option 2 has no passthrough. Option 3 wrongly preserves the outer key.') > 0);
