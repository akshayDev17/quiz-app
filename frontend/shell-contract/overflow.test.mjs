// Every page type, composed by the real site-shell (harness.mjs) and filled with
// realistic data, must lay out at exactly the phone's width: on Android a page
// wider than the viewport is zoomed out to fit, which shrinks all of its text.
// Each page is opened in headless Chrome with phone emulation (mobile, @3x) at
// 360, 390 and 412 px, in both site themes, and document.documentElement's
// scrollWidth and innerWidth must both equal the phone's width (a mobile
// browser widens innerWidth along with the layout when it zooms a too-wide
// page out, so innerWidth alone cannot catch it). A failure names the widest
// element that sticks out past the phone's width. The quiz API is answered from the fixtures
// below.
//
//   SITE_THEMES_DIR=/path/to/site-themes npm run test:overflow
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright-core';
import { APP, SHELL, session } from './harness.mjs';

const NOW = Date.UTC(2026, 10, 6, 9, 30);
const HOUR = 3_600_000;

const me = { email: 'akshay.prabhakant@example.com', display_name: 'Akshay', role: 'admin' };
const card = (id, name, short_name, extra = {}) => ({
  id, name, short_name, difficulty: 'medium', style: 'standard', time_limit_minutes: 20, question_count: 12,
  last: null, open_attempt: null, ...extra,
});
const topics = { topics: [
  { id: 1, name: 'Retrieval-augmented generation', groups: [
    { subtopic: null, sets: [card(1, 'RAG fundamentals · Set 1', 'RAG fundamentals · Set 1',
      { last: { attempt_id: 'a1', status: 'submitted', score: 9.5, max_score: 12 } })] },
    { subtopic: { id: 2, name: 'Embeddings and vector space' }, sets: [
      card(2, 'Embeddings and vector space · Set 1', 'Set 1', { open_attempt: { attempt_id: 'a2', remaining_ms: 7 * 60_000 } }),
      card(3, 'Embeddings and vector space · Set 2', 'Set 2', { difficulty: 'hard', style: 'scenario' }),
      card(5, 'Embeddings and vector space · Set 3', 'Set 3', { question_count: 1,
        last: { attempt_id: 'a4', status: 'submitted', score: 0, max_score: 0 } }),
    ] },
  ] },
  { id: 2, name: 'Distributed systems', groups: [
    { subtopic: { id: 3, name: 'Consensus and replication' }, sets: [card(4, 'Consensus and replication · Set 1', 'Set 1')] },
  ] },
] };
const setIntro = { id: 2, topic: 'Retrieval-augmented generation', subtopic: 'Embeddings and vector space',
  name: 'Embeddings and vector space · Set 1',
  description: 'Cosine similarity, normalisation, approximate nearest-neighbour indexes and their recall trade-offs.',
  time_limit_minutes: 20, question_count: 12, max_attempts: 3, attempts_used: 1, open_attempt_id: null };
const questions = [
  { id: 11, kind: 'choice', prompt: 'Which of these make **cosine similarity** equal to the dot product?\n\n```python\nimport numpy as np\nq = np.asarray(query_embedding, dtype=np.float32) / np.linalg.norm(query_embedding)\n```',
    options: [{ id: 111, body: 'Both vectors are L2-normalised' }, { id: 112, body: 'The vectors have the same dimension' },
      { id: 113, body: 'The index is built as\n\n```python\nindex = faiss.IndexFlatIP(dim); index.add(np.stack([v / np.linalg.norm(v) for v in vectors]))\n```' },
      { id: 114, body: 'Neither vector has a negative component (see https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances#metric_inner_product)' }] },
  { id: 12, kind: 'choice', prompt: 'An HNSW index returns fewer true neighbours after you lower `efSearch`. Why?',
    options: [{ id: 121, body: 'The search keeps a shorter candidate list per layer' }, { id: 122, body: 'The graph is rebuilt with fewer links' }] },
];
// A subjective question: typed into a text box, marked 0–4 by the AI evaluator against its model answer.
// The typed answer and the model answer carry a long unbroken URL and a fenced block.
const LONG_TYPED = 'Each model learns its own space, see https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances#metric_inner_product_and_cosine_similarity_explained\n\nSo re-embed.';
const written = { id: 13, kind: 'subjective', prompt: 'In two or three sentences: why does swapping the embedding model force a full re-index, even at the same dimension?', options: [],
  max_text_length: 2_000 };
