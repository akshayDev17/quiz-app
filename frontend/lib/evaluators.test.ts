import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  budgetLine,
  capText,
  dollars,
  draftOf,
  entryFigure,
  evaluatorLabel,
  keyStateText,
  keyUpdate,
  money,
  moved,
  newKeyBody,
  presetFor,
  spentDollars,
} from './evaluators.ts';
import type { EvaluatorEntry, EvaluatorKey, EvaluatorProvider, ProviderBudget } from './types.ts';

const entry = (extra: Partial<EvaluatorEntry> = {}): EvaluatorEntry => ({
  id: 1, key_id: 1, key_label: 'Personal', provider: 'anthropic', provider_label: 'Anthropic API',
  model: 'claude-haiku-5-5', position: 0, usable: true, problem: null, monthly_cap_usd: 5, spent_usd: 0.0002,
  left_of_cap_usd: 4.9998, provider_budget: null, input_price_per_mtok: 0.1, output_price_per_mtok: 0.5, ...extra,
});
const budget = (extra: Partial<ProviderBudget> = {}): ProviderBudget => ({
  limit: 50, spent: 12.5, remaining: 37.5, currency: 'USD', source: 'AWS Budgets "quiz-ai" (monthly)', as_of: 1, ...extra,
});

const BEDROCK: EvaluatorProvider = {
  id: 'bedrock', label: 'Amazon Bedrock', balance_note: '',
  key_fields: [
    { name: 'api_key', label: 'Bedrock API key', secret: true, placeholder: '', help: '' },
    { name: 'region', label: 'Region', secret: false, placeholder: 'us-east-1', help: '' },
  ],
  billing: { label: 'AWS Budgets, read-only', fields: [
    { name: 'aws_secret_access_key', label: 'Secret access key', secret: true, placeholder: '', help: '' },
    { name: 'budget_name', label: 'Budget name', secret: false, placeholder: '', help: '' },
  ] },
};
const key = (extra: Partial<EvaluatorKey> = {}): EvaluatorKey => ({
  id: 7, provider: 'bedrock', provider_label: 'Amazon Bedrock', label: 'Work AWS', hint: '…ab12',
  settings: { region: 'us-east-1' }, billing: { settings: { budget_name: 'quiz-ai' } }, state: 'ready', problem: null,
  unusable_since: null, retry_at: null, checked_at: null, check_result: null, reads_balance: true,
  provider_budget: null, provider_budget_error: null, spent_usd: 0, entries: 1, created_at: 1, ...extra,
});

test('an entry reads Provider · key · model (the money it can still spend)', () => {
  assert.equal(evaluatorLabel(entry()), 'Anthropic API · Personal · claude-haiku-5-5 ($4.99 left of cap)');
  assert.equal(entryFigure(entry({ monthly_cap_usd: null, left_of_cap_usd: null })), '$0.01 spent this month');
  const uncapped = { monthly_cap_usd: null, left_of_cap_usd: null };
  assert.equal(entryFigure(entry({ ...uncapped, provider_budget: budget() })), '$37.50 left in budget');
  assert.equal(entryFigure(entry({ ...uncapped, provider_budget: budget({ remaining: -1.25 }) })), '$1.25 over budget');
});

test('with a cap and a provider budget, the smaller of the two is shown, named for which it is', () => {
  assert.equal(entryFigure(entry({ left_of_cap_usd: 0, provider_budget: budget({ remaining: 480 }) })), '$0.00 left of cap');
  assert.equal(entryFigure(entry({ left_of_cap_usd: 4.9998, provider_budget: budget() })), '$4.99 left of cap');
  assert.equal(entryFigure(entry({ monthly_cap_usd: 100, left_of_cap_usd: 99, provider_budget: budget() })),
    '$37.50 left in budget');
  assert.equal(entryFigure(entry({ provider_budget: budget({ remaining: -1.25 }) })), '$1.25 over budget');
  assert.equal(entryFigure(entry({ monthly_cap_usd: 100, left_of_cap_usd: 99, provider_budget: budget({ currency: 'EUR' }) })),
    '$99.00 left of cap');
  assert.equal(entryFigure(entry({ monthly_cap_usd: null, left_of_cap_usd: null, provider_budget: budget({ currency: 'EUR' }) })),
    '37.50 EUR left in budget');
});

test('what is left rounds down and what is spent rounds up, to the cent', () => {
  assert.equal(dollars(5), '$5.00');
  assert.equal(dollars(0.019), '$0.01');
  assert.equal(dollars(2.29), '$2.29');
  assert.equal(spentDollars(0.0002), '$0.01');
  assert.equal(spentDollars(0), '$0.00');
  assert.equal(spentDollars(1.2), '$1.20');
  assert.equal(money(12.5, 'EUR'), '12.50 EUR');
  assert.equal(money(12.5, 'USD'), '$12.50');
});

