'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  adminClone,
  adminDelete,
  adminImport,
  adminListSets,
  adminSetStatus,
  getMe,
  isSessionExpired,
  signOut,
} from '../../lib/api';
import { clearReauthFlag, handleSessionExpired } from '../../lib/session';
import type { AdminSets, Me } from '../../lib/types';
import Masthead from '../components/Masthead';
import SignInAgain from '../components/SignInAgain';

type SetRow = AdminSets['sets'][number];

/* Outline icons, one set, recolored per state via currentColor (better-ui). */
const Icons = {
  publish: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 19V6" /><path d="M5 12l7-7 7 7" />
    </svg>
  ),
  archive: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="4" rx="1" /><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8" /><path d="M10 12h4" />
    </svg>
  ),
  clone: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  ),
  trash: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6M14 11v6" />
    </svg>
  ),
  upload: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 9l5-5 5 5" /><path d="M12 4v12" />
    </svg>
  ),
};

export default function AdminPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [sets, setSets] = useState<SetRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);
  const [importName, setImportName] = useState<string | null>(null);

  const fail = useCallback((err: unknown) => {
    if (isSessionExpired(err)) {
      setExpired(true);
      handleSessionExpired();
    } else setError(err instanceof Error ? err.message : 'Something went wrong');
  }, []);

  const reload = useCallback(() => adminListSets().then((r) => setSets(r.sets)), []);

  useEffect(() => {
    getMe()
      .then(async (m) => {
        clearReauthFlag();
        setMe(m);
        if (m.role === 'admin') await reload();
      })
      .catch(fail);
  }, [reload, fail]);

  /** Runs one admin action, then reloads the list whether it worked or not. */
  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      fail(err);
    }
    try {
      await reload();
    } catch (err) {
      fail(err);
    }
    setBusy(false);
  }

  async function importFile(file: File) {
    let doc: unknown;
    try {
      doc = JSON.parse(await file.text());
    } catch (err) {
      setNotice(null);
      setError(`Not valid JSON: ${err instanceof Error ? err.message : String(err)}`);
      return;
    }
    await act(async () => {
      const made = await adminImport(doc);
      setNotice(`Imported “${made.name}” as a draft.`);
    });
  }

  function remove(id: number, name: string) {
    if (!window.confirm(`Delete “${name}” forever? This cannot be undone.`)) return;
    act(async () => {
      await adminDelete(id);
      setNotice(`Deleted “${name}”.`);
    });
  }

  const isAdmin = me?.role === 'admin';

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} />
      <p style={{ marginBottom: 'var(--s4)' }}>
        <Link className="linkbtn" href="/">← All quizzes</Link>
      </p>
      {expired && <SignInAgain />}
      {error && <div className="banner">{error}</div>}
      {me && !isAdmin && <p className="mc">Not available.</p>}
      {!me && !expired && !error && <p className="mc">Loading…</p>}
      {isAdmin && (
        <>
          <h2 className="hl">Admin</h2>
          {notice && <p className="mc" style={{ marginBottom: 'var(--s4)' }}>{notice}</p>}

          <div className="import card">
            <span className="kicker">Import</span>
            <h3 className="import-title">Add a quiz set</h3>
            <p className="import-desc">
              Upload a quiz-set JSON. It lands as a draft — publish it once you’ve reviewed the questions and answer key.
            </p>
            <div className="import-pick">
              <label className="import-btn" htmlFor="importFile">
                {Icons.upload}
                Choose a JSON file
              </label>
              <input
                id="importFile"
                type="file"
                accept="application/json,.json"
                disabled={busy}
                hidden
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  // Clear the input so choosing the same file again (after fixing it) fires onChange.
                  const input = e.target;
                  if (file) {
                    setImportName(file.name);
                    importFile(file).finally(() => { input.value = ''; });
                  }
                }}
              />
              {importName && <span className="import-file">↳ {importName}</span>}
            </div>
          </div>

          <div className="shead">
            <h2>Sets</h2>
          </div>
          {!sets && !error && <p className="mc">Loading…</p>}
          {sets && sets.length === 0 && <p className="mc">No sets yet.</p>}
          {sets && sets.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th className="mc">Name</th>
                  <th className="mc">Topic</th>
                  <th className="mc">Status</th>
                  <th className="mc num">Questions</th>
                  <th className="mc num">Attempts</th>
                  <th className="mc">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sets.map((s) => (
                  <tr key={s.id}>
                    <td>{s.name}</td>
                    <td>{s.topic}</td>
                    <td className="mc">{s.status}</td>
                    <td className="num">{s.question_count}</td>
                    <td className="num">{s.attempt_count}</td>
                    <td>
                      <div className="actions">
                        {s.status !== 'published' && (
                          <button className="iconbtn" disabled={busy} title="Publish" aria-label={`Publish ${s.name}`}
                                  onClick={() => act(() => adminSetStatus(s.id, 'publish'))}>
                            {Icons.publish}
                          </button>
                        )}
                        {s.status === 'published' && (
                          <button className="iconbtn" disabled={busy} title="Archive" aria-label={`Archive ${s.name}`}
                                  onClick={() => act(() => adminSetStatus(s.id, 'archive'))}>
                            {Icons.archive}
                          </button>
                        )}
                        <button className="iconbtn" disabled={busy} title="Clone" aria-label={`Clone ${s.name}`}
                                onClick={() => act(() => adminClone(s.id))}>
                          {Icons.clone}
                        </button>
                        <button className="iconbtn danger" disabled={busy} title="Delete forever" aria-label={`Delete ${s.name} forever`}
                                onClick={() => remove(s.id, s.name)}>
                          {Icons.trash}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
