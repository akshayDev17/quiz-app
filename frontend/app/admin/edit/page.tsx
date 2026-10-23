'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';
import { getAdminSet, getMe, isSessionExpired, signOut, updateAdminSet } from '../../../lib/api';
import { clearReauthFlag } from '../../../lib/session';
import type { Me } from '../../../lib/types';
import Masthead from '../../components/Masthead';
import SignInAgain from '../../components/SignInAgain';

type QOption = { body: string; correct: boolean };
type QDraft = {
  prompt: string;
  explanation: string;
  points: number;
  options: QOption[];
  /** Marked for deletion. Stays on screen (blurred, undoable) until Save. */
  removed: boolean;
};
type Draft = {
  title: string;
  description: string;
  difficulty: string;
  style: string;
  scoring_policy: string;
  time_limit_minutes: string;
  max_attempts: string;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  reveal_answers: boolean;
  questions: QDraft[];
};
type Meta = { topic: string; subtopic: string | null; status: string };

const PER_PAGE = [10, 25, 50] as const;

const message = (err: unknown) => (err instanceof Error ? err.message : 'Something went wrong');
const blankQuestion = (): QDraft => ({
  prompt: '',
  explanation: '',
  points: 1,
  options: [
    { body: '', correct: true },
    { body: '', correct: false },
  ],
  removed: false,
});
const points = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

/**
 * Page buttons with ellipsis: 1 … 4 5 6 … 20. Sets are small, but the editor
 * should not grow a wall of numbers if one ever gets long.
 */
function pageList(current: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out: (number | '…')[] = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  if (start > 2) out.push('…');
  for (let p = start; p <= end; p += 1) out.push(p);
  if (end < total - 1) out.push('…');
  out.push(total);
  return out;
}

/* A hairline ✕ — crisper than the glyph and large enough to hit on a phone. */
const CloseIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
       strokeLinecap="round" aria-hidden="true">
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);