const MODEL_ANSWER = 'Each model learns its own vector space, so old and new vectors are not comparable:\n\n```python\nindex.reset(); index.add(np.stack([new_model.encode(chunk) for chunk in all_chunks_in_the_corpus_without_exception]))\n```';
const sessionOf = (id, qs, extra = {}) => ({
  attempt: { id, set_id: 2, status: 'in_progress', started_at: NOW - 13 * 60_000, deadline_at: NOW + 7 * 60_000, paused_at: null },
  server_now: NOW, set: { name: setIntro.name, topic: setIntro.topic, subtopic: setIntro.subtopic },
  questions: qs.map((q) => ({ max_text_length: null, ...q })), selections: {}, texts: {}, ...extra,
});
const attemptSession = sessionOf('a2', [...questions, written], { selections: { 11: [111] } });
/** The same paper opened on its subjective question, with a long typed answer in the box. */
const writtenSession = sessionOf('a3', [written, ...questions], { texts: { 13: LONG_TYPED } });
// The evaluator's feedback is plain text and can carry a long unbroken token too.
const FEEDBACK = 'You explain that each model has its own vector space; you do not say why the same dimension is no help (see https://example.com/a-very-long-unbroken-reference-to-vector-space-compatibility).';
const writtenResult = (id, prompt, extra) => ({ id, kind: 'subjective', prompt, points: 4, awarded_points: null, is_correct: null,
  explanation: 'Same dimension is a storage coincidence, not compatibility.', options: [], evaluation: 'awaiting', feedback: null,
  text_answer: LONG_TYPED, model_answer: MODEL_ANSWER, ...extra });
