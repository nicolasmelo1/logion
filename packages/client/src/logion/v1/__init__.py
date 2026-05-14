"""V1 API namespace."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._resources.courses import CoursesResource
from logion.v1._resources.health import HealthResource
from logion.v1._resources.identity import IdentityResource
from logion.v1._resources.listings import ListingsResource
from logion.v1._resources.payments import PaymentsResource


class V1Namespace:
    """Namespace for v1 API endpoints."""

    def __init__(self, http: HttpClient) -> None:
        self.health = HealthResource(http)
        self.identity = IdentityResource(http)
        self.listings = ListingsResource(http)
        self.courses = CoursesResource(http)
        self.payments = PaymentsResource(http)
