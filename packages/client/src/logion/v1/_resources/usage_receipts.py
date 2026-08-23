# SPDX-License-Identifier: MIT
"""Usage receipts resource — narrow telemetry submission."""

from __future__ import annotations

from logion._http import HttpClient
from logion._json import JsonObject


class UsageReceiptResource:
    """Submit narrow usage receipts for resource observations."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def submit(
        self,
        resource_id: str,
        version_id: str,
        *,
        observation_id: str,
        task_class: str,
        acquisition_channel: str,
        consent_policy_digest: str,
        harness: str | None = None,
        outcome: str | None = None,
        observed_at: str | None = None,
        coarse_counters: dict[str, int] | None = None,
        pseudonymous_public_key: str | None = None,
        pseudonymous_signature: str | None = None,
    ) -> JsonObject:
        """Submit a narrow usage receipt for a resource observation.

        Only opaque metadata is sent — no raw prompts, source code,
        paths, or task data.

        Parameters
        ----------
        resource_id:
            UUID of the resource used.
        version_id:
            UUID of the specific resource version.
        task_class:
            Classification of the task (e.g. ``software-development``).
        harness:
            Harness name (e.g. ``codex``, ``claude-code``).
        outcome:
            Task outcome (``completed``, ``failed``, ``abandoned``).
        acquisition_channel:
            How the resource was acquired (e.g. ``logion-marketplace``).
        """
        payload: JsonObject = {
            "observation_id": observation_id,
            "task_class": task_class,
            "acquisition_channel": acquisition_channel,
            "consent_policy_digest": consent_policy_digest,
        }
        if harness is not None:
            payload["harness"] = harness
        if outcome is not None:
            payload["outcome"] = outcome
        if observed_at is not None:
            payload["observed_at"] = observed_at
        if coarse_counters is not None:
            payload["coarse_counters"] = coarse_counters
        if pseudonymous_public_key is not None:
            payload["pseudonymous_public_key"] = pseudonymous_public_key
        if pseudonymous_signature is not None:
            payload["pseudonymous_signature"] = pseudonymous_signature
        return self._http.request_object(
            "POST",
            f"/v1/resources/{resource_id}/versions/{version_id}/usage-receipts",
            json=payload,
        )


# Operation-map discovery derives the resource class name from the plural
# namespace while the public SDK keeps the singular class name.
UsageReceiptsResource = UsageReceiptResource
