from __future__ import annotations

from agent_proving_ground._json import opt_str
from agent_proving_ground.assertions.base import (
    Assertion,
    AssertionContext,
    AssertionOutcome,
)


class _ApiQueryAssertion(Assertion):
    """Shared evaluate loop for API-observed-effect assertions.

    Subclasses declare the query type, the result key that proves the
    effect, and pass/fail messages. Adapter capability gaps (query result
    carries ``unsupported``) surface as ``unsupported`` outcomes so the
    runner can apply the optional/required policy.
    """

    type = ""
    query_type = ""
    found_key = "found"
    evidence_keys: tuple[str, ...] = ()
    pass_message = ""  # nosec B105 - assertion copy, not a password.
    fail_message = ""
    # When True the assertion passes if the found_key value is falsy.
    invert = False

    async def evaluate(
        self, ctx: AssertionContext, params: dict
    ) -> AssertionOutcome:
        result = await ctx.api.query(
            ctx.world, {"type": self.query_type, **params}
        )
        if result.get("unsupported"):
            return AssertionOutcome(
                type=self.type,
                status="unsupported",
                message=opt_str(
                    result,
                    "reason",
                    f"adapter does not support {self.query_type}",
                ),
                evidence={},
            )
        observed = bool(result.get(self.found_key))
        passed = (not observed) if self.invert else observed
        evidence = {
            key: result.get(key)
            for key in self.evidence_keys
            if result.get(key) is not None
        }
        if result.get("evidence"):
            evidence["query_evidence"] = result["evidence"]
        if passed:
            return AssertionOutcome(
                type=self.type,
                status="passed",
                message=self.pass_message,
                evidence=evidence,
            )
        # A query that knows *why* it failed says so. The class-level
        # fail_message is a single sentence for every possible cause, and
        # when the cause is "the agent never wrote the artifact" it accuses
        # the product instead: a missing reconcile file was reported as
        # "reconciliation left unresolved, ambiguous, or drifted entries",
        # which sends the reader into the product to look for a defect that
        # is not there.
        reason = result.get("reason") or result.get("error")
        message = (
            f"{self.fail_message} ({reason})"
            if isinstance(reason, str) and reason
            else self.fail_message
        )
        return AssertionOutcome(
            type=self.type,
            status="failed",
            message=message,
            evidence={**params, **evidence},
        )


class GithubIdentityLinkedAssertion(_ApiQueryAssertion):
    type = "api.github_identity_linked"
    query_type = "github_identity_linked"
    found_key = "connected"
    evidence_keys = ("github_login", "scope_tier", "status")
    pass_message = "GitHub identity is linked"
    fail_message = "no linked GitHub identity observed"


class SetupTokenPendingAssertion(_ApiQueryAssertion):
    type = "api.setup_token_pending"
    query_type = "setup_token_pending"
    found_key = "pending"
    evidence_keys = ("token_prefix", "status")
    pass_message = "setup token is pending"
    fail_message = "setup token is not pending"


class CourseExistsAssertion(_ApiQueryAssertion):
    type = "api.course_exists"
    query_type = "course_exists"
    evidence_keys = ("course_id",)
    pass_message = "course exists"  # nosec B105 - assertion copy.
    fail_message = "no matching course found"


class PurchaseExistsAssertion(_ApiQueryAssertion):
    type = "api.purchase_exists"
    query_type = "purchase_exists"
    evidence_keys = ("purchase_id",)
    pass_message = "purchase exists"  # nosec B105 - assertion copy.
    fail_message = "no matching purchase found"


class ReviewExistsAssertion(_ApiQueryAssertion):
    type = "api.review_exists"
    query_type = "review_exists"
    evidence_keys = ("review_id",)
    pass_message = "review exists"  # nosec B105 - assertion copy.
    fail_message = "no matching review found"


