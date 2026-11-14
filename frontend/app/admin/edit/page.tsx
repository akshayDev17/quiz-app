'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useRef, useState } from 'react';
import { getAdminSet, getMe, isSessionExpired, signOut, updateAdminSet } from '../../../lib/api';
import { MARKING_SHORT, maxMarks, WRITTEN_MARKS } from '../../../lib/score';
import { clearReauthFlag } from '../../../lib/session';
import type { AdminQuestion, Me, QuestionKind, Visibility } from '../../../lib/types';
import Masthead, { type Crumb } from '../../components/Masthead';
import SignInAgain from '../../components/SignInAgain';

/** This page in the site path, after "Quiz Room". */
const TAIL: Crumb[] = [{ label: 'Admin', href: '/quiz/admin' }, { label: 'Edit set' }];

type QOption = { body: string; correct: boolean };
type QDraft = {
  kind: QuestionKind;
  prompt: string;
  explanation: string;
  /** Choice questions only; a subjective question is marked out of 4 by the evaluator, so it takes no points. */
  points: number;
  /** Kept while a question is switched to subjective, so switching back restores them. */
  options: QOption[];
  /** Subjective questions only: required, shown on review and on View, and marked against. */
  model_answer: string;
  /** Subjective questions only: the rubric's essential points, one per line (blank = none). */
  key_points: string;
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
  visibility: Visibility;
  questions: QDraft[];
};
type Meta = { topic: string; subtopic: string | null; status: string };

const PER_PAGE = [10, 25, 50] as const;

/** The two visibilities, as the editor offers them. Applies once the set is published. */
const VISIBILITY_CHOICES: { value: Visibility; label: string; hint: string }[] = [
  { value: 'public', label: 'Public', hint: 'Anyone can view it; signed-in solvers can take it' },
  { value: 'private', label: 'Private', hint: 'Only admins can see and take it' },
];

/** The two question types, as the editor offers them. */
const KIND_CHOICES: { value: QuestionKind; label: string; hint: string }[] = [
  { value: 'choice', label: 'Choice', hint: 'Tick options · marked' },
  { value: 'subjective', label: 'Written', hint: `Typed answer · AI-marked out of ${WRITTEN_MARKS}` },
];

const message = (err: unknown) => (err instanceof Error ? err.message : 'Something went wrong');
const blankOptions = (): QOption[] => [
  { body: '', correct: true },
  { body: '', correct: false },
];
const blankQuestion = (): QDraft => ({
  kind: 'choice',
  prompt: '',
  explanation: '',
  points: 1,
  options: blankOptions(),
  model_answer: '',
  key_points: '',
  removed: false,
});

/** The key points as the editor's text box holds them, one per line, and back. */
const keyPointLines = (text: string) => text.split('\n').map((line) => line.trim()).filter(Boolean);

/** A question as the server sent it, as the editor holds it. */
function draftOf(q: AdminQuestion): QDraft {
  const common = { prompt: q.prompt, explanation: q.explanation ?? '', removed: false };
  if (q.type === 'subjective') {
    return {
      ...common, kind: 'subjective', points: 1, options: blankOptions(), model_answer: q.model_answer,
      key_points: (q.key_points ?? []).join('\n'),
    };
  }
  return {
    ...common,
    kind: 'choice',
    points: q.points,
    options: q.options.map((o) => ({ body: o.body, correct: o.correct })),
    model_answer: '',
    key_points: '',
  };
}

/** A question in its import shape: a subjective one carries no options and no points. */
function payloadOf(q: QDraft) {
  const common = { prompt: q.prompt, explanation: q.explanation.trim() || null };
  if (q.kind === 'subjective') {
    const points = keyPointLines(q.key_points);
    return { type: 'subjective', ...common, model_answer: q.model_answer, ...(points.length ? { key_points: points } : {}) };
  }
  return {
    type: 'choice',
    ...common,
    points: Number(q.points),
    options: q.options.map((o) => ({ body: o.body, correct: o.correct })),
  };
}

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
          visibility: d.visibility,
          questions: d.questions.map(draftOf),
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
  const totalMarks = live.reduce(
    (sum, q) => sum + (q.kind === 'subjective' ? WRITTEN_MARKS : maxMarks(q.options.filter((o) => o.correct).length)),
    0,
  );
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
        visibility: draft.visibility,
        questions: live.map(payloadOf),
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
        <Masthead me={me} onSignOut={signOut} tail={TAIL} />

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
                  up to {totalMarks} marks
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
                <div className="ed-field">
                  <span className="lab" id="ed-vis-label">Visibility</span>
                  <div className="ed-vis" role="radiogroup" aria-labelledby="ed-vis-label">
                    {VISIBILITY_CHOICES.map((c) => (
                      <label key={c.value} className={draft.visibility === c.value ? 'on' : ''}>
                        <input type="radio" name="ed-vis" value={c.value} checked={draft.visibility === c.value}
                               onChange={() => set('visibility', c.value)} />
                        <b>{c.label}</b>
                        <span>{c.hint}</span>
                      </label>
                    ))}
                  </div>
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
                    <span className="lab">Marking</span>
                    <p className="ed-static">{MARKING_SHORT}</p>
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
                        {q.kind === 'subjective'
                          ? `Written · AI-marked out of ${WRITTEN_MARKS}`
                          : `${correct} of ${q.options.length} correct · up to ${maxMarks(correct)} marks`}
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
                      <div className="ed-field">
                        <span className="lab" id={`ed-kind-${qi}`}>Type</span>
                        <div className="ed-vis ed-kind" role="radiogroup" aria-labelledby={`ed-kind-${qi}`}>
                          {KIND_CHOICES.map((c) => (
                            <label key={c.value} className={q.kind === c.value ? 'on' : ''}>
                              <input type="radio" name={`ed-kind-${qi}`} value={c.value} checked={q.kind === c.value}
                                     onChange={() => setQuestion(qi, { kind: c.value })} />
                              <b>{c.label}</b>
                              <span>{c.hint}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                      <div className="ed-field">
                        <label className="lab">Prompt</label>
                        <textarea rows={2} value={q.prompt}
                                  onChange={(e) => setQuestion(qi, { prompt: e.target.value })} />
                      </div>
                      <div className="ed-field">
                        <label className="lab">Explanation (blank = none)</label>
                        <textarea rows={2} value={q.explanation}
                                  onChange={(e) => setQuestion(qi, { explanation: e.target.value })} />
                      </div>

                      {q.kind === 'subjective' ? (
                        <div className="ed-field">
                          <label className="lab" htmlFor={`ed-model-${qi}`}>
                            Model answer (required · shown on review and View)
                          </label>
                          <textarea id={`ed-model-${qi}`} rows={4} value={q.model_answer}
                                    onChange={(e) => setQuestion(qi, { model_answer: e.target.value })} />
                          <label className="lab" htmlFor={`ed-points-${qi}`}>
                            Key points (optional · one per line, up to 6 · what the AI evaluator checks)
                          </label>
                          <textarea id={`ed-points-${qi}`} rows={3} value={q.key_points}
                                    placeholder="Each line one essential point a full answer makes"
                                    onChange={(e) => setQuestion(qi, { key_points: e.target.value })} />
                        </div>
                      ) : (
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
                      )}
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
    // The masthead is the fallback so it is in the exported page, where site-shell fills
    // its site path; this page's content needs the query string, so it renders on the client.
    <Suspense fallback={<div className="editor-page"><div className="frame"><Masthead me={null} onSignOut={signOut} tail={TAIL} /></div></div>}>
      <Editor />
    </Suspense>
  );
}
