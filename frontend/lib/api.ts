import type {
  AdminSets,
  AttemptSession,
  History,
  ImportResult,
  Me,
  Results,
  SetIntro,
  SetStatusResult,
  SubmitResult,
  TopicsResponse,
} from './types';

// Empty in production, where the Worker shares the site's origin. Point it at
// the local dev server's origin while developing.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? '';

/**
 * An HTTP failure carrying its status, so the UI can tell "your session ended"
 * (offer sign-in) from "the server is broken" (offer a retry).
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** True when the failure means the Access session is gone and the reader must sign in again. */
export function isSessionExpired(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

/**
 * One fetch for every route.
 *
 * `redirect: 'manual'` matters: when the Cloudflare Access session has expired,
 * Access answers an API call with a 302 to `*.cloudflareaccess.com`. A followed
 * redirect would be a cross-origin fetch that fails with an opaque network
 * error. Manual mode surfaces it as an `opaqueredirect` response instead, which
 * we turn into the same 401 the Worker itself returns for "no identity".
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/quiz/api${path}`, {
    credentials: 'include',
    redirect: 'manual',
    ...init,
  });
  if (res.type === 'opaqueredirect' || res.status === 401) {
    throw new ApiError(401, 'session expired');
  }
  if (res.status === 204) return undefined as T;
  const data = (await res.json().catch(() => ({}))) as T & { error?: string };
  if (!res.ok) {
    throw new ApiError(res.status, data.error ?? `Request failed: HTTP ${res.status}`);
  }
  return data;
}

function send<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method,
    signal,
    ...(body === undefined
      ? {}
      : { headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }),
  });
}

const id = encodeURIComponent;

export const getMe = () => request<Me>('/me');
export const renameMe = (displayName: string) => send<Me>('PATCH', '/me', { display_name: displayName });

export const getTopics = () => request<TopicsResponse>('/topics');
export const getSet = (setId: number) => request<SetIntro>(`/sets/${id(setId)}`);

/** Starts a new attempt (201) or resumes the open one (200); both return the session. */
export const startAttempt = (setId: number) =>
  send<AttemptSession>('POST', `/sets/${id(setId)}/attempts`);
export const getAttempt = (attemptId: string) => request<AttemptSession>(`/attempts/${id(attemptId)}`);
/** `signal` lets the autosave queue abort a save that has stalled. */
export const saveAnswer = (attemptId: string, questionId: number, optionIds: number[], signal?: AbortSignal) =>
  send<void>(
    'PUT',
    `/attempts/${id(attemptId)}/answers/${id(questionId)}`,
    { option_ids: optionIds },
    signal,
  );
export const submitAttempt = (attemptId: string) =>
  send<SubmitResult>('POST', `/attempts/${id(attemptId)}/submit`);
export const getResults = (attemptId: string) => request<Results>(`/attempts/${id(attemptId)}/results`);
export const getHistory = () => request<History>('/attempts');

export const adminListSets = () => request<AdminSets>('/admin/sets');
/** `setJson` is the import document (spec section 4 shape); the server validates it. */
export const adminImport = (setJson: unknown) => send<ImportResult>('POST', '/admin/sets', setJson);
export const adminSetStatus = (setId: number, action: 'publish' | 'archive') =>
  send<SetStatusResult>('POST', `/admin/sets/${id(setId)}/${action}`);
export const adminClone = (setId: number) =>
  send<SetStatusResult>('POST', `/admin/sets/${id(setId)}/clone`);

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
