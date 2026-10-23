import Link from 'next/link';
import { cardFoot } from '../../lib/cardFoot';
import { pluralize } from '../../lib/names';
import type { SetCard as SetCardData } from '../../lib/types';

/** One set on the home page. Links to the open attempt when there is one, else to the set intro. */
export default function SetCard({ card }: { card: SetCardData }) {
  const href = card.open_attempt
    ? `/play?attempt=${encodeURIComponent(card.open_attempt.attempt_id)}`
    : `/set?id=${card.id}`;
  const text = cardFoot(card, Date.now());
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
