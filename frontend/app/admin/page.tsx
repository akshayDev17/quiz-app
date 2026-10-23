'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  adminClone,
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

export default function AdminPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [sets, setSets] = useState<SetRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);

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
          <div className="field">
            <label className="mc" htmlFor="importFile">Import a quiz set (JSON)</label>
            <input
              id="importFile"
              type="file"
              accept="application/json,.json"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                // Clear the input so choosing the same file again (after fixing it) fires onChange.
                const input = e.target;
                if (file) importFile(file).finally(() => { input.value = ''; });
              }}
            />
          </div>
          <div className="shead" style={{ marginTop: 'var(--s6)' }}>
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
                      {s.status !== 'published' && (
                        <button className="btn ghost" disabled={busy} onClick={() => act(() => adminSetStatus(s.id, 'publish'))}>
                          Publish
                        </button>
                      )}
                      {s.status === 'published' && (
                        <button className="btn ghost" disabled={busy} onClick={() => act(() => adminSetStatus(s.id, 'archive'))}>
                          Archive
                        </button>
                      )}
                      <button className="btn ghost" disabled={busy} onClick={() => act(() => adminClone(s.id))}>
                        Clone
                      </button>
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
