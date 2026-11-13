import type {
  EvaluatorEntry,
  EvaluatorKey,
  EvaluatorKeyState,
  EvaluatorProvider,
  KeyUpdate,
  NewKey,
  PricePreset,
  ProviderBudget,
} from './types.ts';

/** Money for the admin's evaluator page: always cents, and never more than is really left. */
export function dollars(n: number): string {
  return `$${(Math.floor(n * 100 + 1e-9) / 100).toFixed(2)}`;
}

/** Spend so far, rounded up to the cent so a few calls never read as nothing. */
export function spentDollars(n: number): string {
  return `$${(Math.ceil(n * 100 - 1e-9) / 100).toFixed(2)}`;
}

/** A provider's own figure in its currency: dollars as "$12.50", anything else as "12.50 EUR". */
export function money(n: number, currency: string): string {
  return currency === 'USD' ? dollars(n) : `${(Math.floor(n * 100 + 1e-9) / 100).toFixed(2)} ${currency}`;
}

/** The best money figure for an entry: the provider's own budget, else what is left of its cap, else its spend. */
export function entryFigure(e: Pick<EvaluatorEntry, 'provider_budget' | 'left_of_cap_usd' | 'spent_usd'>): string {
  const b = e.provider_budget;
  if (b) return b.remaining < 0 ? `${money(-b.remaining, b.currency)} over budget` : `${money(b.remaining, b.currency)} left in budget`;
  if (e.left_of_cap_usd !== null) return `${dollars(e.left_of_cap_usd)} left of cap`;
  return `${spentDollars(e.spent_usd)} spent this month`;
}

/** An entry as the admin list names it: "Anthropic API · Personal · claude-haiku-5-5 ($4.99 left of cap)". */
export function evaluatorLabel(
  e: Pick<EvaluatorEntry, 'provider_label' | 'key_label' | 'model' | 'provider_budget' | 'left_of_cap_usd' | 'spent_usd'>,
): string {
  return `${e.provider_label} · ${e.key_label} · ${e.model} (${entryFigure(e)})`;
}

export function capText(e: Pick<EvaluatorEntry, 'monthly_cap_usd' | 'left_of_cap_usd'>): string {
  if (e.monthly_cap_usd === null || e.left_of_cap_usd === null) return 'No cap';
  return `${dollars(e.left_of_cap_usd)} left of a ${dollars(e.monthly_cap_usd)} cap`;
}

export function budgetLine(b: ProviderBudget): string {
  if (b.remaining < 0) return `${b.source}: over by ${money(-b.remaining, b.currency)} (limit ${money(b.limit, b.currency)})`;
  return `${b.source}: ${money(b.remaining, b.currency)} left of ${money(b.limit, b.currency)}`;
}

const STATE_TEXT: Record<EvaluatorKeyState, string> = {
  ready: 'ready', out_of_credit: 'out of credit', key_refused: 'key refused', unreadable: 'cannot be read',
};
export const keyStateText = (state: EvaluatorKeyState): string => STATE_TEXT[state];

/** What a key form holds: every field by name, secret ones as typed (never prefilled). */
export type KeyDraft = { label: string; fields: Record<string, string>; billing: Record<string, string>; removeBilling: boolean };

/** A fresh draft for a provider, or, given a stored key, its shown values with every secret blank. */
export function draftOf(stored: EvaluatorKey | null, provider: EvaluatorProvider): KeyDraft {
  const fill = (fields: EvaluatorProvider['key_fields'], shown: Record<string, string>) =>
    Object.fromEntries(fields.map((f) => [f.name, f.secret ? '' : (shown[f.name] ?? '')]));
  return {
    label: stored?.label ?? '',
    fields: fill(provider.key_fields, stored?.settings ?? {}),
    billing: fill(provider.billing?.fields ?? [], stored?.billing?.settings ?? {}),
    removeBilling: false,
  };
}

const trimmed = (values: Record<string, string>) =>
  Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v.trim()]));
const changed = (a: Record<string, string>, b: Record<string, string>) =>
  Object.keys({ ...a, ...b }).some((k) => (a[k] ?? '').trim() !== (b[k] ?? '').trim());
const oneSpaced = (s: string) => s.trim().split(/\s+/).join(' ');

/**
 * What to send for an edited key. A part (the key, or its billing credential) is sent whole, and
 * only when one of its secrets was typed again: the page never has the stored secret to resend.
 */
export function keyUpdate(
  stored: EvaluatorKey, provider: EvaluatorProvider, draft: KeyDraft,
): { update: KeyUpdate | null; problem: string | null } {
  const start = draftOf(stored, provider);
  const update: KeyUpdate = {};
  if (oneSpaced(draft.label) !== stored.label) update.label = oneSpaced(draft.label);
  const keySecrets = provider.key_fields.filter((f) => f.secret);
  if (keySecrets.some((f) => draft.fields[f.name]?.trim())) update.fields = trimmed(draft.fields);
  else if (changed(draft.fields, start.fields)) return { update: null, problem: 'Paste the key again to change its other values.' };
  if (draft.removeBilling) {
    if (stored.billing) update.billing = null;
  } else if (provider.billing) {
    const billingSecrets = provider.billing.fields.filter((f) => f.secret);
    if (billingSecrets.some((f) => draft.billing[f.name]?.trim())) update.billing = trimmed(draft.billing);
    else if (changed(draft.billing, start.billing)) {
      return { update: null, problem: 'Paste the billing secret again to change the billing credential.' };
    }
  }
  return { update: Object.keys(update).length ? update : null, problem: null };
}

export function newKeyBody(provider: EvaluatorProvider, draft: KeyDraft, withBilling: boolean): NewKey {
  const body: NewKey = { provider: provider.id, label: oneSpaced(draft.label), fields: trimmed(draft.fields) };
  if (withBilling && provider.billing) body.billing = trimmed(draft.billing);
  return body;
}

/** The published prices for a provider and model, when the backend lists them. */
export function presetFor(presets: PricePreset[], provider: string, model: string): PricePreset | undefined {
  const id = model.trim();
  return presets.find((p) => p.provider === provider && p.model === id);
}

/** Move the entry at `index` one place up (-1) or down (+1); out of range leaves the order as it is. */
export function moved<T>(items: T[], index: number, step: -1 | 1): T[] {
  const to = index + step;
  if (index < 0 || index >= items.length || to < 0 || to >= items.length) return items;
  const next = items.slice();
  const here = next[index];
  next[index] = next[to];
  next[to] = here;
  return next;
}
