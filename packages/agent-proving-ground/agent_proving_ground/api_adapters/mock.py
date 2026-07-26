from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent_proving_ground.api_adapters.base import ApiAdapter, World


class MockUser(BaseModel):
    id: str
    email: str


class MockAgent(BaseModel):
    id: str
    user_id: str
    api_key: str | None = None


class MockCourse(BaseModel):
    id: str
    owner_agent_id: str
    title: str
    status: str = "draft"
    price_cents: int = 0
    version: str = "v1"


class MockPurchase(BaseModel):
    id: str
    buyer_agent_id: str
    course_id: str
    price_cents: int


class MockReview(BaseModel):
    id: str
    course_id: str
    course_version: str
    reviewer_agent_id: str
    rating: int


class MockUsageReport(BaseModel):
    id: str
    agent_id: str
    course_id: str
    course_version: str


class MockBounty(BaseModel):
    id: str
    creator_agent_id: str
    course_id: str
    status: str = "open"
    amount_cents: int = 0


class MockBountySubmission(BaseModel):
    id: str
    bounty_id: str
    submitter_agent_id: str
    status: str = "submitted"


class MockLedgerEntry(BaseModel):
    id: str
    user_id: str
    amount_cents: int
    kind: str
    reference: str | None = None


class MockIndexedListing(BaseModel):
    id: str
    resource_type: str = "agent_skill"
    canonical_uri: str


class MockResource(BaseModel):
    id: str
    resource_type: str
    canonical_uri: str
    projections: list[dict[str, str]] = Field(default_factory=list)


class MockWorldState(BaseModel):
    users: dict[str, MockUser] = Field(default_factory=dict)
    agents: dict[str, MockAgent] = Field(default_factory=dict)
    courses: dict[str, MockCourse] = Field(default_factory=dict)
    purchases: list[MockPurchase] = Field(default_factory=list)
    reviews: list[MockReview] = Field(default_factory=list)
    usage_reports: list[MockUsageReport] = Field(default_factory=list)
    bounties: dict[str, MockBounty] = Field(default_factory=dict)
    bounty_submissions: list[MockBountySubmission] = Field(
        default_factory=list
    )
    ledger: list[MockLedgerEntry] = Field(default_factory=list)
    indexed_listings: dict[str, MockIndexedListing] = Field(
        default_factory=dict
    )
    resources: dict[str, MockResource] = Field(default_factory=dict)
    backfill_runs: list[dict[str, int]] = Field(default_factory=list)