class UsageReportExistsAssertion(_ApiQueryAssertion):
    type = "api.usage_report_exists"
    query_type = "usage_report_exists"
    evidence_keys = ("report_id",)
    pass_message = "usage report exists"  # nosec B105 - assertion copy.
    fail_message = "no matching usage report found"


class BountyExistsAssertion(_ApiQueryAssertion):
    type = "api.bounty_exists"
    query_type = "bounty_exists"
    evidence_keys = ("bounty_id",)
    pass_message = "bounty exists"  # nosec B105 - assertion copy.
    fail_message = "no matching bounty found"


class BountySubmissionExistsAssertion(_ApiQueryAssertion):
    type = "api.bounty_submission_exists"
    query_type = "bounty_submission_exists"
    evidence_keys = ("submission_id",)
    pass_message = "bounty submission exists"  # nosec B105 - assertion copy.
    fail_message = "no matching bounty submission found"


class BountyAcceptedAssertion(_ApiQueryAssertion):
    type = "api.bounty_accepted"
    query_type = "bounty_accepted"
    evidence_keys = ("submission_id", "bounty_id")
    pass_message = "bounty submission accepted"  # nosec B105 - assertion copy.
    fail_message = "no accepted bounty submission found"


class CreditBalanceChangedAssertion(_ApiQueryAssertion):
    type = "api.credit_balance_changed"
    query_type = "credit_balance_changed"
    found_key = "changed"
    pass_message = "credit balance changed"  # nosec B105 - assertion copy.
    fail_message = "credit balance did not change"


class NoDoubleCreditDebitAssertion(_ApiQueryAssertion):
    type = "api.no_double_credit_debit"
    query_type = "no_double_credit_debit"
    found_key = "double_debit_found"
    invert = True
    pass_message = "no double credit debit found"  # nosec B105 - assertion copy.
    fail_message = "double credit debit detected"


class CourseRemainsPurchasableAssertion(_ApiQueryAssertion):
    type = "api.course_remains_purchasable"
    query_type = "course_remains_purchasable"
    found_key = "purchasable"
    evidence_keys = ("course_id",)
    pass_message = "course remains purchasable"  # nosec B105 - assertion copy.
    fail_message = "no published purchasable course found"


class AdminStateObservedAssertion(_ApiQueryAssertion):
    type = "api.admin_state_observed"
    query_type = "admin_state_observed"
    pass_message = "admin/operator view observed consistent state"  # nosec B105
    fail_message = "admin state could not be observed"


class SourceLinkExistsAssertion(_ApiQueryAssertion):
    type = "api.source_link_exists"
    query_type = "source_link_exists"
    evidence_keys = ("course_id",)
    pass_message = "source link exists"
    fail_message = "no matching source link found"


class BountySubmissionPrOpenedAssertion(_ApiQueryAssertion):
    type = "api.bounty_submission_pr_opened"
    query_type = "bounty_submission_pr_opened"
    found_key = "opened"
    evidence_keys = ("submission_id", "pr_url")
    pass_message = "bounty submission PR is opened"
    fail_message = "bounty submission PR is not opened"


class BountySubmissionAcceptedAssertion(_ApiQueryAssertion):
    type = "api.bounty_submission_accepted"
    query_type = "bounty_submission_accepted"
    found_key = "accepted"
    pass_message = "bounty submission is accepted"
    fail_message = "bounty submission is not accepted"


class IndexedListingExistsAssertion(_ApiQueryAssertion):
    type = "api.indexed_listing_exists"
    query_type = "indexed_listing_exists"
    evidence_keys = ("listing_id", "tier")
    pass_message = "indexed listing exists"
    fail_message = "no matching indexed listing found"


class IndexedListingTierAssertion(_ApiQueryAssertion):
    type = "api.indexed_listing_tier"
    query_type = "indexed_listing_tier"
    found_key = "tier_matches"
    evidence_keys = ("listing_id", "tier")
    pass_message = "indexed listing tier matches"
    fail_message = "indexed listing tier does not match"


