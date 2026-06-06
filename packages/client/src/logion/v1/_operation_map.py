# SPDX-License-Identifier: MIT
from __future__ import annotations

IMPLEMENTED_OPERATIONS: dict[str, str] = {
    # Health
    "health_health_get": "client.v1.health.check",
    # Identity
    "create_user_with_agent": ("client.v1.identity.create_user_with_agent"),
    "add_agent_to_user": "client.v1.identity.add_agent_to_user",
    "rotate_agent_api_key": "client.v1.identity.rotate_api_key",
    # Listings
    "search_listings": "client.v1.listings.search",
    # Courses
    "create_course": "client.v1.courses.create",
    "get_course": "client.v1.courses.get",
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
    "list_credit_packs": "client.v1.credits.list_packs",
    "create_credit_top_up": "client.v1.credits.create_top_up",
    "get_credit_top_up": "client.v1.credits.get_top_up",
    # Payments
    "create_onboarding_link": ("client.v1.payments.create_onboarding_link"),
    "get_order": "client.v1.payments.get_order",
    "get_seller_readiness": ("client.v1.payments.get_seller_readiness"),
    "get_creator_earnings": "client.v1.payments.get_creator_earnings",
    "create_cash_out": "client.v1.payments.create_cash_out",
    # Courses — purchase
    "purchase_course": "client.v1.courses.purchase",
    # Bounties
    "create_bounty": "client.v1.bounties.create",
    "list_bounties": "client.v1.bounties.list",
    "cancel_bounty": "client.v1.bounties.delete",
    "get_bounty": "client.v1.bounties.get",
    "fund_bounty": "client.v1.bounties.update_funding",
    "create_bounty_payout": ("client.v1.bounties.create_payout"),
    "open_bounty": "client.v1.bounties.update_status",
    "list_bounty_submissions": ("client.v1.bounties.list_submissions"),
    "create_bounty_submission": ("client.v1.bounties.create_submission"),
    "withdraw_bounty_submission": ("client.v1.bounties.delete_submission"),
    "get_bounty_submission": ("client.v1.bounties.get_submission"),
    "accept_bounty_submission": ("client.v1.bounties.accept_submission"),
    "reject_bounty_submission": ("client.v1.bounties.reject_submission"),
    # Course reviews
    "list_human_review_queue": ("client.v1.course_reviews.list"),
    "get_human_review_detail": ("client.v1.course_reviews.get"),
    "approve_human_review": ("client.v1.course_reviews.approve"),
    "reject_human_review": ("client.v1.course_reviews.reject"),
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
    "admin_create_cash_out": "client.v1.admin.create_cash_out",
}

UNSUPPORTED_OPERATIONS: dict[str, str] = {}
