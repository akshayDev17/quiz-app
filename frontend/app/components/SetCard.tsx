import Link from 'next/link';
import { formatClock, remainingSeconds } from '../../lib/countdown';
import { pluralize } from '../../lib/names';
import type { SetCard as SetCardData } from '../../lib/types';

function foot(card: SetCardData): string {
  if (card.open_attempt) {
    const { deadline_at } = card.open_attempt;
    // The topics response carries no server time, so this uses the device clock: close enough
    // for a label. The play screen corrects for the offset.
    return deadline_at === null
      ? 'Resume'
      : `Resume · ${formatClock(remainingSeconds(deadline_at, 0, Date.now()))} left`;
  }
  return card.last ? `Last: ${card.last.score} / ${card.last.max_score}` : 'Not attempted';
}

/** One set on the home page. Links to the open attempt when there is one, else to the set intro. */
export default function SetCard({ card }: { card: SetCardData }) {
  const href = card.open_attempt
    ? `/play?attempt=${encodeURIComponent(card.open_attempt.attempt_id)}`
    : `/set?id=${card.id}`;
  const text = foot(card);
  const active = card.open_attempt !== null || card.last !== null;
  return (
    <Link className="card set-card" href={href}>
      <h3>{card.short_name}</h3>
      <div className="chips">
        <span className={card.time_limit_minutes ? 'chip timed' : 'chip'}>
          {card.time_limit_minutes ? `${card.time_limit_minutes} min` : 'Untimed'}
        </span>
        <span className="chip">{pluralize(card.question_count, 'question')}</span>
      </div>
      <div className="mc foot">{active ? <span className="state">{text}</span> : text}</div>
    </Link>
  );
}