function Editor() {
  const router = useRouter();
  const id = Number(useSearchParams().get('id') ?? '');
  const [me, setMe] = useState<Me | null>(null);
  const [name, setName] = useState('');
  const [meta, setMeta] = useState<Meta>({ topic: '', subtopic: null, status: 'draft' });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);
  const [perPage, setPerPage] = useState<number>(PER_PAGE[0]);
  const [page, setPage] = useState(1);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const questionsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!id) {
      setError('No set selected');
      return;
    }
    getMe().then(setMe, () => {});
    getAdminSet(id).then(
      (d) => {
        clearReauthFlag();
        setName(d.name);
        setMeta({ topic: d.topic, subtopic: d.subtopic, status: d.status });
        setDraft({
          title: d.title ?? '',
          description: d.description ?? '',
          difficulty: d.difficulty ?? '',
          style: d.style,
          scoring_policy: d.scoring_policy,
          time_limit_minutes: d.time_limit_minutes == null ? '' : String(d.time_limit_minutes),
          max_attempts: d.max_attempts == null ? '' : String(d.max_attempts),
          shuffle_questions: d.shuffle_questions,
          shuffle_options: d.shuffle_options,
          reveal_answers: d.reveal_answers,
          questions: d.questions.map((q) => ({
            prompt: q.prompt,
            explanation: q.explanation ?? '',
            points: q.points,
            options: q.options.map((o) => ({ body: o.body, correct: o.correct })),
            removed: false,
          })),
        });
      },
      (err) => {
        if (isSessionExpired(err)) setExpired(true);
        else setError(message(err));
      },
    );
  }, [id]);

  /* ---- derived ------------------------------------------------------- */
  const questions = draft?.questions ?? [];
  const live = questions.filter((q) => !q.removed);
  const removedCount = questions.length - live.length;
  const totalPoints = live.reduce((sum, q) => sum + (Number(q.points) || 0), 0);
  const totalPages = Math.max(1, Math.ceil(questions.length / perPage));
  const current = Math.min(page, totalPages);
  const from = (current - 1) * perPage;
  const visible = questions.slice(from, from + perPage);

  /* ---- edits --------------------------------------------------------- */
  function set<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((d) => (d ? { ...d, [key]: value } : d));
  }

  function setQuestion(qi: number, patch: Partial<QDraft>) {
    setDraft((d) =>
      d ? { ...d, questions: d.questions.map((q, i) => (i === qi ? { ...q, ...patch } : q)) } : d,
    );
  }

  function setOption(qi: number, oi: number, patch: Partial<QOption>) {
    setDraft((d) =>
      d
        ? {
            ...d,
            questions: d.questions.map((q, i) =>
              i === qi ? { ...q, options: q.options.map((o, j) => (j === oi ? { ...o, ...patch } : o)) } : q,
            ),
          }
        : d,
    );
  }

  function scrollToQuestions() {
    requestAnimationFrame(() =>
      questionsRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }),
    );
  }

  /* The new question is appended, so show the page it lands on. The page has to
     be set from the index here: the state update above has not landed yet, so
     anything that reads questions.length would still see the old length. */
  function addQuestion() {
    const at = questions.length;
    setDraft((d) => (d ? { ...d, questions: [...d.questions, blankQuestion()] } : d));
    setPage(Math.floor(at / perPage) + 1);
    scrollToQuestions();
  }

  /* ---- save ---------------------------------------------------------- */
  async function save() {
    if (!draft) return;
    if (live.length === 0) {
      setError('A set needs at least one question — undo a removal or add one.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await updateAdminSet(id, {
        title: draft.title.trim() || null,
        description: draft.description.trim() || null,
        difficulty: draft.difficulty || null,
        style: draft.style,
        scoring_policy: draft.scoring_policy,
        time_limit_minutes: draft.time_limit_minutes === '' ? null : Number(draft.time_limit_minutes),
        max_attempts: draft.max_attempts === '' ? null : Number(draft.max_attempts),
        shuffle_questions: draft.shuffle_questions,
        shuffle_options: draft.shuffle_options,
        reveal_answers: draft.reveal_answers,
        questions: live.map((q) => ({
          prompt: q.prompt,
          explanation: q.explanation.trim() || null,
          points: Number(q.points),
          options: q.options.map((o) => ({ body: o.body, correct: o.correct })),
        })),
      });
      router.push('/admin');
    } catch (err) {
      if (isSessionExpired(err)) setExpired(true);
      else setError(message(err));
      setBusy(false);
      setConfirmDelete(false);
    }
  }

  function onSaveClicked() {
    if (!draft || busy) return;
    if (live.length === 0) {
      setError('A set needs at least one question — undo a removal or add one.');
      return;
    }
    if (removedCount > 0) setConfirmDelete(true);
    else save();
  }

  const title = draft ? draft.title.trim() || name : name;

  return (
    <div className="editor-page">
      <div className="frame">
        <Masthead me={me} onSignOut={signOut} />

        <p className="ed-crumb">
          <Link className="linkbtn" href="/admin">← Back to admin</Link>
        </p>

        {expired && <SignInAgain />}
        {error && <div className="banner">{error}</div>}
        {!draft && !error && !expired && <p className="ed-muted">Loading…</p>}

        {draft && (
          <>
            <div className="ed-bar">
              <div className="ed-bar-title">
                {title}
                <span>
                  {meta.status} · {live.length} {live.length === 1 ? 'question' : 'questions'} ·{' '}
                  {points(totalPoints)} points
                  {removedCount > 0 && (
                    <em className="ed-pending"> · {removedCount} to delete on save</em>
                  )}
                </span>
              </div>
              <Link className="ed-btn" href="/admin">Cancel</Link>
              <button className="ed-btn primary" onClick={onSaveClicked} disabled={busy}>
                {busy ? 'Saving…' : 'Save'}
              </button>
            </div>

            {confirmDelete && (
              <div className="ed-confirm" role="alertdialog" aria-label="Confirm deletions">
                <span>
                  Saving will permanently delete{' '}
                  <b>{removedCount === 1 ? '1 question' : `${removedCount} questions`}</b>.
                </span>
                <button className="ed-btn primary" onClick={save} disabled={busy}>
                  Delete and save
                </button>
                <button className="ed-btn" onClick={() => setConfirmDelete(false)}>Keep them</button>
              </div>
            )}

            <section className="ed-panel">
              <header className="ed-ph">
                <b>Set details</b>
                <span className="meta">
                  {meta.topic}
                  {meta.subtopic ? ` › ${meta.subtopic}` : ''}
                </span>
              </header>
              <div className="ed-pb">
                <div className="ed-field">
                  <label className="lab" htmlFor="ed-title">Title</label>
                  <input id="ed-title" value={draft.title} placeholder={name}
                         onChange={(e) => set('title', e.target.value)} />
                </div>
                <div className="ed-field">
                  <label className="lab" htmlFor="ed-desc">Description</label>
                  <textarea id="ed-desc" rows={2} value={draft.description}
                            onChange={(e) => set('description', e.target.value)} />
                </div>
                <div className="ed-grid3">
                  <div>
                    <label className="lab" htmlFor="ed-diff">Difficulty</label>
                    <select id="ed-diff" value={draft.difficulty}
                            onChange={(e) => set('difficulty', e.target.value)}>
                      <option value="">—</option>
                      <option value="easy">easy</option>
                      <option value="medium">medium</option>
                      <option value="hard">hard</option>
                    </select>
                  </div>
                  <div>
                    <label className="lab" htmlFor="ed-style">Style</label>
                    <select id="ed-style" value={draft.style}
                            onChange={(e) => set('style', e.target.value)}>
                      <option value="standard">standard</option>
                      <option value="scenario">scenario</option>
                    </select>
                  </div>
                  <div>
                    <label className="lab" htmlFor="ed-scoring">Scoring</label>
                    <select id="ed-scoring" value={draft.scoring_policy}
                            onChange={(e) => set('scoring_policy', e.target.value)}>
                      <option value="all_or_nothing">all_or_nothing</option>
                      <option value="partial">partial</option>
                    </select>
                  </div>
                </div>
                <div className="ed-grid3">
                  <div>
                    <label className="lab" htmlFor="ed-time">Time limit (min, blank = untimed)</label>
                    <input id="ed-time" inputMode="numeric" value={draft.time_limit_minutes}
                           onChange={(e) => set('time_limit_minutes', e.target.value)} />
                  </div>
                  <div>
                    <label className="lab" htmlFor="ed-max">Max attempts (blank = unlimited)</label>
                    <input id="ed-max" inputMode="numeric" value={draft.max_attempts}
                           onChange={(e) => set('max_attempts', e.target.value)} />
                  </div>
                  <div>
                    <span className="lab">Behaviour</span>
                    <div className="ed-checks">
                      <label><input type="checkbox" checked={draft.shuffle_questions}
                                    onChange={(e) => set('shuffle_questions', e.target.checked)} /> Shuffle questions</label>
                      <label><input type="checkbox" checked={draft.shuffle_options}
                                    onChange={(e) => set('shuffle_options', e.target.checked)} /> Shuffle options</label>
                      <label><input type="checkbox" checked={draft.reveal_answers}
                                    onChange={(e) => set('reveal_answers', e.target.checked)} /> Reveal answers</label>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <div ref={questionsRef} className="ed-questions">
              {visible.map((q, offset) => {
                const qi = from + offset;
                const correct = q.options.filter((o) => o.correct).length;
                const lastLive = !q.removed && live.length <= 1;
                return (
                  <section className={`ed-panel${q.removed ? ' gone' : ''}`} key={qi}>
                    <header className="ed-ph">
                      <b>Question {qi + 1}</b>
                      <span className="meta">
                        {points(q.points)} points · {correct} of {q.options.length} correct
                      </span>
                      {!q.removed && (
                        <button className="ed-btn ed-remove" disabled={lastLive}
                                title={lastLive ? 'A set needs at least one question' : undefined}
                                onClick={() => setQuestion(qi, { removed: true })}>
                          Remove
                        </button>
                      )}
                    </header>

                    <div className="ed-pb" inert={q.removed || undefined}>
                      <div className="ed-promptrow">
                        <div className="ed-field">
                          <label className="lab">Prompt</label>
                          <textarea rows={2} value={q.prompt}
                                    onChange={(e) => setQuestion(qi, { prompt: e.target.value })} />
                        </div>
                        <div className="ed-field ed-pts">
                          <label className="lab">Points</label>
                          <input inputMode="decimal" value={String(q.points)}
                                 onChange={(e) => setQuestion(qi, { points: Number(e.target.value) })} />
                        </div>
                      </div>
                      <div className="ed-field">
                        <label className="lab">Explanation (blank = none)</label>
                        <textarea rows={2} value={q.explanation}
                                  onChange={(e) => setQuestion(qi, { explanation: e.target.value })} />
                      </div>

                      <div className="ed-field">
                        <span className="lab">Options — tick the correct ones</span>
                        {q.options.map((o, oi) => (
                          <div className="ed-opt" key={oi}>
                            <span className="idx">{oi + 1}</span>
                            <input type="checkbox" checked={o.correct} title="Correct"
                                   onChange={(e) => setOption(qi, oi, { correct: e.target.checked })} />
                            <input value={o.body} placeholder="Option body"
                                   onChange={(e) => setOption(qi, oi, { body: e.target.value })} />
                            <button className="ed-x" disabled={q.options.length <= 2}
                                    title="Remove option" aria-label="Remove option"
                                    onClick={() => setQuestion(qi, { options: q.options.filter((_, j) => j !== oi) })}>
                              {CloseIcon}
                            </button>
                          </div>
                        ))}
                        <button className="ed-btn"
                                onClick={() => setQuestion(qi, { options: [...q.options, { body: '', correct: false }] })}>
                          Add option
                        </button>
                      </div>
                    </div>

                    {q.removed && (
                      <div className="ed-gone">
                        <div className="ed-gone-box">
                          <span>Question {qi + 1} is marked for removal</span>
                          <button className="ed-btn" onClick={() => setQuestion(qi, { removed: false })}>
                            Undo
                          </button>
                        </div>
                      </div>
                    )}
                  </section>
                );
              })}
            </div>

            <div className="ed-foot">
              <div className="ed-foot-left">
                <button className="ed-btn" onClick={addQuestion}>Add question</button>
                <label className="ed-perpage">
                  Questions per page
                  <select value={perPage}
                          onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }}>
                    {PER_PAGE.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
              </div>

              {totalPages > 1 && (
                <nav className="ed-pager" aria-label="Question pages">
                  <button onClick={() => setPage(current - 1)} disabled={current === 1} aria-label="Previous page">‹</button>
                  {pageList(current, totalPages).map((item, i) =>
                    item === '…' ? (
                      <span className="gap" key={`gap-${i}`}>…</span>
                    ) : (
                      <button key={item} onClick={() => setPage(item)}
                              aria-current={item === current ? 'page' : undefined}>
                        {item}
                      </button>
                    ),
                  )}
                  <button onClick={() => setPage(current + 1)} disabled={current === totalPages} aria-label="Next page">›</button>
                  <span className="range">
                    {from + 1}–{Math.min(from + perPage, questions.length)} of {questions.length}
                  </span>
                </nav>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function EditSetPage() {
  return (
    <Suspense fallback={null}>
      <Editor />
    </Suspense>
  );
}
