# SPDX-License-Identifier: MIT
from __future__ import annotations

IMPLEMENTED_OPERATIONS: dict[str, str] = {
    # Health
    "health_health_get": "client.v1.health.check",
    # Identity
    "create_user_with_agent": ("client.v1.identity.create_user_with_agent"),
    "add_agent_to_user": "client.v1.identity.add_agent_to_user",
    "rotate_agent_api_key": (
        "client.v1.identity.rotate_api_key"  # pragma: allowlist secret
    ),
    "begin_github_authorization": (
        "client.v1.identity.begin_github_authorization"
    ),
    "complete_github_callback": "client.v1.identity.complete_github_callback",
    "begin_github_device_flow": (
        "client.v1.identity.begin_github_device_flow"
    ),
    "poll_github_device_flow": "client.v1.identity.poll_github_device_flow",
    "get_github_identity": "client.v1.identity.get_github_identity",
    "revoke_github_identity": "client.v1.identity.revoke_github_identity",
    # Listings
    "search_listings": "client.v1.listings.search",
    # Generic resources
    "list_resources": "client.v1.resources.search",
    "get_resource": "client.v1.resources.get",
    "list_resource_versions": "client.v1.resources.versions",
    "get_acquisition_plan": "client.v1.resources.acquisition_plan",
    "create_artifact_download": "client.v1.resources.create_download",
    # Native-use feedback and narrow receipts
    "submit_feedback": "client.v1.resource_feedback.submit",
    "list_my_feedback": "client.v1.resource_feedback.list_mine",
    "list_resource_feedback": "client.v1.resource_feedback.list_for_resource",
    "get_feedback_summary": "client.v1.resource_feedback.get_summary",
    "submit_usage_receipt": "client.v1.usage_receipts.submit",
    # Evals
    "upload_eval_contract": "client.v1.evals.upload_contract",
    "get_eval_contract": "client.v1.evals.get_contract",
    "submit_eval_result": "client.v1.evals.submit_result",
    # Courses
    "create_course": "client.v1.courses.create",
    "get_course": "client.v1.courses.get",
    "list_my_courses": "client.v1.courses.mine",
    "update_course": "client.v1.courses.update",
    "get_my_course_review": "client.v1.courses.get_my_review",
    "request_publication": ("client.v1.courses.request_publication_review"),
    "get_review_status": ("client.v1.courses.get_latest_publication_review"),
    "get_course_review_feedback": ("client.v1.courses.get_review_feedback"),
    "list_course_reviews": "client.v1.courses.list_reviews",
    "create_upload_session": ("client.v1.courses.create_upload_session"),
    "get_course_version": "client.v1.courses.get_version",
    "upsert_course_review": "client.v1.courses.review_version",
    "complete_upload_session": ("client.v1.courses.complete_upload_session"),
    # Credits
    "get_credit_balance": "client.v1.credits.get_balance",
    "list_credit_ledger": "client.v1.credits.list_ledger",
    "create_credit_top_up": "client.v1.credits.create_top_up",
    "get_credit_top_up": "client.v1.credits.get_top_up",
    # Payments
    "create_onboarding_link": ("client.v1.payments.create_onboarding_link"),
    "get_order": "client.v1.payments.get_order",
    "get_seller_readiness": ("client.v1.payments.get_seller_readiness"),
    "get_creator_earnings": "client.v1.payments.get_creator_earnings",
    "request_cash_out": "client.v1.payments.request_cash_out",
    # Courses — purchase
    "purchase_course": "client.v1.courses.purchase",
    "set_course_source_link": "client.v1.courses.set_source_link",
    "get_course_source_link": "client.v1.courses.get_source_link",
    "delete_course_source_link": "client.v1.courses.delete_source_link",
    # Bounties
    "create_bounty": "client.v1.bounties.create",
    "list_bounties": "client.v1.bounties.list",
    "cancel_bounty": "client.v1.bounties.delete",
    "get_bounty": "client.v1.bounties.get",
    "fund_bounty": "client.v1.bounties.update_funding",
    "create_bounty_payout": ("client.v1.bounties.create_payout"),
    "open_bounty": "client.v1.bounties.update_status",
    "open_submission_pr": "client.v1.bounties.open_pr",
    "update_bounty": "client.v1.bounties.update",
    "list_bounty_submissions": ("client.v1.bounties.list_submissions"),
    "create_bounty_submission": ("client.v1.bounties.create_submission"),
    "withdraw_bounty_submission": ("client.v1.bounties.delete_submission"),
    "get_bounty_submission": "client.v1.bounties.get_submission",
    "accept_bounty_submission": ("client.v1.bounties.accept_submission"),
    "reject_bounty_submission": ("client.v1.bounties.reject_submission"),
    # GitHub setup (landing companion)
    "setup_github_start": "client.v1.github_setup.start",
    "setup_github_callback": (  # pragma: allowlist secret
        "client.v1.github_setup.callback"
    ),
    "claim_setup_handoff": "client.v1.github_setup.claim_handoff",
    "redeem_setup_token": "client.v1.github_setup.redeem_token",
    "get_setup_token_status": (  # pragma: allowlist secret
        "client.v1.github_setup.get_token_status"
    ),
    # Course reviews
    "list_human_review_queue": ("client.v1.course_reviews.list"),
    "get_review_bundle": "client.v1.course_reviews.get_bundle",
    "get_human_review_detail": ("client.v1.course_reviews.get"),
    "approve_human_review": ("client.v1.course_reviews.approve"),
    "reject_human_review": ("client.v1.course_reviews.reject"),
    # Referrals
    "get_referral_code": "client.v1.referrals.get_code",
    "get_referral_link": "client.v1.referrals.get_link",
    "get_referral_stats": "client.v1.referrals.get_stats",
    "list_referral_attributions": "client.v1.referrals.list_attributions",
    # Notifications
    "list_notifications": "client.v1.notifications.list",
    "get_unread_count": ("client.v1.notifications.get_unread_count"),
    # Reports
    "create_report": "client.v1.reports.create",
    # Admin
    "list_moderation_queue": "client.v1.admin.list_courses",
    "get_course_moderation_detail": ("client.v1.admin.get_course"),
    "block_course": "client.v1.admin.update_course_status",
    "get_user_detail": "client.v1.admin.get_user",
    "suspend_user": "client.v1.admin.suspend_user",
    "reactivate_user": "client.v1.admin.unsuspend_user",
    "get_agent_detail": "client.v1.admin.get_agent",
    "suspend_agent": "client.v1.admin.suspend_agent",
    "reactivate_agent": "client.v1.admin.unsuspend_agent",
    "list_reports": "client.v1.admin.list_reports",
    "get_report_detail": "client.v1.admin.get_report",
    "resolve_report": "client.v1.admin.resolve_report",
    "dismiss_report": "client.v1.admin.dismiss_report",
    "set_referral_attribution_status": (
        "client.v1.admin.set_referral_attribution_status"
    ),
}

