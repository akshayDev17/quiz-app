'use client';

import { useEffect, useState } from 'react';
import { getMe, getTopics, isSessionExpired, signOut } from '../lib/api';
import { pluralize, subtopicGroupLabel } from '../lib/names';
import type { Me, TopicsResponse } from '../lib/types';
import Masthead from './components/Masthead';
import NamePrompt from './components/NamePrompt';
import SetCard from './components/SetCard';

export default function Home() {
  const [me, setMe] = useState<Me | null>(null);
  const [topics, setTopics] = useState<TopicsResponse['topics'] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMe(), getTopics()]).then(
      ([m, t]) => {
        setMe(m);
        setTopics(t.topics);
      },
      (err) => {
        // Access re-authenticates on navigation, so a reload is the way back in.
        if (isSessionExpired(err)) window.location.reload();
        else setError(err instanceof Error ? err.message : 'Something went wrong');
      },
    );
  }, []);

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} />
      {error && <div className="banner">{error}</div>}
      {!error && !topics && <p className="mc">Loading…</p>}
      {topics && topics.length === 0 && <p className="mc">No quizzes yet</p>}
      {topics?.map((topic, i) => (
        <section key={topic.id}>
          <div className="shead">
            <span className="num">{String(i + 1).padStart(2, '0')}</span>
            <h2>{topic.name}</h2>
            <span className="mc count">
              {pluralize(topic.groups.reduce((n, g) => n + g.sets.length, 0), 'set')}
            </span>
          </div>
          {topic.groups.map((group) => (
            <div key={group.subtopic?.id ?? 'whole'}>
              <div className="subhead mc">{subtopicGroupLabel(group.subtopic)}</div>
              <ul className="cards">
                {group.sets.map((card) => (
                  <li key={card.id}>
                    <SetCard card={card} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ))}
      {me && me.display_name === null && (
        <NamePrompt email={me.email} onSaved={setMe} />
      )}
    </div>
  );
}
