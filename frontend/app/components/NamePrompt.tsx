'use client';

import { useState } from 'react';
import { renameMe } from '../../lib/api';
import type { Me } from '../../lib/types';

/** First-visit dialog asking for a display name; rendered only while `display_name` is null. */
export default function NamePrompt({ email, onSaved }: { email: string; onSaved: (me: Me) => void }) {
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setSaving(true);
    setError(null);
    try {
      onSaved(await renameMe(trimmed));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save your name');
      setSaving(false);
    }
  }

  return (
    <div className="scrim on">
      <form className="card dialog" role="dialog" aria-modal="true" aria-labelledby="name-prompt-title" onSubmit={save}>
        <div className="kicker">First visit</div>
        <h3 id="name-prompt-title">What should we call you?</h3>
        <p>Shown in the masthead. You’re signed in as <code>{email}</code>.</p>
        {error && <div className="banner" style={{ marginTop: 'var(--s4)' }}>{error}</div>}
        <div className="field">
          <label className="mc" htmlFor="nameInput">Display name</label>
          <input
            id="nameInput"
            maxLength={60}
            autoComplete="name"
            required
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="row">
          <button className="btn" type="submit" disabled={saving}>Continue</button>
        </div>
      </form>
    </div>
  );
}
