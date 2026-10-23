/** Timer turns amber below this many seconds remaining. */
export const AMBER_BELOW_S = 300;
/** Timer turns red below this many seconds remaining. */
export const RED_BELOW_S = 60;
/** Quiet period after the last answer change before it is saved. */
export const AUTOSAVE_DEBOUNCE_MS = 400;
/** How long the "Time's up" overlay shows before moving on to results. */
export const TIMES_UP_OVERLAY_MS = 1500;

/** Server clock minus client clock, in ms. Add it to the client clock to get server time. */
export function clockOffset(serverNow: number, clientNow: number): number {
  return serverNow - clientNow;
}

/**
 * Whole seconds left until the deadline, never negative.
 *
 * Recomputed from the absolute deadline on every call rather than decremented,
 * so a sleeping laptop or a throttled background tab cannot make it drift.
 */
export function remainingSeconds(deadlineAt: number, offsetMs: number, clientNow: number): number {
  return Math.max(0, Math.ceil((deadlineAt - (clientNow + offsetMs)) / 1000));
}

export function timerTone(s: number): 'normal' | 'amber' | 'red' {
  if (s < RED_BELOW_S) return 'red';
  if (s < AMBER_BELOW_S) return 'amber';
  return 'normal';
}

/** `MM:SS`, or `H:MM:SS` from one hour up. */
export function formatClock(s: number): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}
