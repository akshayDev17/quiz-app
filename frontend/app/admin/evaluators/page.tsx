'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  adminAddEntry,
  adminAddKey,
  adminCheckKey,
  adminEvaluators,
  adminOrderEntries,
  adminRemoveEntry,
  adminRemoveKey,
  adminRerunEvaluations,
  adminUpdateEntry,
  adminUpdateKey,
  getMe,
  isSessionExpired,
  signOut,
} from '../../../lib/api';
import {
  budgetLine,
  capText,
  draftOf,
  evaluatorLabel,
  keyStateText,
  keyUpdate,
  moved,
  newKeyBody,
  presetFor,
  spentDollars,
  type KeyDraft,
} from '../../../lib/evaluators';
import { clearReauthFlag, handleSessionExpired } from '../../../lib/session';
import type {
  AdminEvaluators,
  EvaluatorEntry,
  EvaluatorField,
  EvaluatorKey,
  EvaluatorProvider,
  Me,
} from '../../../lib/types';
import Masthead, { type Crumb } from '../../components/Masthead';
import SignInAgain from '../../components/SignInAgain';

/** This page in the site path, after "Quiz Room". */
const TAIL: Crumb[] = [{ label: 'Admin', href: '/quiz/admin' }, { label: 'AI evaluators' }];

/** An entry's editable numbers, as the inputs hold them. An empty cap means no cap. */
type Fields = { cap: string; input: string; output: string };
const fieldsOf = (e: EvaluatorEntry): Fields => ({
  cap: e.monthly_cap_usd === null ? '' : String(e.monthly_cap_usd),
  input: String(e.input_price_per_mtok),
  output: String(e.output_price_per_mtok),
});
const payloadOf = (f: Fields) => ({
  monthly_cap_usd: f.cap.trim() === '' ? null : Number(f.cap),
  input_price_per_mtok: Number(f.input),
  output_price_per_mtok: Number(f.output),
});
const sameFields = (a: Fields, b: Fields) => a.cap === b.cap && a.input === b.input && a.output === b.output;

/** A time on this page: the admin's own clock and locale. */
const when = (ms: number) => new Date(ms).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

const Chevron = ({ up }: { up: boolean }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={up ? 'm6 15 6-6 6 6' : 'm6 9 6 6 6-6'} />
  </svg>
);

/** One input per field a provider needs; secret ones are password inputs the browser must not fill. */
function FieldInputs({ fields, values, onChange, disabled, secretHint }: {
  fields: EvaluatorField[]; values: Record<string, string>; onChange: (name: string, value: string) => void;
  disabled: boolean; secretHint?: string;
}) {
  return (
    <div className="ev-grid ev-grid-auto">
      {fields.map((f) => (
        <label key={f.name} className="field">
          <span className="mc">{f.label}</span>
          <input
            type={f.secret ? 'password' : 'text'}
            autoComplete={f.secret ? 'new-password' : 'off'}
            spellCheck={false}
            value={values[f.name] ?? ''}
            placeholder={f.secret && secretHint ? secretHint : f.placeholder}
            disabled={disabled}
            onChange={(e) => onChange(f.name, e.target.value)}
          />
          {f.help && <span className="ev-help">{f.help}</span>}
        </label>
      ))}
    </div>
  );
}

