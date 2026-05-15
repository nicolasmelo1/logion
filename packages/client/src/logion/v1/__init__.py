"""V1 API namespace."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._resources.admin import AdminResource
from logion.v1._resources.bounties import BountiesResource
from logion.v1._resources.course_reviews import CourseReviewsResource
from logion.v1._resources.courses import CoursesResource
from logion.v1._resources.health import HealthResource
from logion.v1._resources.identity import IdentityResource
from logion.v1._resources.listings import ListingsResource
from logion.v1._resources.notifications import NotificationsResource
from logion.v1._resources.payments import PaymentsResource
from logion.v1._resources.reports import ReportsResource


class V1Namespace:
    """Namespace for v1 API endpoints."""

    def __init__(self, http: HttpClient) -> None:
        self.health = HealthResource(http)
        self.identity = IdentityResource(http)
        self.listings = ListingsResource(http)
        self.courses = CoursesResource(http)
        self.payments = PaymentsResource(http)
        self.course_reviews = CourseReviewsResource(http)
        self.notifications = NotificationsResource(http)
        self.reports = ReportsResource(http)
        self.admin = AdminResource(http)
        self.bounties = BountiesResource(http)
