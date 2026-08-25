# SPDX-License-Identifier: MIT
"""Publisher receipts resource — publisher-integrated observation submission."""

from __future__ import annotations

from logion._http import HttpClient
from logion._json import JsonObject


class PublisherReceiptResource:
    """Submit publisher-integrated observation receipts for resource versions."""

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
        harness: str | None = None,
        outcome: str | None = None,
        observed_at: str | None = None,
        coarse_counters: dict[str, int] | None = None,
        pseudonymous_public_key: str | None = None,
        pseudonymous_signature: str | None = None,
        distribution_digest: str | None = None,
        instrumentation_profile_digest: str | None = None,
        integration_version: str | None = None,
        publisher_identity: str | None = None,
    ) -> JsonObject:
        """Submit a publisher-integrated receipt for a resource version.

        Server-authoritative fields (identity_tier, pseudonymous_subject_id,
        publisher_verified, consent_policy_digest) are derived server-side
        and never accepted from the request body.

        Parameters
        ----------
        resource_id:
            UUID of the resource used.
        version_id:
            UUID of the specific resource version.
        observation_id:
            UUID identifying the observation event.
        task_class:
            Classification of the task (e.g. ``software-development``).
        acquisition_channel:
            How the resource was acquired (e.g. ``npx_skills``).
        """
        payload: JsonObject = {
            "observation_id": observation_id,
            "task_class": task_class,
            "acquisition_channel": acquisition_channel,
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
        if distribution_digest is not None:
            payload["distribution_digest"] = distribution_digest
        if instrumentation_profile_digest is not None:
            payload["instrumentation_profile_digest"] = instrumentation_profile_digest
        if integration_version is not None:
            payload["integration_version"] = integration_version
        if publisher_identity is not None:
            payload["publisher_identity"] = publisher_identity
        return self._http.request_object(
            "POST",
            f"/v1/resources/{resource_id}/versions/{version_id}/publisher-receipts",
            json=payload,
        )


# Operation-map discovery derives the resource class name from the plural
# namespace while the public SDK keeps the singular class name.
PublisherReceiptsResource = PublisherReceiptResource