// Negative marking, below zero: the first question is +2 −1, the second left blank at −2; then a written
// answer in each state: AI-marked with feedback, awaiting evaluation (so the score is provisional), flagged.
const results = {
  attempt: { id: 'a1', status: 'submitted', started_at: NOW - 2 * HOUR, finished_at: NOW - HOUR, score: 2, max_score: 16,
             awaiting_count: 1 },
  set: { id: 2, name: setIntro.name, topic: setIntro.topic, scoring_policy: 'negative_marking', reveal_answers: true },
  questions: questions.map((q, i) => ({ id: q.id, kind: 'choice', prompt: q.prompt, points: 2, awarded_points: i ? -2 : 1, is_correct: false,
    explanation: 'Normalising both vectors makes the denominator 1, so cosine similarity reduces to the inner product.',
    options: q.options.map((o, j) => ({ id: o.id, body: o.body, selected: !i && (j === 0 || j === 2), correct: j === 0 })) })).concat([
    writtenResult(written.id, written.prompt, { evaluation: 'marked', awarded_points: 3, feedback: FEEDBACK }),
    writtenResult(14, 'In one sentence: what does normalising embeddings to unit length buy you?', {}),
    writtenResult(15, 'Why can an approximate index miss a true nearest neighbour?', { evaluation: 'flagged', awarded_points: 0 }),
  ]),
};
// An all-written set taken before written answers were marked: nothing in it is marked, so 0 out of 0.
const unmarkedResults = {
  attempt: { id: 'a4', status: 'submitted', started_at: NOW - 3 * HOUR, finished_at: NOW - 3 * HOUR + 10 * 60_000, score: 0, max_score: 0,
             awaiting_count: 0 },
  set: { id: 5, name: 'Embeddings and vector space · Set 3', topic: setIntro.topic, scoring_policy: 'negative_marking', reveal_answers: true },
  questions: [writtenResult(written.id, written.prompt, { points: null, evaluation: null })],
};
const history = { attempts: [
  { id: 'a2', set_id: 2, name: 'Embeddings and vector space · Set 1', topic: 'Retrieval-augmented generation', status: 'in_progress',
    started_at: NOW - 13 * 60_000, finished_at: null, score: null, max_score: null, awaiting_count: 0 },
  { id: 'a1', set_id: 2, name: 'Embeddings and vector space · Set 1', topic: 'Retrieval-augmented generation', status: 'submitted',
    started_at: NOW - 2 * HOUR, finished_at: NOW - HOUR, score: 9.5, max_score: 12, awaiting_count: 0 },
  { id: 'a4', set_id: 5, name: unmarkedResults.set.name, topic: unmarkedResults.set.topic, status: 'submitted',
    started_at: unmarkedResults.attempt.started_at, finished_at: unmarkedResults.attempt.finished_at, score: 0, max_score: 0,
    awaiting_count: 0 },
  { id: 'a0', set_id: 4, name: 'Consensus and replication · Set 1', topic: 'Distributed systems', status: 'expired',
    started_at: NOW - 30 * HOUR, finished_at: NOW - 29 * HOUR, score: -13.5, max_score: 24, awaiting_count: 2 },
] };
const adminSets = { sets: [
  { id: 2, topic: 'Retrieval-augmented generation', name: 'Embeddings and vector space · Set 1', status: 'published', visibility: 'private', question_count: 12, attempt_count: 14 },
  { id: 3, topic: 'Retrieval-augmented generation', name: 'Embeddings and vector space · Set 2', status: 'draft', visibility: 'public', question_count: 10, attempt_count: 0 },
  { id: 4, topic: 'Distributed systems', name: 'Consensus and replication · Set 1', status: 'archived', visibility: 'public', question_count: 8, attempt_count: 3 },
] };
const adminSet = {
  id: 2, name: setIntro.name, topic: setIntro.topic, subtopic: setIntro.subtopic, status: 'published', seq: 1, question_count: 2,
  difficulty: 'medium', style: 'standard', title: null, description: setIntro.description, time_limit_minutes: 20,
  scoring_policy: 'partial', max_attempts: 3, shuffle_questions: true, shuffle_options: true, reveal_answers: true,
  visibility: 'public',
  questions: questions.map((q) => ({ type: 'choice', prompt: q.prompt, explanation: null, points: 1,
    options: q.options.map((o, j) => ({ body: o.body, correct: j === 0 })) })).concat([
    { type: 'subjective', prompt: written.prompt, explanation: null, model_answer: MODEL_ANSWER,
      key_points: ['Each embedding model learns its own vector space', 'Old and new vectors cannot be compared, whatever their dimension'] },
  ]),
};
// The admin's evaluators: keys in each state (one out of credit, one with a cloud budget), long
// labels, ids and endpoints, entries with and without a cap, and the published presets.
const SOURCE = 'Anthropic list price, platform.claude.com/docs/en/about-claude/pricing, read 2026-11-13 (Claude Haiku 5.5: prompts up to 100k tokens).';
const field = (name, label, secret, placeholder = '', help = '') => ({ name, label, secret, placeholder, help });
const budgetReading = { limit: 50, spent: 12.5, remaining: 37.5, currency: 'USD',
  source: 'AWS Budgets "quiz-app-evaluator-monthly-budget" (monthly)', as_of: 1794580000000 };
const evaluatorKey = (id, provider, provider_label, label, extra = {}) => ({ id, provider, provider_label, label, hint: '…a1b2',
  settings: {}, billing: null, state: 'ready', problem: null, unusable_since: null, retry_at: null, checked_at: null,
  check_result: null, reads_balance: false, provider_budget: null, provider_budget_error: null, spent_usd: 0.0123,
  entries: 1, created_at: 1794570000000, ...extra });
