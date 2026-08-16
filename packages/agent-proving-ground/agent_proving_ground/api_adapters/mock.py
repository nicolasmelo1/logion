from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from agent_proving_ground._json import (
    JsonObject,
    JsonValue,
    children,
    elements,
    opt_bool,
    opt_int,
    opt_str,
)
from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)
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


class MockResourceFeedback(BaseModel):
    id: str
    resource_id: str
    version_id: str
    reporter_agent_id: str
    rating: int = 0
    acquisition_channel: str = "npx_skills"
    installation_id: str = ""
    body: str = ""
    task_class: str = ""
    completed_task: bool = True
    projection_disposition: str = "not_a_course"
    course_review_id: str | None = None


class MockUsageObservation(BaseModel):
    observation_id: str
    agent_id: str
    resource_id: str
    version_id: str
    channel: str = "npx_skills"
    scope_id: str = ""
    repository: str = ""
    event: str = "resource_invoked"
    raw_payload: str = ""


class MockPendingUsage(BaseModel):
    pending_id: str
    agent_id: str
    resource_id: str
    version_id: str
    repository: str = ""


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
    resource_feedback: list[MockResourceFeedback] = Field(default_factory=list)
    usage_observations: list[MockUsageObservation] = Field(
        default_factory=list
    )
    pending_usage: list[MockPendingUsage] = Field(default_factory=list)


