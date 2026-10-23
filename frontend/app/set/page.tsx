'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import { getMe, getSet, isSessionExpired, signOut, startAttempt } from '../../lib/api';
import { pluralize } from '../../lib/names';
import type { Me, SetIntro } from '../../lib/types';
import { clearReauthFlag, handleSessionExpired } from '../../lib/session';
import Masthead from '../components/Masthead';
import SignInAgain from '../components/SignInAgain';

function Intro() {
  const router = useRouter();
  const params = useSearchParams();
  const setId = Number(params.get('id'));
  const [me, setMe] = useState<Me | null>(null);
  const [intro, setIntro] = useState<SetIntro | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [expired, setExpired] = useState(false);

  function fail(err: unknown) {
    if (isSessionExpired(err)) {
      setExpired(true);
      handleSessionExpired();
    } else setError(err instanceof Error ? err.message : 'Something went wrong');
  }

  useEffect(() => {
    if (!Number.isInteger(setId) || setId <= 0) {
      setError('No such quiz');
      return;
    }
    Promise.all([getMe(), getSet(setId)]).then(([m, s]) => {
      clearReauthFlag();
      setMe(m);
      setIntro(s);
    }, fail);
  }, [setId]);

  async function start() {
    setStarting(true);
    try {
      const session = await startAttempt(setId);
      router.push(`/play?attempt=${encodeURIComponent(session.attempt.id)}`);
    } catch (err) {
      setStarting(false);
      fail(err);
    }
  }

  const minutes = intro?.time_limit_minutes ?? null;
  const resuming = intro?.open_attempt_id != null;
  const noAttemptsLeft =
    intro !== null && !resuming && intro.max_attempts !== null && intro.attempts_used >= intro.max_attempts;

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} />
      <p style={{ marginBottom: 'var(--s4)' }}>
        <Link className="linkbtn" href="/">← All quizzes</Link>
      </p>
      {expired && <SignInAgain />}
      {error && <div className="banner">{error}</div>}
      {!error && !expired && !intro && <p className="mc">Loading…</p>}
      {intro && (
        <div className="card intro">
          <div className="kicker">{intro.topic + (intro.subtopic ? ` › ${intro.subtopic}` : '')}</div>
          <h2 className="hl">{intro.name}</h2>
          {intro.description && <p className="standfirst">{intro.description}</p>}
          <ul className="rules">
            <li>{pluralize(intro.question_count, 'question')}. Some have more than one correct answer.</li>
            <li>
              {minutes
                ? `${minutes}-minute time limit. When it runs out, your saved answers are submitted automatically.`
                : 'No time limit.'}
            </li>
            <li>You won’t see whether an answer is right until you submit.</li>
          </ul>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s4)', flexWrap: 'wrap' }}>
            {noAttemptsLeft ? (
              <span className="mc">No attempts left</span>
            ) : (
              <>
                <button className="btn" onClick={start} disabled={starting}>
                  {resuming ? 'Resume' : 'Start'}
                </button>
                {minutes && !resuming && <span className="mc">The timer starts when you press Start</span>}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SetPage() {
  return (
    <Suspense fallback={null}>
      <Intro />
    </Suspense>
  );
}