class PlatformBountyAcceptedAssertion(_ApiQueryAssertion):
    type = "api.platform_bounty_accepted"
    query_type = "platform_bounty_accepted"
    found_key = "accepted"
    evidence_keys = ("bounty_id", "submission_id")
    pass_message = "platform bounty is accepted"
    fail_message = "platform bounty is not accepted"


class BountySubmissionRejectedAssertion(_ApiQueryAssertion):
    type = "api.bounty_submission_rejected"
    query_type = "bounty_submission_rejected"
    found_key = "rejected"
    pass_message = "bounty submission is rejected"
    fail_message = "bounty submission is not rejected"


class ResourceProjectionExistsAssertion(_ApiQueryAssertion):
    type = "api.resource_projection_exists"
    query_type = "resource_projection_exists"
    evidence_keys = ("resource_id",)
    pass_message = "resource projection exists"
    fail_message = "no matching resource projection found"


class ResourceBackfillCompleteAssertion(_ApiQueryAssertion):
    type = "api.resource_backfill_complete"
    query_type = "resource_backfill_complete"
    pass_message = "resource backfill is complete"
    fail_message = "resource backfill is not complete"


class ResourceBackfillAppliedAssertion(_ApiQueryAssertion):
    type = "api.resource_backfill_applied"
    query_type = "resource_backfill_applied"
    pass_message = (
        "resource backfill reported two creates, two links, and a snapshot"
    )
    fail_message = (
        "resource backfill did not report 2 creates, 2 links, and a snapshot"
    )


class ResourceIdentityUniqueAssertion(_ApiQueryAssertion):
    type = "api.resource_identity_unique"
    query_type = "resource_identity_unique"
    pass_message = "resource identities are unique"
    fail_message = "duplicate resource identities found"


class ResourceBackfillIdempotentAssertion(_ApiQueryAssertion):
    type = "api.resource_backfill_idempotent"
    query_type = "resource_backfill_idempotent"
    pass_message = "resource backfill rerun preserved counters and identities"
    fail_message = "resource backfill rerun was not idempotent"


class ResourceSearchReturnsKindsAssertion(_ApiQueryAssertion):
    type = "api.resource_search_returns_kinds"
    query_type = "resource_search_returns_kinds"
    found_key = "kinds_match"
    evidence_keys = ("projection_kinds", "matched_canonicals")
    pass_message = "resource search returns expected fixture projections"
    fail_message = (
        "resource search does not return expected fixture projections"
    )


class LegacyCoursePurchaseExistsAssertion(_ApiQueryAssertion):
    type = "api.legacy_course_purchase_exists"
    query_type = "legacy_course_purchase_exists"
    evidence_keys = ("purchase_id",)
    pass_message = "legacy course purchase exists"
    fail_message = "no matching legacy course purchase found"


class HarnessScopeTargetsResolvedAssertion(_ApiQueryAssertion):
    type = "api.harness_scope_targets_resolved"
    query_type = "harness_scope_targets_resolved"
    found_key = "resolved"
    evidence_keys = ("harnesses", "scopes", "resolved")
    pass_message = "harness scope targets resolved for all requested harnesses"
    fail_message = "one or more harness scope targets were not resolved"


class ResourceAcquirePlanDryRunAssertion(_ApiQueryAssertion):
    type = "api.resource_acquire_plan_dry_run"
    query_type = "resource_acquire_plan_dry_run"
    found_key = "valid"
    evidence_keys = (
        "harness",
        "scope",
        "zero_write",
        "executable",
        "permissions_required",
    )
    pass_message = (
        "resource acquire dry-run plan is valid, "
        "zero-write, and non-executable"
    )
    fail_message = (
        "resource acquire dry-run plan is invalid, "
        "non-zero-write, or prematurely executable"
    )


