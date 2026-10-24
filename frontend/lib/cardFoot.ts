import { formatClock } from './countdown.ts';
import { formatScore } from './score.ts';
import type { SetCard } from './types';

/**
 * The foot line of a home-page set card: resume with time left, the last score, or not attempted.
 *
 * The time left comes from the server rather than being re-derived from a deadline: a
 * paused attempt's deadline may already be in the past (the extension happens on
 * resume), so deriving would show 00:00 for an attempt that has full time left.
 */
export function cardFoot(card: SetCard): string {
  if (card.open_attempt) {
    const { remaining_ms } = card.open_attempt;
    return remaining_ms === null
      ? 'Resume'
      : `Resume · ${formatClock(Math.ceil(remaining_ms / 1000))} left`;
  }
  return card.last
    ? `Last: ${formatScore(card.last.score)} / ${formatScore(card.last.max_score)}`
    : 'Not attempted';
}
