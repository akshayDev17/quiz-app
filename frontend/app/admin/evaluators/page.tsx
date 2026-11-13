'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  adminAddEvaluator,
  adminEvaluators,
  adminOrderEvaluators,
  adminRemoveEvaluator,
  adminRerunEvaluations,
  adminUpdateEvaluator,
  getMe,
  isSessionExpired,
  signOut,
} from '../../../lib/api';
import { dollars, evaluatorLabel, moved, presetFor, spentDollars } from '../../../lib/evaluators';
import { clearReauthFlag, handleSessionExpired } from '../../../lib/session';
import type { AdminEvaluators, EvaluatorModel, Me } from '../../../lib/types';
import Masthead, { type Crumb } from '../../components/Masthead';
import SignInAgain from '../../components/SignInAgain';

/** This page in the site path, after "Quiz Room". */
const TAIL: Crumb[] = [{ label: 'Admin', href: '/quiz/admin' }, { label: 'AI evaluators' }];

/** An entry's editable numbers, as the inputs hold them. */
type Fields = { budget: string; input: string; output: string };
const fieldsOf = (m: EvaluatorModel): Fields => ({
  budget: String(m.monthly_budget_usd),
  input: String(m.input_price_per_mtok),
  output: String(m.output_price_per_mtok),
});
const payloadOf = (f: Fields) => ({
  monthly_budget_usd: Number(f.budget),
  input_price_per_mtok: Number(f.input),
  output_price_per_mtok: Number(f.output),
});
const sameFields = (a: Fields, b: Fields) => a.budget === b.budget && a.input === b.input && a.output === b.output;

/** The default budget of a new entry, the provider workspace cap this was designed around. */
const NEW_BUDGET = '5';

const Chevron = ({ up }: { up: boolean }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={up ? 'm6 15 6-6 6 6' : 'm6 9 6 6 6-6'} />
  </svg>
);

/**
 * The AI evaluators that mark written answers: admin only (the server refuses anyone else on
 * every route). The admin orders "Provider · Model ($X.XX left)" entries, sets each one's monthly
 * budget and per-token prices, sees which providers have their Worker secrets, and re-runs
 * answers still awaiting evaluation. Secret values never reach this page; spend is the app's own
 * ledger, not the provider's bill.
 */