class ResourceAcquisitionExistsAssertion(_ApiQueryAssertion):
    type = "api.resource_acquisition_exists"
    query_type = "resource_acquisition_exists"
    found_key = "acquired"
    evidence_keys = (
        "resource_id",
        "installation_id",
        "verification",
        "channel",
    )
    pass_message = "resource acquisition receipt exists with verification"
    fail_message = "no verified acquisition receipt observed"


class ResourceDistributionSelectedAssertion(_ApiQueryAssertion):
    type = "api.resource_distribution_selected"
    query_type = "resource_distribution_selected"
    found_key = "selected"
    evidence_keys = ("channel", "distribution_id")
    pass_message = "an allowed distribution channel was selected"
    fail_message = "no allowed distribution channel observed in receipt"


class NativeInstallReconciledAssertion(_ApiQueryAssertion):
    type = "api.native_install_reconciled"
    query_type = "native_install_reconciled"
    found_key = "reconciled"
    evidence_keys = (
        "matched_count",
        "unresolved_count",
        "ambiguous_count",
        "drifted_count",
        "channels",
    )
    pass_message = (
        "local inventory reconciled to on-disk installations with no "
        "unresolved, ambiguous, or drifted entries"
    )
    fail_message = (
        "reconciliation left unresolved, ambiguous, or drifted entries, "
        "or claimed installations that are not on disk"
    )


class InstallDriftReportedAssertion(_ApiQueryAssertion):
    type = "files.install_drift_reported"
    query_type = "install_drift_reported"
    found_key = "drift_reported"
    evidence_keys = ("installation_id", "drifted_count")
    pass_message = "a tampered installation was reported as drifted"
    fail_message = "a tampered installation was not reported as drifted"


class ScopeIsolationPreservedAssertion(_ApiQueryAssertion):
    type = "files.scope_isolation_preserved"
    query_type = "scope_isolation_preserved"
    found_key = "isolated"
    evidence_keys = ("added", "removed", "changed")
    pass_message = "no file changed outside the requested acquisition scope"
    fail_message = "the acquisition wrote outside its requested scope"


class InventoryReceiptMatchesAssertion(_ApiQueryAssertion):
    type = "files.inventory_receipt_matches"
    query_type = "inventory_receipt_matches"
    found_key = "matches"
    evidence_keys = ("installation_id", "matched_ids")
    pass_message = "reconcile report contains the acquisition receipt"
    fail_message = "reconcile report does not contain the acquisition receipt"


class InstalledArtifactDigestMatchesAssertion(_ApiQueryAssertion):
    type = "files.installed_artifact_digest_matches"
    query_type = "installed_artifact_digest_matches"
    found_key = "digest_matches"
    evidence_keys = ("content_digest", "computed_digest", "files")
    pass_message = "installed artifact digest matches the receipt"
    fail_message = "installed artifact digest does not match the receipt"


class NativeHarnessDiscoversInstallationAssertion(_ApiQueryAssertion):
    type = "files.native_harness_discovers_installation"
    query_type = "native_harness_discovers_installation"
    found_key = "discovered"
    evidence_keys = ("harness", "scope", "digests", "paths")
    pass_message = "a fresh native harness session discovers the installation"
    fail_message = "fresh native harness state does not match inventory"


class AcquisitionIdempotentAssertion(_ApiQueryAssertion):
    type = "api.acquisition_idempotent"
    query_type = "acquisition_idempotent"
    found_key = "idempotent"
    evidence_keys = ("first_installation_id", "second_installation_id")
    pass_message = "repeated acquisition resolves to the same installation"
    fail_message = (
        "repeated acquisition changed installation identity or digest"
    )


class HarnessScopeNestedRepoAssertion(_ApiQueryAssertion):
    type = "api.harness_scope_nested_repo"
    query_type = "harness_scope_nested_repo"
    found_key = "nested"
    evidence_keys = ("harnesses", "nested_repo")
    pass_message = "nested repo scope resolved correctly for all harnesses"
    fail_message = (
        "nested repo scope resolution failed for one or more harnesses"
    )


