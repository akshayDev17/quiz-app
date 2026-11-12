import Link from 'next/link';
import { pluralize } from '../../lib/names';
import type { PublicSetCard as PublicSetCardData } from '../../lib/types';

/**
 * The "Sign up · coming soon" button: disabled until sign-up opens. Shared by the signed-out
 * card and View's footer.
 */
export function SignUpSoon() {
  return (
    <button className="btn ghost soon" disabled>
      Sign up<span className="sub">coming soon</span>
    </button>
  );
}

/**
 * One set on the home page for a signed-out visitor: SetCard's head and chips, but the card is
 * not a link. Its foot carries the two ways on, as equal buttons: sign up (not open yet) and
 * View, the one live action, so it is the filled one.
 */
export default function PublicSetCard({ card, kicker }: { card: PublicSetCardData; kicker?: string }) {
  return (
    <div className="card set-card public">
      {kicker && <div className="kicker-c">{kicker}</div>}
      <h3>{card.short_name}</h3>
      <div className="chips">
        <span className={card.time_limit_minutes ? 'chip timed' : 'chip'}>
          {card.time_limit_minutes ? `${card.time_limit_minutes} min` : 'Untimed'}
        </span>
        <span className="chip">{pluralize(card.question_count, 'question')}</span>
      </div>
      <div className="foot actions">
        <SignUpSoon />
        <Link className="btn" href={`/view?id=${card.id}`} aria-label={`View ${card.name}`}>View</Link>
      </div>
    </div>
  );
}
