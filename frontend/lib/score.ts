/** The marks every quiz is taken under, as the backend's `NegativeMarking` applies them. */
export const MARKING_RULE =
  'Each correct option you tick earns +2 and each wrong one costs −1; a correct option left unticked costs nothing. ' +
  'A question left blank costs −2.';

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

/** `score / max_score` as a whole percent, below zero when the score is; 0 when there is nothing to score. */
export function percent(score: number, maxScore: number): number {
  return maxScore > 0 ? Math.round((100 * score) / maxScore) : 0;
}