const evaluatorEntry = (id, key, model, extra = {}) => ({ id, key_id: key.id, key_label: key.label, provider: key.provider,
  provider_label: key.provider_label, model, position: id - 1, usable: true, problem: null, monthly_cap_usd: 5,
  spent_usd: 0.0123, left_of_cap_usd: 4.9877, provider_budget: null, input_price_per_mtok: 0.1, output_price_per_mtok: 0.5, ...extra });
const personal = evaluatorKey(1, 'anthropic', 'Anthropic API', 'Anthropic, personal default workspace', {
  state: 'out_of_credit', problem: 'out of credit at provider', unusable_since: 1794580000000, retry_at: 1794583600000,
  checked_at: 1794580000000, check_result: 'out of credit at provider' });
const work = evaluatorKey(2, 'bedrock', 'Amazon Bedrock', 'Work AWS account', {
  settings: { region: 'ap-southeast-2' }, billing: { settings: { account_id: '123456789012', budget_name: 'quiz-app-evaluator-monthly-budget' } },
  reads_balance: true, provider_budget: budgetReading });
const foundry = evaluatorKey(3, 'azure', 'Azure AI Foundry', 'Foundry', {
  settings: { endpoint: 'https://my-very-long-resource-name-for-the-quiz-app.services.ai.azure.com/anthropic' },
  provider_budget_error: 'Microsoft Entra refused the billing credential (401 invalid_client)', entries: 1 });
const adminEvaluators = {
  month: '2026-11',
  key_storage: { ready: true, secret: 'KEY_ENCRYPTION_KEY' },
  providers: [
    { id: 'anthropic', label: 'Anthropic API', key_fields: [field('api_key', 'API key', true, 'paste the key')], billing: null,
      balance_note: "Anthropic has no API for an account's prepaid balance. The page shows this month's spend from each call's tokens, and marks the key out of credit when Anthropic refuses a call for credit." },
    { id: 'bedrock', label: 'Amazon Bedrock',
      key_fields: [field('api_key', 'Bedrock API key', true, 'paste the key'), field('region', 'Region', false, 'us-east-1')],
      billing: { label: 'AWS Budgets, read-only', fields: [
        field('aws_access_key_id', 'Access key ID', true, 'AKIA…', 'An IAM user or role key allowed only budgets:ViewBudget.'),
        field('aws_secret_access_key', 'Secret access key', true, 'paste the secret'),
        field('account_id', 'AWS account ID', false, '123456789012'), field('budget_name', 'Budget name', false, 'quiz-ai')] },
      balance_note: 'With a read-only AWS Budgets credential, the page shows the budget’s own figures.' },
    { id: 'azure', label: 'Azure AI Foundry',
      key_fields: [field('api_key', 'API key', true, 'paste the key'),
        field('endpoint', 'Endpoint', false, 'https://<resource>.services.ai.azure.com/anthropic')],
      billing: { label: 'Azure Cost Management, read-only', fields: [field('tenant_id', 'Tenant ID', false), field('client_id', 'Client ID', false),
        field('client_secret', 'Client secret', true), field('scope', 'Scope', false), field('budget_name', 'Budget name', false)] },
      balance_note: 'With a read-only Azure budget credential, the page shows the budget’s own figures.' },
  ],
  keys: [personal, work, foundry],
  entries: [
    evaluatorEntry(1, personal, 'claude-haiku-5-5', { usable: false, problem: 'out of credit at provider' }),
    evaluatorEntry(2, work, 'anthropic.claude-sonnet-5-5', { monthly_cap_usd: null, left_of_cap_usd: null, spent_usd: 0,
      provider_budget: budgetReading, input_price_per_mtok: 2, output_price_per_mtok: 10 }),
    evaluatorEntry(3, foundry, 'my-claude-haiku-deployment-for-the-quiz-app-evaluation', { monthly_cap_usd: 12.5, left_of_cap_usd: 12.5 }),
  ],
  defaults: { monthly_cap_usd: 5 },
  price_presets: [{ provider: 'anthropic', model: 'claude-haiku-5-5', input_price_per_mtok: 0.1, output_price_per_mtok: 0.5, source: SOURCE }],
  queue: { awaiting: 3, flagged: 1, awaiting_reasons: { 'out of credit at provider': 2, 'daily limit per person reached': 1 } },
  quotas: { per_user_daily: 20, global_daily: 300, calls_today: 17 },
};