class MockApiAdapter(ApiAdapter):
    name = "mock"

    def __init__(self, *, seed_course: bool = True) -> None:
        self._state = MockWorldState()
        self._seed_course = seed_course
        self._artifact_queries = LogionApiQueries(
            "mock://local", RoleKeyStore({})
        )

    async def start(self) -> None:
        pass

    def seed_resource_fixture(self, fixture: JsonObject) -> None:
        """Load the public fixture used by the deterministic scenario test."""
        for listing in children(fixture, "indexed_listings"):
            listing_item = MockIndexedListing.model_validate(listing)
            self._state.indexed_listings[listing_item.id] = listing_item
        for course in children(fixture, "courses"):
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

    async def snapshot(self, world: World) -> JsonObject:  # noqa: ARG002
        return self._state.model_dump(mode="json")

    async def query(  # noqa: C901
        self,
        world: World,  # noqa: ARG002
        query: JsonObject,
    ) -> JsonObject:
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
                duplicates: list[JsonObject] = [
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
                projection_kind = opt_str(
                    query,
                    "projection_kind",
                    "indexed_listing",
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
                canonicals = elements(query, "canonicals")
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
                expected_pairs = {
                    (str(canonical), str(kind))
                    for canonical, kind in zip(canonicals, kinds, strict=True)
                }
                found_pairs = {
                    (
                        resource.canonical_uri,
                        str(projection.get("projection_kind")),
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
            case "harness_scope_targets_resolved":
                harnesses = elements(query, "harnesses")
                scopes = elements(query, "scopes")
                if (
                    not isinstance(harnesses, list)
                    or not isinstance(scopes, list)
                    or not harnesses
                    or not scopes
                ):
                    return {
                        "resolved": False,
                        "unsupported": True,
                        "reason": "harnesses and scopes lists are required",
                    }
                known_harnesses = {
                    "codex",
                    "claude-code",
                    "hermes",
                    "pi",
                    "opencode",
                }
                known_scopes = {
                    "repo-current",
                    "repo-parent",
                    "repo-root",
                    "user",
                    "admin",
                    "system",
                    "custom",
                }
                all_known = all(
                    h in known_harnesses for h in harnesses
                ) and all(s in known_scopes for s in scopes)
                return {
                    "resolved": all_known,
                    "harnesses": harnesses,
                    "scopes": scopes,
                }
            case "resource_acquire_plan_dry_run":
                harness = query.get("harness")
                scope = query.get("scope")
                zero_write = opt_bool(query, "zero_write", default=True)
                if not harness or not scope:
                    return {
                        "valid": False,
                        "unsupported": True,
                        "reason": "harness and scope are required",
                    }
                return {
                    "valid": True,
                    "harness": harness,
                    "scope": scope,
                    "zero_write": bool(zero_write),
                    "executable": False,
                    "permissions_required": (
                        "unknown-until-distribution-is-resolved"
                    ),
                }
            case "harness_scope_nested_repo":
                harnesses = elements(query, "harnesses")
                nested_repo = opt_str(query, "nested_repo", "")
                if (
                    not isinstance(harnesses, list)
                    or not harnesses
                    or not nested_repo
                ):
                    return {
                        "nested": False,
                        "unsupported": True,
                        "reason": (
                            "harnesses list and nested_repo are required"
                        ),
                    }
                return {
                    "nested": True,
                    "harnesses": harnesses,
                    "nested_repo": nested_repo,
                }
            case "harness_inventory_distinct_scopes":
                harnesses = elements(query, "harnesses")
                if not isinstance(harnesses, list) or not harnesses:
                    return {
                        "distinct": False,
                        "unsupported": True,
                        "reason": "harnesses list is required",
                    }
                return {
                    "distinct": True,
                    "harnesses": harnesses,
                }
            case "resource_acquisition_exists":
                return {
                    "acquired": True,
                    "resource_id": opt_str(query, "resource_id", "r"),
                    "installation_id": "i",
                    "verification": opt_str(query, "verification", "exact"),
                    "channel": opt_str(query, "channel", "logion_bundle"),
                }
            case "resource_distribution_selected":
                channel = opt_str(query, "channel", "logion_bundle")
                allowed = elements(query, "allowed_channels")
                return {
                    "selected": channel in allowed if allowed else True,
                    "channel": channel,
                    "distribution_id": opt_str(query, "distribution_id", "d"),
                }
            case "native_install_reconciled":
                return {
                    "reconciled": True,
                    "matched_count": 1,
                    "unresolved_count": 0,
                    "ambiguous_count": 0,
                    "drifted_count": 0,
                    "channels": [
                        opt_str(query, "expected_channel", "logion_bundle")
                    ],
                }
            case "inventory_receipt_matches":
                iid = opt_str(query, "installation_id", "i")
                return {
                    "matches": True,
                    "installation_id": iid,
                    "matched_ids": [iid],
                }
            case "installed_artifact_digest_matches":
                return {
                    "digest_matches": True,
                    "content_digest": opt_str(query, "content_digest", ""),
                    "computed_digest": opt_str(query, "content_digest", ""),
                    "files": 1,
                }
            case "install_drift_reported":
                return {
                    "drift_reported": True,
                    "installation_id": opt_str(query, "installation_id", "i"),
                    "drifted_count": 1,
                }
            case "scope_isolation_preserved":
                return {
                    "isolated": True,
                    "added": [],
                    "removed": [],
                    "changed": [],
                }
            case "acquisition_idempotent":
                iid = opt_str(query, "installation_id", "i")
                return {
                    "idempotent": True,
                    "first_installation_id": iid,
                    "second_installation_id": iid,
                }
            case "observation_envelope_no_raw_data":
                return {"clean": True}
            case "native_use_observed":
                agent = query.get("agent")
                repo = opt_str(query, "repository", "")
                for obs in self._state.usage_observations:
                    if obs.agent_id == f"agent_{agent}" and (
                        not repo or obs.repository == repo
                    ):
                        return {
                            "observed": True,
                            "resource_id": obs.resource_id,
                            "version_id": obs.version_id,
                            "channel": obs.channel,
                            "scope_id": obs.scope_id,
                        }
                return {"observed": False}
            case "feedback_pending":
                agent = query.get("agent")
                repo = opt_str(query, "repository", "")
                pending = [
                    p
                    for p in self._state.pending_usage
                    if p.agent_id == f"agent_{agent}"
                    and (not repo or p.repository == repo)
                ]
                return {
                    "has_pending": bool(pending),
                    "pending_count": len(pending),
                    "resource_ids": [p.resource_id for p in pending],
                }
            case "resource_feedback_exists":
                reporter = query.get("reporter_agent")
                for fb in self._state.resource_feedback:
                    if fb.reporter_agent_id == f"agent_{reporter}":
                        return {
                            "found": True,
                            "feedback_id": fb.id,
                            "resource_id": fb.resource_id,
                            "version_id": fb.version_id,
                        }
                return {"found": False}
            case "feedback_linked_to_acquisition":
                reporter = query.get("reporter_agent")
                for fb in self._state.resource_feedback:
                    if (
                        fb.reporter_agent_id == f"agent_{reporter}"
                        and fb.installation_id
                    ):
                        return {
                            "linked": True,
                            "feedback_id": fb.id,
                            "acquisition_channel": fb.acquisition_channel,
                            "installation_id": fb.installation_id,
                        }
                return {"linked": False}
            case "course_review_projection_exists":
                reporter = query.get("reporter_agent")
                for fb in self._state.resource_feedback:
                    if (
                        fb.reporter_agent_id == f"agent_{reporter}"
                        and fb.course_review_id is not None
                    ):
                        return {
                            "found": True,
                            "feedback_id": fb.id,
                            "projection_disposition": fb.projection_disposition,  # noqa: E501
                            "course_review_id": fb.course_review_id,
                        }
                return {
                    "found": False,
                    "unsupported": True,
                    "reason": (
                        "no course projection exists for this "
                        "feedback in the mock adapter"
                    ),
                }
            case "raw_observation_not_uploaded":
                agent = query.get("agent")
                checked = [
                    obs
                    for obs in self._state.usage_observations
                    if obs.agent_id == f"agent_{agent}"
                ]
                has_raw = any(obs.raw_payload for obs in checked)
                return {
                    "clean": not has_raw,
                    "observation_count": len(checked),
                    "checked_fields": ["raw_payload"],
                }
            case "feedback_submission_idempotent":
                reporter = query.get("reporter_agent")
                fbs = [
                    fb
                    for fb in self._state.resource_feedback
                    if fb.reporter_agent_id == f"agent_{reporter}"
                ]
                if len(fbs) < 2:
                    return {
                        "idempotent": True,
                        "first_feedback_id": fbs[0].id if fbs else "",
                        "second_feedback_id": "",
                    }
                return {
                    "idempotent": fbs[0].id == fbs[1].id,
                    "first_feedback_id": fbs[0].id,
                    "second_feedback_id": fbs[1].id,
                }
            case _:
                return {"error": "unknown query type"}

    def record_operation(  # noqa: C901
        self, agent_id: str, operation: str, **kwargs: JsonValue
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
            course_id = opt_str(kwargs, "course_id", "course_fixture")
            version = opt_str(kwargs, "course_version", "v1")
            self._state.usage_reports.append(
                MockUsageReport(
                    id=f"usage_{len(self._state.usage_reports)}",
                    agent_id=f"agent_{agent_id}",
                    course_id=course_id,
                    course_version=version,
                )
            )
        elif operation == "publish_course":
            course_id = opt_str(
                kwargs, "course_id", f"course_{len(self._state.courses)}"
            )
            self._state.courses[course_id] = MockCourse(
                id=course_id,
                owner_agent_id=f"agent_{agent_id}",
                title=opt_str(kwargs, "title", "Untitled"),
                status="published",
                price_cents=opt_int(kwargs, "price_cents", 0),
                version="v1",
            )
        elif operation == "purchase_course":
            resolved_id = opt_str(kwargs, "course_id")
            if resolved_id is None:
                published = [
                    c
                    for c in self._state.courses.values()
                    if c.status == "published"
                ]
                resolved_id = (
                    published[0].id if published else "course_fixture"
                )
            course_id = resolved_id
            course = self._state.courses.get(course_id)
            price = opt_int(
                kwargs, "price_cents", course.price_cents if course else 0
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
            course_id = opt_str(kwargs, "course_id", "course_fixture")
            course = self._state.courses.get(course_id)
            self._state.reviews.append(
                MockReview(
                    id=f"review_{len(self._state.reviews)}",
                    course_id=course_id,
                    course_version=course.version if course else "v1",
                    reviewer_agent_id=f"agent_{agent_id}",
                    rating=opt_int(kwargs, "rating", 5),
                )
            )
        elif operation == "create_bounty":
            bounty_id = opt_str(
                kwargs, "bounty_id", f"bounty_{len(self._state.bounties)}"
            )
            self._state.bounties[bounty_id] = MockBounty(
                id=bounty_id,
                creator_agent_id=f"agent_{agent_id}",
                course_id=opt_str(kwargs, "course_id", "course_fixture"),
                status="open",
                amount_cents=opt_int(kwargs, "amount_cents", 0),
            )
        elif operation == "fund_bounty":
            fund_bounty_id = opt_str(kwargs, "bounty_id")
            bounty = (
                self._state.bounties.get(fund_bounty_id)
                if fund_bounty_id is not None
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
            submit_bounty_id = opt_str(kwargs, "bounty_id", "")
            if submit_bounty_id in self._state.bounties:
                self._state.bounty_submissions.append(
                    MockBountySubmission(
                        id=f"submission_{len(self._state.bounty_submissions)}",
                        bounty_id=submit_bounty_id,
                        submitter_agent_id=f"agent_{agent_id}",
                        status="submitted",
                    )
                )
        elif operation == "accept_bounty_submission":
            accept_bounty_id = opt_str(kwargs, "bounty_id")
            for sub in self._state.bounty_submissions:
                if accept_bounty_id and sub.bounty_id != accept_bounty_id:
                    continue
                bounty = self._state.bounties.get(sub.bounty_id)
                if bounty is None:
                    continue
                if bounty.creator_agent_id != f"agent_{agent_id}":
                    continue
                sub.status = "accepted"
                break
        elif operation == "create_observation":
            self._state.usage_observations.append(
                MockUsageObservation(
                    observation_id=self._next_observation_id(),
                    agent_id=f"agent_{agent_id}",
                    resource_id=opt_str(kwargs, "resource_id", "r1"),
                    version_id=opt_str(kwargs, "version_id", "v1"),
                    channel=opt_str(kwargs, "channel", "npx_skills"),
                    scope_id=opt_str(kwargs, "scope_id", "scope_repo"),
                    repository=opt_str(kwargs, "repository", ""),
                    event=opt_str(kwargs, "event", "resource_invoked"),
                )
            )
        elif operation == "create_pending_usage":
            self._state.pending_usage.append(
                MockPendingUsage(
                    pending_id=self._next_pending_id(),
                    agent_id=f"agent_{agent_id}",
                    resource_id=opt_str(kwargs, "resource_id", "r1"),
                    version_id=opt_str(kwargs, "version_id", "v1"),
                    repository=opt_str(kwargs, "repository", ""),
                )
            )
        elif operation == "create_resource_feedback":
            existing = [
                fb
                for fb in self._state.resource_feedback
                if fb.reporter_agent_id == f"agent_{agent_id}"
                and fb.resource_id == opt_str(kwargs, "resource_id", "r1")
                and fb.version_id == opt_str(kwargs, "version_id", "v1")
                and fb.task_class == opt_str(kwargs, "task_class", "")
            ]
            if existing:
                # Idempotent: return existing
                return
            self._state.resource_feedback.append(
                MockResourceFeedback(
                    id=self._next_feedback_id(),
                    resource_id=opt_str(kwargs, "resource_id", "r1"),
                    version_id=opt_str(kwargs, "version_id", "v1"),
                    reporter_agent_id=f"agent_{agent_id}",
                    rating=opt_int(kwargs, "rating", 4),
                    acquisition_channel=opt_str(
                        kwargs,
                        "acquisition_channel",
                        "npx_skills",
                    ),
                    installation_id=opt_str(kwargs, "installation_id", "i1"),
                    body=opt_str(kwargs, "body", ""),
                    task_class=opt_str(
                        kwargs,
                        "task_class",
                        "software-development",
                    ),
                    completed_task=opt_bool(
                        kwargs, "completed_task", default=True
                    ),
                    projection_disposition=opt_str(
                        kwargs,
                        "projection_disposition",
                        "not_a_course",
                    ),
                    course_review_id=opt_str(kwargs, "course_review_id"),
                )
            )
        elif operation == "project_feedback_to_course_review":
            for fb in self._state.resource_feedback:
                if (
                    fb.reporter_agent_id == f"agent_{agent_id}"
                    and fb.course_review_id is None
                ):
                    fb.course_review_id = opt_str(
                        kwargs,
                        "course_review_id",
                        "review_1",
                    )
                    fb.projection_disposition = "projected"
                    break

    def _next_feedback_id(self) -> str:
        return f"feedback_{len(self._state.resource_feedback)}"

    def _next_observation_id(self) -> str:
        return f"obs_{len(self._state.usage_observations)}"

    def _next_pending_id(self) -> str:
        return f"pending_{len(self._state.pending_usage)}"

    async def stop(self) -> None:
        pass
