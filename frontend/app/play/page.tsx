'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';
import {
  ApiError,
  getAttempt,
  getMe,
  isSessionExpired,
  saveAnswer,
  signOut,
  submitAttempt,
} from '../../lib/api';
import { clockOffset, TIMES_UP_OVERLAY_MS } from '../../lib/countdown';
import { letter } from '../../lib/letters';
import { SaveQueue, type SaveState } from '../../lib/saveQueue';
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
  const [confirmOpen, setConfirmOpen] = useState(false);
  /** Inputs are locked while submitting and for good once time is up. */
  const [locked, setLocked] = useState(false);
  const [timesUp, setTimesUp] = useState(false);
  const [signInExpired, setSignInExpired] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const queueRef = useRef<SaveQueue | null>(null);
  /** True while a flush + submit is under way: the finish sequence never runs twice at once. */
  const finishing = useRef(false);
  const timedOut = useRef(false);

  useEffect(() => {
    const queue = new SaveQueue((qid, ids) => saveAnswer(attemptId, qid, ids));
    queueRef.current = queue;
    const off = queue.onChange(() => {
      setSaveState(queue.state());
      setSavedHidden(false);
      if (queue.state() === 'error' && isSessionExpired(queue.lastError)) setSignInExpired(true);
    });
    return () => {
      off();
      queue.dispose();
    };
  }, [attemptId]);

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
  const inputsOff = locked || confirmOpen || signInExpired;

  function reportFinishError(err: unknown) {
    if (isSessionExpired(err)) setSignInExpired(true);
    else setSubmitError(`Could not submit: ${message(err)}`);
  }

  /**
   * Saves what is pending, submits, and moves to the results.
   *
   * After a timeout, a failed save does not hold up the submit: the server keeps what reached it
   * and the deadline has passed anyway. On a submit by choice, a failed save stops the submit so
   * no answer is silently dropped — except a 409, which means the attempt is already finished.
   */
  async function finishOnServer(afterTimeout: boolean) {
    const queue = queueRef.current;
    if (queue) {
      await queue.flush().catch((err: unknown) => {
        if (isSessionExpired(err)) throw err;
        if (afterTimeout || (err instanceof ApiError && err.status === 409)) return;
        throw err;
      });
    }
    const result = await submitAttempt(attemptId);
    return result.attempt_id;
  }

  async function submit() {
    if (finishing.current) return;
    finishing.current = true;
    setConfirmOpen(false);
    setLocked(true);
    setSubmitError(null);
    try {
      router.replace(resultsUrl(await finishOnServer(timedOut.current)));
    } catch (err) {
      finishing.current = false;
      if (!timedOut.current) setLocked(false);
      setTimesUp(false);
      reportFinishError(err);
    }
  }

  /** The timeout sequence. `<Timer>` calls it once; `finishing` keeps it off a submit in flight. */
  async function onTimeUp() {
    timedOut.current = true;
    setLocked(true);
    setConfirmOpen(false);
    setTimesUp(true);
    if (finishing.current) return; // a submit by choice is already on its way
    finishing.current = true;
    const overlay = sleep(TIMES_UP_OVERLAY_MS);
    try {
      const id = await finishOnServer(true);
      await overlay;
      router.replace(resultsUrl(id));
    } catch (err) {
      await overlay;
      finishing.current = false;
      setTimesUp(false);
      reportFinishError(err);
    }
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
  const saveLabel = saveState === 'saved' && savedHidden ? '' : SAVE_LABEL[saveState];

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
              <Timer deadlineAt={session.attempt.deadline_at} offsetMs={offsetMs} onExpire={onTimeUp} />
            )}
            <button className="btn" onClick={() => setConfirmOpen(true)} disabled={inputsOff}>
              Submit
            </button>
          </div>
          {submitError && (
            <div className="banner">
              {submitError}{' '}
              <button className="linkbtn" onClick={submit}>Try again</button>
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
            Time’s up<span className="mc">Submitting your saved answers</span>
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
