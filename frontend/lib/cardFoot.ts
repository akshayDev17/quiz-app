import { formatClock, remainingSeconds } from './countdown.ts';
import { formatScore } from './score.ts';
import type { SetCard } from './types';

/** The foot line of a home-page set card: resume with time left, the last score, or not attempted. */
export function cardFoot(card: SetCard, nowMs: number): string {
  if (card.open_attempt) {
    const { deadline_at } = card.open_attempt;
    // The topics response carries no server time, so this uses the device clock: close enough
    // for a label. The play screen corrects for the offset.
    return deadline_at === null
      ? 'Resume'
      : `Resume · ${formatClock(remainingSeconds(deadline_at, 0, nowMs))} left`;
  }
  return card.last
    ? `Last: ${formatScore(card.last.score)} / ${formatScore(card.last.max_score)}`
    : 'Not attempted';
}
