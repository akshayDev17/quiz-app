// Shared by the site-shell tests: one `wrangler dev` session per test over the
// static export, with no Cloudflare account. It needs the export (`npm run
// build`, which writes out/) and a checkout of akshayDev17/site-themes in
// SITE_THEMES_DIR.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { after, before } from 'node:test';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
export const frontend = join(here, '..');
export const out = join(frontend, 'out');
const wrangler = join(frontend, 'node_modules/.bin/wrangler');
export const siteThemes = process.env.SITE_THEMES_DIR && resolve(process.env.SITE_THEMES_DIR);

export const APP = join(frontend, 'wrangler.jsonc');
export const UNBOUND = join(here, 'unbound.jsonc');
export const THROWING_SHELL = join(here, 'throwing-shell.jsonc');
export const SHELL = siteThemes && join(siteThemes, 'shell/wrangler.jsonc');

// Each path the Worker serves as a page, and the exported file behind it.
export const PAGES = {
  '/quiz': 'index.html',
  '/quiz/': 'index.html',
  '/quiz/set?id=x': 'set.html',
  '/quiz/play': 'play.html',
  '/quiz/results': 'results.html',
  '/quiz/history': 'history.html',
  '/quiz/admin': 'admin.html',
  '/quiz/admin/edit': 'admin/edit.html',
};

before(() => {
  assert.ok(siteThemes, 'set SITE_THEMES_DIR to a checkout of akshayDev17/site-themes');
  assert.ok(existsSync(SHELL), `no site-shell config at ${SHELL}`);
  assert.ok(existsSync(join(out, 'index.html')), 'no static export: run `npm run build` first');
});

const scratch = mkdtempSync(join(tmpdir(), 'quiz-shell-contract-'));
after(() => rmSync(scratch, { recursive: true, force: true }));

/** A port nothing is listening on right now (the OS picks it). */
function freePort() {
  return new Promise((resolvePort, reject) => {
    const probe = createServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const { port } = probe.address();
      probe.close(() => resolvePort(port));
    });
  });
}

/**
 * Starts one wrangler dev session and stops it when the test ends. The dev
 * registry is private to this run: a site-shell left running by any other
 * `wrangler dev` on the machine would otherwise answer this session's binding.
 */
export async function session(t, configs) {
  const port = await freePort();
  const args = ['dev', ...configs.flatMap((c) => ['-c', c]), '--ip', '127.0.0.1', '--port', String(port),
    '--inspector-port', String(await freePort()), '--persist-to', join(scratch, 'state'), '--log-level', 'info'];
  const env = { ...process.env, WRANGLER_SEND_METRICS: 'false', WRANGLER_REGISTRY_PATH: join(scratch, 'registry') };
  const child = spawn(wrangler, args, { cwd: frontend, env, stdio: ['ignore', 'pipe', 'pipe'] });
  let log = '';
  child.stdout.on('data', (d) => (log += d));
  child.stderr.on('data', (d) => (log += d));
  const exited = new Promise((r) => child.on('exit', r));
  t.after(() => {
    child.kill('SIGTERM');
    return exited;
  });
  for (let i = 0; i < 120 && !/Ready on/.test(log); i++) await new Promise((r) => setTimeout(r, 500));
  if (!/Ready on/.test(log)) throw new Error(`wrangler dev did not start:\n${log}`);
  return { base: `http://127.0.0.1:${port}`, log: () => log };
}
