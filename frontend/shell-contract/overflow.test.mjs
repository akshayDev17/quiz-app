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
  { id: 11, prompt: 'Which of these make **cosine similarity** equal to the dot product?\n\n```python\nimport numpy as np\nq = np.asarray(query_embedding, dtype=np.float32) / np.linalg.norm(query_embedding)\n```',
    options: [{ id: 111, body: 'Both vectors are L2-normalised' }, { id: 112, body: 'The vectors have the same dimension' },
      { id: 113, body: 'The index is built as\n\n```python\nindex = faiss.IndexFlatIP(dim); index.add(np.stack([v / np.linalg.norm(v) for v in vectors]))\n```' },
      { id: 114, body: 'Neither vector has a negative component (see https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances#metric_inner_product)' }] },
  { id: 12, prompt: 'An HNSW index returns fewer true neighbours after you lower `efSearch`. Why?',
    options: [{ id: 121, body: 'The search keeps a shorter candidate list per layer' }, { id: 122, body: 'The graph is rebuilt with fewer links' }] },
];
const attemptSession = {
  attempt: { id: 'a2', set_id: 2, status: 'in_progress', started_at: NOW - 13 * 60_000, deadline_at: NOW + 7 * 60_000, paused_at: null },
  server_now: NOW, set: { name: setIntro.name, topic: setIntro.topic, subtopic: setIntro.subtopic },
  questions, selections: { 11: [111] },
};
// Negative marking, below zero: the first question is +2 −1, the second left blank at −2.
const results = {
  attempt: { id: 'a1', status: 'submitted', started_at: NOW - 2 * HOUR, finished_at: NOW - HOUR, score: -1, max_score: 4 },
  set: { id: 2, name: setIntro.name, topic: setIntro.topic, scoring_policy: 'negative_marking', reveal_answers: true },
  questions: questions.map((q, i) => ({ id: q.id, prompt: q.prompt, points: 2, awarded_points: i ? -2 : 1, is_correct: false,
    explanation: 'Normalising both vectors makes the denominator 1, so cosine similarity reduces to the inner product.',
    options: q.options.map((o, j) => ({ id: o.id, body: o.body, selected: !i && (j === 0 || j === 2), correct: j === 0 })) })),
};
const history = { attempts: [
  { id: 'a2', set_id: 2, name: 'Embeddings and vector space · Set 1', topic: 'Retrieval-augmented generation', status: 'in_progress',
    started_at: NOW - 13 * 60_000, finished_at: null, score: null, max_score: null },
  { id: 'a1', set_id: 2, name: 'Embeddings and vector space · Set 1', topic: 'Retrieval-augmented generation', status: 'submitted',
    started_at: NOW - 2 * HOUR, finished_at: NOW - HOUR, score: 9.5, max_score: 12 },
  { id: 'a0', set_id: 4, name: 'Consensus and replication · Set 1', topic: 'Distributed systems', status: 'expired',
    started_at: NOW - 30 * HOUR, finished_at: NOW - 29 * HOUR, score: -13.5, max_score: 24 },
] };
const adminSets = { sets: [
  { id: 2, topic: 'Retrieval-augmented generation', name: 'Embeddings and vector space · Set 1', status: 'published', question_count: 12, attempt_count: 14 },
  { id: 3, topic: 'Retrieval-augmented generation', name: 'Embeddings and vector space · Set 2', status: 'draft', question_count: 10, attempt_count: 0 },
  { id: 4, topic: 'Distributed systems', name: 'Consensus and replication · Set 1', status: 'archived', question_count: 8, attempt_count: 3 },
] };
const adminSet = {
  id: 2, name: setIntro.name, topic: setIntro.topic, subtopic: setIntro.subtopic, status: 'published', seq: 1, question_count: 2,
  difficulty: 'medium', style: 'standard', title: null, description: setIntro.description, time_limit_minutes: 20,
  scoring_policy: 'partial', max_attempts: 3, shuffle_questions: true, shuffle_options: true, reveal_answers: true,
  questions: questions.map((q) => ({ prompt: q.prompt, explanation: null, points: 1,
    options: q.options.map((o, j) => ({ body: o.body, correct: j === 0 })) })),
};

/** GET /quiz/api<path> → body. */
const API = {
  '/me': me, '/topics': topics, '/sets/2': setIntro, '/attempts/a2': attemptSession, '/attempts/a1/results': results,
  '/attempts': history, '/admin/sets': adminSets, '/admin/sets/2': adminSet,
};

/** Each page type, and the element whose presence means its data has rendered. */
const PAGES = {
  '/quiz': '.shead',
  '/quiz/set?id=2': 'h1, h2',
  '/quiz/play?attempt=a2': '.opt',
  '/quiz/results?attempt=a1': '.ropt',
  '/quiz/history': '.table td',
  '/quiz/admin': '.table td',
  '/quiz/admin/edit?id=2': 'textarea',
};
const WIDTHS = [360, 390, 412];
const THEMES = ['classic-light', 'classic-dark'];

let browser;
before(async () => {
  browser = await chromium.launch({ channel: 'chrome' });
});
after(() => browser?.close());

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
      await context.route((url) => url.pathname.startsWith('/quiz/api/'), (route) => {
        const path = new URL(route.request().url()).pathname.slice('/quiz/api'.length);
        const body = API[path];
        return body ? route.fulfill({ json: body }) : route.fulfill({ status: 404, json: { error: 'not found' } });
      });
      for (const [path, ready] of Object.entries(PAGES)) {
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