test('the cap and the provider budget read as plain sentences', () => {
  assert.equal(capText(entry()), '$4.99 left of a $5.00 cap');
  assert.equal(capText(entry({ monthly_cap_usd: null, left_of_cap_usd: null })), 'No cap');
  assert.equal(budgetLine(budget()), 'AWS Budgets "quiz-ai" (monthly): $37.50 left of $50.00');
  assert.equal(budgetLine(budget({ limit: 40, spent: 41.25, remaining: -1.25 })),
    'AWS Budgets "quiz-ai" (monthly): over by $1.25 (limit $40.00)');
});

test('a key state reads as words', () => {
  assert.deepEqual(['ready', 'out_of_credit', 'key_refused', 'unreadable'].map((s) => keyStateText(s as never)),
    ['ready', 'out of credit', 'key refused', 'cannot be read']);
});

test('editing a key starts from its shown values with every secret blank', () => {
  const draft = draftOf(key(), BEDROCK);
  assert.deepEqual(draft, { label: 'Work AWS', fields: { api_key: '', region: 'us-east-1' },
    billing: { aws_secret_access_key: '', budget_name: 'quiz-ai' }, removeBilling: false });
});

test('a key update sends only what changed, and the whole part when a secret is re-entered', () => {
  const base = draftOf(key(), BEDROCK);
  assert.deepEqual(keyUpdate(key(), BEDROCK, base), { update: null, problem: null });
  assert.deepEqual(keyUpdate(key(), BEDROCK, { ...base, label: '  Work  AWS 2 ' }),
    { update: { label: 'Work AWS 2' }, problem: null });
  assert.deepEqual(keyUpdate(key(), BEDROCK, { ...base, fields: { api_key: ' new-key ', region: 'eu-west-1' } }),
    { update: { fields: { api_key: 'new-key', region: 'eu-west-1' } }, problem: null });
  assert.deepEqual(keyUpdate(key(), BEDROCK, { ...base, fields: { api_key: '', region: 'eu-west-1' } }),
    { update: null, problem: 'Paste the key again to change its other values.' });
  assert.deepEqual(keyUpdate(key(), BEDROCK, { ...base, billing: { aws_secret_access_key: 's3cret', budget_name: 'quiz-ai' } }),
    { update: { billing: { aws_secret_access_key: 's3cret', budget_name: 'quiz-ai' } }, problem: null });
  assert.deepEqual(keyUpdate(key(), BEDROCK, { ...base, billing: { aws_secret_access_key: '', budget_name: 'other' } }),
    { update: null, problem: 'Paste the billing secret again to change the billing credential.' });
  assert.deepEqual(keyUpdate(key(), BEDROCK, { ...base, removeBilling: true }),
    { update: { billing: null }, problem: null });
  assert.deepEqual(keyUpdate(key({ billing: null }), BEDROCK, { ...draftOf(key({ billing: null }), BEDROCK), removeBilling: true }),
    { update: null, problem: null });
});

test('a new key sends its fields, and its billing credential only when asked', () => {
  const draft = { label: ' Work ', fields: { api_key: ' k ', region: 'us-east-1' },
    billing: { aws_secret_access_key: 's', budget_name: 'b' }, removeBilling: false };
  assert.deepEqual(newKeyBody(BEDROCK, draft, false),
    { provider: 'bedrock', label: 'Work', fields: { api_key: 'k', region: 'us-east-1' } });
  assert.deepEqual(newKeyBody(BEDROCK, draft, true),
    { provider: 'bedrock', label: 'Work', fields: { api_key: 'k', region: 'us-east-1' },
      billing: { aws_secret_access_key: 's', budget_name: 'b' } });
});

test('a preset is found by provider and exact model id', () => {
  const presets = [
    { provider: 'anthropic', model: 'claude-haiku-5-5', input_price_per_mtok: 0.1, output_price_per_mtok: 0.5, source: 's' },
    { provider: 'bedrock', model: 'anthropic.claude-haiku-5-5', input_price_per_mtok: 0.1, output_price_per_mtok: 0.5, source: 's' },
  ];
  assert.equal(presetFor(presets, 'anthropic', ' claude-haiku-5-5 ')?.provider, 'anthropic');
  assert.equal(presetFor(presets, 'bedrock', 'claude-haiku-5-5'), undefined);
});

test('an entry moves one place, and never off either end', () => {
  assert.deepEqual(moved([1, 2, 3], 1, -1), [2, 1, 3]);
  assert.deepEqual(moved([1, 2, 3], 1, 1), [1, 3, 2]);
  assert.deepEqual(moved([1, 2, 3], 0, -1), [1, 2, 3]);
  assert.deepEqual(moved([1, 2, 3], 2, 1), [1, 2, 3]);
});
