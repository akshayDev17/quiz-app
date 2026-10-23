'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getHistory, getMe, isSessionExpired, signOut } from '../../lib/api';
import { formatScore } from '../../lib/score';
import { clearReauthFlag, handleSessionExpired } from '../../lib/session';
import type { History, Me } from '../../lib/types';
import Masthead from '../components/Masthead';
import SignInAgain from '../components/SignInAgain';

type Attempt = History['attempts'][number];

const STATUS_LABEL: Record<Attempt['status'], string> = {
  in_progress: 'In progress',
  submitted: 'Submitted',
  expired: 'Time ran out',
};

/** Finished attempts open their results; one still running opens the quiz. */
function attemptHref(a: Attempt): string {
  const base = a.status === 'in_progress' ? '/play' : '/results';
  return `${base}?attempt=${encodeURIComponent(a.id)}`;
}

export default function HistoryPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [attempts, setAttempts] = useState<Attempt[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    Promise.all([getMe(), getHistory()]).then(
      ([m, h]) => {
        clearReauthFlag();
        setMe(m);
        setAttempts(h.attempts);
      },
      (err) => {
        if (isSessionExpired(err)) {
          setExpired(true);
          handleSessionExpired();
        } else setError(err instanceof Error ? err.message : 'Something went wrong');
      },
    );
  }, []);

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} />
      <p style={{ marginBottom: 'var(--s4)' }}>
        <Link className="linkbtn" href="/">← All quizzes</Link>
      </p>
      <h2 className="hl">History</h2>
      {expired && <SignInAgain />}
      {error && <div className="banner">{error}</div>}
      {!error && !expired && !attempts && <p className="mc">Loading…</p>}
      {attempts && attempts.length === 0 && <p className="mc">No attempts yet.</p>}
      {attempts && attempts.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th className="mc">Quiz</th>
              <th className="mc">Topic</th>
              <th className="mc">Date</th>
              <th className="mc">Status</th>
              <th className="mc num">Score</th>
            </tr>
          </thead>
          <tbody>
            {attempts.map((a) => (
              <tr key={a.id}>
                <td>
                  <Link href={attemptHref(a)}>{a.name}</Link>
                </td>
                <td>{a.topic}</td>
                <td>{new Date(a.started_at).toLocaleString()}</td>
                <td className="mc">{STATUS_LABEL[a.status]}</td>
                <td className="num">
                  {a.score !== null && a.max_score !== null
                    ? `${formatScore(a.score)} / ${formatScore(a.max_score)}`
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
