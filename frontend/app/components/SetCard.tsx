import Link from 'next/link';
import { formatClock } from '../../lib/countdown';
import { pluralize } from '../../lib/names';
import { formatScore } from '../../lib/score';
import type { SetCard as SetCardData } from '../../lib/types';

/** The card's foot line, split into three visual tiers:
 *  resume (filled accent pill) > last score (faint accent chip) > not attempted (muted text). */
function Foot({ card }: { card: SetCardData }) {
  if (card.open_attempt) {
    const { remaining_ms } = card.open_attempt;
    const time = remaining_ms === null ? null : `${formatClock(Math.ceil(remaining_ms / 1000))} left`;
    return (
      <span className="pill">
        <span className="arrow">Resume →</span>
        {time && <span className="time">{time}</span>}
      </span>
    );
  }
  if (card.last) {
    return (
      <span className="chip score">
        Last: {formatScore(card.last.score)} / {formatScore(card.last.max_score)}
      </span>
    );
  }
  return <span>Not attempted</span>;
}

/** One set on the home page. Links to the open attempt when there is one, else to the set intro. */
export default function SetCard({ card, kicker }: { card: SetCardData; kicker?: string }) {
  const href = card.open_attempt
    ? `/play?attempt=${encodeURIComponent(card.open_attempt.attempt_id)}`
    : `/set?id=${card.id}`;
  return (
    <Link className="card set-card" href={href}>
      {kicker && <div className="kicker-c">{kicker}</div>}
      <h3>{card.short_name}</h3>
      <div className="chips">
        <span className={card.time_limit_minutes ? 'chip timed' : 'chip'}>
          {card.time_limit_minutes ? `${card.time_limit_minutes} min` : 'Untimed'}
        </span>
        <span className="chip">{pluralize(card.question_count, 'question')}</span>
      </div>
      <div className={`mc foot${card.open_attempt ? ' resume' : ''}`}>
        <Foot card={card} />
      </div>
    </Link>
  );
}
