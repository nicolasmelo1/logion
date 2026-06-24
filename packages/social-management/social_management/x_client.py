"""X / Twitter client. Backends: 'api' (official) and 'off' (manual render).

No browser/scraping backend. No scheduler. One post per explicit call.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote

import httpx

from social_management.config import SocialConfig
from social_management.cost import CostEstimator, SpendLedger
from social_management.errors import (
    ConfirmationRequiredError,
    MissingCredentialsError,
)
from social_management.models import PostResult

X_API = "https://api.x.com/2/tweets"


class XClient:
    """Official X API client with a hard cost + confirmation gate."""

    def __init__(
        self,
        config: SocialConfig,
        *,
        ledger: SpendLedger | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._ledger = ledger or SpendLedger()
        self._http = client or httpx.Client(timeout=15.0)

    def _auth_header(self) -> dict[str, str]:
        """OAuth1.0a signature header, or 'Bearer <token>' if bearer set.

        OAuth1 signing: HMAC-SHA1 over the request per RFC 5849 using
        the four X_* secrets. Does not include the JSON body in the
        signature (X API v2 convention).
        """
        bearer = self._config.x_bearer_token
        if bearer:
            return {"Authorization": f"Bearer {bearer}"}

        # OAuth1.0a HMAC-SHA1 signing.
        method = "POST"
        url = X_API
        oauth_params = {
            "oauth_consumer_key": self._config.x_api_key,
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self._config.x_access_token,
            "oauth_version": "1.0",
        }
        # Sort + percent-encode all oauth_params.
        encoded_params = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}"
            for k, v in sorted(oauth_params.items())
        )
        base_string = (
            f"{method}&{quote(url, safe='')}&{quote(encoded_params, safe='')}"
        )
        signing_key = (
            f"{quote(self._config.x_api_secret, safe='')}&"
            f"{quote(self._config.x_access_secret, safe='')}"
        )
        signature = base64.b64encode(
            hmac.new(
                signing_key.encode(),
                base_string.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()
        oauth_params["oauth_signature"] = signature
        header = "OAuth " + ", ".join(
            f'{k}="{quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        )
        return {"Authorization": header}

    def post(
        self, text: str, *, confirm: bool = False, dry_run: bool = False
    ) -> PostResult:
        """Post `text` to X, gated by budget + confirmation.

        Flow:
          1. estimate = CostEstimator.estimate(text)
          2. If backend != api or creds missing -> manual render
             (PostResult(sent=False, rendered=text, note='manual')); NO
             network, NO cost. (Raises nothing — graceful degrade.)
          3. ledger.check_and_reserve(estimate, budget) ->
             BudgetExceededError
          4. if dry_run: return PostResult(dry_run=True, sent=False,
             cost_cents=estimate.cents, rendered=text) WITHOUT
             network/record.
          5. if not confirm: raise ConfirmationRequiredError
             (mentions estimate.dollars and whether it has a link).
          6. POST /2/tweets {"text": text}; raise_for_status.
          7. ledger.record(estimate); return PostResult(sent=True,
             cost_cents=estimate.cents, remote_id=<tweet id>).
        """
        estimate = CostEstimator.estimate(text)
        # Raise if backend=api was explicitly requested but no creds.
        if self._config.x_backend == "api" and not (
            self._config.has_x_oauth1() or self._config.x_bearer_token
        ):
            raise MissingCredentialsError(
                "X_BACKEND=api but no X credentials configured"
            )
        if not self._config.x_is_live():
            return PostResult(
                platform="x",
                target="x",
                dry_run=dry_run,
                sent=False,
                cost_cents=0,
                rendered=text,
                note="X backend off/unconfigured — copy this to post manually",
            )
        self._ledger.check_and_reserve(
            estimate, self._config.x_monthly_budget_cents
        )
        if dry_run:
            return PostResult(
                platform="x",
                target="x",
                dry_run=True,
                sent=False,
                cost_cents=estimate.cents,
                rendered=text,
                note=estimate.reason,
            )
        if not confirm:
            raise ConfirmationRequiredError(
                f"X post costs ~{estimate.dollars} "
                f"({'LINK POST' if estimate.has_link else 'no link'}); "
                f"re-run with --confirm"
            )
        resp = self._http.post(
            X_API, json={"text": text}, headers=self._auth_header()
        )
        resp.raise_for_status()
        tweet_id = resp.json()["data"]["id"]
        self._ledger.record(estimate)
        return PostResult(
            platform="x",
            target="x",
            dry_run=False,
            sent=True,
            cost_cents=estimate.cents,
            remote_id=tweet_id,
            rendered=text,
        )
