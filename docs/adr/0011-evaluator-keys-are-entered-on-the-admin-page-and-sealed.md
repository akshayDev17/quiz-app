# 0011. Evaluator keys are entered on the admin page and sealed; money shown is real or the app's own tracking

**Status:** Accepted · 2026-11-14

## Context

ADR 0010 has written answers marked by an AI evaluator from an ordered list the admin
keeps. Its first draft read each provider's key from a Worker secret
(`ANTHROPIC_API_KEY`, …) and gave each provider · model entry a typed-in monthly
budget, shown as "($X.XX left)".

The owner rejected that: "what if i attach a different key tomorrow? if i wish to remove
existing keys, then what? what if i wanted a new model tomorrow? or a new api key for the
same model". With keys as Worker secrets, every change of key needs the command line, a
provider can have only one key, and two keys for one model cannot exist. A typed-in
budget is a number the app made up, not one any provider reported.

Constraints that stand:

- The owner is the only admin; keys, models and money are admin-only on every route.
- No organisation admin key and no provider admin API: the owner's Anthropic key is in
  a personal default workspace, which has neither.
- Anthropic has no API that returns an account's prepaid balance. AWS and Azure do
  report budgets, through their own billing APIs, with their own credentials.
- The Worker cannot write its own secrets without holding a Cloudflare API token, which
  would be a bigger secret than any AI key.
- A key must never reach GitHub, a log, a response or a prompt.

## Decision

### Keys are first-class, stored sealed in D1

An evaluator **key** is a row the admin adds, replaces or removes on the admin page:
provider, label, the values that provider needs, and optionally a separate read-only
**billing credential**. Secret values are stored only **sealed** with AES-256-GCM
(`keycipher`): `v1:` + base64(12-byte random IV, ciphertext and tag), with additional
data naming the provider and the part (`evaluator-credential:<provider>:<key|billing>`),
so a sealed value moved to another row or part fails to open. Non-secret values (a
region, an endpoint, an account id, a budget name) are stored plain, to be shown.

The master key is one Worker secret, `KEY_ENCRYPTION_KEY` (32 random bytes, base64),
set once by the owner with `wrangler secret put`. It is the only thing that needs the
command line. In the Worker the cipher is Web Crypto (`crypto.subtle`, `worker_crypto`);
`local_server.py` uses the `cryptography` package with the same format, and the two were
checked against each other in workerd. Without the master key nothing can be sealed or
opened: the page says key storage is not set up, and answers wait.

Write-only: no route ever returns a key value or a sealed value. The page shows the
label, the provider, the last four characters, the non-secret settings and the key's
status. Keys are opened only to build an adapter for one request, never cached across
requests. Changing the master key makes stored keys unreadable (shown as such) until
they are pasted again; that is the rotation story, with no re-encryption tooling.

### An entry is a key and a model

The admin's ordered list holds **entries**, each one key and one model (for Azure, the
deployment name), with per-token prices for the app's spend tracking and an optional
**monthly cap**. Two keys for the same model are two entries. Removing a key removes
its entries; the ledger keeps their history.

Marking walks the list in order (ADR 0010 step 4). An entry is passed over when its key
is marked unusable and not yet due a retry, when its key cannot be opened, or when its
cap has no room for the call's conservative estimate. A provider **credit refusal**
(HTTP 402 `billing_error`, or a 400 whose message is about the credit balance) or a
**refused key** (401, 403) is not billed: the key is marked (`out_of_credit` or
`key_refused`, with the time), and the same submit moves on to the next entry. A marked
key is retried automatically by the next marking call an hour later, and at once by
**Check now**; a call that gets an answer clears the mark. Any other failure (another
HTTP error such as a 400, 404, 429 or 5xx, a timeout or network failure, or a reply cut off
at `max_tokens`) also moves the same submit on to the next entry, without marking the key;
a timeout keeps its reservation as spend. Calls refused with an HTTP error (credit, key or
otherwise) are not billed and do not count toward the daily quotas. Only a reply the model
finished ends the walk; when every entry fails, the answers wait, with the last failure's
reason shown on the admin page.

### Money: the provider's figure where it has one, else the app's tracking

Each entry shows the best real figure its provider can give, never a typed-in balance:

- **Anthropic**: no API exposes the balance. The page shows this month's spend from each
  call's usage times the entry's prices, and "out of credit at provider" when Anthropic
  refuses a call for credit.
- **Bedrock**: with an optional read-only billing credential (an IAM key allowed only
  `budgets:ViewBudget`, the account id and a budget name), **Check now** reads AWS
  Budgets `DescribeBudget`, signed with Signature Version 4 (checked against the AWS
  documentation's examples and botocore), and shows its limit, spend and what is left.
- **Azure**: with an optional read-only billing credential (an app registration with the
  Cost Management Reader role, the scope and a budget name), **Check now** takes a
  client-credentials token from Microsoft Entra and reads the consumption budget.
- A provider whose ordinary key reports its own balance needs only a `read_balance`
  that reads the key's own fields; the interface leaves room for it.

Readings are taken only on **Check now**, never on a page load or a submit, and stored
with their time; a failed reading keeps the last good figures and shows why it failed,
in words that hold no secret or response body. The **cap** is the app's own stop, shown
as "$X left of cap"; the provider's own spend limit or budget alert stays the hard stop.

**Check now** probes the key with the smallest billable request (16 output tokens, a
fraction of a cent), recorded in the ledger as a `check` row that counts toward the
entry's spend but not toward the daily quotas.

### Open numbers stay configuration

The owner has not settled the money numbers. They are Worker `vars` with defaults in
code (`composition.settings_from`): `EVAL_USER_DAILY_LIMIT` (20),
`EVAL_GLOBAL_DAILY_LIMIT` (300) and `EVAL_DEFAULT_MONTHLY_CAP_USD` (5, the cap prefilled
for a new entry). How long submit waits for one call is the rubric's own sizing
(`rubric.TIMEOUT_BASE_S` + `TIMEOUT_PER_ITEM_S` per answer). Key expiry, per-deploy approval and an AI Gateway are not built.

## Consequences

- The owner adds, replaces and removes keys and models from the page, with no deploy.
- Keys move from Cloudflare's secret store into the app's database, sealed. A D1 export
  or backup holds only sealed values, useless without the master key; anyone who can run
  code as the Worker can open them, as with Worker secrets before.
- A hijacked admin session can now **replace** a key (sending calls, and their cost, to
  the attacker's key) or remove one, though it still cannot read one. Before, it could do
  neither. Cloudflare Access guards the admin session, and every key route is
  admin-only, checked in the service on every call.
- "Remaining" is honest: the provider's own budget figure where a billing API exists,
  else the app's tracked spend against an optional cap, labelled as such.
- An out-of-credit Anthropic key costs one refused, unbilled request per hour of
  marking traffic until it is topped up or removed.

## Alternatives rejected

- **Keep keys as Worker secrets**: the owner's objection stands; one key per provider,
  and every change needs the command line.
- **Have the Worker write Worker secrets through the Cloudflare API**: needs a Cloudflare
  API token in the Worker, a far more powerful secret than the keys it would protect.
- **Cloudflare Secrets Store**: account-level secrets still managed through the
  Cloudflare API or dashboard, so the same token problem from inside the Worker.
- **A typed-in remaining balance**: a number no provider reported, which drifts from the
  truth on the first call made elsewhere.
- **An Anthropic Admin API key for usage and cost**: needs an organisation, which the
  owner's personal workspace is not, and would be a key with far wider powers.