class HarnessInventoryDistinctScopesAssertion(_ApiQueryAssertion):
    type = "api.harness_inventory_distinct_scopes"
    query_type = "harness_inventory_distinct_scopes"
    found_key = "distinct"
    evidence_keys = ("harnesses",)
    pass_message = "harness inventory keeps nested scope skills distinct"
    fail_message = "harness inventory merged or lost nested scope skills"


class ObservationEnvelopeNoRawDataAssertion(_ApiQueryAssertion):
    type = "api.observation_envelope_no_raw_data"
    query_type = "observation_envelope_no_raw_data"
    found_key = "clean"
    evidence_keys = ()
    pass_message = "observation envelope contains no raw task data"
    fail_message = "observation envelope leaked raw task data"


class NativeUseObservedAssertion(_ApiQueryAssertion):
    type = "files.native_use_observed"
    query_type = "native_use_observed"
    found_key = "observed"
    evidence_keys = ("resource_id", "version_id", "channel", "scope_id")
    pass_message = "native use was observed for the installed resource"
    fail_message = "no native use observation found for the installed resource"


class FeedbackPendingAssertion(_ApiQueryAssertion):
    type = "files.feedback_pending"
    query_type = "feedback_pending"
    found_key = "has_pending"
    evidence_keys = ("pending_count", "resource_ids")
    pass_message = "pending usage records exist for the agent"
    fail_message = "no pending usage records found for the agent"


class ResourceFeedbackExistsAssertion(_ApiQueryAssertion):
    type = "api.resource_feedback_exists"
    query_type = "resource_feedback_exists"
    found_key = "found"
    evidence_keys = ("feedback_id", "resource_id", "version_id")
    pass_message = "resource feedback exists"
    fail_message = "no matching resource feedback found"


class FeedbackLinkedToAcquisitionAssertion(_ApiQueryAssertion):
    type = "api.feedback_linked_to_acquisition"
    query_type = "feedback_linked_to_acquisition"
    found_key = "linked"
    evidence_keys = ("feedback_id", "acquisition_channel", "installation_id")
    pass_message = "feedback is linked to an acquisition record"
    fail_message = "feedback is not linked to an acquisition record"


class CourseReviewProjectionExistsAssertion(_ApiQueryAssertion):
    type = "api.course_review_projection_exists"
    query_type = "course_review_projection_exists"
    found_key = "found"
    evidence_keys = (
        "feedback_id",
        "projection_disposition",
        "course_review_id",
    )
    pass_message = "course review projection exists for the feedback"
    fail_message = "no course review projection found for the feedback"


class RawObservationNotUploadedAssertion(_ApiQueryAssertion):
    type = "api.raw_observation_not_uploaded"
    query_type = "raw_observation_not_uploaded"
    found_key = "clean"
    evidence_keys = ("observation_count", "checked_fields")
    pass_message = "no raw observation data was uploaded"
    fail_message = "raw observation data was detected in uploaded records"


class FeedbackSubmissionIdempotentAssertion(_ApiQueryAssertion):
    type = "api.feedback_submission_idempotent"
    query_type = "feedback_submission_idempotent"
    found_key = "idempotent"
    evidence_keys = ("first_feedback_id", "second_feedback_id")
    pass_message = "feedback submission is idempotent"
    fail_message = "feedback submission created duplicate records"


class RemoteMcpReconciledAssertion(_ApiQueryAssertion):
    type = "files.remote_mcp_reconciled"
    query_type = "remote_mcp_reconciled"
    found_key = "reconciled"
    evidence_keys = ("resource_id", "installation_id", "channel")
    pass_message = "pre-existing remote MCP connector was reconciled"
    fail_message = "remote MCP connector was not reconciled"


