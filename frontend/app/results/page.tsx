'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import { ApiError, getMe, getResults, isSessionExpired, signOut } from '../../lib/api';
import { letter } from '../../lib/letters';
import { formatScore, isMarked, NOT_MARKED, percent } from '../../lib/score';
import { clearReauthFlag, handleSessionExpired } from '../../lib/session';
import type { ChoiceResult, Me, Results, SubjectiveResult } from '../../lib/types';
import Markdown from '../components/Markdown';
import ModelAnswer from '../components/ModelAnswer';
import Masthead, { type Crumb } from '../components/Masthead';
import SignInAgain from '../components/SignInAgain';

/** This page in the site path, after "Quiz Room". */
const TAIL: Crumb[] = [{ label: 'Results' }];

type Option = ChoiceResult['options'][number];

const POLICY_LABEL = {
  negative_marking: 'Negative marking',
  all_or_nothing: 'All-or-nothing',
  partial: 'Partial credit',
} as const;

/** How one option is marked. Without the answer key only the reader's own picks show. */
function optionMark(o: Option, reveal: boolean): { cls: string; tag: string } {
  if (!reveal) return { cls: '', tag: o.selected ? 'your pick' : '' };
  if (o.selected && o.correct) return { cls: 'hit', tag: 'your pick ✓' };
  if (o.selected) return { cls: 'wrong', tag: 'your pick ✗' };
  if (o.correct) return { cls: 'missed', tag: 'correct, missed' };
  return { cls: '', tag: '' };
}

/**
 * A subjective question: never marked, so "Not marked" in place of Correct/Incorrect and no
 * points. The solver's text shows exactly as typed (plain, not Markdown); the model answer and
 * explanation follow the set's reveal_answers.
 */
function WrittenCard({ q, index, reveal }: { q: SubjectiveResult; index: number; reveal: boolean }) {
  return (
    <div className="card rq">
      <div className="rq-head">
        <span className="n">{String(index + 1).padStart(2, '0')}</span>
        <h3>
          <Markdown text={q.prompt} />
        </h3>
        <span className="mark blank">Not marked</span>
      </div>
      <div className="answer-block">
        <span className="mc lab">Your answer</span>
        {q.text_answer ? <div className="typed">{q.text_answer}</div> : <div className="none">Left blank</div>}
      </div>
      {reveal && q.model_answer && <ModelAnswer text={q.model_answer} />}
      {reveal && q.explanation && (
        <div className="expl">
          <Markdown text={q.explanation} />
        </div>
      )}
    </div>
  );
}

function QuestionCard({ q, index, reveal }: { q: ChoiceResult; index: number; reveal: boolean }) {
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

  // Only marked questions: a blank one costs −2. A blank subjective question costs nothing.
  const unanswered = results
    ? results.questions.filter((q) => q.kind !== 'subjective' && !q.options.some((o) => o.selected)).length
    : 0;

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} tail={TAIL} />
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
            {isMarked(results.attempt.max_score) ? (
              <>
                <div>
                  {/* Two unbreakable halves: a narrow column wraps "−4 / 22" before the slash, never inside it. */}
                  <span className="v">
                    <span className="nw">{formatScore(results.attempt.score)}</span>{' '}
                    <span className="nw">/ {formatScore(results.attempt.max_score)}</span>
                  </span>
                  <span className="k">Score</span>
                </div>
                <div>
                  <span className="v">{formatScore(percent(results.attempt.score, results.attempt.max_score))}%</span>
                  <span className="k">{POLICY_LABEL[results.set.scoring_policy]}</span>
                </div>
                <div>
                  <span className="v">{unanswered}</span>
                  <span className="k">Unanswered</span>
                </div>
              </>
            ) : (
              <div>
                <span className="v">{NOT_MARKED}</span>
                <span className="k">Score</span>
              </div>
            )}
          </div>
          {results.questions.map((q, i) =>
            q.kind === 'subjective' ? (
              <WrittenCard key={q.id} q={q} index={i} reveal={results.set.reveal_answers} />
            ) : (
              <QuestionCard key={q.id} q={q} index={i} reveal={results.set.reveal_answers} />
            ),
          )}
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
    // The masthead is the fallback so it is in the exported page, where site-shell fills
    // its site path; this page's content needs the query string, so it renders on the client.
    <Suspense fallback={<div className="frame"><Masthead me={null} onSignOut={signOut} tail={TAIL} /></div>}>
      <ResultsView />
    </Suspense>
  );
}