/**
 * The AI evaluators that mark written answers: admin only (the server refuses anyone else on
 * every route). The admin adds keys (stored sealed, never shown again), orders "Provider · key ·
 * model" entries with optional monthly caps, checks a key now, and re-runs answers still
 * awaiting evaluation. Money is the provider's own budget where it reports one, else the app's
 * tracking of the tokens it sent.
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
  const [keyId, setKeyId] = useState<number | null>(null);
  const [model, setModel] = useState('');
  const [fresh, setFresh] = useState<Fields>({ cap: '', input: '', output: '' });

  const fail = useCallback((err: unknown) => {
    if (isSessionExpired(err)) {
      setExpired(true);
      handleSessionExpired();
    } else setError(err instanceof Error ? err.message : 'Something went wrong');
  }, []);

  const show = useCallback((s: AdminEvaluators) => {
    setState(s);
    setEdits(Object.fromEntries(s.entries.map((e) => [e.id, fieldsOf(e)])));
    setKeyId((k) => (k !== null && s.keys.some((x) => x.id === k) ? k : s.keys[0]?.id ?? null));
    setFresh((f) => (f.cap === '' && f.input === '' ? { ...f, cap: String(s.defaults.monthly_cap_usd) } : f));
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

  /** Runs one action and shows the page's state it returns. True when it worked. */
  async function act(action: () => Promise<AdminEvaluators>): Promise<boolean> {
    setBusy(true);
    setError(null);
    setRerunNote(null);
    let ok = false;
    try {
      show(await action());
      ok = true;
    } catch (err) {
      fail(err);
    }
    setBusy(false);
    return ok;
  }

  function rerun() {
    act(async () => {
      const r = await adminRerunEvaluations();
      setRerunNote(`Re-ran ${r.attempts_tried} ${r.attempts_tried === 1 ? 'attempt' : 'attempts'}; ${r.still_awaiting} still awaiting.`);
      return adminEvaluators();
    });
  }

  const chosenKey = state?.keys.find((k) => k.id === keyId) ?? null;

  /** Picking a model the backend has published prices for fills them in. */
  function pickModel(next: string, provider = chosenKey?.provider ?? '') {
    setModel(next);
    const preset = state && presetFor(state.price_presets, provider, next);
    if (preset) {
      setFresh((f) => ({ ...f, input: String(preset.input_price_per_mtok), output: String(preset.output_price_per_mtok) }));
    }
  }

  function addEntry() {
    if (keyId === null || !state) return;
    act(async () => {
      const s = await adminAddEntry({ key_id: keyId, model: model.trim(), ...payloadOf(fresh) });
      setModel('');
      setFresh({ cap: String(s.defaults.monthly_cap_usd), input: '', output: '' });
      return s;
    });
  }

  function reorder(index: number, step: -1 | 1) {
    if (!state) return;
    act(() => adminOrderEntries(moved(state.entries.map((e) => e.id), index, step)));
  }

  function removeEntry(e: EvaluatorEntry) {
    if (!window.confirm(`Remove ${e.provider_label} · ${e.key_label} · ${e.model}? Its spend this month stays in the ledger.`)) return;
    act(() => adminRemoveEntry(e.id));
  }

  const isAdmin = me?.role === 'admin';
  const providerOf = (id: string) => state?.providers.find((p) => p.id === id);
  const presets = state && chosenKey ? state.price_presets.filter((p) => p.provider === chosenKey.provider) : [];
  const preset = state && chosenKey ? presetFor(state.price_presets, chosenKey.provider, model) : undefined;
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
            Written answers are marked by the first entry below, top to bottom, that can take the call: its key
            works and its monthly cap, if it has one, still has room. A key the provider refuses for credit, or
            refuses outright, is passed over and tried again an hour later. When no entry can, answers wait as{' '}
            <i>awaiting evaluation</i> and are never scored 0 for it.
          </p>
          <p className="ev-note">
            Spend is this app’s own tracking of the tokens it sent{state ? ` in ${state.month} (UTC)` : ''}, priced
            at the rates set here. A budget figure, where a key has a billing credential, is the provider’s own.
            Keep a spend limit or budget alert at the provider as the hard stop.
          </p>
          {!state && !error && <p className="mc">Loading…</p>}

          {state && !state.key_storage.ready && (
            <div className="card ev-entry ev-storage" role="note">
              <b>Key storage is not set up.</b> Keys are stored sealed under the <code>{state.key_storage.secret}</code>{' '}
              Worker secret, which the owner sets once from <code>backend/</code> (docs/deploy.md §C). Until then no
              key can be added or used, and written answers wait.
            </div>
          )}

          {state && (
            <>
              <div className="shead">
                <h2>Order</h2>
              </div>
              {state.entries.length === 0 && (
                <p className="mc">No entries yet: every written answer waits until you add a key and an entry.</p>
              )}
              <ol className="ev-list">
                {state.entries.map((e, i) => {
                  const f = edits[e.id] ?? fieldsOf(e);
                  const changed = !sameFields(f, fieldsOf(e));
                  const set = (patch: Partial<Fields>) => setEdits((x) => ({ ...x, [e.id]: { ...f, ...patch } }));
                  return (
                    <li key={e.id} className="card ev-entry">
                      <div className="ev-head">
                        <span className="ev-n">{i + 1}</span>
                        <b className="ev-label">{evaluatorLabel(e)}</b>
                        <span className={`chip ${e.usable ? 'ev-ok' : 'ev-miss'}`}>
                          {e.usable ? 'usable' : `${e.problem} · passed over`}
                        </span>
                      </div>
                      <p className="ev-sub">Spent {spentDollars(e.spent_usd)} this month · {capText(e)}</p>
                      {e.provider_budget && (
                        <p className="ev-sub">
                          {budgetLine(e.provider_budget)}
                          {e.provider_budget.as_of ? `, as of ${when(e.provider_budget.as_of)}` : ''}
                        </p>
                      )}
                      <div className="ev-grid">
                        <label className="field">
                          <span className="mc">Monthly cap, USD (empty: none)</span>
                          <input inputMode="decimal" value={f.cap} disabled={busy} placeholder="no cap"
                                 onChange={(x) => set({ cap: x.target.value })} />
                        </label>
                        <label className="field">
                          <span className="mc">Input, USD per M tokens</span>
                          <input inputMode="decimal" value={f.input} disabled={busy}
                                 onChange={(x) => set({ input: x.target.value })} />
                        </label>
                        <label className="field">
                          <span className="mc">Output, USD per M tokens</span>
                          <input inputMode="decimal" value={f.output} disabled={busy}
                                 onChange={(x) => set({ output: x.target.value })} />
                        </label>
                      </div>
                      <div className="ev-actions">
                        <button className="iconbtn" disabled={busy || i === 0} title="Move up"
                                aria-label={`Move ${e.model} up`} onClick={() => reorder(i, -1)}>
                          <Chevron up />
                        </button>
                        <button className="iconbtn" disabled={busy || i === state.entries.length - 1} title="Move down"
                                aria-label={`Move ${e.model} down`} onClick={() => reorder(i, 1)}>
                          <Chevron up={false} />
                        </button>
                        <span className="ev-fill" />
                        <button className="btn ghost" disabled={busy || !changed}
                                onClick={() => act(() => adminUpdateEntry(e.id, payloadOf(f)))}>
                          Save
                        </button>
                        <button className="btn ghost ev-remove" disabled={busy} onClick={() => removeEntry(e)}>
                          Remove
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ol>

              <div className="shead">
                <h2>Add an entry</h2>
              </div>
              {state.keys.length === 0 ? (
                <p className="mc">Add a key below first: an entry is a key and a model.</p>
              ) : (
                <div className="card ev-entry ev-add">
                  <div className="ev-grid ev-grid-halves">
                    <label className="field">
                      <span className="mc">Key</span>
                      <select value={keyId ?? ''} disabled={busy}
                              onChange={(x) => {
                                const next = Number(x.target.value);
                                setKeyId(next);
                                pickModel(model, state.keys.find((k) => k.id === next)?.provider);
                              }}>
                        {state.keys.map((k) => (
                          <option key={k.id} value={k.id}>{k.provider_label} · {k.label}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span className="mc">Model id{chosenKey?.provider === 'azure' ? ' (deployment name)' : ''}</span>
                      <input list="ev-models" value={model} disabled={busy} placeholder={presets[0]?.model ?? 'model id'}
                             autoComplete="off" spellCheck={false} onChange={(x) => pickModel(x.target.value)} />
                      <datalist id="ev-models">
                        {presets.map((p) => <option key={p.model} value={p.model} />)}
                      </datalist>
                    </label>
                  </div>
                  <div className="ev-grid">
                    <label className="field">
                      <span className="mc">Monthly cap, USD (empty: none)</span>
                      <input inputMode="decimal" value={fresh.cap} disabled={busy} placeholder="no cap"
                             onChange={(x) => setFresh({ ...fresh, cap: x.target.value })} />
                    </label>
                    <label className="field">
                      <span className="mc">Input, USD per M tokens</span>
                      <input inputMode="decimal" value={fresh.input} disabled={busy}
                             onChange={(x) => setFresh({ ...fresh, input: x.target.value })} />
                    </label>
                    <label className="field">
                      <span className="mc">Output, USD per M tokens</span>
                      <input inputMode="decimal" value={fresh.output} disabled={busy}
                             onChange={(x) => setFresh({ ...fresh, output: x.target.value })} />
                    </label>
                  </div>
                  {preset && <p className="ev-sub">Prices filled in from: {preset.source}</p>}
                  <div className="ev-actions">
                    <span className="ev-fill" />
                    <button className="btn" disabled={busy || keyId === null || !model.trim() || !fresh.input || !fresh.output}
                            onClick={addEntry}>
                      Add to the end
                    </button>
                  </div>
                </div>
              )}

              <div className="shead">
                <h2>Keys</h2>
              </div>
              {state.keys.length === 0 && <p className="mc">No keys yet.</p>}
              <ul className="ev-list">
                {state.keys.map((k) => {
                  const provider = providerOf(k.provider);
                  return provider ? (
                    <KeyCard key={k.id} stored={k} provider={provider} busy={busy} act={act}
                             check={state.check?.key_id === k.id ? state.check : undefined} />
                  ) : null;
                })}
              </ul>
              <AddKey providers={state.providers} ready={state.key_storage.ready} busy={busy} act={act} />

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
                {state.quotas.calls_today === 1 ? 'call' : 'calls'} today) but never a cap.
              </p>
            </>
          )}
        </>
      )}
    </div>
  );
}

/** One stored key: what identifies it, its status, and Check now, Edit and Remove. */
function KeyCard({ stored, provider, busy, act, check }: {
  stored: EvaluatorKey; provider: EvaluatorProvider; busy: boolean;
  act: (action: () => Promise<AdminEvaluators>) => Promise<boolean>;
  check?: AdminEvaluators['check'];
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<KeyDraft>(() => draftOf(stored, provider));
  const plan = keyUpdate(stored, provider, draft);
  /** A stored setting by its field's label: "Region: us-east-1", not "region: us-east-1". */
  const labelled = (values: Record<string, string>, fields: EvaluatorField[]) =>
    Object.entries(values).map(([name, value]) => [fields.find((f) => f.name === name)?.label ?? name, value] as const);
  const settings = labelled(stored.settings, provider.key_fields);
  const billingSettings = labelled(stored.billing?.settings ?? {}, provider.billing?.fields ?? []);

  function startEditing() {
    setDraft(draftOf(stored, provider));
    setEditing(true);
  }

  async function save() {
    if (!plan.update) return;
    const update = plan.update;
    if (await act(() => adminUpdateKey(stored.id, update))) setEditing(false);
  }

  function remove() {
    const also = stored.entries ? ` and its ${stored.entries} ${stored.entries === 1 ? 'entry' : 'entries'}` : '';
    if (!window.confirm(`Remove the key “${stored.label}”${also}? Its spend stays in the ledger.`)) return;
    act(() => adminRemoveKey(stored.id));
  }

  return (
    <li className="card ev-entry ev-key">
      <div className="ev-head">
        <b className="ev-label">{stored.label}</b>
        <span className="chip">{stored.provider_label}</span>
        <span className={`chip ${stored.state === 'ready' ? 'ev-ok' : 'ev-miss'}`}>{keyStateText(stored.state)}</span>
      </div>
      <p className="ev-sub">
        {stored.hint ? <>Key <code>{stored.hint}</code> · </> : null}
        {settings.map(([label, value]) => <span key={label}>{label}: <code>{value}</code> · </span>)}
        {stored.entries} {stored.entries === 1 ? 'entry' : 'entries'} · spent {spentDollars(stored.spent_usd)} this month
      </p>
      {stored.problem && (
        <p className="ev-sub ev-warn">
          {stored.problem.charAt(0).toUpperCase() + stored.problem.slice(1)}
          {stored.unusable_since ? ` since ${when(stored.unusable_since)}` : ''}
          {stored.retry_at ? `; marking tries it again after ${when(stored.retry_at)}` : ''}
        </p>
      )}
      {provider.billing && (
        <p className="ev-sub">
          {stored.billing
            ? <>Billing: {provider.billing.label}{billingSettings.length ? ' · ' : ''}
                {billingSettings.map(([label, value], i) => (
                  <span key={label}>{i ? ' · ' : ''}{label}: <code>{value}</code></span>
                ))}</>
            : <>No billing credential: the page tracks spend only.</>}
        </p>
      )}
      {stored.provider_budget && (
        <p className="ev-sub">
          {budgetLine(stored.provider_budget)}
          {stored.provider_budget.as_of ? `, as of ${when(stored.provider_budget.as_of)}` : ''}
        </p>
      )}
      {stored.reads_balance && !stored.provider_budget && !stored.provider_budget_error && (
        <p className="ev-sub">No budget reading yet: Check now reads it.</p>
      )}
      {stored.provider_budget_error && <p className="ev-sub ev-warn">Budget reading: {stored.provider_budget_error}</p>}
      {!stored.reads_balance && !provider.billing && provider.balance_note && (
        <p className="ev-sub">{provider.balance_note}</p>
      )}

      {editing && (
        <div className="ev-form">
          <label className="field">
            <span className="mc">Label</span>
            <input value={draft.label} disabled={busy} maxLength={60} onChange={(x) => setDraft({ ...draft, label: x.target.value })} />
          </label>
          <p className="ev-sub">To replace the key, paste the new one. Left empty, the stored key stays.</p>
          <FieldInputs fields={provider.key_fields} values={draft.fields} disabled={busy}
                       secretHint={`stored ${stored.hint || 'key'}: paste to replace`}
                       onChange={(name, value) => setDraft({ ...draft, fields: { ...draft.fields, [name]: value } })} />
          {provider.billing && (
            <>
              <p className="ev-sub">
                {provider.billing.label}: {stored.billing ? 'paste its secrets to replace it.' : 'optional, to read the real budget on Check now.'}
              </p>
              <FieldInputs fields={provider.billing.fields} values={draft.billing} disabled={busy || draft.removeBilling}
                           secretHint={stored.billing ? 'stored: paste to replace' : undefined}
                           onChange={(name, value) => setDraft({ ...draft, billing: { ...draft.billing, [name]: value } })} />
              {stored.billing && (
                <label className="ev-check-row">
                  <input type="checkbox" checked={draft.removeBilling} disabled={busy}
                         onChange={(x) => setDraft({ ...draft, removeBilling: x.target.checked })} />
                  <span>Remove the billing credential</span>
                </label>
              )}
            </>
          )}
          {plan.problem && <p className="ev-sub ev-warn">{plan.problem}</p>}
          <div className="ev-actions">
            <span className="ev-fill" />
            <button className="btn ghost" disabled={busy} onClick={() => setEditing(false)}>Cancel</button>
            <button className="btn" disabled={busy || !plan.update} onClick={save}>Save key</button>
          </div>
        </div>
      )}

      {!editing && (
        <div className="ev-actions">
          <button className="btn ghost" disabled={busy} onClick={() => act(() => adminCheckKey(stored.id))}>Check now</button>
          {check ? (
            <span className="mc ev-check" role="status">
              {check.result}{check.provider_budget_error ? ` · budget: ${check.provider_budget_error}` : ''}
            </span>
          ) : stored.checked_at ? (
            <span className="mc ev-check">Checked {when(stored.checked_at)}: {stored.check_result}</span>
          ) : null}
          <span className="ev-fill" />
          <button className="btn ghost" disabled={busy} onClick={startEditing}>Edit</button>
          <button className="btn ghost ev-remove" disabled={busy} onClick={remove}>Remove</button>
        </div>
      )}
    </li>
  );
}

/** The form for a new key: the provider's fields, and its optional read-only billing credential. */
function AddKey({ providers, ready, busy, act }: {
  providers: EvaluatorProvider[]; ready: boolean; busy: boolean;
  act: (action: () => Promise<AdminEvaluators>) => Promise<boolean>;
}) {
  const [providerId, setProviderId] = useState(providers[0]?.id ?? '');
  const provider = providers.find((p) => p.id === providerId) ?? providers[0];
  const [draft, setDraft] = useState<KeyDraft>(() => (provider ? draftOf(null, provider) : draftOf(null, providers[0])));
  const [withBilling, setWithBilling] = useState(false);
  if (!provider) return null;

  const missing = [...provider.key_fields.filter((f) => !draft.fields[f.name]?.trim()),
    ...(withBilling && provider.billing ? provider.billing.fields.filter((f) => !draft.billing[f.name]?.trim()) : [])];

  function pick(id: string) {
    const next = providers.find((p) => p.id === id);
    if (!next) return;
    setProviderId(id);
    setDraft({ ...draftOf(null, next), label: draft.label });
    setWithBilling(false);
  }

  async function add() {
    if (await act(() => adminAddKey(newKeyBody(provider, draft, withBilling)))) {
      setDraft(draftOf(null, provider));
      setWithBilling(false);
    }
  }

  return (
    <div className="card ev-entry ev-add">
      <p className="ev-sub ev-add-title"><b>Add a key</b> · stored sealed; only its label and last four characters are shown again.</p>
      <div className="ev-grid ev-grid-2">
        <label className="field">
          <span className="mc">Provider</span>
          <select value={providerId} disabled={busy || !ready} onChange={(x) => pick(x.target.value)}>
            {providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="mc">Label</span>
          <input value={draft.label} disabled={busy || !ready} maxLength={60} placeholder="e.g. Personal"
                 onChange={(x) => setDraft({ ...draft, label: x.target.value })} />
        </label>
      </div>
      <FieldInputs fields={provider.key_fields} values={draft.fields} disabled={busy || !ready}
                   onChange={(name, value) => setDraft({ ...draft, fields: { ...draft.fields, [name]: value } })} />
      {provider.balance_note && <p className="ev-sub">{provider.balance_note}</p>}
      {provider.billing && (
        <>
          <label className="ev-check-row">
            <input type="checkbox" checked={withBilling} disabled={busy || !ready} onChange={(x) => setWithBilling(x.target.checked)} />
            <span>Also add a billing credential ({provider.billing.label})</span>
          </label>
          {withBilling && (
            <FieldInputs fields={provider.billing.fields} values={draft.billing} disabled={busy || !ready}
                         onChange={(name, value) => setDraft({ ...draft, billing: { ...draft.billing, [name]: value } })} />
          )}
        </>
      )}
      <div className="ev-actions">
        <span className="ev-fill" />
        <button className="btn" disabled={busy || !ready || !draft.label.trim() || missing.length > 0} onClick={add}>
          Add key
        </button>
      </div>
    </div>
  );
}
