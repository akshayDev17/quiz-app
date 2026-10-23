'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';
import {
  ApiError,
  getAttempt,
  getMe,
  isSessionExpired,
  pauseAttempt,
  resumeAttempt,
  saveAnswer,
  signOut,
  submitAttempt,
} from '../../lib/api';
import { clockOffset, TIMES_UP_OVERLAY_MS } from '../../lib/countdown';
import { letter } from '../../lib/letters';
import { isTerminal, SaveQueue, submitAfterTimeout, type SaveState } from '../../lib/saveQueue';
import { clearReauthFlag } from '../../lib/session';
import type { AttemptSession, Me } from '../../lib/types';
import ConfirmDialog from '../components/ConfirmDialog';
import Markdown from '../components/Markdown';
import Masthead from '../components/Masthead';
import QuestionNav from '../components/QuestionNav';
import Timer from '../components/Timer';

const SAVE_LABEL: Record<SaveState, string> = {
  idle: '',
  saving: 'Saving…',
  saved: 'Saved',
  error: 'Not saved — retrying',
};

const resultsUrl = (attemptId: string) => `/results?attempt=${encodeURIComponent(attemptId)}`;
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const message = (err: unknown) => (err instanceof Error ? err.message : 'Something went wrong');

function Play() {
  const router = useRouter();
  const attemptId = useSearchParams().get('attempt') ?? '';

  const [me, setMe] = useState<Me | null>(null);
  const [session, setSession] = useState<AttemptSession | null>(null);
  const [offsetMs, setOffsetMs] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  /** Selected option ids per question id, kept in the question's option order. */
  const [sel, setSel] = useState<Record<number, number[]>>({});
  const [cur, setCur] = useState(0);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  /** "Saved" is dropped on moving to another question (as in the sketch); saving and errors stay. */
  const [savedHidden, setSavedHidden] = useState(false);
  /** The save failure is terminal (dropped, not retrying) rather than waiting to retry. */
  const [saveRejected, setSaveRejected] = useState(false);
  /** A rejected answer (e.g. 422) — shown in a banner while the quiz stays usable. */
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  /** Inputs are locked while submitting and for good once time is up. */
  const [locked, setLocked] = useState(false);
  const [timesUp, setTimesUp] = useState(false);
  const [signInExpired, setSignInExpired] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  /** A pause/resume request is in flight. */
  const [pauseBusy, setPauseBusy] = useState(false);
  /** Submitted after the buzzer, but these questions' latest answers never reached the server. */
  const [unsavedAtBuzzer, setUnsavedAtBuzzer] = useState<{ attemptId: string; labels: string[] } | null>(
    null,
  );

  const queueRef = useRef<SaveQueue | null>(null);
  /** True while a flush + submit is under way: the finish sequence never runs twice at once. */
  const finishing = useRef(false);
  const timedOut = useRef(false);

  useEffect(() => {
    const queue = new SaveQueue((qid, ids, signal, keepalive) =>
      saveAnswer(attemptId, qid, ids, signal, keepalive),
    );
    queueRef.current = queue;
    // Leaving or hiding the tab: send pending answers now, as requests that outlive the page.
    const sendNow = () => queue.flushKeepalive();
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') sendNow();
    };
    window.addEventListener('pagehide', sendNow);
    document.addEventListener('visibilitychange', onVisibility);
    /** The failure already acted on; onChange fires on every change, the reaction once per failure. */
    let handled: unknown = null;
    const off = queue.onChange(() => {
      const state = queue.state();
      const err = queue.lastError;
      setSaveState(state);
      setSaveRejected(state === 'error' && isTerminal(err));
      setSavedHidden(false);
      if (state !== 'error') setSaveNotice(null);
      if (state !== 'error' || err === handled) return;
      handled = err;
      if (isSessionExpired(err)) {
        setSignInExpired(true);
      } else if (err instanceof ApiError && (err.status === 409 || err.status === 404)) {
        // Most likely finished elsewhere (another tab, or expired): if so, show the results.
        getAttempt(attemptId).then(
          (s) => {
            if (s.attempt.status !== 'in_progress') router.replace(resultsUrl(s.attempt.id));
            else setSaveNotice(`Answer not saved: ${err.message}`);
          },
          (e) => {
            if (isSessionExpired(e)) setSignInExpired(true);
            else setSaveNotice(`Answer not saved: ${err.message}`);
          },
        );
      } else if (isTerminal(err)) {
        setSaveNotice(`Answer not saved: ${message(err)}`);
      }
    });
    return () => {
      window.removeEventListener('pagehide', sendNow);
      document.removeEventListener('visibilitychange', onVisibility);
      off();
      queue.dispose();
    };
  }, [attemptId, router]);

  useEffect(() => {
    if (!attemptId) {
      setLoadError('No such attempt');
      return;
    }
    getMe().then(setMe, () => {
      // The masthead can do without the name; getAttempt reports a real failure.
    });
    getAttempt(attemptId).then(
      (s) => {
        clearReauthFlag();
        if (s.attempt.status !== 'in_progress') {
          router.replace(resultsUrl(s.attempt.id));
          return;
        }
        setOffsetMs(clockOffset(s.server_now, Date.now()));
        const restored: Record<number, number[]> = {};
        for (const [qid, ids] of Object.entries(s.selections)) restored[Number(qid)] = ids;
        setSel(restored);
        setSession(s);
      },
      (err) => {
        if (isSessionExpired(err)) setSignInExpired(true);
        else setLoadError(message(err));
      },
    );
  }, [attemptId, router]);

  const questions = session?.questions ?? [];
  const question = questions[cur];
  const answered = questions.map((q) => (sel[q.id]?.length ?? 0) > 0);
  const answeredCount = answered.filter(Boolean).length;
  /** A paused attempt freezes the clock and locks the answers until resumed. */
  const paused = session?.attempt.paused_at != null;
  const inputsOff = locked || confirmOpen || signInExpired || paused;

  function reportFinishError(err: unknown) {
    if (isSessionExpired(err)) setSignInExpired(true);
    else setSubmitError(`Could not submit: ${message(err)}`);
  }

  /** Freeze the clock (saving pending answers first) or resume it. */
  async function togglePause() {
    if (!session || pauseBusy) return;
    setPauseBusy(true);
    setSubmitError(null);
    try {
      if (session.attempt.paused_at != null) {
        const s = await resumeAttempt(attemptId);
        setOffsetMs(clockOffset(s.server_now, Date.now()));
        setSession(s);
      } else {
        await queueRef.current?.flush(); // save pending answers before freezing
        const s = await pauseAttempt(attemptId);
        setOffsetMs(clockOffset(s.server_now, Date.now()));
        setSession(s);
      }
    } catch (err) {
      if (isSessionExpired(err)) setSignInExpired(true);
      else setSubmitError(message(err));
    } finally {
      setPauseBusy(false);
    }
  }

  const submitOnServer = async () => (await submitAttempt(attemptId)).attempt_id;

  /**
   * Submit by choice: save what is pending, submit, move to the results. A save that still fails
   * stops the submit, so no answer is silently dropped. (A terminally rejected save, e.g. 409,
   * never makes flush reject: the submit itself then reports the attempt's real state.)
   */
  async function submit() {
    if (finishing.current) return;
    finishing.current = true;
    setConfirmOpen(false);
    setLocked(true);
    setSubmitError(null);
    try {
      await queueRef.current?.flush();
      router.replace(resultsUrl(await submitOnServer()));
    } catch (err) {
      finishing.current = false;
      // Time ran out while this was on its way: hand over to the timeout sequence.
      if (timedOut.current && !isSessionExpired(err)) return void finishAfterTimeout();
      setLocked(false);
      reportFinishError(err);
    }
  }

  /**
   * After the buzzer: keep retrying unsaved answers within the grace budget, submit regardless,
   * and if some answers never made it, say which before moving on.
   */
  async function finishAfterTimeout() {
    if (finishing.current) return;
    finishing.current = true;
    setTimesUp(true);
    setSubmitError(null);
    const overlay = sleep(TIMES_UP_OVERLAY_MS);
    try {
      const { attemptId: id, unsaved } = await submitAfterTimeout(queueRef.current!, submitOnServer);
      // Submitted: stop retrying, or a late 409 would whisk the reader past the notice below.
      queueRef.current?.dispose();
      await overlay;
      if (unsaved.length === 0) {
        router.replace(resultsUrl(id));
        return;
      }
      const labels = unsaved.map((qid) => `Q${questions.findIndex((q) => q.id === qid) + 1}`);
      setUnsavedAtBuzzer({ attemptId: id, labels });
    } catch (err) {
      await overlay;
      finishing.current = false;
      setTimesUp(false);
      reportFinishError(err);
    }
  }

  /** The timeout sequence. `<Timer>` calls it once; `finishing` keeps it off a submit in flight. */
  function onTimeUp() {
    timedOut.current = true;
    setLocked(true);
    setConfirmOpen(false);
    setTimesUp(true);
    void finishAfterTimeout();
  }

  function toggle(optionId: number) {
    if (inputsOff || !question) return;
    const now = sel[question.id] ?? [];
    const next = now.includes(optionId) ? now.filter((x) => x !== optionId) : [...now, optionId];
    const ordered = question.options.map((o) => o.id).filter((oid) => next.includes(oid));
    setSel({ ...sel, [question.id]: ordered });
    queueRef.current?.set(question.id, ordered);
  }

  function jump(i: number) {
    setCur(Math.max(0, Math.min(questions.length - 1, i)));
    setSavedHidden(true);
  }

  // Keys 1–9 toggle options, arrows move. Off while a dialog is open or once finishing.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (inputsOff || !question || e.altKey || e.ctrlKey || e.metaKey) return;
      const n = Number(e.key);
      if (Number.isInteger(n) && n >= 1 && n <= 9 && n <= question.options.length) {
        e.preventDefault();
        toggle(question.options[n - 1].id);
      } else if (e.key === 'ArrowRight') {
        jump(cur + 1);
      } else if (e.key === 'ArrowLeft') {
        jump(cur - 1);
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  });

  const unanswered = questions.flatMap((_, i) => (answered[i] ? [] : [`Q${i + 1}`]));
  const saveLabel =
    saveState === 'saved' && savedHidden ? '' : saveRejected ? 'Not saved' : SAVE_LABEL[saveState];

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} />
      {loadError && <div className="banner">{loadError}</div>}
      {!loadError && !session && !signInExpired && <p className="mc">Loading…</p>}
      {session && question && (
        <section>
          <div className="bar">
            <span className="title">{session.set.name}</span>
            <span className="mc">{answeredCount} / {questions.length} answered</span>
            {session.attempt.deadline_at !== null && (
              <Timer
                deadlineAt={session.attempt.deadline_at}
                offsetMs={offsetMs}
                pausedAt={session.attempt.paused_at}
                onExpire={onTimeUp}
              />
            )}
            {session.attempt.deadline_at !== null && (
              <button
                className="btn ghost"
                onClick={togglePause}
                disabled={locked || confirmOpen || signInExpired || pauseBusy}
              >
                {paused ? 'Resume' : 'Pause'}
              </button>
            )}
            <button className="btn" onClick={() => setConfirmOpen(true)} disabled={inputsOff}>
              Submit
            </button>
          </div>
          {saveNotice && <div className="banner">{saveNotice}</div>}
          {submitError && (
            <div className="banner">
              {submitError}{' '}
              <button className="linkbtn" onClick={timedOut.current ? finishAfterTimeout : submit}>
                Try again
              </button>
            </div>
          )}
          <div className="layout">
            <div className={locked ? 'card qcard locked' : 'card qcard'}>
              <div className="kicker">Question {cur + 1} of {questions.length}</div>
              <div className="qprompt">
                <Markdown text={question.prompt} />
              </div>
              <div className="mc hint">Select all that apply</div>
              {question.options.map((o, i) => {
                const on = (sel[question.id] ?? []).includes(o.id);
                return (
                  <label key={o.id} className={on ? 'opt sel' : 'opt'}>
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={inputsOff}
                      onChange={() => toggle(o.id)}
                    />
                    <span className="letter">{letter(i)}</span>
                    <div>
                      <Markdown text={o.body} />
                    </div>
                  </label>
                );
              })}
              <div className="row">
                <button className="btn ghost" onClick={() => jump(cur - 1)} disabled={cur === 0}>
                  ← Previous
                </button>
                <span className="mc saved" aria-live="polite">{saveLabel}</span>
                <button
                  className="btn ghost"
                  onClick={() => jump(cur + 1)}
                  disabled={cur === questions.length - 1}
                >
                  Next →
                </button>
              </div>
            </div>
            <QuestionNav answered={answered} current={cur} onJump={jump} />
          </div>
        </section>
      )}
      {confirmOpen && (
        <ConfirmDialog
          total={questions.length}
          unanswered={unanswered}
          onConfirm={submit}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
      {timesUp && (
        <div className="scrim on" role="alert">
          <div className="timesup">
            Time’s up
            {unsavedAtBuzzer ? (
              <>
                <span className="mc">
                  Not saved: {unsavedAtBuzzer.labels.join(', ')}. Your other answers were submitted.
                </span>
                <button
                  className="btn"
                  style={{ marginTop: 'var(--s4)' }}
                  onClick={() => router.replace(resultsUrl(unsavedAtBuzzer.attemptId))}
                  autoFocus
                >
                  See results
                </button>
              </>
            ) : (
              <span className="mc">Submitting your saved answers</span>
            )}
          </div>
        </div>
      )}
      {signInExpired && (
        <div className="scrim on">
          <div className="card dialog" role="alertdialog" aria-modal="true" aria-describedby="signin-expired">
            <p id="signin-expired">
              Your sign-in expired. Sign in again to continue — your saved answers and the timer are
              kept on the server.
            </p>
            <div className="row">
              <button className="btn" onClick={() => window.location.reload()} autoFocus>
                Sign in again
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PlayPage() {
  return (
    <Suspense fallback={null}>
      <Play />
    </Suspense>
  );
}
