'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';
import { getAdminSet, getMe, isSessionExpired, signOut, updateAdminSet } from '../../../lib/api';
import { clearReauthFlag } from '../../../lib/session';
import type { Me } from '../../../lib/types';
import Masthead from '../../components/Masthead';
import SignInAgain from '../../components/SignInAgain';

type QOption = { body: string; correct: boolean };
type QDraft = { prompt: string; explanation: string; points: number; options: QOption[] };
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

const message = (err: unknown) => (err instanceof Error ? err.message : 'Something went wrong');
const blankQuestion = (): QDraft => ({
  prompt: '',
  explanation: '',
  points: 1,
  options: [
    { body: '', correct: true },
    { body: '', correct: false },
  ],
});

/* A hairline ✕ — crisper than the glyph and large enough to hit on a phone. */
const CloseIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
       strokeLinecap="round" aria-hidden="true">
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);

function Editor() {
  const router = useRouter();
  const id = Number(useSearchParams().get('id') ?? '');
  const [me, setMe] = useState<Me | null>(null);
  const [name, setName] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);

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
          })),
        });
      },
      (err) => {
        if (isSessionExpired(err)) setExpired(true);
        else setError(message(err));
      },
    );
  }, [id]);

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

  async function save() {
    if (!draft) return;
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
        questions: draft.questions.map((q) => ({
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
    }
  }

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} />
      <p style={{ marginBottom: 'var(--s4)' }}>
        <Link className="linkbtn" href="/admin">← Back to admin</Link>
      </p>
      {expired && <SignInAgain />}
      {error && <div className="banner">{error}</div>}
      {!draft && !error && !expired && <p className="mc">Loading…</p>}
      {draft && (
        <>
          <h2 className="hl">Edit set</h2>
          <p className="mc" style={{ marginBottom: 'var(--s5)' }}>{name}</p>

          <div className="card editor-set">
            <div className="field">
              <label className="mc" htmlFor="title">Title (optional)</label>
              <input id="title" value={draft.title} placeholder={name}
                     onChange={(e) => set('title', e.target.value)} />
            </div>
            <div className="field">
              <label className="mc" htmlFor="description">Description (optional)</label>
              <textarea id="description" rows={2} value={draft.description}
                        onChange={(e) => set('description', e.target.value)} />
            </div>
            <div className="editor-grid">
              <div className="field">
                <label className="mc" htmlFor="difficulty">Difficulty</label>
                <select id="difficulty" value={draft.difficulty}
                        onChange={(e) => set('difficulty', e.target.value)}>
                  <option value="">—</option>
                  <option value="easy">easy</option>
                  <option value="medium">medium</option>
                  <option value="hard">hard</option>
                </select>
              </div>
              <div className="field">
                <label className="mc" htmlFor="style">Style</label>
                <select id="style" value={draft.style} onChange={(e) => set('style', e.target.value)}>
                  <option value="standard">standard</option>
                  <option value="scenario">scenario</option>
                </select>
              </div>
              <div className="field">
                <label className="mc" htmlFor="scoring">Scoring</label>
                <select id="scoring" value={draft.scoring_policy}
                        onChange={(e) => set('scoring_policy', e.target.value)}>
                  <option value="all_or_nothing">all_or_nothing</option>
                  <option value="partial">partial</option>
                </select>
              </div>
              <div className="field">
                <label className="mc" htmlFor="time">Time limit (min)</label>
                <input id="time" inputMode="numeric" value={draft.time_limit_minutes} placeholder="untimed"
                       onChange={(e) => set('time_limit_minutes', e.target.value)} />
              </div>
              <div className="field">
                <label className="mc" htmlFor="maxatts">Max attempts</label>
                <input id="maxatts" inputMode="numeric" value={draft.max_attempts} placeholder="unlimited"
                       onChange={(e) => set('max_attempts', e.target.value)} />
              </div>
            </div>
            <div className="editor-checks">
              <label><input type="checkbox" checked={draft.shuffle_questions}
                            onChange={(e) => set('shuffle_questions', e.target.checked)} /> Shuffle questions</label>
              <label><input type="checkbox" checked={draft.shuffle_options}
                            onChange={(e) => set('shuffle_options', e.target.checked)} /> Shuffle options</label>
              <label><input type="checkbox" checked={draft.reveal_answers}
                            onChange={(e) => set('reveal_answers', e.target.checked)} /> Reveal answers</label>
            </div>
          </div>

          <div className="shead"><h2>Questions</h2></div>
          {draft.questions.map((q, qi) => (
            <div className="card editor-q" key={qi}>
              <div className="editor-q-head">
                <span className="mc">Question {qi + 1}</span>
                <button className="linkbtn danger" disabled={draft.questions.length <= 1}
                        onClick={() => set('questions', draft.questions.filter((_, i) => i !== qi))}>
                  Remove
                </button>
              </div>

              <div className="field">
                <label className="mc">Prompt</label>
                <textarea rows={3} value={q.prompt}
                          onChange={(e) => setQuestion(qi, { prompt: e.target.value })} />
              </div>
              <div className="field">
                <label className="mc">Explanation (optional)</label>
                <textarea rows={2} value={q.explanation}
                          onChange={(e) => setQuestion(qi, { explanation: e.target.value })} />
              </div>
              <div className="field" style={{ maxWidth: '11rem' }}>
                <label className="mc">Points</label>
                <input inputMode="decimal" value={String(q.points)}
                       onChange={(e) => setQuestion(qi, { points: Number(e.target.value) })} />
              </div>

              <div className="field" style={{ marginTop: 'var(--s4)' }}>
                <label className="mc">Options · tick the correct ones</label>
                {q.options.map((o, oi) => (
                  <div className="opt-row" key={oi}>
                    <input type="checkbox" checked={o.correct} title="Correct"
                           onChange={(e) => setOption(qi, oi, { correct: e.target.checked })} />
                    <input value={o.body} placeholder="Option body"
                           onChange={(e) => setOption(qi, oi, { body: e.target.value })} />
                    <button className="opt-remove" disabled={q.options.length <= 2}
                            title="Remove option" aria-label="Remove option"
                            onClick={() => setQuestion(qi, { options: q.options.filter((_, j) => j !== oi) })}>
                      {CloseIcon}
                    </button>
                  </div>
                ))}
                <button className="btn ghost" style={{ alignSelf: 'flex-start' }}
                        onClick={() => setQuestion(qi, { options: [...q.options, { body: '', correct: false }] })}>
                  + Add option
                </button>
              </div>
            </div>
          ))}
          <button className="btn ghost"
                  onClick={() => set('questions', [...draft.questions, blankQuestion()])}>
            + Add question
          </button>

          <div className="editor-actions">
            <button className="btn" onClick={save} disabled={busy}>
              {busy ? 'Saving…' : 'Save'}
            </button>
            <Link className="btn ghost" href="/admin">Cancel</Link>
          </div>
        </>
      )}
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
