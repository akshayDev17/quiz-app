'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import { ApiError, getMe, getResults, isSessionExpired, signOut } from '../../lib/api';
import { letter } from '../../lib/letters';
import { formatScore, percent } from '../../lib/score';
import { clearReauthFlag, handleSessionExpired } from '../../lib/session';
import type { Me, Results } from '../../lib/types';
import Markdown from '../components/Markdown';
import Masthead from '../components/Masthead';
import SignInAgain from '../components/SignInAgain';

type Question = Results['questions'][number];
type Option = Question['options'][number];

const POLICY_LABEL = { all_or_nothing: 'All-or-nothing', partial: 'Partial credit' } as const;

/** How one option is marked. Without the answer key only the reader's own picks show. */
function optionMark(o: Option, reveal: boolean): { cls: string; tag: string } {
  if (!reveal) return { cls: '', tag: o.selected ? 'your pick' : '' };
  if (o.selected && o.correct) return { cls: 'hit', tag: 'your pick ✓' };
  if (o.selected) return { cls: 'wrong', tag: 'your pick ✗' };
  if (o.correct) return { cls: 'missed', tag: 'correct, missed' };
  return { cls: '', tag: '' };
}

function QuestionCard({ q, index, reveal }: { q: Question; index: number; reveal: boolean }) {
  const blank = !q.options.some((o) => o.selected);
  const [markCls, markText] = q.is_correct
    ? ['ok', 'Correct']
    : blank
      ? ['blank', 'Blank']
      : ['bad', 'Incorrect'];
  return (
    <div className="card rq">
      <div className="rq-head">
        <span className="n">{String(index + 1).padStart(2, '0')}</span>
        <h3>
          <Markdown text={q.prompt} />
        </h3>
        <span className={`mark ${markCls}`}>
          {markText} · {formatScore(q.awarded_points)}/{formatScore(q.points)}
        </span>
      </div>
      {q.options.map((o, i) => {
        const { cls, tag } = optionMark(o, reveal);
        return (
          <div key={o.id} className={cls ? `ropt ${cls}` : 'ropt'}>
            <span className="letter">{letter(i)}</span>
            <div>
              <Markdown text={o.body} />
            </div>
            <span className="mc tag">{tag}</span>
          </div>
        );
      })}
      {reveal && q.explanation && (
        <div className="expl">
          <Markdown text={q.explanation} />
        </div>
      )}
    </div>
  );
}

function ResultsView() {
  const router = useRouter();
  const params = useSearchParams();
  const attemptId = params.get('attempt');
  const [me, setMe] = useState<Me | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    if (!attemptId) {
      setError('No such attempt');
      return;
    }
    Promise.all([getMe(), getResults(attemptId)]).then(
      ([m, r]) => {
        clearReauthFlag();
        setMe(m);
        setResults(r);
      },
      (err) => {
        if (isSessionExpired(err)) {
          setExpired(true);
          handleSessionExpired();
        } else if (err instanceof ApiError && err.status === 409) {
          // Still open: there are no results yet, the quiz itself is where it goes on.
          router.replace(`/play?attempt=${encodeURIComponent(attemptId)}`);
        } else setError(err instanceof Error ? err.message : 'Something went wrong');
      },
    );
  }, [attemptId, router]);

  const unanswered = results ? results.questions.filter((q) => !q.options.some((o) => o.selected)).length : 0;

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} />
      {expired && <SignInAgain />}
      {error && <div className="banner">{error}</div>}
      {!error && !expired && !results && <p className="mc">Loading…</p>}
      {results && (
        <>
          <div className="kicker">{results.set.topic} · Results</div>
          <h2 className="hl">{results.set.name}</h2>
          {results.attempt.status === 'expired' && (
            <div className="banner">Time’s up — your saved answers were submitted automatically</div>
          )}
          <div className="stats">
            <div>
              <span className="v">
                {formatScore(results.attempt.score)} / {formatScore(results.attempt.max_score)}
              </span>
              <span className="k">Score</span>
            </div>
            <div>
              <span className="v">{percent(results.attempt.score, results.attempt.max_score)}%</span>
              <span className="k">{POLICY_LABEL[results.set.scoring_policy]}</span>
            </div>
            <div>
              <span className="v">{unanswered}</span>
              <span className="k">Unanswered</span>
            </div>
          </div>
          {results.questions.map((q, i) => (
            <QuestionCard key={q.id} q={q} index={i} reveal={results.set.reveal_answers} />
          ))}
          <p>
            <Link className="btn ghost" href="/" style={{ display: 'inline-block', textDecoration: 'none' }}>
              Back to quizzes
            </Link>
          </p>
        </>
      )}
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={null}>
      <ResultsView />
    </Suspense>
  );
}
