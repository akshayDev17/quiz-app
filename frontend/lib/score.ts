import { pluralize } from './names.ts';

/** The marks every quiz is taken under, as the backend's `NegativeMarking` applies them. */
export const MARKING_RULE =
  'Each correct option you tick earns +2 and each wrong one costs −1; a correct option left unticked costs nothing. ' +
  'A question left blank costs −2.';

/** What a written (subjective) question is worth, as the backend's `SUBJECTIVE_MARKS`. */
export const WRITTEN_MARKS = 4;

/** How written answers are marked (ADR 0010): out of 4 by the AI evaluator, never below 0. */
export const WRITTEN_RULE =
  `Each written answer is marked out of ${WRITTEN_MARKS} by an AI evaluator against the model answer, ` +
  'with partial credit; a blank or wrong one scores 0, never less.';

/**
 * The set intro's line on what a set holds and its line on how it is marked, for a set of
 * `questionCount` questions of which `subjectiveCount` are written (marked 0–4 by the AI evaluator).
 * A set with no choice questions drops the choice-only copy; a mixed one gives both rules.
 */
export function writeIntroRules(questionCount: number, subjectiveCount: number): { questions: string; marking: string } {
  const count = pluralize(questionCount, 'question');
  if (subjectiveCount >= questionCount) {
    return { questions: `${count}, each answered in writing.`, marking: WRITTEN_RULE };
  }
  return {
    questions: `${count}. Some have more than one correct answer.`,
    marking: subjectiveCount > 0 ? `${MARKING_RULE} ${WRITTEN_RULE}` : MARKING_RULE,
  };
}

/** The same rule in a few words, for tight spots. */
export const MARKING_SHORT = '+2 right · −1 wrong · −2 blank';

/** The most a question can score: +2 for each of its correct options. */
export function maxMarks(correctOptions: number): number {
  return 2 * correctOptions;
}

/** A score for display: at most 2 decimals, trailing zeros trimmed (`2.5`, `4`, `0.33`), and a
 *  true minus sign below zero (`−3`). */
export function formatScore(n: number): string {
  const rounded = Math.round(n * 100) / 100;
  return rounded < 0 ? `−${String(-rounded)}` : String(Math.abs(rounded));
}

/** What an attempt reads as when nothing in it is marked: an all-written set taken before written
 *  answers were marked (its max_score is 0). */
export const NOT_MARKED = 'Not marked';

/** Whether an attempt has anything to score: false only when its max_score is 0. */
export function isMarked(maxScore: number): boolean {
  return maxScore > 0;
}

/**
 * An attempt's score in a line: `score / max_score`, or "Not marked" when nothing in it is marked.
 * With written answers still awaiting the evaluator, the score so far is provisional, and says so.
 */
export function scoreLine(score: number, maxScore: number, awaiting = 0): string {
  if (!isMarked(maxScore)) return NOT_MARKED;
  const line = `${formatScore(score)} / ${formatScore(maxScore)}`;
  return awaiting > 0 ? `${line} · ${awaiting} awaiting` : line;
}

/** `score / max_score` as a whole percent, below zero when the score is. Only for a marked attempt (`isMarked`). */
export function percent(score: number, maxScore: number): number {
  return Math.round((100 * score) / maxScore);
}
