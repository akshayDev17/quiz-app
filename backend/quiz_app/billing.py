"""Real budget figures from a cloud provider's own billing API (ADR 0011).

An evaluator key can carry an optional, separate, read-only billing credential. With one,
the admin page shows what the provider itself reports, never a typed-in balance:

* Amazon Bedrock: an AWS Budgets budget (``DescribeBudget``), read with an IAM access key
  that may only ``budgets:ViewBudget``. The request is signed with Signature Version 4.
* Azure AI Foundry: an Azure consumption budget, read with a Microsoft Entra app
  registration (client id and secret) holding the Cost Management Reader role on the
  budget's scope.

Anthropic has no API for an account's prepaid balance, so an Anthropic key has no reader:
its page shows the month's spend from each call's tokens, and a provider credit refusal
(``evaluators.OUT_OF_CREDIT``) is what tells it the balance ran out.

A reading is taken only when the admin presses "check now", never on a page load or a
submit. Errors carry a short reason safe to show an admin: a status and the provider's
error code, never a secret and never a raw response body.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlencode

from .transport import HttpSend

BILLING_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class BalanceReading:
    limit_micros: int
    spent_micros: int
    currency: str
    source: str   # what the figure is, for the page: e.g. 'AWS Budgets "quiz-ai" (monthly)'

    @property
    def remaining_micros(self) -> int:
        """Can be negative: a budget is a limit the provider reports on, not one it enforces."""
        return self.limit_micros - self.spent_micros


class BillingError(Exception):
    """Why a reading failed, in words safe to show an admin."""


def _micros(amount: object) -> int:
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise BillingError("the provider's reply had no readable amount") from None
    if not value.is_finite():
        raise BillingError("the provider's reply had no readable amount")
    return int((value * 1_000_000).to_integral_value())


def _json(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError:
        raise BillingError("the provider's reply was not JSON") from None
    if not isinstance(data, dict):
        raise BillingError("the provider's reply was not a JSON object")
    return data


# -- AWS Signature Version 4 ----------------------------------------------------

def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def sigv4_signing_key(secret_key: str, date: str, region: str, service: str) -> bytes:
    """``kSigning`` for a ``YYYYMMDD`` date (AWS: "Create a signed AWS API request", step 4)."""
    k_date = _hmac(("AWS4" + secret_key).encode("utf-8"), date)
    return _hmac(_hmac(_hmac(k_date, region), service), "aws4_request")


def sigv4_authorization(
    method: str, path: str, query: str, headers: dict[str, str], payload: bytes,
    access_key: str, secret_key: str, amz_date: str, region: str, service: str,
) -> str:
    """The ``Authorization`` header for a request whose ``headers`` (``host`` and
    ``x-amz-date`` among them) are all signed. ``query`` is already canonical (sorted,
    encoded)."""
    names = sorted(name.lower() for name in headers)
    lowered = {name.lower(): " ".join(str(value).strip().split()) for name, value in headers.items()}
    canonical_headers = "".join(f"{name}:{lowered[name]}\n" for name in names)
    signed_headers = ";".join(names)
    canonical_request = "\n".join([
        method, quote(path, safe="/-_.~"), query, canonical_headers, signed_headers,
        hashlib.sha256(payload).hexdigest(),
    ])
    date = amz_date[:8]
    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signature = hmac.new(sigv4_signing_key(secret_key, date, region, service), to_sign.encode("utf-8"),
                         hashlib.sha256).hexdigest()
    return (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}")


# -- AWS Budgets ------------------------------------------------------------------

AWS_BUDGETS_HOST = "budgets.amazonaws.com"
AWS_BUDGETS_REGION = "us-east-1"   # the Budgets API has one endpoint, signed for us-east-1


async def read_aws_budget(values: dict[str, str], send: HttpSend, now_ms: int) -> BalanceReading:
    """``DescribeBudget`` for ``budget_name`` in ``account_id``, signed with the read-only
    ``aws_access_key_id`` / ``aws_secret_access_key``."""
    body = json.dumps({"AccountId": values["account_id"], "BudgetName": values["budget_name"]})
    amz_date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now_ms // 1000))
    headers = {
        "content-type": "application/x-amz-json-1.1",
        "host": AWS_BUDGETS_HOST,
        "x-amz-date": amz_date,
        "x-amz-target": "AWSBudgetServiceGateway.DescribeBudget",
    }
    authorization = sigv4_authorization(
        "POST", "/", "", headers, body.encode("utf-8"), values["aws_access_key_id"],
        values["aws_secret_access_key"], amz_date, AWS_BUDGETS_REGION, "budgets",
    )
    sent = {name: value for name, value in headers.items() if name != "host"}  # the runtime sets Host
    sent["authorization"] = authorization
    try:
        response = await send("POST", f"https://{AWS_BUDGETS_HOST}/", sent, body, BILLING_TIMEOUT_S)
    except Exception:
        raise BillingError("AWS Budgets did not answer") from None
    if response.status != 200:
        code = ""
        try:
            code = str(json.loads(response.text).get("__type", "")).rsplit("#", 1)[-1]
        except (ValueError, AttributeError):
            pass
        raise BillingError(f"AWS Budgets refused the request ({response.status}{' ' + code if code else ''})")
    budget = _json(response.text).get("Budget")
    try:
        limit = budget["BudgetLimit"]
        spent = budget["CalculatedSpend"]["ActualSpend"]
        grain = str(budget.get("TimeUnit", "")).lower()
    except (KeyError, TypeError):
        raise BillingError("AWS Budgets returned a budget with no limit or spend") from None
    currency = str(limit.get("Unit") or "USD")
    source = f'AWS Budgets "{values["budget_name"]}"' + (f" ({grain})" if grain else "")
    return BalanceReading(_micros(limit.get("Amount")), _micros(spent.get("Amount")), currency, source)


# -- Azure consumption budgets ----------------------------------------------------

AZURE_BUDGET_API_VERSION = "2023-05-01"


async def read_azure_budget(values: dict[str, str], send: HttpSend, now_ms: int) -> BalanceReading:
    """A client-credentials token from Microsoft Entra for ``tenant_id``, then the consumption
    budget ``budget_name`` at ``scope`` (``subscriptions/<id>`` or a resource group in it)."""
    form = urlencode({
        "grant_type": "client_credentials",
        "client_id": values["client_id"],
        "client_secret": values["client_secret"],
        "scope": "https://management.azure.com/.default",
    })
    token_url = f"https://login.microsoftonline.com/{quote(values['tenant_id'], safe='')}/oauth2/v2.0/token"
    try:
        token = await send("POST", token_url, {"content-type": "application/x-www-form-urlencoded"}, form,
                           BILLING_TIMEOUT_S)
    except Exception:
        raise BillingError("Microsoft Entra did not answer") from None
    if token.status != 200:
        code = ""
        try:
            code = str(json.loads(token.text).get("error", ""))
        except (ValueError, AttributeError):
            pass
        raise BillingError(f"Microsoft Entra refused the billing credential ({token.status}{' ' + code if code else ''})")
    access = _json(token.text).get("access_token")
    if not isinstance(access, str) or not access:
        raise BillingError("Microsoft Entra returned no access token")
    url = (f"https://management.azure.com/{values['scope']}/providers/Microsoft.Consumption/budgets/"
           f"{quote(values['budget_name'], safe='')}?api-version={AZURE_BUDGET_API_VERSION}")
    try:
        response = await send("GET", url, {"authorization": f"Bearer {access}"}, None, BILLING_TIMEOUT_S)
    except Exception:
        raise BillingError("Azure Cost Management did not answer") from None
    if response.status != 200:
        code = ""
        try:
            code = str((json.loads(response.text).get("error") or {}).get("code", ""))
        except (ValueError, AttributeError):
            pass
        raise BillingError(f"Azure refused the budget request ({response.status}{' ' + code if code else ''})")
    props = _json(response.text).get("properties")
    try:
        spend = props["currentSpend"]
        limit = props["amount"]
        grain = str(props.get("timeGrain", "")).lower()
    except (KeyError, TypeError):
        raise BillingError("Azure returned a budget with no amount or current spend") from None
    currency = str(spend.get("unit") or "USD")
    source = f'Azure budget "{values["budget_name"]}"' + (f" ({grain})" if grain else "")
    return BalanceReading(_micros(limit), _micros(spend.get("amount")), currency, source)
