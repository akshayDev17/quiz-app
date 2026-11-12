'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import { getMe, getPublicSet, isSignedOut, signOut } from '../../lib/api';
import { letter } from '../../lib/letters';
import type { Me, PublicSet } from '../../lib/types';
import Markdown from '../components/Markdown';
import ModelAnswer from '../components/ModelAnswer';
import Masthead, { type Crumb, type Session } from '../components/Masthead';
import { SignUpSoon } from '../components/PublicSetCard';

/** This page in the site path, after "Quiz Room". */
const TAIL: Crumb[] = [{ label: 'View' }];

type Question = PublicSet['questions'][number];

/**
 * One question in the results layout with every score taken out: no Correct/Incorrect mark, no
 * points, no picks. Each correct option is marked "correct" in the treatment results gives a
 * correct pick. A subjective question has no options: it is tagged "Written" and shows its model
 * answer. A set that hides its answers shows the options unmarked, no model answer and no
 * explanation.
 */
function QuestionCard({ q, index }: { q: Question; index: number }) {
  return (
    <div className="card rq">
      <div className="rq-head">
        <span className="n">{String(index + 1).padStart(2, '0')}</span>
        <h3>
          <Markdown text={q.prompt} />
        </h3>
        {q.kind === 'subjective' && <span className="mark blank">Written</span>}
      </div>
      {q.options.map((o, i) => (
        <div key={o.id} className={o.correct ? 'ropt hit' : 'ropt'}>
          <span className="letter">{letter(i)}</span>
          <div>
            <Markdown text={o.body} />
          </div>
          <span className="mc tag">{o.correct ? 'correct' : ''}</span>
        </div>
      ))}
      {q.kind === 'subjective' && q.model_answer && <ModelAnswer text={q.model_answer} />}
      {q.explanation && (
        <div className="expl">
          <Markdown text={q.explanation} />
        </div>
      )}
    </div>
  );
}

/**
 * View: a published set read in the results layout, by anyone, without taking it. The figures
 * that results gives as a score are replaced by what the set is: its questions, its time limit
 * and how many options are correct in all.
 */
function View() {
  const params = useSearchParams();
  const setId = Number(params.get('id'));
  const [me, setMe] = useState<Me | null>(null);
  const [session, setSession] = useState<Session>('pending');
  const [view, setView] = useState<PublicSet | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Only for the masthead: View itself is the same for everyone.
    getMe().then(
      (m) => {
        setMe(m);
        setSession('signed-in');
      },
      (err) => setSession(isSignedOut(err) ? 'signed-out' : 'signed-in'),
    );
  }, []);

  useEffect(() => {
    if (!Number.isInteger(setId) || setId <= 0) {
      setError('No such quiz');
      return;
    }
    getPublicSet(setId).then(setView, (err) =>
      setError(isSignedOut(err) ? 'Sign in to view this quiz' : err instanceof Error ? err.message : 'Something went wrong'),
    );
  }, [setId]);

  const correct = view?.questions.reduce((n, q) => n + q.options.filter((o) => o.correct).length, 0) ?? 0;
  const minutes = view?.set.time_limit_minutes ?? null;

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} tail={TAIL} session={session} />
      {error && <div className="banner">{error}</div>}
      {!error && !view && <p className="mc">Loading…</p>}
      {view && (
        <>
          <div className="kicker">
            {view.set.topic}
            {view.set.subtopic ? ` › ${view.set.subtopic}` : ''} · View
          </div>
          <h2 className="hl">{view.set.name}</h2>
          <div className="stats">
            <div>
              <span className="v">{view.set.question_count}</span>
              <span className="k">{view.set.question_count === 1 ? 'Question' : 'Questions'}</span>
            </div>
            <div>
              <span className="v">{minutes ?? '—'}</span>
              <span className="k">{minutes === null ? 'Untimed' : minutes === 1 ? 'Minute' : 'Minutes'}</span>
            </div>
            <div>
              <span className="v">{view.set.reveal_answers ? correct : '—'}</span>
              <span className="k">{view.set.reveal_answers ? correct === 1 ? 'Correct option' : 'Correct options' : 'Answers hidden'}</span>
            </div>
          </div>
          {view.questions.map((q, i) => (
            <QuestionCard key={q.id} q={q} index={i} />
          ))}
          <div className="view-foot">
            {session === 'signed-out' && <SignUpSoon />}
            <Link className="btn" href="/">Back to quizzes</Link>
          </div>
        </>
      )}
    </div>
  );
}

export default function ViewPage() {
  return (
    // The masthead is the fallback so it is in the exported page, where site-shell fills
    // its site path; this page's content needs the query string, so it renders on the client.
    <Suspense fallback={<div className="frame"><Masthead me={null} onSignOut={signOut} tail={TAIL} session="pending" /></div>}>
      <View />
    </Suspense>
  );
}
