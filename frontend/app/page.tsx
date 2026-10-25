'use client';

import { Fragment, useEffect, useState } from 'react';
import { getMe, getTopics, isSessionExpired, signOut } from '../lib/api';
import { pluralize, subtopicGroupLabel } from '../lib/names';
import { clearReauthFlag, handleSessionExpired } from '../lib/session';
import type { Me, TopicsResponse } from '../lib/types';
import Masthead from './components/Masthead';
import NamePrompt from './components/NamePrompt';
import SetCard from './components/SetCard';
import SignInAgain from './components/SignInAgain';

type Group = TopicsResponse['topics'][number]['groups'][number];

/** Free = a subtopic with ≥2 sets (own collapsible row), or the whole-course group.
 *  Single = a subtopic with exactly one set, merged into the "Other modules" bucket. */
function splitGroups(groups: Group[]) {
  const free: Group[] = [];
  const singles: Group[] = [];
  for (const g of groups) {
    if (g.subtopic && g.sets.length === 1) singles.push(g);
    else free.push(g);
  }
  return { free, singles };
}

export default function Home() {
  const [me, setMe] = useState<Me | null>(null);
  const [topics, setTopics] = useState<TopicsResponse['topics'] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  // Default view = topics only: everything starts collapsed.
  const [openTopics, setOpenTopics] = useState<Set<number>>(new Set());
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    Promise.all([getMe(), getTopics()]).then(
      ([m, t]) => {
        clearReauthFlag();
        setMe(m);
        setTopics(t.topics);
      },
      (err) => {
        if (isSessionExpired(err)) {
          setExpired(true);
          handleSessionExpired();
        } else setError(err instanceof Error ? err.message : 'Something went wrong');
      },
    );
  }, []);

  const toggleTopic = (id: number) =>
    setOpenTopics((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleGroup = (key: string) =>
    setOpenGroups((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  return (
    <div className="frame">
      <Masthead me={me} onSignOut={signOut} />
      {expired && <SignInAgain />}
      {error && <div className="banner">{error}</div>}
      {!error && !expired && !topics && <p className="mc">Loading…</p>}
      {topics && topics.length === 0 && <p className="mc">No quizzes yet</p>}
      {topics?.map((topic, i) => {
        const subtopicCount = topic.groups.filter((g) => g.subtopic).length;
        const quizCount = topic.groups.reduce((n, g) => n + g.sets.length, 0);
        const topicOpen = openTopics.has(topic.id);
        const { free, singles } = splitGroups(topic.groups);
        return (
          <section key={topic.id}>
            <button className="shead" aria-expanded={topicOpen} onClick={() => toggleTopic(topic.id)}>
              <span className="num">{String(i + 1).padStart(2, '0')}</span>
              <span className="shead-name">{topic.name}</span>
              <span className="counts">
                {pluralize(subtopicCount, 'subtopic')} · {pluralize(quizCount, 'quiz')}
              </span>
              <span className="fill" />
              <span className="chev">{topicOpen ? '−' : '+'}</span>
            </button>

            {topicOpen && (
              <div className="groups">
                {free.map((g) => {
                  const key = `free:${topic.id}:${g.subtopic?.id ?? 'whole'}`;
                  const open = openGroups.has(key);
                  return (
                    <Fragment key={key}>
                      <button className="subhead" aria-expanded={open} onClick={() => toggleGroup(key)}>
                        <span className="label">{subtopicGroupLabel(g.subtopic)}</span>
                        <span className="cnt">{pluralize(g.sets.length, 'quiz')}</span>
                        <span className="fill" />
                        <span className="chev">{open ? '−' : '+'}</span>
                      </button>
                      {open && (
                        <ul className="cards">
                          {g.sets.map((c) => (
                            <li key={c.id}>
                              <SetCard card={c} />
                            </li>
                          ))}
                        </ul>
                      )}
                    </Fragment>
                  );
                })}

                {singles.length > 0 && (
                  <Fragment>
                    <button
                      className="subhead merged"
                      aria-expanded={openGroups.has(`merged:${topic.id}`)}
                      onClick={() => toggleGroup(`merged:${topic.id}`)}
                    >
                      <span className="label">Other modules</span>
                      <span className="cnt">{pluralize(singles.length, 'quiz')}</span>
                      <span className="fill" />
                      <span className="chev">{openGroups.has(`merged:${topic.id}`) ? '−' : '+'}</span>
                    </button>
                    {openGroups.has(`merged:${topic.id}`) && (
                      <ul className="cards">
                        {singles.map((g) =>
                          g.sets.map((c) => (
                            <li key={c.id}>
                              <SetCard card={c} kicker={g.subtopic!.name} />
                            </li>
                          )),
                        )}
                      </ul>
                    )}
                  </Fragment>
                )}
              </div>
            )}
          </section>
        );
      })}
      {me && me.display_name === null && <NamePrompt email={me.email} onSaved={setMe} />}
    </div>
  );
}
