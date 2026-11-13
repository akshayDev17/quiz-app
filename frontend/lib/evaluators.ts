import type { EvaluatorModel, PricePreset } from './types.ts';

/** Money for the admin's evaluator page: always cents, and never more than is really left. */
export function dollars(n: number): string {
  return `$${(Math.floor(n * 100 + 1e-9) / 100).toFixed(2)}`;
}

/** Spend so far, rounded up to the cent so a few calls never read as nothing. */
export function spentDollars(n: number): string {
  return `$${(Math.ceil(n * 100 - 1e-9) / 100).toFixed(2)}`;
}

/** An evaluator as the admin list names it: "Anthropic API · claude-haiku-5-5 ($4.99 left)". */
export function evaluatorLabel(m: Pick<EvaluatorModel, 'provider_label' | 'model' | 'remaining_usd'>): string {
  return `${m.provider_label} · ${m.model} (${dollars(m.remaining_usd)} left)`;
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
