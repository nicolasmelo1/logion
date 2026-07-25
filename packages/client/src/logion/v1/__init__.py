# SPDX-License-Identifier: MIT
"""V1 API namespace."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._resources.admin import AdminResource
from logion.v1._resources.bounties import BountiesResource
from logion.v1._resources.course_reviews import CourseReviewsResource
from logion.v1._resources.courses import CoursesResource
from logion.v1._resources.credits import CreditsResource
from logion.v1._resources.github_setup import GithubSetupResource
from logion.v1._resources.health import HealthResource
from logion.v1._resources.identity import IdentityResource
from logion.v1._resources.indexed_listings import IndexedListingsResource
from logion.v1._resources.listings import ListingsResource
from logion.v1._resources.notifications import NotificationsResource
from logion.v1._resources.payments import PaymentsResource
from logion.v1._resources.referrals import ReferralsResource
from logion.v1._resources.reports import ReportsResource
from logion.v1._resources.resources import ResourcesResource


class V1Namespace:
    """Namespace for v1 API endpoints."""

    def __init__(self, http: HttpClient) -> None:
        self.health = HealthResource(http)
        self.identity = IdentityResource(http)
        self.listings = ListingsResource(http)
        self.indexed_listings = IndexedListingsResource(http)
        self.courses = CoursesResource(http)
        self.credits = CreditsResource(http)
        self.payments = PaymentsResource(http)
        self.course_reviews = CourseReviewsResource(http)
        self.notifications = NotificationsResource(http)
        self.reports = ReportsResource(http)
        self.admin = AdminResource(http)
        self.bounties = BountiesResource(http)
        self.referrals = ReferralsResource(http)
        self.github_setup = GithubSetupResource(http)
        self.resources = ResourcesResource(http)
