import { ApiError, isSessionExpired } from './api.ts';
import { AUTOSAVE_DEBOUNCE_MS } from './countdown.ts';

export type SaveState = 'idle' | 'saving' | 'saved' | 'error';
/**
 * Saves one answer. The queue aborts `signal` when the save outlives `SAVE_TIMEOUT_MS`, except for
 * a `keepalive` save (sent as the page goes away), which is left to finish on its own.
 */
export type SaveFn = (qid: number, ids: number[], signal: AbortSignal, keepalive?: boolean) => Promise<void>;

/** Retry delays after the 1st, 2nd, 3rd… consecutive failure; the last one repeats. */
const BACKOFF_MS = [1000, 2000, 4000, 8000];
/** A save still pending after this long is aborted and counted as a (retryable) failure. */
export const SAVE_TIMEOUT_MS = 5000;
/**
 * How long the timeout sequence keeps retrying unsaved answers before it submits anyway. The
 * server accepts writes for GRACE_MS (10 s) after the deadline; this stays under it with room for
 * the submit itself.
 */
export const TIMEOUT_SAVE_BUDGET_MS = 8000;

/** A save that did not answer within `SAVE_TIMEOUT_MS`. */
export class SaveTimeoutError extends Error {
  constructor() {
    super('save timed out');
    this.name = 'SaveTimeoutError';
  }
}

/** `flush(budgetMs)` ran out of time; these questions' latest answers are not on the server. */
export class UnsavedAnswers extends Error {
  readonly questionIds: number[];

  constructor(questionIds: number[]) {
    super(`answers not saved for questions ${questionIds.join(', ')}`);
    this.name = 'UnsavedAnswers';
    this.questionIds = questionIds;
  }
}

/** Network errors and 5xx may pass; they are retried. */
export function isRetryable(error: unknown): boolean {
  return !(error instanceof ApiError) || error.status >= 500;
}

/**
 * A rejection retrying cannot fix (409 attempt finished, 404, 422, any other 4xx but 401): the
 * entry is dropped. A 401 is not terminal: the value is kept for after the reader signs in again.
 */
export function isTerminal(error: unknown): boolean {
  return !isRetryable(error) && !isSessionExpired(error);
}

/** One question's latest unsaved value and where it is in its save. */
type Entry = {
  ids: number[];
  /** Bumped by every `set`, so a finishing save can tell whether it sent the latest value. */
  version: number;
  /** The debounce or retry timer, if one is waiting. */
  timer: ReturnType<typeof setTimeout> | null;
  inFlight: Promise<void> | null;
  failures: number;
  error: unknown;
};

/**
 * Autosave for the play screen: per-question debounce, one save in flight per question, and
 * retry with backoff until the latest value is on the server.
 *
 * An entry exists while its question has a value the server has not confirmed. A newer `set`
 * replaces the value and supersedes a waiting retry. Only network errors and 5xx are retried.
 * A save that fails because the sign-in expired keeps its entry but is not retried: retrying
 * cannot succeed until the reader signs in again. Any other 4xx is terminal (`isTerminal`): the
 * entry is dropped and its question reports 'error' until it is answered again; `flush` does not
 * wait on or reject for it (the submit that follows gets the server's verdict itself).
 */
export class SaveQueue {
  /** The error from the most recent failed save; read it when `state()` is `'error'`. */
  lastError: unknown = null;

  private readonly save: SaveFn;
  private readonly debounceMs: number;
  private readonly entries = new Map<number, Entry>();
  /** Questions whose last save was rejected terminally, until they are answered again. */
  private readonly rejected = new Set<number>();
  private readonly listeners = new Set<() => void>();
  private savedAny = false;

  constructor(save: SaveFn, debounceMs = AUTOSAVE_DEBOUNCE_MS) {
    this.save = save;
    this.debounceMs = debounceMs;
  }

  /** Records `ids` as the answer to `qid` and saves it once `qid` has been quiet for the debounce. */
  set(qid: number, ids: number[]): void {
    const prev = this.entries.get(qid);
    const entry: Entry = prev ?? { ids, version: 0, timer: null, inFlight: null, failures: 0, error: null };
    entry.ids = [...ids];
    entry.version += 1;
    entry.failures = 0;
    entry.error = null;
    this.entries.set(qid, entry);
    this.rejected.delete(qid);
    this.schedule(qid, entry, this.debounceMs);
    this.notify();
  }