class VendorInstallUnchangedAssertion(_ApiQueryAssertion):
    type = "files.vendor_install_unchanged"
    query_type = "vendor_install_unchanged"
    found_key = "unchanged"
    evidence_keys = ("before", "after")
    pass_message = "vendor installation remained unchanged"
    fail_message = "vendor installation was rewritten"


class NoMcpProxyInstalledAssertion(_ApiQueryAssertion):
    type = "files.no_mcp_proxy_installed"
    query_type = "no_mcp_proxy_installed"
    found_key = "absent"
    evidence_keys = ("paths",)
    pass_message = "no MCP proxy was installed"
    fail_message = "an MCP proxy was installed"


class RemoteMcpUseAttributedAssertion(_ApiQueryAssertion):
    type = "api.remote_mcp_use_attributed"
    query_type = "remote_mcp_use_attributed"
    found_key = "attributed"
    evidence_keys = ("resource_id", "version_id", "channel")
    pass_message = "remote MCP use was attributed to the vendor resource"
    fail_message = "remote MCP use was not attributed"


class OriginalPublisherPreservedAssertion(_ApiQueryAssertion):
    type = "api.original_publisher_preserved"
    query_type = "original_publisher_preserved"
    found_key = "preserved"
    evidence_keys = ("publisher",)
    pass_message = "original vendor publisher was preserved"
    fail_message = "original vendor publisher was replaced"


class RemoteMcpFeedbackLinkedAssertion(_ApiQueryAssertion):
    type = "api.remote_mcp_feedback_linked"
    query_type = "remote_mcp_feedback_linked"
    found_key = "linked"
    evidence_keys = ("feedback_id", "acquisition_channel")
    pass_message = "remote MCP feedback is linked to native acquisition"
    fail_message = "remote MCP feedback is not linked"


class RemoteMcpPrivatePayloadNotRecordedAssertion(_ApiQueryAssertion):
    type = "api.remote_mcp_private_payload_not_recorded"
    query_type = "remote_mcp_private_payload_not_recorded"
    found_key = "clean"
    evidence_keys = ("checked_fields",)
    pass_message = "remote MCP private payload was not recorded"
    fail_message = "remote MCP private payload leaked into evidence"


# Phase 15.12 — AI Catalog and ARD discovery assertions.
# These check that the AI Catalog document, ARD search responses,
# connectors snapshot, agent finder queries, and related provenance
# are valid and that discovery works without AKTP or ASM-specific schemas.


class AICatalogDocumentValidAssertion(_ApiQueryAssertion):
    type = "api.ai_catalog_document_valid"
    query_type = "ai_catalog_document_valid"
    found_key = "valid"
    evidence_keys = ("spec_version", "entry_count", "conformance_level")
    pass_message = "AI Catalog document is valid and conformant"
    fail_message = "AI Catalog document is missing or invalid"


class AICatalogConformanceLevelValidAssertion(_ApiQueryAssertion):
    type = "api.ai_catalog_conformance_level_valid"
    query_type = "ai_catalog_conformance_level_valid"
    found_key = "valid"
    evidence_keys = ("conformance_level",)
    pass_message = "AI Catalog conformance level is valid"
    fail_message = "AI Catalog conformance level is missing or invalid"


class ARDSearchResponseValidAssertion(_ApiQueryAssertion):
    type = "api.ard_search_response_valid"
    query_type = "ard_search_response_valid"
    found_key = "valid"
    evidence_keys = ("result_count", "has_scores", "registry_origin")
    pass_message = "ARD search response is valid"
    fail_message = "ARD search response is missing or invalid"


class ARDConnectorsSnapshotPinnedAssertion(_ApiQueryAssertion):
    type = "api.ard_connectors_snapshot_pinned"
    query_type = "ard_connectors_snapshot_pinned"
    found_key = "pinned"
    evidence_keys = ("commit_sha", "file_digest", "finder_count")
    pass_message = "ARD connectors snapshot is pinned to an immutable commit"
    fail_message = "ARD connectors snapshot is not pinned or stale"


