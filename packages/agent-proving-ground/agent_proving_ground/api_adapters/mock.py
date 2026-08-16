from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

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


#: Signature every operation handler shares.
type _OperationHandler = Callable[..., None]


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

    async def query(
        self,
        world: World,  # noqa: ARG002
        query: JsonObject,
    ) -> JsonObject:
        """Answer one observed-effect query.

        Each query type is a method registered in ``_QUERIES``. This
        was one 500-line ``match`` with 42 cases; the dispatch table
        mirrors the convention LogionApiQueries already uses.
        """
        handler = self._QUERIES.get(str(query.get("type")))
        if handler is None:
            return {"error": "unknown query type"}
        return handler(self, query)

    def _q_course_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``course_exists`` observed-effect query."""
        status = query.get("status")
        owner = query.get("owner_agent")
        for course in self._state.courses.values():
            if status and course.status != status:
                continue
            if owner and course.owner_agent_id != f"agent_{owner}":
                continue
            return {"found": True, "course_id": course.id}
        return {"found": False}

    def _q_usage_report_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``usage_report_exists`` observed-effect query."""
        agent = query.get("agent")
        for report in self._state.usage_reports:
            if report.agent_id == f"agent_{agent}":
                return {"found": True, "report_id": report.id}
        return {"found": False}

    def _q_purchase_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``purchase_exists`` observed-effect query."""
        buyer = query.get("buyer_agent")
        for purchase in self._state.purchases:
            if purchase.buyer_agent_id == f"agent_{buyer}":
                return {"found": True, "purchase_id": purchase.id}
        return {"found": False}

    def _q_review_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``review_exists`` observed-effect query."""
        reviewer = query.get("reviewer_agent")
        for review in self._state.reviews:
            if review.reviewer_agent_id == f"agent_{reviewer}":
                return {"found": True, "review_id": review.id}
        return {"found": False}

    def _q_bounty_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``bounty_exists`` observed-effect query."""
        creator = query.get("creator_agent")
        status = query.get("status")
        for bounty in self._state.bounties.values():
            if creator and bounty.creator_agent_id != f"agent_{creator}":
                continue
            if status and bounty.status != status:
                continue
            return {"found": True, "bounty_id": bounty.id}
        return {"found": False}

    def _q_bounty_submission_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``bounty_submission_exists`` observed-effect query."""
        submitter = query.get("submitter_agent")
        for sub in self._state.bounty_submissions:
            if sub.submitter_agent_id == f"agent_{submitter}":
                return {"found": True, "submission_id": sub.id}
        return {"found": False}

    def _q_bounty_accepted(self, query: JsonObject) -> JsonObject:
        """Answer the ``bounty_accepted`` observed-effect query."""
        creator = query.get("creator_agent")
        submitter = query.get("submitter_agent")
        for sub in self._state.bounty_submissions:
            if sub.status != "accepted":
                continue
            bounty_or_none = self._state.bounties.get(sub.bounty_id)
            if bounty_or_none is None:
                continue
            bounty = bounty_or_none
            if creator and bounty.creator_agent_id != f"agent_{creator}":
                continue
            if submitter and sub.submitter_agent_id != f"agent_{submitter}":
                continue
            return {"found": True, "submission_id": sub.id}
        return {"found": False}

    def _q_no_double_credit_debit(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``no_double_credit_debit`` observed-effect query."""
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

    def _q_admin_state_observed(self, query: JsonObject) -> JsonObject:
        """Answer the ``admin_state_observed`` observed-effect query."""
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

    def _q_credit_balance_changed(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``credit_balance_changed`` observed-effect query."""
        return {"changed": True}

    def _q_course_remains_purchasable(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``course_remains_purchasable`` observed-effect query."""
        for course in self._state.courses.values():
            if course.status == "published":
                return {"purchasable": True, "course_id": course.id}
        return {"purchasable": False}

    def _q_source_link_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``source_link_exists`` observed-effect query."""
        course_id = query.get("course")
        if course_id and course_id in self._state.courses:
            return {
                "found": True,
                "course_id": course_id,
                "evidence": {"source": "mock"},
            }
        return {"found": False}

    def _q_bounty_submission_pr_opened(self, query: JsonObject) -> JsonObject:
        """Answer the ``bounty_submission_pr_opened`` observed-effect query."""
        return {
            "opened": True,
            "submission_id": query.get("submission") or "submission_1",
            "pr_url": "https://github.com/owner/repo/pull/1",
        }

    def _q_bounty_submission_accepted(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``bounty_submission_accepted`` observed-effect query."""
        return {"accepted": True}

    def _q_bounty_submission_rejected(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``bounty_submission_rejected`` observed-effect query."""
        return {"rejected": True}

    def _q_resource_projection_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``resource_projection_exists`` observed-effect query."""
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

    def _q_resource_backfill_complete(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``resource_backfill_complete`` observed-effect query."""
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

    def _q_resource_identity_unique(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``resource_identity_unique`` observed-effect query."""
        identities = [
            (r.resource_type, r.canonical_uri)
            for r in self._state.resources.values()
        ]
        return {"found": len(identities) == len(set(identities))}

    def _q_resource_backfill_idempotent(self, query: JsonObject) -> JsonObject:
        """Answer the ``resource_backfill_idempotent``
        observed-effect query.
        """
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

    def _q_resource_backfill_applied(self, query: JsonObject) -> JsonObject:
        """Answer the ``resource_backfill_applied`` observed-effect query."""
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

    def _q_resource_search_returns_kinds(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``resource_search_returns_kinds``
        observed-effect query.
        """
        kinds = query.get("projection_kinds")
        canonicals = elements(query, "canonicals")
        if (
            not isinstance(kinds, list)
            or not kinds
            or not all(isinstance(kind, str) and kind for kind in kinds)
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

    def _q_legacy_course_purchase_exists(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``legacy_course_purchase_exists``
        observed-effect query.
        """
        for purchase in self._state.purchases:
            return {"found": True, "purchase_id": purchase.id}
        return {"found": False}

    def _q_harness_scope_targets_resolved(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``harness_scope_targets_resolved``
        observed-effect query.
        """
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
        all_known = all(h in known_harnesses for h in harnesses) and all(
            s in known_scopes for s in scopes
        )
        return {
            "resolved": all_known,
            "harnesses": harnesses,
            "scopes": scopes,
        }

    def _q_resource_acquire_plan_dry_run(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``resource_acquire_plan_dry_run``
        observed-effect query.
        """
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
            "permissions_required": ("unknown-until-distribution-is-resolved"),
        }

    def _q_harness_scope_nested_repo(self, query: JsonObject) -> JsonObject:
        """Answer the ``harness_scope_nested_repo`` observed-effect query."""
        harnesses = elements(query, "harnesses")
        nested_repo = opt_str(query, "nested_repo", "")
        if not isinstance(harnesses, list) or not harnesses or not nested_repo:
            return {
                "nested": False,
                "unsupported": True,
                "reason": ("harnesses list and nested_repo are required"),
            }
        return {
            "nested": True,
            "harnesses": harnesses,
            "nested_repo": nested_repo,
        }

    def _q_harness_inventory_distinct_scopes(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``harness_inventory_distinct_scopes``
        observed-effect query.
        """
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

    def _q_resource_acquisition_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``resource_acquisition_exists`` observed-effect query."""
        return {
            "acquired": True,
            "resource_id": opt_str(query, "resource_id", "r"),
            "installation_id": "i",
            "verification": opt_str(query, "verification", "exact"),
            "channel": opt_str(query, "channel", "logion_bundle"),
        }

    def _q_resource_distribution_selected(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``resource_distribution_selected``
        observed-effect query.
        """
        channel = opt_str(query, "channel", "logion_bundle")
        allowed = elements(query, "allowed_channels")
        return {
            "selected": channel in allowed if allowed else True,
            "channel": channel,
            "distribution_id": opt_str(query, "distribution_id", "d"),
        }

    def _q_native_install_reconciled(self, query: JsonObject) -> JsonObject:
        """Answer the ``native_install_reconciled`` observed-effect query."""
        return {
            "reconciled": True,
            "matched_count": 1,
            "unresolved_count": 0,
            "ambiguous_count": 0,
            "drifted_count": 0,
            "channels": [opt_str(query, "expected_channel", "logion_bundle")],
        }

    def _q_inventory_receipt_matches(self, query: JsonObject) -> JsonObject:
        """Answer the ``inventory_receipt_matches`` observed-effect query."""
        iid = opt_str(query, "installation_id", "i")
        return {
            "matches": True,
            "installation_id": iid,
            "matched_ids": [iid],
        }

    def _q_installed_artifact_digest_matches(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``installed_artifact_digest_matches``
        observed-effect query.
        """
        return {
            "digest_matches": True,
            "content_digest": opt_str(query, "content_digest", ""),
            "computed_digest": opt_str(query, "content_digest", ""),
            "files": 1,
        }

    def _q_install_drift_reported(self, query: JsonObject) -> JsonObject:
        """Answer the ``install_drift_reported`` observed-effect query."""
        return {
            "drift_reported": True,
            "installation_id": opt_str(query, "installation_id", "i"),
            "drifted_count": 1,
        }

    def _q_scope_isolation_preserved(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``scope_isolation_preserved`` observed-effect query."""
        return {
            "isolated": True,
            "added": [],
            "removed": [],
            "changed": [],
        }

    def _q_acquisition_idempotent(self, query: JsonObject) -> JsonObject:
        """Answer the ``acquisition_idempotent`` observed-effect query."""
        iid = opt_str(query, "installation_id", "i")
        return {
            "idempotent": True,
            "first_installation_id": iid,
            "second_installation_id": iid,
        }

    def _q_observation_envelope_no_raw_data(
        self,
        query: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Answer the ``observation_envelope_no_raw_data``
        observed-effect query.
        """
        return {"clean": True}

    def _q_native_use_observed(self, query: JsonObject) -> JsonObject:
        """Answer the ``native_use_observed`` observed-effect query."""
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

    def _q_feedback_pending(self, query: JsonObject) -> JsonObject:
        """Answer the ``feedback_pending`` observed-effect query."""
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

    def _q_resource_feedback_exists(self, query: JsonObject) -> JsonObject:
        """Answer the ``resource_feedback_exists`` observed-effect query."""
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

    def _q_feedback_linked_to_acquisition(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``feedback_linked_to_acquisition``
        observed-effect query.
        """
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

    def _q_course_review_projection_exists(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``course_review_projection_exists``
        observed-effect query.
        """
        reporter = query.get("reporter_agent")
        for fb in self._state.resource_feedback:
            if (
                fb.reporter_agent_id == f"agent_{reporter}"
                and fb.course_review_id is not None
            ):
                return {
                    "found": True,
                    "feedback_id": fb.id,
                    "projection_disposition": fb.projection_disposition,
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

    def _q_raw_observation_not_uploaded(self, query: JsonObject) -> JsonObject:
        """Answer the ``raw_observation_not_uploaded``
        observed-effect query.
        """
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

    def _q_feedback_submission_idempotent(
        self, query: JsonObject
    ) -> JsonObject:
        """Answer the ``feedback_submission_idempotent``
        observed-effect query.
        """
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

    #: Query type -> handler. Defined after the methods so each
    #: name is already bound.
    _QUERIES: ClassVar[
        dict[str, Callable[[MockApiAdapter, JsonObject], JsonObject]]
    ] = {
        "course_exists": _q_course_exists,
        "usage_report_exists": _q_usage_report_exists,
        "purchase_exists": _q_purchase_exists,
        "review_exists": _q_review_exists,
        "bounty_exists": _q_bounty_exists,
        "bounty_submission_exists": _q_bounty_submission_exists,
        "bounty_accepted": _q_bounty_accepted,
        "no_double_credit_debit": _q_no_double_credit_debit,
        "admin_state_observed": _q_admin_state_observed,
        "credit_balance_changed": _q_credit_balance_changed,
        "course_remains_purchasable": _q_course_remains_purchasable,
        "source_link_exists": _q_source_link_exists,
        "bounty_submission_pr_opened": _q_bounty_submission_pr_opened,
        "bounty_submission_accepted": _q_bounty_submission_accepted,
        "bounty_submission_rejected": _q_bounty_submission_rejected,
        "resource_projection_exists": _q_resource_projection_exists,
        "resource_backfill_complete": _q_resource_backfill_complete,
        "resource_identity_unique": _q_resource_identity_unique,
        "resource_backfill_idempotent": _q_resource_backfill_idempotent,
        "resource_backfill_applied": _q_resource_backfill_applied,
        "resource_search_returns_kinds": _q_resource_search_returns_kinds,
        "legacy_course_purchase_exists": _q_legacy_course_purchase_exists,
        "harness_scope_targets_resolved": _q_harness_scope_targets_resolved,
        "resource_acquire_plan_dry_run": _q_resource_acquire_plan_dry_run,
        "harness_scope_nested_repo": _q_harness_scope_nested_repo,
        "harness_inventory_distinct_scopes": (
            _q_harness_inventory_distinct_scopes
        ),
        "resource_acquisition_exists": _q_resource_acquisition_exists,
        "resource_distribution_selected": _q_resource_distribution_selected,
        "native_install_reconciled": _q_native_install_reconciled,
        "inventory_receipt_matches": _q_inventory_receipt_matches,
        "installed_artifact_digest_matches": (
            _q_installed_artifact_digest_matches
        ),
        "install_drift_reported": _q_install_drift_reported,
        "scope_isolation_preserved": _q_scope_isolation_preserved,
        "acquisition_idempotent": _q_acquisition_idempotent,
        "observation_envelope_no_raw_data": (
            _q_observation_envelope_no_raw_data
        ),
        "native_use_observed": _q_native_use_observed,
        "feedback_pending": _q_feedback_pending,
        "resource_feedback_exists": _q_resource_feedback_exists,
        "feedback_linked_to_acquisition": _q_feedback_linked_to_acquisition,
        "course_review_projection_exists": _q_course_review_projection_exists,
        "raw_observation_not_uploaded": _q_raw_observation_not_uploaded,
        "feedback_submission_idempotent": _q_feedback_submission_idempotent,
    }

    def record_operation(
        self, agent_id: str, operation: str, **kwargs: JsonValue
    ) -> None:
        """Record one agent operation against the mock state.

        Each operation is a method registered in ``_OPERATIONS``,
        matching how ``query`` dispatches. Unknown operations are
        ignored: a scenario may exercise a surface this adapter does
        not model.
        """
        handler = self._OPERATIONS.get(operation)
        if handler is not None:
            handler(self, agent_id, **kwargs)

    def _op_backfill_resources(
        self,
        agent_id: str,  # noqa: ARG002
        **kwargs: JsonValue,  # noqa: ARG002
    ) -> None:
        """Record the ``backfill_resources`` operation."""
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

    def _op_create_usage_report(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``create_usage_report`` operation."""
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

    def _op_publish_course(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``publish_course`` operation."""
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

    def _op_purchase_course(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``purchase_course`` operation."""
        resolved_id = opt_str(kwargs, "course_id")
        if resolved_id is None:
            published = [
                c
                for c in self._state.courses.values()
                if c.status == "published"
            ]
            resolved_id = published[0].id if published else "course_fixture"
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

    def _op_create_review(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``create_review`` operation."""
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

    def _op_create_bounty(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``create_bounty`` operation."""
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

    def _op_fund_bounty(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``fund_bounty`` operation."""
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

    def _op_submit_bounty(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``submit_bounty`` operation."""
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

    def _op_accept_bounty_submission(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``accept_bounty_submission`` operation."""
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

    def _op_create_observation(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``create_observation`` operation."""
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

    def _op_create_pending_usage(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``create_pending_usage`` operation."""
        self._state.pending_usage.append(
            MockPendingUsage(
                pending_id=self._next_pending_id(),
                agent_id=f"agent_{agent_id}",
                resource_id=opt_str(kwargs, "resource_id", "r1"),
                version_id=opt_str(kwargs, "version_id", "v1"),
                repository=opt_str(kwargs, "repository", ""),
            )
        )

    def _op_create_resource_feedback(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``create_resource_feedback`` operation."""
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

    def _op_project_feedback_to_course_review(
        self,
        agent_id: str,
        **kwargs: JsonValue,
    ) -> None:
        """Record the ``project_feedback_to_course_review`` operation."""
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

    #: Operation name -> handler, defined after the methods so each
    #: name is already bound.
    _OPERATIONS: ClassVar[dict[str, _OperationHandler]] = {
        "backfill_resources": _op_backfill_resources,
        "create_usage_report": _op_create_usage_report,
        "publish_course": _op_publish_course,
        "purchase_course": _op_purchase_course,
        "create_review": _op_create_review,
        "create_bounty": _op_create_bounty,
        "fund_bounty": _op_fund_bounty,
        "submit_bounty": _op_submit_bounty,
        "accept_bounty_submission": _op_accept_bounty_submission,
        "create_observation": _op_create_observation,
        "create_pending_usage": _op_create_pending_usage,
        "create_resource_feedback": _op_create_resource_feedback,
        "project_feedback_to_course_review": (
            _op_project_feedback_to_course_review
        ),
    }

    def _next_feedback_id(self) -> str:
        return f"feedback_{len(self._state.resource_feedback)}"

    def _next_observation_id(self) -> str:
        return f"obs_{len(self._state.usage_observations)}"

    def _next_pending_id(self) -> str:
        return f"pending_{len(self._state.pending_usage)}"

    async def stop(self) -> None:
        pass
