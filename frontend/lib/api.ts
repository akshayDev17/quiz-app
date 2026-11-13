import type {
  AdminEvaluators,
  AdminSetDetail,
  AdminSets,
  AttemptSession,
  History,
  ImportResult,
  Me,
  PublicSet,
  PublicTopicsResponse,
  EvaluatorFields,
  RerunResult,
  Results,
  SetIntro,
  SetStatusResult,
  SetVisibilityResult,
  SubmitResult,
  TopicsResponse,
  Visibility,
} from './types';

// Empty in production, where the Worker shares the site's origin. Point it at
// the local dev server's origin while developing.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? '';

/** Pause before the one retry of a request the Worker answered 401. */
export const AUTH_RETRY_DELAY_MS = 300;

/**
 * An HTTP failure carrying its status, so the UI can tell "your session ended"
 * (offer sign-in) from "the server is broken" (offer a retry).
 *
 * `signedOut` marks the one 401 that came from Cloudflare Access rather than the
 * Worker: the request carried no Access session at all, so Access redirected it
 * to its sign-in page. A real 401 from the Worker means a session it failed to read.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly signedOut: boolean;

  constructor(status: number, message: string, signedOut = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.signedOut = signedOut;
  }
}

/** True when the failure means the Access session is gone and the reader must sign in again. */
export function isSessionExpired(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

/**
 * True when Access redirected the request to its sign-in: the reader has no session at all.
 * On a page anyone may open (the quiz home, View) that means a signed-out visitor, not an
 * expired session; protected pages keep treating it as `isSessionExpired`.
 */
export function isSignedOut(error: unknown): boolean {
  return error instanceof ApiError && error.signedOut;
}

/**
 * One fetch for every route.
 *
 * `redirect: 'manual'` matters: when the Cloudflare Access session has expired,
 * Access answers an API call with a 302 to `*.cloudflareaccess.com`. A followed
 * redirect would be a cross-origin fetch that fails with an opaque network
 * error. Manual mode surfaces it as an `opaqueredirect` response instead, which
 * we turn into a 401 marked `signedOut` (see `isSignedOut`).
 *
 * A real 401 is retried once after a short pause. The Worker sometimes fails to
 * read a valid session's identity, and sibling requests with the same cookies
 * still succeed, so one transient miss must not read as "your sign-in expired".
 * Retrying is safe for every method: a 401 means the Worker rejected the request
 * before any route ran. An expired session shows up as the redirect instead,
 * which is not retried.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const call = () =>
    fetch(`${API_BASE}/quiz/api${path}`, {
      credentials: 'include',
      redirect: 'manual',
      ...init,
    });
  let res = await call();
  if (res.status === 401) {
    await new Promise((resolve) => setTimeout(resolve, AUTH_RETRY_DELAY_MS));
    res = await call();
  }
  if (res.type === 'opaqueredirect') throw new ApiError(401, 'not signed in', true);
  if (res.status === 401) throw new ApiError(401, 'session expired');
  if (res.status === 204) return undefined as T;
  const data = (await res.json().catch(() => ({}))) as T & { error?: string };
  if (!res.ok) {
    throw new ApiError(res.status, data.error ?? `Request failed: HTTP ${res.status}`);
  }
  return data;
}

function send<T>(
  method: string,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
  keepalive?: boolean,
): Promise<T> {
  return request<T>(path, {
    method,
    signal,
    ...(keepalive ? { keepalive: true } : {}),
    ...(body === undefined
      ? {}
      : { headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }),
  });
}

const id = encodeURIComponent;

export const getMe = () => request<Me>('/me');
export const renameMe = (displayName: string) => send<Me>('PATCH', '/me', { display_name: displayName });

export const getTopics = () => request<TopicsResponse>('/topics');
/** The catalogue for a signed-out visitor: published, public sets, nothing of any person. */
export const getPublicTopics = () => request<PublicTopicsResponse>('/public/topics');
/** One published, public set with its answer key, for View. */
export const getPublicSet = (setId: number) => request<PublicSet>(`/public/sets/${id(setId)}`);
/**
 * A protected page whose only job is to be reached: Access signs the reader in on the way
 * (it is not among the paths anyone may open), then it hands them back to the quiz home.
 */
export const SIGN_IN_HREF = '/quiz/signin';
export const getSet = (setId: number) => request<SetIntro>(`/sets/${id(setId)}`);

/** Starts a new attempt (201) or resumes the open one (200); both return the session. */
export const startAttempt = (setId: number) =>
  send<AttemptSession>('POST', `/sets/${id(setId)}/attempts`);
export const getAttempt = (attemptId: string) => request<AttemptSession>(`/attempts/${id(attemptId)}`);
/**
 * One question's answer as the API takes it: the ticked options of a choice question, or the
 * text typed for a subjective one (blank text clears it).
 */
export type Answer = { option_ids: number[] } | { text: string };

/**
 * `signal` lets the autosave queue abort a save that has stalled. `keepalive` lets the request
 * outlive the page, for the saves sent as it is hidden or unloaded.
 */
export const saveAnswer = (
  attemptId: string,
  questionId: number,
  answer: Answer,
  signal?: AbortSignal,
  keepalive?: boolean,
) =>
  send<void>(
    'PUT',
    `/attempts/${id(attemptId)}/answers/${id(questionId)}`,
    answer,
    signal,
    keepalive,
  );
export const submitAttempt = (attemptId: string) =>
  send<SubmitResult>('POST', `/attempts/${id(attemptId)}/submit`);
/** An answer the browser still holds, sent along with a pause. */
export type PendingAnswer = { question_id: number } & Answer;

/**
 * Freeze the clock (timed attempts only), storing `answers` in the same request.
 *
 * The server writes them and `paused_at` in one transaction: once paused the attempt
 * accepts no more writes, so anything left unsaved at that moment would be lost.
 */
export const pauseAttempt = (attemptId: string, answers: PendingAnswer[] = []) =>
  send<AttemptSession>(
    'POST',
    `/attempts/${id(attemptId)}/pause`,
    answers.length ? { answers } : undefined,
  );
/** Extend the deadline by the paused duration and restart the clock. */
export const resumeAttempt = (attemptId: string) =>
  send<AttemptSession>('POST', `/attempts/${id(attemptId)}/resume`);
export const getResults = (attemptId: string) => request<Results>(`/attempts/${id(attemptId)}/results`);
export const getHistory = () => request<History>('/attempts');

export const adminListSets = () => request<AdminSets>('/admin/sets');
/** `setJson` is the import document (spec section 4 shape); the server validates it. */
export const adminImport = (setJson: unknown) => send<ImportResult>('POST', '/admin/sets', setJson);
export const adminSetStatus = (setId: number, action: 'publish' | 'archive') =>
  send<SetStatusResult>('POST', `/admin/sets/${id(setId)}/${action}`);
export const adminSetVisibility = (setId: number, visibility: Visibility) =>
  send<SetVisibilityResult>('POST', `/admin/sets/${id(setId)}/visibility`, { visibility });
export const adminClone = (setId: number) =>
  send<SetStatusResult>('POST', `/admin/sets/${id(setId)}/clone`);
export const adminDelete = (setId: number) => send<void>('DELETE', `/admin/sets/${id(setId)}`);
/** The set with its questions and answer key, for the in-place editor. */
export const getAdminSet = (setId: number) => request<AdminSetDetail>(`/admin/sets/${id(setId)}`);
/** Replace the set's props and questions in place. */
export const updateAdminSet = (setId: number, body: unknown) =>
  send<ImportResult>('PUT', `/admin/sets/${id(setId)}`, body);

/** The AI evaluators of written answers (admin only): each call returns the whole page's state. */
export const adminEvaluators = () => request<AdminEvaluators>('/admin/evaluators');
export const adminAddEvaluator = (body: { provider: string; model: string } & EvaluatorFields) =>
  send<AdminEvaluators>('POST', '/admin/evaluators', body);
export const adminUpdateEvaluator = (modelId: number, body: EvaluatorFields) =>
  send<AdminEvaluators>('PUT', `/admin/evaluators/${id(modelId)}`, body);
export const adminRemoveEvaluator = (modelId: number) =>
  send<AdminEvaluators>('DELETE', `/admin/evaluators/${id(modelId)}`);
export const adminOrderEvaluators = (ids: number[]) =>
  send<AdminEvaluators>('POST', '/admin/evaluators/order', { ids });
/** Mark written answers still awaiting evaluation, a few attempts per call, quotas aside. */
export const adminRerunEvaluations = () => send<RerunResult>('POST', '/admin/evaluations/rerun');

/**
 * End the session.
 *
 * Cloudflare Access's logout endpoint has no return target (`?returnTo=` is
 * rejected, `?redirect_url=` ignored), so a top-level navigation to it strands
 * the reader on Cloudflare's own sign-in page. Instead we ask it to clear the
 * cookie in the background (a same-origin fetch still gets its `Set-Cookie`
 * processed), then send the reader to the site root.
 *
 * If the background call did not take, fall back to the navigation, which
 * always works.
 */
export async function signOut(): Promise<void> {
  const logoutUrl = `${API_BASE}/cdn-cgi/access/logout`;
  try {
    await fetch(logoutUrl, { credentials: 'include', redirect: 'manual' });
  } catch {
    // Leaving is the reader's intent; a failed call must not trap them here.
  }

  const stillSignedIn = await getMe().then(
    () => true,
    () => false,
  );
  if (stillSignedIn) {
    window.location.href = logoutUrl;
    return;
  }
  window.location.href = '/';
}