// What a signed-out visitor reads: the cards without anyone's attempts, and one set for View.
const publicCard = ({ last, open_attempt, ...rest }) => rest;
const publicTopics = { topics: topics.topics.map((t) => ({ ...t, groups: t.groups.map((g) => ({ ...g, sets: g.sets.map(publicCard) })) })) };
const publicSet = {
  set: { id: 2, name: setIntro.name, topic: setIntro.topic, subtopic: setIntro.subtopic, description: setIntro.description,
    time_limit_minutes: 20, question_count: 2, reveal_answers: true },
  questions: questions.map((q) => ({ id: q.id, kind: 'choice', prompt: q.prompt,
    explanation: 'Normalising both vectors makes the denominator 1, so cosine similarity reduces to the inner product.',
    model_answer: null,
    options: q.options.map((o, j) => ({ id: o.id, body: o.body, correct: j === 0 })) })).concat([
    { id: written.id, kind: 'subjective', prompt: written.prompt, explanation: null, model_answer: MODEL_ANSWER, options: [] },
  ]),
};

/** GET /quiz/api<path> → body. */
const API = {
  '/me': me, '/topics': topics, '/sets/2': setIntro, '/attempts/a2': attemptSession, '/attempts/a3': writtenSession, '/attempts/a1/results': results,
  '/attempts/a4/results': unmarkedResults,
  '/attempts': history, '/admin/sets': adminSets, '/admin/sets/2': adminSet, '/admin/evaluators': adminEvaluators,
  '/public/topics': publicTopics, '/public/sets/2': publicSet,
};

/** Each page type, the element whose presence means its data has rendered, and whether the reader is signed out. */
const PAGES = {
  '/quiz': { ready: '.shead' },
  '/quiz/set?id=2': { ready: 'h1, h2' },
  '/quiz/play?attempt=a2': { ready: '.opt' },
  '/quiz/play?attempt=a3': { ready: 'textarea.written' },
  '/quiz/results?attempt=a1': { ready: '.answer-block.model' },
  '/quiz/results?attempt=a4': { ready: '.answer-block.model' },
  '/quiz/history': { ready: '.table td' },
  '/quiz/admin': { ready: '.table td' },
  '/quiz/admin/edit?id=2': { ready: 'textarea' },
  '/quiz/admin/evaluators': { ready: '.ev-entry' },
  // Signed out: Access redirects every protected API call to its sign-in.
  '/quiz?signed-out': { ready: '.shead', signedOut: true },
  '/quiz/view?id=2': { ready: '.answer-block.model', signedOut: true },
};
/** The public reads; every other API path is protected. */
const isPublic = (path) => path.startsWith('/public/');
const WIDTHS = [360, 390, 412];
const THEMES = ['classic-light', 'classic-dark'];

let browser;
before(async () => {
  browser = await chromium.launch({ channel: 'chrome' });
});
after(() => browser?.close());

/** Answers the quiz API from the fixtures above; a protected call redirects to sign-in while `signedOut()` holds. */
function answerApi(context, signedOut = () => false) {
  return context.route((url) => url.pathname.startsWith('/quiz/api/'), (route) => {
    const path = new URL(route.request().url()).pathname.slice('/quiz/api'.length);
    if (signedOut() && !isPublic(path)) {
      return route.fulfill({ status: 302, headers: { location: 'https://team.cloudflareaccess.com/cdn-cgi/access/login' } });
    }
    const body = API[path];
    return body ? route.fulfill({ json: body }) : route.fulfill({ status: 404, json: { error: 'not found' } });
  });
}

