"""Who is asking? — authentication as a port.

Every quiz route needs an authenticated identity. Rather than scatter that
knowledge through the router, it lives behind :class:`IdentityProvider`: the router asks the port "who is
this?", gets an :class:`Identity` or ``None``, and never learns how the answer
was produced.

That seam matters because the mechanism is genuinely undecided:

* :class:`CloudflareAccessIdentity` reads the identity Cloudflare Access
  already resolved. Access sits in front of the Worker, so there is no
  hand-rolled crypto here at all — but Access is a *hostname/path* gate, and
  its one-time-PIN screen is served by Cloudflare, not by us.
* :class:`DevIdentity` is the local stand-in, so the same router and the same
  repository run on a laptop with no Access, no domain and no email provider.

Swapping in a self-hosted OTP flow later means adding one more implementation
of this ABC. Nothing else in the backend changes — that is the point.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlsplit


def request_path(request) -> str:
    """The request path, or ``""`` when there is no usable URL. ``request.url`` is a JS string over the FFI boundary."""
    try:
        return urlsplit(str(request.url)).path
    except Exception:
        return ""


def normalize_email(email: str) -> str:
    """Identity is case-insensitive: strip whitespace, lowercase."""
    return email.strip().lower()


def parse_emails(raw: str | None) -> frozenset[str]:
    """A comma-separated list of emails (e.g. the ``ADMIN_EMAILS`` secret) as a normalized set.

    Missing, ``None`` or blank gives the empty set; empty entries are dropped.
    """
    return frozenset(e for e in (normalize_email(part) for part in (raw or "").split(",")) if e)


@dataclass(frozen=True)
class Identity:
    """An authenticated user."""

    email: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "email", normalize_email(self.email))


class IdentityProvider(ABC):
    """Resolve the caller of a request to an :class:`Identity`, or ``None``."""

    @abstractmethod
    async def identify(self, request) -> Identity | None:
        """Return the caller's identity, or ``None`` if they are anonymous.

        Implementations must **fail closed**: any error, missing binding or
        unexpected shape resolves to ``None``, never to a default identity.
        """


class AnonymousIdentity(IdentityProvider):
    """Always anonymous. The safe default, and the test double."""

    async def identify(self, request) -> Identity | None:
        return None


class DevIdentity(IdentityProvider):
    """Local-development identity: one fixed user.

    Used by ``local_server.py`` so the frontend can be exercised end to end
    without Cloudflare. It is *never* wired into the Worker.
    """

    def __init__(self, email: str):
        self._email = normalize_email(email)

    async def identify(self, request) -> Identity | None:
        return Identity(self._email) if self._email else None


class CloudflareAccessIdentity(IdentityProvider):
    """Read the identity Cloudflare Access already established.

    Citations, precisely attributed — the two facts live on two different pages:

    * That ``ctx`` exists as ``self.ctx`` in a Python ``WorkerEntrypoint``:
      the Context API page says ctx is exposed "As a class property of the
      ``WorkerEntrypoint`` class (``this.ctx``)".
      https://developers.cloudflare.com/workers/runtime-apis/context/

    * That ``ctx.access`` carries the identity:
      "When Cloudflare Access authenticates a request that directly invokes
      your Worker, the Worker can read the signed-in user's identity […]
      through ``ctx.access``", and "``ctx.access`` is ``undefined`` if Access
      did not authenticate the request."
      https://developers.cloudflare.com/workers/configuration/cloudflare-access/

      (Note: the Context API page does **not** document ``ctx.access``, even
      though Cloudflare's own Access changelog links to an anchor there. Cite
      the configuration page, not the Context page.)

    **Python support is undocumented.** Every ``ctx.access`` example in
    Cloudflare's docs is JavaScript, and the string never appears on a Python
    page. ``self.ctx`` demonstrably exists in Python (the docs' own Cache API
    example uses ``self.ctx.waitUntil``), so ``self.ctx.access`` may well work —
    but that is an inference, not a citation. It must be verified empirically on
    the deployed Worker, ideally via a health check.

    If it does not exist, ``identify`` returns ``None`` and every protected
    route answers 401. That is the correct failure direction, but it is also why
    :meth:`IdentityProvider.identify` failing closed is not by itself enough —
    something has to *tell you* it failed closed.

    **Intermittent misses, and why there is one retry.** In production, signed-in
    requests sometimes came back 401 while sibling requests carrying the same
    cookies got 200. The only 401 the Worker produces is "no identity", and
    ``getIdentity()`` is the step most likely to fail transiently. Cloudflare does
    not say what it does, but the full identity lives behind Access's
    ``get-identity`` endpoint, not in the token ("Due to cookie size limits and
    bandwidth considerations"), so it is likely a network lookup. That is an
    inference, not a citation.
    https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/application-token/
    So a lookup that throws or resolves without an email is retried once after a
    short pause. An absent ``ctx.access`` is not retried: it is fixed for the
    request ("``undefined`` if Access did not authenticate the request").

    Every miss logs one JSON line (see :func:`_log_line`) naming the branch that fired:
    ``access-missing``, ``identity-threw`` (with the error class and message) or
    ``no-email``, plus the request path. A retry that recovers logs too, which is
    the evidence that the retry is what helps. Tokens, cookies, headers and the
    email are never logged.

    There is deliberately **no fallback** to the ``Cf-Access-Jwt-Assertion`` or
    ``Cf-Access-Authenticated-User-Email`` request headers. Cloudflare does not
    document that Access strips a client-sent copy of either header. Its
    guidance is to validate the JWT's signature and ``aud`` "to ensure that the
    request came from Access and not a malicious third party", and doing that
    here would need the team domain, the audience tag and RS256 verification
    through WebCrypto. Trusting either header raw would let a client name any
    email.
    https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
    """

    ATTEMPTS = 2

    def __init__(self, ctx, retry_delay_s: float = 0.1, log=print):
        self._ctx = ctx
        self._retry_delay_s = retry_delay_s
        self._log = log

    async def identify(self, request) -> Identity | None:
        try:
            access = getattr(self._ctx, "access", None)
        except Exception as e:  # an unreadable binding is as good as an absent one
            access, error = None, e
        else:
            error = None
        if access is None:
            self._log(_log_line("access_identity_missing", request, [_outcome("access-missing", error)]))
            return None
        outcomes = []
        for attempt in range(self.ATTEMPTS):
            if attempt:
                await asyncio.sleep(self._retry_delay_s)
            try:
                email = getattr(await access.getIdentity(), "email", None)
                identity = Identity(email) if email else None
            except Exception as e:  # fail closed: any surprise from the binding is a miss, never an identity
                outcomes.append(_outcome("identity-threw", e))
                continue
            if identity is None:
                outcomes.append(_outcome("no-email"))
                continue
            if outcomes:
                self._log(_log_line("access_identity_recovered", request, outcomes))
            return identity
        self._log(_log_line("access_identity_missing", request, outcomes))
        return None


_ERROR_CHARS = 200


def _outcome(branch: str, error: BaseException | None = None) -> dict:
    """One failed lookup: the branch, plus the error's class and (truncated) message when one was raised."""
    if error is None:
        return {"branch": branch}
    try:
        message = str(error)[:_ERROR_CHARS]
    except Exception:
        message = "<unprintable>"
    return {"branch": branch, "error_class": type(error).__name__, "error": message}


def _log_line(event: str, request, outcomes: list[dict]) -> str:
    """The structured log line. Only the path, the branches and error text; never a header, cookie or email."""
    return json.dumps({
        "event": event,
        "path": request_path(request),
        "branch": outcomes[-1]["branch"],
        "attempts": outcomes,
    })
