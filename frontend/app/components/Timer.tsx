'use client';

import { useEffect, useRef, useState } from 'react';
import { formatClock, remainingSeconds, timerTone } from '../../lib/countdown';

/**
 * The countdown in the play bar.
 *
 * One 250 ms interval recomputes the time left from the absolute deadline on every tick, so a
 * throttled tab or a sleeping laptop shows the true time the moment it wakes. `onExpire` fires
 * exactly once, on the first tick that sees zero, however many ticks see it after that.
 *
 * While the attempt is paused (`pausedAt` set) the clock is frozen: it shows the time left as of
 * the pause, never ticks, and never expires.
 */
export default function Timer({
  deadlineAt,
  offsetMs,
  pausedAt = null,
  onExpire,
}: {
  deadlineAt: number;
  /** Server clock minus client clock (`clockOffset`). */
  offsetMs: number;
  /** Epoch ms at which the attempt was paused, or null while running. */
  pausedAt?: number | null;
  onExpire: () => void;
}) {
  const frozenSeconds = pausedAt == null ? null : Math.max(0, Math.ceil((deadlineAt - pausedAt) / 1000));
  const [seconds, setSeconds] = useState(
    () => frozenSeconds ?? remainingSeconds(deadlineAt, offsetMs, Date.now()),
  );
  const fired = useRef(false);
  const expire = useRef(onExpire);
  expire.current = onExpire;

  useEffect(() => {
    if (frozenSeconds !== null) {
      setSeconds(frozenSeconds);
      return;
    }
    const tick = () => {
      const s = remainingSeconds(deadlineAt, offsetMs, Date.now());
      setSeconds(s);
      if (s === 0 && !fired.current) {
        fired.current = true;
        clearInterval(id);
        expire.current();
      }
    };
    const id = setInterval(tick, 250);
    tick();
    return () => clearInterval(id);
  }, [deadlineAt, offsetMs, frozenSeconds]);

  const tone = timerTone(seconds);
  const cls = `timer${tone === 'normal' ? '' : ` ${tone}`}${frozenSeconds !== null ? ' paused' : ''}`;
  return (
    <span className={cls} role="timer" aria-label={frozenSeconds !== null ? 'Timer paused' : 'Time left'}>
      {formatClock(seconds)}
    </span>
  );
}