export default function EvaluatorsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<AdminEvaluators | null>(null);
  const [edits, setEdits] = useState<Record<number, Fields>>({});
  const [error, setError] = useState<string | null>(null);
  /** What the last re-run did, shown beside its button. */
  const [rerunNote, setRerunNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [fresh, setFresh] = useState<Fields>({ budget: NEW_BUDGET, input: '', output: '' });

  const fail = useCallback((err: unknown) => {
    if (isSessionExpired(err)) {
      setExpired(true);
      handleSessionExpired();
    } else setError(err instanceof Error ? err.message : 'Something went wrong');
  }, []);

  const show = useCallback((s: AdminEvaluators) => {
    setState(s);
    setEdits(Object.fromEntries(s.models.map((m) => [m.id, fieldsOf(m)])));
    setProvider((p) => p || s.providers.find((x) => x.usable)?.id || s.providers[0]?.id || '');
  }, []);

  useEffect(() => {
    getMe()
      .then(async (m) => {
        clearReauthFlag();
        setMe(m);
        if (m.role === 'admin') show(await adminEvaluators());
      })
      .catch(fail);
  }, [show, fail]);

  /** Runs one action and shows the page's state it returns. */
  async function act(action: () => Promise<AdminEvaluators>) {
    setBusy(true);
    setError(null);
    setRerunNote(null);
    try {
      show(await action());
    } catch (err) {
      fail(err);
    }
    setBusy(false);
  }

  function rerun() {
    act(async () => {
      const r = await adminRerunEvaluations();
      setRerunNote(`Re-ran ${r.attempts_tried} ${r.attempts_tried === 1 ? 'attempt' : 'attempts'}; ${r.still_awaiting} still awaiting.`);
      return adminEvaluators();
    });
  }

  /** Picking a model the backend has published prices for fills them in. */
  function pickModel(next: string, forProvider = provider) {
    setModel(next);
    const preset = state && presetFor(state.price_presets, forProvider, next);
    if (preset) {
      setFresh((f) => ({ ...f, input: String(preset.input_price_per_mtok), output: String(preset.output_price_per_mtok) }));
    }
  }

  function add() {
    act(async () => {
      const s = await adminAddEvaluator({ provider, model: model.trim(), ...payloadOf(fresh) });
      setModel('');
      setFresh({ budget: NEW_BUDGET, input: '', output: '' });
      return s;
    });
  }

  function reorder(index: number, step: -1 | 1) {
    if (!state) return;
    const ids = moved(state.models.map((m) => m.id), index, step);
    act(() => adminOrderEvaluators(ids));
  }

  function remove(m: EvaluatorModel) {
    if (!window.confirm(`Remove ${m.provider_label} · ${m.model}? Its spend this month stays in the ledger.`)) return;
    act(() => adminRemoveEvaluator(m.id));
  }

  const isAdmin = me?.role === 'admin';
  const presets = state ? state.price_presets.filter((p) => p.provider === provider) : [];
  const preset = state ? presetFor(state.price_presets, provider, model) : undefined;
  const providerUsable = state?.providers.find((p) => p.id === provider)?.usable ?? false;
  const reasons = state ? Object.entries(state.queue.awaiting_reasons) : [];

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} tail={TAIL} />
      <p style={{ marginBottom: 'var(--s4)' }}>
        <Link className="linkbtn" href="/admin">← Admin</Link>
      </p>
      {expired && <SignInAgain />}
      {error && <div className="banner">{error}</div>}
      {me && !isAdmin && <p className="mc">Not available.</p>}
      {!me && !expired && !error && <p className="mc">Loading…</p>}
      {isAdmin && (
        <>
          <h2 className="hl">AI evaluators</h2>
          <p className="ev-lede">
            Written answers are marked by the first entry below, top to bottom, whose provider has its secret set
            and whose budget for this month still has room. When none can, answers wait as <i>awaiting
            evaluation</i> and are never scored 0 for it.
          </p>
          <p className="ev-note">
            Budgets and spend are this app’s own ledger of the tokens it sent
            {state ? ` in ${state.month} (UTC)` : ''}, priced at the rates set here. They are not the provider’s
            billing figure: keep a monthly spend limit at the provider as the hard backstop.
          </p>
          {!state && !error && <p className="mc">Loading…</p>}

          {state && (
            <>
              <div className="shead">
                <h2>Order</h2>
              </div>
              {state.models.length === 0 && (
                <p className="mc">No evaluators yet: every written answer waits until you add one.</p>
              )}
              <ol className="ev-list">
                {state.models.map((m, i) => {
                  const f = edits[m.id] ?? fieldsOf(m);
                  const changed = !sameFields(f, fieldsOf(m));
                  const set = (patch: Partial<Fields>) => setEdits((e) => ({ ...e, [m.id]: { ...f, ...patch } }));
                  return (
                    <li key={m.id} className="card ev-entry">
                      <div className="ev-head">
                        <span className="ev-n">{i + 1}</span>
                        <b className="ev-label">{evaluatorLabel(m)}</b>
                        <span className={`chip ${m.usable ? 'ev-ok' : 'ev-miss'}`}>
                          {m.usable ? 'usable' : 'secret missing · skipped'}
                        </span>
                      </div>
                      <p className="ev-sub">
                        Spent {spentDollars(m.spent_usd)} of {dollars(m.monthly_budget_usd)} this month
                      </p>
                      <div className="ev-grid">
                        <label className="field">
                          <span className="mc">Monthly budget, USD</span>
                          <input inputMode="decimal" value={f.budget} disabled={busy}
                                 onChange={(e) => set({ budget: e.target.value })} />
                        </label>
                        <label className="field">
                          <span className="mc">Input, USD per M tokens</span>
                          <input inputMode="decimal" value={f.input} disabled={busy}
                                 onChange={(e) => set({ input: e.target.value })} />
                        </label>
                        <label className="field">
                          <span className="mc">Output, USD per M tokens</span>
                          <input inputMode="decimal" value={f.output} disabled={busy}
                                 onChange={(e) => set({ output: e.target.value })} />
                        </label>
                      </div>
                      <div className="ev-actions">
                        <button className="iconbtn" disabled={busy || i === 0} title="Move up"
                                aria-label={`Move ${m.model} up`} onClick={() => reorder(i, -1)}>
                          <Chevron up />
                        </button>
                        <button className="iconbtn" disabled={busy || i === state.models.length - 1} title="Move down"
                                aria-label={`Move ${m.model} down`} onClick={() => reorder(i, 1)}>
                          <Chevron up={false} />
                        </button>
                        <span className="ev-fill" />
                        <button className="btn ghost" disabled={busy || !changed}
                                onClick={() => act(() => adminUpdateEvaluator(m.id, payloadOf(f)))}>
                          Save
                        </button>
                        <button className="btn ghost ev-remove" disabled={busy} onClick={() => remove(m)}>
                          Remove
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ol>

              <div className="shead">
                <h2>Add an evaluator</h2>
              </div>
              <div className="card ev-entry ev-add">
                <div className="ev-grid ev-grid-2">
                  <label className="field">
                    <span className="mc">Provider</span>
                    <select value={provider} disabled={busy}
                            onChange={(e) => { setProvider(e.target.value); pickModel(model, e.target.value); }}>
                      {state.providers.map((p) => (
                        <option key={p.id} value={p.id}>{p.label}{p.usable ? '' : ' (secret missing)'}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="mc">Model id{provider === 'azure' ? ' (deployment name)' : ''}</span>
                    <input list="ev-models" value={model} disabled={busy} placeholder={presets[0]?.model ?? 'model id'}
                           autoComplete="off" spellCheck={false} onChange={(e) => pickModel(e.target.value)} />
                    <datalist id="ev-models">
                      {presets.map((p) => <option key={p.model} value={p.model} />)}
                    </datalist>
                  </label>
                </div>
                <div className="ev-grid">
                  <label className="field">
                    <span className="mc">Monthly budget, USD</span>
                    <input inputMode="decimal" value={fresh.budget} disabled={busy}
                           onChange={(e) => setFresh({ ...fresh, budget: e.target.value })} />
                  </label>
                  <label className="field">
                    <span className="mc">Input, USD per M tokens</span>
                    <input inputMode="decimal" value={fresh.input} disabled={busy}
                           onChange={(e) => setFresh({ ...fresh, input: e.target.value })} />
                  </label>
                  <label className="field">
                    <span className="mc">Output, USD per M tokens</span>
                    <input inputMode="decimal" value={fresh.output} disabled={busy}
                           onChange={(e) => setFresh({ ...fresh, output: e.target.value })} />
                  </label>
                </div>
                {preset && <p className="ev-sub">Prices filled in from: {preset.source}</p>}
                {!providerUsable && (
                  <p className="ev-sub">This provider’s secret is not set, so it will be skipped until it is.</p>
                )}
                <div className="ev-actions">
                  <span className="ev-fill" />
                  <button className="btn" disabled={busy || !provider || !model.trim() || !fresh.input || !fresh.output}
                          onClick={add}>
                    Add to the end
                  </button>
                </div>
              </div>

              <div className="shead">
                <h2>Providers</h2>
              </div>
              <ul className="ev-providers">
                {state.providers.map((p) => (
                  <li key={p.id}>
                    <b>{p.label}</b>
                    <span className={`chip ${p.usable ? 'ev-ok' : 'ev-miss'}`}>{p.usable ? 'usable' : 'secret missing'}</span>
                    {p.secrets.length > 0 && (
                      <span className="ev-secrets">
                        Worker secret{p.secrets.length > 1 ? 's' : ''}: {p.secrets.map((s) => <code key={s}>{s}</code>)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <p className="ev-note">
                The owner sets each secret from <code>backend/</code> with <code>wrangler secret put NAME</code>; this page
                only shows whether it is present, never its value.
              </p>

              <div className="shead">
                <h2>Waiting and flagged</h2>
              </div>
              <p className="ev-lede">
                <b>{state.queue.awaiting}</b> written {state.queue.awaiting === 1 ? 'answer' : 'answers'} awaiting
                evaluation · <b>{state.queue.flagged}</b> flagged for review (scored 0: the evaluator’s reply was unusable).
              </p>
              {reasons.length > 0 && (
                <ul className="ev-reasons">
                  {reasons.map(([why, n]) => <li key={why}>{n} · {why}</li>)}
                </ul>
              )}
              <div className="ev-actions">
                <button className="btn" disabled={busy || state.queue.awaiting === 0} onClick={rerun}>
                  Re-run awaiting evaluations
                </button>
                {rerunNote && <span className="mc" role="status">{rerunNote}</span>}
              </div>
              <p className="ev-note">
                A re-run marks up to 5 attempts per click, oldest first. It skips the daily limits
                ({state.quotas.per_user_daily} per person, {state.quotas.global_daily} for the site; {state.quotas.calls_today}{' '}
                {state.quotas.calls_today === 1 ? 'call' : 'calls'} today) but never a budget.
              </p>
            </>
          )}
        </>
      )}
    </div>
  );
}
