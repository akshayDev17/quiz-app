'use client';

import { useEffect } from 'react';
import { signOut } from '../../lib/api';
import Masthead, { type Crumb } from '../components/Masthead';

/** This page in the site path, after "Quiz Room". */
const TAIL: Crumb[] = [{ label: 'Sign in' }];

/**
 * Where the signed-out masthead's Sign in goes. A protected page whose only job is to be
 * reached: Access signs the reader in on the way here (it is not among the paths anyone may
 * open), then this hands them back to the quiz home, now signed in.
 */
export default function SignIn() {
  useEffect(() => {
    window.location.replace('/quiz');
  }, []);
  return (
    <div className="frame">
      <Masthead me={null} onSignOut={signOut} tail={TAIL} session="pending" />
      <p className="mc">Signing you in…</p>
    </div>
  );
}
