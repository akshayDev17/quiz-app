/** A score for display: at most 2 decimals, trailing zeros trimmed (`2.5`, `4`, `0.33`). */
export function formatScore(n: number): string {
  return String(Math.round(n * 100) / 100);
}

/** `score / max_score` as a whole percent; 0 when there is nothing to score. */
export function percent(score: number, maxScore: number): number {
  return maxScore > 0 ? Math.round((100 * score) / maxScore) : 0;
}
