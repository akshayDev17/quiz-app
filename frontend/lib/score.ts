import { pluralize } from './names.ts';

/** The marks every quiz is taken under, as the backend's `NegativeMarking` applies them. */
export const MARKING_RULE =
  'Each correct option you tick earns +2 and each wrong one costs −1; a correct option left unticked costs nothing. ' +
  'A question left blank costs −2.';

/**
 * The set intro's line on what a set holds and its line on how it is marked, for a set of
 * `questionCount` questions of which `subjectiveCount` are written (never marked, nothing for a blank).
 * A set with no choice questions drops the choice-only copy; a mixed one keeps the marking rule
 * and adds that the written questions are not marked.
 */
export function writeIntroRules(questionCount: number, subjectiveCount: number): { questions: string; marking: string } {
  const count = pluralize(questionCount, 'question');
  if (subjectiveCount >= questionCount) {
    return { questions: `${count}, each answered in writing.`, marking: 'Written answers are not marked.' };
  }
  return {
    questions: `${count}. Some have more than one correct answer.`,
    marking: subjectiveCount > 0
      ? `${MARKING_RULE} Written questions are not marked, so leaving one blank costs nothing.`
      : MARKING_RULE,
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

/** What an attempt reads as when nothing in its set is marked: every question is subjective. */
export const NOT_MARKED = 'Not marked';

/** Whether an attempt has anything to score: false when every question in its set is subjective, so max_score is 0. */
export function isMarked(maxScore: number): boolean {
  return maxScore > 0;
}

/** An attempt's score in a line: `score / max_score`, or "Not marked" when nothing in its set is marked. */
export function scoreLine(score: number, maxScore: number): string {
  return isMarked(maxScore) ? `${formatScore(score)} / ${formatScore(maxScore)}` : NOT_MARKED;
}

/** `score / max_score` as a whole percent, below zero when the score is. Only for a marked attempt (`isMarked`). */
export function percent(score: number, maxScore: number): number {
  return Math.round((100 * score) / maxScore);
}