  /**
   * Sends every pending value now and resolves once all of them are saved. It cannot hang: every
   * save times out after `SAVE_TIMEOUT_MS`.
   *
   * Without a budget, a value that has already failed gets one immediate retry here; if that
   * fails too, flush rejects with its error so the caller can show it.
   * With `budgetMs`, failed values keep retrying on the queue's backoff until they land or the
   * budget runs out; then flush rejects with `UnsavedAnswers` naming the questions left.
   * Either way an expired sign-in rejects at once, and terminally rejected values are not waited on.
   */
  async flush(budgetMs = 0): Promise<void> {
    const all = Promise.all([...this.entries.keys()].map((qid) => this.flushOne(qid, budgetMs > 0)));
    if (budgetMs <= 0) {
      await all;
      return;
    }
    let timer: ReturnType<typeof setTimeout> | undefined;
    const outOfTime = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new UnsavedAnswers(this.unsaved())), budgetMs);
    });
    try {
      await Promise.race([all, outOfTime]);
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Sends every pending value now as a keepalive request, without waiting: for `pagehide` and the
   * tab being hidden, when debounce and retry timers may never fire. A value already in flight is
   * left alone; a newer value behind it follows on the usual path.
   */
  flushKeepalive(): void {
    for (const [qid, entry] of this.entries) this.send(qid, entry, true);
  }

  /**
   * The answers this queue still holds: values the server has not confirmed. A pause
   * sends these so the freeze and the answers commit together rather than the freeze
   * landing first and the autosave being refused behind it.
   */
  pendingAnswers(): { question_id: number; option_ids: number[] }[] {
    return [...this.entries].map(([questionId, entry]) => ({
      question_id: questionId,
      option_ids: [...entry.ids],
    }));
  }

  /** Questions whose latest answer the server has not confirmed (rejected ones excluded). */
  unsaved(): number[] {
    return [...this.entries.keys()];
  }

  state(): SaveState {
    if (this.rejected.size > 0) return 'error';
    if (this.entries.size === 0) return this.savedAny ? 'saved' : 'idle';
    for (const e of this.entries.values()) if (e.error !== null) return 'error';
    return 'saving';
  }

  /** Calls `cb` whenever the state may have changed. Returns the unsubscribe. */
  onChange(cb: () => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  /** Cancels every waiting timer, for when the page goes away. In-flight saves still finish. */
  dispose(): void {
    for (const e of this.entries.values()) this.clearTimer(e);
    this.listeners.clear();
  }

  private async flushOne(qid: number, keepRetrying: boolean): Promise<void> {
    let sentHere = false;
    for (;;) {
      const entry = this.entries.get(qid);
      if (!entry) return;
      if (entry.inFlight) {
        await entry.inFlight;
        continue;
      }
      if (isSessionExpired(entry.error)) throw entry.error;
      if (entry.error !== null && sentHere) {
        if (!keepRetrying) throw entry.error;
        await this.nextChange(); // the backoff timer resends; the caller's budget bounds the wait
        continue;
      }
      sentHere = true;
      this.send(qid, entry);
    }
  }

  private nextChange(): Promise<void> {
    return new Promise((resolve) => {
      const off = this.onChange(() => {
        off();
        resolve();
      });
    });
  }

  private schedule(qid: number, entry: Entry, delayMs: number): void {
    this.clearTimer(entry);
    entry.timer = setTimeout(() => {
      entry.timer = null;
      this.send(qid, entry);
    }, delayMs);
  }

  private clearTimer(entry: Entry): void {
    if (entry.timer !== null) clearTimeout(entry.timer);
    entry.timer = null;
  }

  /** Starts a save of the entry's current value, unless one is already in flight (it resends on landing). */
  private send(qid: number, entry: Entry, keepalive = false): void {
    this.clearTimer(entry);
    if (entry.inFlight) return;
    const version = entry.version;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    // A keepalive save is never aborted (it is meant to outlive the page), but the queue still
    // stops waiting on it after the timeout, so flush cannot hang.
    const timedOut = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        if (!keepalive) controller.abort();
        reject(new SaveTimeoutError());
      }, SAVE_TIMEOUT_MS);
    });
    const attempt = Promise.race([this.save(qid, entry.ids, controller.signal, keepalive), timedOut]);
    entry.inFlight = attempt.finally(() => clearTimeout(timer)).then(
      () => {
        entry.inFlight = null;
        if (entry.version === version) {
          this.entries.delete(qid);
          this.savedAny = true;
        } else if (entry.timer === null) {
          // A newer value arrived while this one was in flight and its debounce already ran out.
          this.send(qid, entry);
        }
        this.notify();
      },
      (err: unknown) => {
        entry.inFlight = null;
        if (entry.version !== version) {
          if (entry.timer === null) this.send(qid, entry);
        } else if (isTerminal(err)) {
          this.entries.delete(qid);
          this.rejected.add(qid);
          this.lastError = err;
        } else {
          entry.failures += 1;
          entry.error = err;
          this.lastError = err;
          if (isRetryable(err)) {
            this.schedule(qid, entry, BACKOFF_MS[Math.min(entry.failures, BACKOFF_MS.length) - 1]);
          }
        }
        this.notify();
      },
    );
    this.notify();
  }

  private notify(): void {
    for (const cb of this.listeners) cb();
  }
}

/**
 * The save half of the timeout sequence: retry what is unsaved within `TIMEOUT_SAVE_BUDGET_MS`
 * (the server's grace period lets those writes land), then submit regardless — the clock has run
 * out. Resolves with the attempt id from `submit` and the questions whose answers did not make it.
 * An expired sign-in is rethrown without submitting: nothing can be sent until it is renewed.
 */
export async function submitAfterTimeout(
  queue: SaveQueue,
  submit: () => Promise<string>,
): Promise<{ attemptId: string; unsaved: number[] }> {
  let unsaved: number[] = [];
  try {
    await queue.flush(TIMEOUT_SAVE_BUDGET_MS);
  } catch (err) {
    if (isSessionExpired(err)) throw err;
    unsaved = err instanceof UnsavedAnswers ? err.questionIds : queue.unsaved();
  }
  return { attemptId: await submit(), unsaved };
}