class AgentFindersQueriedAssertion(_ApiQueryAssertion):
    type = "api.agent_finders_queried"
    query_type = "agent_finders_queried"
    found_key = "queried"
    evidence_keys = ("finder_count", "query_family")
    pass_message = "at least one enabled Agent Finder was queried"
    fail_message = "no Agent Finders were queried"


class AgentFinderResultProvenanceVisibleAssertion(_ApiQueryAssertion):
    type = "api.agent_finder_result_provenance_visible"
    query_type = "agent_finder_result_provenance_visible"
    found_key = "visible"
    evidence_keys = ("finder_id", "endpoint", "result_count")
    pass_message = "Agent Finder result provenance is visible"
    fail_message = "Agent Finder result provenance is missing"


class CatalogCrawlCompletedAssertion(_ApiQueryAssertion):
    type = "api.catalog_crawl_completed"
    query_type = "catalog_crawl_completed"
    found_key = "completed"
    evidence_keys = (
        "seen",
        "created",
        "matched",
        "new_versions",
        "quarantined",
    )
    pass_message = "catalog crawl completed with an auditable import report"
    fail_message = "catalog crawl did not complete or has no import report"


class ARDResourceIngestedAssertion(_ApiQueryAssertion):
    type = "api.ard_resource_ingested"
    query_type = "ard_resource_ingested"
    found_key = "ingested"
    evidence_keys = ("resource_id", "canonical_uri")
    pass_message = "a resource was ingested through ARD discovery"
    fail_message = "no resource was ingested through ARD discovery"


class ARDRecordRejectedAssertion(_ApiQueryAssertion):
    type = "api.ard_record_rejected"
    query_type = "ard_record_rejected"
    found_key = "rejected"
    evidence_keys = ("reason", "error_code")
    pass_message = "malformed ARD record was quarantined with a stable reason"
    fail_message = "malformed ARD record was not rejected or quarantined"


class SelfCrawlNoDuplicateAssertion(_ApiQueryAssertion):
    type = "api.self_crawl_no_duplicate"
    query_type = "self_crawl_no_duplicate"
    found_key = "no_duplicates"
    evidence_keys = ("crawl_count", "resource_count")
    pass_message = "self-crawl produced zero duplicate resources"
    fail_message = "self-crawl produced duplicate resources"


class ResourceSourceProvenanceVisibleAssertion(_ApiQueryAssertion):
    type = "api.resource_source_provenance_visible"
    query_type = "resource_source_provenance_visible"
    found_key = "visible"
    evidence_keys = ("source_type", "source_uri", "upstream_repo")
    pass_message = "resource source provenance is visible"
    fail_message = "resource source provenance is missing"


class SearchFiltersByTypeAndSourceAssertion(_ApiQueryAssertion):
    type = "api.search_filters_by_type_and_source"
    query_type = "search_filters_by_type_and_source"
    found_key = "filtered"
    evidence_keys = ("type_filter", "source_filter", "result_count")
    pass_message = "search can filter by resource type and source"
    fail_message = "search filtering by type and source is not working"


class DiscoverySucceedsWithoutAKTPAssertion(_ApiQueryAssertion):
    type = "api.discovery_succeeds_without_aktp"
    query_type = "discovery_succeeds_without_aktp"
    found_key = "succeeded"
    evidence_keys = ("aktp_required", "ard_endpoint")
    pass_message = "discovery succeeds without any AKTP endpoint"
    fail_message = "discovery requires an AKTP endpoint"


class IngestedModelRequiresNoASMSchemaAssertion(_ApiQueryAssertion):
    type = "api.ingested_model_requires_no_asm_schema"
    query_type = "ingested_model_requires_no_asm_schema"
    found_key = "agnostic"
    evidence_keys = ("has_asm_schema", "resource_id")
    pass_message = (
        "ingested model remains artifact-agnostic without ASM schema"
    )
    fail_message = "ingested model has ASM-specific schema or fields"
