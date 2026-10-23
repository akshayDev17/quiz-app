'use client';

import { useEffect, useRef, useState } from 'react';
import { formatClock, remainingSeconds, timerTone } from '../../lib/countdown';

/**
 * The countdown in the play bar.
 *
 * One 250 ms interval recomputes the time left from the absolute deadline on every tick, so a
 * throttled tab or a sleeping laptop shows the true time the moment it wakes. `onExpire` fires
 * exactly once, on the first tick that sees zero, however many ticks see it after that.
 */
export default function Timer({
  deadlineAt,
  offsetMs,
  onExpire,
}: {
  deadlineAt: number;
  /** Server clock minus client clock (`clockOffset`). */
  offsetMs: number;
  onExpire: () => void;
}) {
  const [seconds, setSeconds] = useState(() => remainingSeconds(deadlineAt, offsetMs, Date.now()));
  const fired = useRef(false);
  const expire = useRef(onExpire);
  expire.current = onExpire;

  useEffect(() => {
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
  }, [deadlineAt, offsetMs]);

  const tone = timerTone(seconds);
  return (
    <span className={tone === 'normal' ? 'timer' : `timer ${tone}`} role="timer" aria-label="Time left">
      {formatClock(seconds)}
    </span>
  );
}