/** Opens every collapsed section (the home page's topics and subtopics), so all of its content is laid out. */
async function expandAll(page) {
  for (let i = 0; i < 20; i++) {
    const closed = page.locator('button[aria-expanded="false"]:visible');
    if ((await closed.count()) === 0) return;
    await closed.first().click();
  }
}

/** scrollWidth and innerWidth, and the widest element reaching past `vw`, the phone's width. */
function measure(page, vw) {
  return page.evaluate((vw) => {
    // Content inside a scroll container (a code block, a scrolling table) moves the page no wider.
    const scrolledAway = (el) => {
      for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        if (getComputedStyle(p).overflowX !== 'visible') return true;
      }
      return false;
    };
    let widest = null;
    for (const el of document.querySelectorAll('body *')) {
      if (scrolledAway(el)) continue;
      const right = el.getBoundingClientRect().right;
      if (right > vw + 0.5 && (!widest || right > widest.right)) {
        widest = { right: Math.round(right), el: `${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? `.${el.className.trim().split(/\s+/).join('.')}` : ''}` };
      }
    }
    return { scrollWidth: document.documentElement.scrollWidth, innerWidth, widest };
  }, vw);
}

test('every page type lays out at exactly the phone width (360, 390, 412 px; both themes)', async (t) => {
  const s = await session(t, [APP, SHELL]);
  const failures = [];
  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      const context = await browser.newContext({ viewport: { width, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
      await context.addInitScript((id) => { try { localStorage.setItem('site-theme', id); } catch {} }, theme);
      let signedOut = false;
      await answerApi(context, () => signedOut);
      for (const [path, { ready, signedOut: out = false }] of Object.entries(PAGES)) {
        signedOut = out;
        const page = await context.newPage();
        await page.goto(`${s.base}${path}`, { waitUntil: 'load' }).catch((err) => {
          throw new Error(`${err.message}\nwrangler dev:\n${s.log().slice(-3000)}`);
        });
        await page.waitForSelector(ready, { state: 'attached' });
        await expandAll(page);
        assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), theme);
        const m = await measure(page, width);
        if (m.scrollWidth !== width || m.innerWidth !== width) failures.push(`${theme} @${width}: ${path} lays out at ${m.scrollWidth} px, innerWidth ${m.innerWidth} (widest: ${JSON.stringify(m.widest)})`);
        await page.close();
      }
      await context.close();
    }
  }
  assert.deepEqual(failures, []);
});

test('a set with nothing marked reads Not marked wherever its score shows: results, set card, history', async (t) => {
  const s = await session(t, [APP, SHELL]);
  const context = await browser.newContext();
  await answerApi(context);
  const page = await context.newPage();

  await page.goto(`${s.base}/quiz/results?attempt=a4`, { waitUntil: 'load' });
  await page.waitForSelector('.stats .v');
  const stats = await page.locator('.stats > div').evaluateAll((cells) => cells.map((c) => c.textContent));
  assert.deepEqual(stats, ['Not markedScore'], 'results: one Not marked cell, no 0 / 0, no percent, no marking label');

  await page.goto(`${s.base}/quiz`, { waitUntil: 'load' });
  await page.waitForSelector('.shead');
  await expandAll(page);
  const foot = (name) => page.locator('.set-card', { has: page.locator('h3', { hasText: new RegExp(`^${name}$`) }) }).locator('.foot').textContent();
  assert.equal(await foot('Set 3'), 'Last: Not marked', 'set card: an unmarked last attempt');
  assert.equal(await foot('RAG fundamentals · Set 1'), 'Last: 9.5 / 12', 'set card: a marked last attempt keeps its score');

  await page.goto(`${s.base}/quiz/history`, { waitUntil: 'load' });
  await page.waitForSelector('.table td');
  const scores = await page.locator('.table tbody tr td:last-child').allTextContents();
  assert.deepEqual(scores, ['—', '9.5 / 12', 'Not marked', '−13.5 / 24 · 2 awaiting'],
    'history: the unmarked attempt reads Not marked, a provisional one says how many answers await');

  await context.close();
});