# IDs staged ahead of a private-main contract sync. They must be explicit SDK
# classifications now, so the sync candidate is audited with the same surface
# map that will merge alongside its generated contract.
PREDECLARED_OPERATION_IDS = frozenset({
    "create_platform_bounty",
    "fund_platform_bounty",
    "accept_platform_bounty_submission",
    "reject_platform_bounty_submission",
    "get_api_capabilities",
})

UNSUPPORTED_OPERATIONS: dict[str, str] = {
    # Runner/coordinator endpoints are generated for contract compatibility,
    # but have no stable handwritten SDK resource surface yet.
    "enroll_runner": ("Runner operator endpoint; no stable SDK resource yet."),
    "rotate_runner_key": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    "lease_execution_job": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    "runner_heartbeat": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    "upload_execution_artifact": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    "submit_execution_receipt": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    "list_runners": ("Runner operator endpoint; no stable SDK resource yet."),
    "create_execution_job": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    "list_execution_jobs": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    "get_execution_job": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    "cancel_execution_job": (
        "Runner operator endpoint; no stable SDK resource yet."
    ),
    # Indexer ingestion endpoints have generated primitives, but are not part
    # of the stable, handwritten SDK resource surface yet.
    "get_known_indexed_sources": "Indexer-only ingestion endpoint.",
    "create_indexed_bundle_upload": "Indexer-only ingestion endpoint.",
    "complete_indexed_bundle_upload": "Indexer-only ingestion endpoint.",
    "batch_upsert_listings": "Indexer-only ingestion endpoint.",
    "open_indexing_run": "Indexer-only ingestion endpoint.",
    "get_indexing_run_progress": "Indexer-only ingestion endpoint.",
    "complete_indexing_run": "Indexer-only ingestion endpoint.",
    "update_indexing_run_progress": "Indexer-only ingestion endpoint.",
    "get_indexed_listing": "No handwritten SDK resource exists yet.",
    "get_api_capabilities": (
        "Compatibility metadata is API-only until the CLI resource is added."
    ),
    # Platform-funded bounty administration is intentionally API-only for now.
    # Generated request primitives remain available, but the public SDK has no
    # stable admin resource surface for these founder-admin operations.
    "create_platform_bounty": (
        "Founder-admin API workflow; no stable SDK resource yet."
    ),
    "fund_platform_bounty": (
        "Founder-admin API workflow; no stable SDK resource yet."
    ),
    "accept_platform_bounty_submission": (
        "Founder-admin API workflow; no stable SDK resource yet."
    ),
    "reject_platform_bounty_submission": (
        "Founder-admin API workflow; no stable SDK resource yet."
    ),
    # AI Catalog / ARD endpoints have generated primitives but no
    # handwritten SDK resource yet.
    "get_catalog": (
        "AI Catalog document endpoint; no stable SDK resource yet."
    ),
    "search": "ARD search endpoint; no stable SDK resource yet.",
    "explore": "ARD explore endpoint; no stable SDK resource yet.",
    "list_agents": "ARD list endpoint; no stable SDK resource yet.",
    "get_source_status": (
        "ARD source status endpoint; no stable SDK resource yet."
    ),
    "record_source_snapshot": (
        "ARD operator snapshot write; no stable SDK resource yet."
    ),
    "ingest_catalog_entries": (
        "AI Catalog ingestion; operator tooling, no SDK resource yet."
    ),
}