class MockApiAdapter(ApiAdapter):
    name = "mock"

    def __init__(self, *, seed_course: bool = True) -> None:
        self._state = MockWorldState()
        self._seed_course = seed_course

    async def start(self) -> None:
        pass

    def seed_resource_fixture(self, fixture: dict[str, Any]) -> None:
        """Load the public fixture used by the deterministic scenario test."""
        for listing in fixture.get("indexed_listings", []):
            listing_item = MockIndexedListing.model_validate(listing)
            self._state.indexed_listings[listing_item.id] = listing_item
        for course in fixture.get("courses", []):
            course_item = MockCourse.model_validate(course)
            self._state.courses[course_item.id] = course_item

    async def create_world(
        self,
        run_id: str,
        scenario_name: str,
        agent_ids: list[str],
        agent_roles: dict[str, str] | None = None,
    ) -> World:
        agent_roles = agent_roles or {}
        for agent_id in agent_ids:
            user = MockUser(
                id=f"user_{agent_id}", email=f"{agent_id}@example.test"
            )
            agent = MockAgent(id=f"agent_{agent_id}", user_id=user.id)
            self._state.users[user.id] = user
            self._state.agents[agent.id] = agent
        if self._seed_course and scenario_name == "skill_report_contract":
            fixture = MockCourse(
                id="course_fixture",
                owner_agent_id="agent_fixture_owner",
                title="Fixture Course",
                status="published",
                price_cents=0,
                version="v1",
            )
            self._state.courses[fixture.id] = fixture
        return World(
            run_id=run_id,
            base_url="http://mock.example.test",
            root_dir=Path(),
            agent_env={aid: {} for aid in agent_ids},
            handles={aid: f"agent_{aid}" for aid in agent_ids},
            data={
                "state": self._state.model_dump(mode="json"),
                "agent_roles": agent_roles,
            },
        )

    async def snapshot(self, world: World) -> dict[str, Any]:  # noqa: ARG002
        return self._state.model_dump(mode="json")

    async def query(  # noqa: C901
        self,
        world: World,  # noqa: ARG002
        query: dict[str, Any],
    ) -> dict[str, Any]:
        match query.get("type"):
            case "course_exists":
                status = query.get("status")
                owner = query.get("owner_agent")
                for course in self._state.courses.values():
                    if status and course.status != status:
                        continue
                    if owner and course.owner_agent_id != f"agent_{owner}":
                        continue
                    return {"found": True, "course_id": course.id}
                return {"found": False}
            case "usage_report_exists":
                agent = query.get("agent")
                for report in self._state.usage_reports:
                    if report.agent_id == f"agent_{agent}":
                        return {"found": True, "report_id": report.id}
                return {"found": False}
            case "purchase_exists":
                buyer = query.get("buyer_agent")
                for purchase in self._state.purchases:
                    if purchase.buyer_agent_id == f"agent_{buyer}":
                        return {"found": True, "purchase_id": purchase.id}
                return {"found": False}
            case "review_exists":
                reviewer = query.get("reviewer_agent")
                for review in self._state.reviews:
                    if review.reviewer_agent_id == f"agent_{reviewer}":
                        return {"found": True, "review_id": review.id}
                return {"found": False}
            case "bounty_exists":
                creator = query.get("creator_agent")
                status = query.get("status")
                for bounty in self._state.bounties.values():
                    if (
                        creator
                        and bounty.creator_agent_id != f"agent_{creator}"
                    ):
                        continue
                    if status and bounty.status != status:
                        continue
                    return {"found": True, "bounty_id": bounty.id}
                return {"found": False}
            case "bounty_submission_exists":
                submitter = query.get("submitter_agent")
                for sub in self._state.bounty_submissions:
                    if sub.submitter_agent_id == f"agent_{submitter}":
                        return {"found": True, "submission_id": sub.id}
                return {"found": False}
            case "bounty_accepted":
                creator = query.get("creator_agent")
                submitter = query.get("submitter_agent")
                for sub in self._state.bounty_submissions:
                    if sub.status != "accepted":
                        continue
                    bounty_or_none = self._state.bounties.get(sub.bounty_id)
                    if bounty_or_none is None:
                        continue
                    bounty = bounty_or_none
                    if (
                        creator
                        and bounty.creator_agent_id != f"agent_{creator}"
                    ):
                        continue
                    if (
                        submitter
                        and sub.submitter_agent_id != f"agent_{submitter}"
                    ):
                        continue
                    return {"found": True, "submission_id": sub.id}
                return {"found": False}
            case "no_double_credit_debit":
                seen: dict[tuple[str, str, str], int] = {}
                for entry in self._state.ledger:
                    if entry.kind != "course_purchase_debit":
                        continue
                    marker = (
                        entry.user_id,
                        entry.kind,
                        entry.reference or "",
                    )
                    seen[marker] = seen.get(marker, 0) + 1
                duplicates = [
                    {"user_id": m[0], "reference": m[2], "count": count}
                    for m, count in seen.items()
                    if count > 1
                ]
                return {
                    "double_debit_found": bool(duplicates),
                    "duplicates": duplicates,
                }
            case "admin_state_observed":
                owner = query.get("course_owner_agent")
                buyer = query.get("buyer_agent")
                owner_course_seen = any(
                    course.owner_agent_id == f"agent_{owner}"
                    for course in self._state.courses.values()
                )
                buyer_purchase_seen = any(
                    purchase.buyer_agent_id == f"agent_{buyer}"
                    for purchase in self._state.purchases
                )
                return {
                    "found": owner_course_seen and buyer_purchase_seen,
                    "evidence": {
                        "owner_course_seen": owner_course_seen,
                        "buyer_purchase_seen": buyer_purchase_seen,
                    },
                }
            case "credit_balance_changed":
                return {"changed": True}
            case "course_remains_purchasable":
                for course in self._state.courses.values():
                    if course.status == "published":
                        return {"purchasable": True, "course_id": course.id}
                return {"purchasable": False}
            case "source_link_exists":
                course_id = query.get("course")
                if course_id and course_id in self._state.courses:
                    return {
                        "found": True,
                        "course_id": course_id,
                        "evidence": {"source": "mock"},
                    }
                return {"found": False}
            case "bounty_submission_pr_opened":
                return {
                    "opened": True,
                    "submission_id": query.get("submission") or "submission_1",
                    "pr_url": "https://github.com/owner/repo/pull/1",
                }
            case "bounty_submission_accepted":
                return {"accepted": True}
            case "bounty_submission_rejected":
                return {"rejected": True}
            case "resource_projection_exists":
                projection_kind = query.get(
                    "projection_kind", "indexed_listing"
                )
                for resource in self._state.resources.values():
                    if any(
                        p.get("projection_kind") == projection_kind
                        for p in resource.projections
                    ):
                        return {
                            "found": True,
                            "resource_id": resource.id,
                        }
                return {"found": False}
            case "resource_backfill_complete":
                missing = [
                    listing_id
                    for listing_id in self._state.indexed_listings
                    if not any(
                        p.get("projection_id") == listing_id
                        for resource in self._state.resources.values()
                        for p in resource.projections
                    )
                ]
                return {"found": bool(self._state.resources) and not missing}
            case "resource_identity_unique":
                identities = [
                    (r.resource_type, r.canonical_uri)
                    for r in self._state.resources.values()
                ]
                return {"found": len(identities) == len(set(identities))}
            case "resource_backfill_idempotent":
                required = {
                    "rerun_created",
                    "rerun_linked",
                    "before_identity_snapshot",
                    "after_identity_snapshot",
                }
                if not required.issubset(query):
                    return {
                        "found": False,
                        "unsupported": True,
                        "reason": "idempotency captures are required",
                    }
                created = query["rerun_created"]
                linked = query["rerun_linked"]
                before = query["before_identity_snapshot"]
                after = query["after_identity_snapshot"]
                snapshots_nonempty = str(before).strip() not in {
                    "",
                    "[]",
                    "{}",
                    "null",
                    "None",
                }
                return {
                    "found": str(created) == "0"
                    and str(linked) == "0"
                    and snapshots_nonempty
                    and before == after
                }
            case "resource_backfill_applied":
                created = query.get("resources_created")
                linked = query.get("projections_linked")
                snapshot = query.get("identity_snapshot")
                empty_snapshots = {"", "[]", "{}", "null", "None"}
                return {
                    "found": str(created) == "2"
                    and str(linked) == "2"
                    and isinstance(snapshot, str)
                    and snapshot.strip() not in empty_snapshots
                }
            case "resource_search_returns_kinds":
                kinds = query.get("projection_kinds")
                canonicals = query.get("canonicals", [])
                if (
                    not isinstance(kinds, list)
                    or not kinds
                    or not all(
                        isinstance(kind, str) and kind for kind in kinds
                    )
                    or not isinstance(canonicals, list)
                    or len(kinds) != len(canonicals)
                    or not all(
                        isinstance(canonical, str) and canonical
                        for canonical in canonicals
                    )
                ):
                    return {
                        "kinds_match": False,
                        "unsupported": True,
                        "reason": "invalid fixture expectations",
                    }
                expected_pairs = set(zip(canonicals, kinds, strict=True))
                found_pairs = {
                    (
                        resource.canonical_uri,
                        projection.get("projection_kind"),
                    )
                    for resource in self._state.resources.values()
                    for projection in resource.projections
                }
                matched_pairs = expected_pairs & found_pairs
                matched_kinds = sorted({kind for _, kind in matched_pairs})
                matched_canonicals = sorted({
                    canonical for canonical, _ in matched_pairs
                })
                return {
                    "kinds_match": expected_pairs.issubset(matched_pairs),
                    "projection_kinds": matched_kinds,
                    "matched_canonicals": matched_canonicals,
                }
            case "legacy_course_purchase_exists":
                for purchase in self._state.purchases:
                    return {"found": True, "purchase_id": purchase.id}
                return {"found": False}
            case _:
                return {"error": "unknown query type"}

    def record_operation(  # noqa: C901
        self, agent_id: str, operation: str, **kwargs: Any
    ) -> None:
        if operation == "backfill_resources":
            created = 0
            linked = 0
            sources = [
                *self._state.indexed_listings.values(),
                *[
                    MockIndexedListing(
                        id=course.id,
                        resource_type="course",
                        canonical_uri=f"course:{course.id}",
                    )
                    for course in self._state.courses.values()
                    if course.status == "published"
                ],
            ]
            for source in sources:
                resource = self._state.resources.get(source.id)
                if resource is None:
                    resource = MockResource(
                        id=f"resource_{source.id}",
                        resource_type=source.resource_type,
                        canonical_uri=source.canonical_uri,
                    )
                    self._state.resources[source.id] = resource
                    created += 1
                if not any(
                    p.get("projection_id") == source.id
                    for p in resource.projections
                ):
                    resource.projections.append({
                        "projection_kind": "indexed_listing"
                        if source.resource_type == "agent_skill"
                        else "published_course",
                        "projection_id": source.id,
                    })
                    linked += 1
            self._state.backfill_runs.append({
                "resources_created": created,
                "projections_linked": linked,
            })
        elif operation == "create_usage_report":
            course_id = kwargs.get("course_id", "course_fixture")
            version = kwargs.get("course_version", "v1")
            self._state.usage_reports.append(
                MockUsageReport(
                    id=f"usage_{len(self._state.usage_reports)}",
                    agent_id=f"agent_{agent_id}",
                    course_id=course_id,
                    course_version=version,
                )
            )
        elif operation == "publish_course":
            course_id = kwargs.get(
                "course_id", f"course_{len(self._state.courses)}"
            )
            self._state.courses[course_id] = MockCourse(
                id=course_id,
                owner_agent_id=f"agent_{agent_id}",
                title=kwargs.get("title", "Untitled"),
                status="published",
                price_cents=kwargs.get("price_cents", 0),
                version="v1",
            )
        elif operation == "purchase_course":
            course_id = kwargs.get("course_id")
            if course_id is None:
                published = [
                    c
                    for c in self._state.courses.values()
                    if c.status == "published"
                ]
                course_id = published[0].id if published else "course_fixture"
            course = self._state.courses.get(course_id)
            price = kwargs.get(
                "price_cents", course.price_cents if course else 0
            )
            self._state.purchases.append(
                MockPurchase(
                    id=f"purchase_{len(self._state.purchases)}",
                    buyer_agent_id=f"agent_{agent_id}",
                    course_id=course_id,
                    price_cents=price,
                )
            )
            self._state.ledger.append(
                MockLedgerEntry(
                    id=f"ledger_{len(self._state.ledger)}",
                    user_id=f"user_{agent_id}",
                    amount_cents=-price,
                    kind="course_purchase_debit",
                    reference=course_id,
                )
            )
        elif operation == "create_review":
            course_id = kwargs.get("course_id", "course_fixture")
            course = self._state.courses.get(course_id)
            self._state.reviews.append(
                MockReview(
                    id=f"review_{len(self._state.reviews)}",
                    course_id=course_id,
                    course_version=course.version if course else "v1",
                    reviewer_agent_id=f"agent_{agent_id}",
                    rating=kwargs.get("rating", 5),
                )
            )
        elif operation == "create_bounty":
            bounty_id = kwargs.get(
                "bounty_id", f"bounty_{len(self._state.bounties)}"
            )
            self._state.bounties[bounty_id] = MockBounty(
                id=bounty_id,
                creator_agent_id=f"agent_{agent_id}",
                course_id=kwargs.get("course_id", "course_fixture"),
                status="open",
                amount_cents=kwargs.get("amount_cents", 0),
            )
        elif operation == "fund_bounty":
            bounty_id = kwargs.get("bounty_id")
            bounty = (
                self._state.bounties.get(bounty_id)
                if isinstance(bounty_id, str)
                else None
            )
            if bounty is not None and bounty.status == "open":
                bounty.status = "funded"
                self._state.ledger.append(
                    MockLedgerEntry(
                        id=f"ledger_{len(self._state.ledger)}",
                        user_id=f"user_{agent_id}",
                        amount_cents=-bounty.amount_cents,
                        kind="bounty_funding_debit",
                        reference=bounty.id,
                    )
                )
        elif operation == "submit_bounty":
            bounty_id = kwargs.get("bounty_id")
            if bounty_id in self._state.bounties:
                self._state.bounty_submissions.append(
                    MockBountySubmission(
                        id=f"submission_{len(self._state.bounty_submissions)}",
                        bounty_id=bounty_id,
                        submitter_agent_id=f"agent_{agent_id}",
                        status="submitted",
                    )
                )
        elif operation == "accept_bounty_submission":
            bounty_id = kwargs.get("bounty_id")
            for sub in self._state.bounty_submissions:
                if bounty_id and sub.bounty_id != bounty_id:
                    continue
                bounty = self._state.bounties.get(sub.bounty_id)
                if bounty is None:
                    continue
                if bounty.creator_agent_id != f"agent_{agent_id}":
                    continue
                sub.status = "accepted"
                break

    async def stop(self) -> None:
        pass
