'use client';

import { Fragment, useEffect, useState } from 'react';
import { getMe, getPublicTopics, getTopics, isSessionExpired, isSignedOut, signOut } from '../lib/api';
import { pluralize, subtopicGroupLabel } from '../lib/names';
import { clearReauthFlag, handleSessionExpired } from '../lib/session';
import type { Me, PublicSetCard as PublicCard, SetCard as Card, Topics } from '../lib/types';
import Masthead, { type Session } from './components/Masthead';
import NamePrompt from './components/NamePrompt';
import PublicSetCard from './components/PublicSetCard';
import SetCard from './components/SetCard';
import SignInAgain from './components/SignInAgain';

/** A signed-in reader's cards carry their own attempts; a signed-out visitor's do not. */
type AnyCard = Card | PublicCard;
type Group = Topics<AnyCard>[number]['groups'][number];

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

/** Today's card for a signed-in reader; for a signed-out visitor, the card with Sign up and View. */
function CardFor({ card, kicker }: { card: AnyCard; kicker?: string }) {
  return 'open_attempt' in card ? <SetCard card={card} kicker={kicker} /> : <PublicSetCard card={card} kicker={kicker} />;
}

/**
 * The quiz home. Anyone may open it: `/me` decides what it shows. Signed in (200), today's
 * catalogue with the reader's own attempts. No Access session (`isSignedOut`), the public
 * catalogue with Sign up and View on each card. A real 401 is an expired session, as on every
 * protected page: the "sign-in expired" banner and one reload. So is a signed-out answer while
 * the public catalogue is itself behind sign-in (before Access opens it), which keeps this page
 * exactly as it was until then.
 */
export default function Home() {
  const [me, setMe] = useState<Me | null>(null);
  const [session, setSession] = useState<Session>('pending');
  const [topics, setTopics] = useState<Topics<AnyCard> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  // Default view = topics only: everything starts collapsed.
  const [openTopics, setOpenTopics] = useState<Set<number>>(new Set());
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fail = (err: unknown) => {
      if (isSessionExpired(err)) {
        setExpired(true);
        handleSessionExpired();
      } else setError(err instanceof Error ? err.message : 'Something went wrong');
    };
    // Both at once, as before, so a signed-in reader waits no longer than they used to.
    const meCall = getMe();
    // The masthead's links follow /me alone, without waiting for the catalogue. Anything but
    // "signed out" keeps today's History and Sign out.
    meCall.then(
      () => setSession('signed-in'),
      (err) => setSession(isSignedOut(err) ? 'signed-out' : 'signed-in'),
    );
    Promise.allSettled([meCall, getTopics()]).then(([m, t]) => {
      if (m.status === 'fulfilled' && t.status === 'fulfilled') {
        clearReauthFlag();
        setMe(m.value);
        setTopics(t.value.topics);
      } else if (m.status === 'rejected' && isSignedOut(m.reason)) {
        getPublicTopics().then((p) => setTopics(p.topics), (err) => {
          setSession('signed-in');
          fail(err);
        });
      } else fail(m.status === 'rejected' ? m.reason : (t as PromiseRejectedResult).reason);
    });
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
      <Masthead me={me} onSignOut={signOut} tail={[]} session={expired ? 'signed-in' : session} />
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
                {pluralize(subtopicCount, 'subtopic').replace(' ', '\u00a0')}{'\u00a0· '}{pluralize(quizCount, 'quiz').replace(' ', '\u00a0')}
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
                              <CardFor card={c} />
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
                              <CardFor card={c} kicker={g.subtopic!.name} />
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
