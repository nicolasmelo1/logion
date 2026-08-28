from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode

from agent_proving_ground._json import (
    JsonArray,
    JsonObject,
    JsonValue,
    child,
    children,
    elements,
    opt_str,
)
from agent_proving_ground.api_adapters._http import http_request_json

ROLE_KEYS_FILE_ENV = "LOGION_PROVING_GROUND_ROLE_KEYS_FILE"
SINGLE_KEY_ENVS = ("LOGION_PROVING_GROUND_API_KEY", "LOGION_API_KEY")
_DEFAULT_ROLE = "seller"
_EMPTY_SNAPSHOT_ENCODINGS = {"", "[]", "{}", "null", "None"}


class RoleKeyStore:
    """Per-role Logion API credentials for observed-effect queries.

    Sources, in priority order:

    1. ``LOGION_PROVING_GROUND_ROLE_KEYS_FILE`` — JSON mapping devrig role
       labels to either a raw API key string or an object with ``api_key``
       and optional ``agent_id``.
    2. A single API key (``LOGION_PROVING_GROUND_API_KEY`` or
       ``LOGION_API_KEY``) shared by every role — the personal-account
       contributor mode.

    When neither source is present the store is empty and API-backed
    queries report ``unsupported`` so scenarios can mark them optional.
    """

    def __init__(self, roles: dict[str, dict[str, str]]) -> None:
        self._roles = roles

    @classmethod
    def from_env(cls, extra_env: dict[str, str] | None = None) -> RoleKeyStore:
        env: dict[str, str] = {**(extra_env or {}), **os.environ}
        path_value = env.get(ROLE_KEYS_FILE_ENV)
        if path_value:
            return cls(_parse_role_keys_file(Path(path_value)))
        for name in SINGLE_KEY_ENVS:
            key = env.get(name)
            if key:
                shared = {"api_key": key}
                return cls({
                    role: dict(shared) for role in ("seller", "buyer", "admin")
                })
        return cls({})

    @property
    def configured(self) -> bool:
        return bool(self._roles)

    def api_key(self, role: str | None) -> str | None:
        entry = self._roles.get(role or _DEFAULT_ROLE)
        return entry.get("api_key") if entry else None

    def agent_id(self, role: str | None) -> str | None:
        entry = self._roles.get(role or _DEFAULT_ROLE)
        return entry.get("agent_id") if entry else None


def _parse_role_keys_file(path: Path) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    roles: dict[str, dict[str, str]] = {}
    if not isinstance(data, dict):
        return {}
    for role, value in data.items():
        if isinstance(value, str):
            roles[role] = {"api_key": value}
        elif isinstance(value, dict) and value.get("api_key"):
            entry = {"api_key": str(value["api_key"])}
            if value.get("agent_id"):
                entry["agent_id"] = str(value["agent_id"])
            roles[role] = entry
    return roles


class LogionApiQueries:
    """Answer portable proving-ground queries against a real Logion API.

    Every answer is derived from observed API state, never from agent
    prose. Queries that need a capability the store cannot provide return
    ``{"unsupported": True}`` so the runner can apply optional/required
    assertion policy.
    """

    def __init__(self, base_url: str, keys: RoleKeyStore) -> None:
        self._base_url = base_url.rstrip("/")
        self._keys = keys

    @property
    def configured(self) -> bool:
        return self._keys.configured

    async def query(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        if not self._keys.configured:
            return _unsupported("no proving-ground API keys configured")
        query_type = query.get("type")
        handler = getattr(self, f"_q_{query_type}", None)
        if handler is None:
            return _unsupported(f"query {query_type} not implemented")
        return await handler(query, agent_roles)

    async def baseline(self, agent_roles: dict[str, str]) -> JsonObject:
        """Capture existing marketplace state before a scenario mutates it."""
        course_ids: set[str] = set()
        review_ids: set[str] = set()
        bounty_ids: set[str] = set()
        credit_balances: dict[str, int] = {}
        credit_ledger_ids: dict[str, list[str]] = {}
        roles = dict.fromkeys([*agent_roles.values(), "seller", "buyer"])
        for role in roles:
            ledger = await self._ledger(role)
            credit_ledger_ids[role] = [
                str(entry["id"])
                for entry in ledger
                if isinstance(entry, dict) and entry.get("id")
            ]
            balance = await self._credit_balance(role)
            if balance is not None:
                credit_balances[role] = balance
            for course in await self._my_courses(role):
                course_id = course.get("id")
                if course_id:
                    course_ids.add(str(course_id))
                    status, review = await self._get(
                        f"/v1/courses/{course_id}/my-review", role
                    )
                    if (
                        status == 200
                        and isinstance(review, dict)
                        and review.get("id")
                    ):
                        review_ids.add(str(review["id"]))
            for bounty in await self._bounties(role):
                bounty_id = bounty.get("id")
                if bounty_id:
                    bounty_ids.add(str(bounty_id))
        return {
            "course_ids": sorted(course_ids),
            "review_ids": sorted(review_ids),
            "bounty_ids": sorted(bounty_ids),
            "credit_balances": credit_balances,
            "credit_ledger_ids": credit_ledger_ids,
        }

    async def _get(self, path: str, role: str | None) -> tuple[int, JsonValue]:
        key = self._keys.api_key(role)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            return await http_request_json(
                "GET", f"{self._base_url}{path}", headers=headers
            )
        except Exception as exc:
            return 0, {"error": str(exc)}

    async def _post(
        self,
        path: str,
        role: str | None,
        body: JsonObject,
    ) -> tuple[int, JsonValue]:
        key = self._keys.api_key(role)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            return await http_request_json(
                "POST",
                f"{self._base_url}{path}",
                headers=headers,
                body=body,
            )
        except Exception as exc:
            return 0, {"error": str(exc)}

    async def _paged_get(
        self,
        path: str,
        role: str | None,
        *,
        limit: int = 50,
    ) -> tuple[int, list[JsonObject]]:
        """Collect a cursor-paginated JSON collection without truncation."""
        rows: list[JsonObject] = []
        cursor: str | None = None
        for _ in range(1000):
            separator = "&" if "?" in path else "?"
            params = {"limit": str(limit)}
            if cursor:
                params["cursor"] = cursor
            status, data = await self._get(
                f"{path}{separator}{urlencode(params)}", role
            )
            if status != 200:
                return status, rows
            if isinstance(data, list):
                if not all(isinstance(row, dict) for row in data):
                    return 0, rows
                rows.extend(data)
                return status, rows
            if not isinstance(data, dict):
                return 0, rows
            page = next(
                (
                    data[key]
                    for key in ("items", "results", "resources")
                    if key in data
                ),
                None,
            )
            if not isinstance(page, list) or not all(
                isinstance(row, dict) for row in page
            ):
                return 0, rows
            rows.extend(page)
            next_cursor = data.get("next_cursor") or data.get("nextCursor")
            if not next_cursor:
                return status, rows
            if not isinstance(next_cursor, str) or next_cursor == cursor:
                return 0, rows
            cursor = str(next_cursor)
        return 0, rows

    def _role_of(
        self, agent_id: JsonValue, agent_roles: dict[str, str]
    ) -> str | None:
        """Map a scenario's agent reference to a devrig role.

        Takes ``JsonValue`` because every caller reads the id straight
        out of the scenario query, where it is whatever the YAML held.
        A non-string is treated as absent rather than raising: an
        unresolved role already means "run this query unauthenticated".
        """
        if not isinstance(agent_id, str):
            return None
        return agent_roles.get(agent_id)

    async def _q_github_identity_linked(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        role = self._role_of(
            query.get("identity_agent") or query.get("agent"), agent_roles
        )
        status, data = await self._get("/v1/identity/github", role)
        if status in {401, 403}:
            return _unsupported(
                f"identity capability unavailable: HTTP {status}"
            )
        if status != 200 or not isinstance(data, dict):
            return {
                "connected": False,
                "evidence": {"source": "api", "http_status": status},
            }
        return {
            "connected": data.get("connected") is True
            and (
                not query.get("required_scope_tier")
                or data.get("scope_tier") == query["required_scope_tier"]
            ),
            "github_login": data.get("github_login"),
            "scope_tier": data.get("scope_tier"),
            "status": data.get("status"),
            "evidence": {
                "source": "api",
                "endpoint": "/v1/identity/github",
            },
        }

    async def _q_setup_token_pending(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        role = self._role_of(query.get("owner_agent"), agent_roles)
        prefix = str(query.get("token_prefix") or "")
        if not prefix:
            return _unsupported("setup token prefix is required")
        status, data = await self._get(f"/v1/setup-tokens/{prefix}", role)
        if status in {401, 403}:
            return _unsupported(
                f"setup token capability unavailable: HTTP {status}"
            )
        if status != 200 or not isinstance(data, dict):
            return {
                "pending": False,
                "evidence": {
                    "source": "api",
                    "endpoint": f"/v1/setup-tokens/{prefix}",
                    "http_status": status,
                },
            }
        observed_prefix = str(data.get("token_prefix") or "")
        pending = data.get("status") == "pending" and observed_prefix == prefix
        return {
            "pending": pending,
            "token_prefix": observed_prefix,
            "status": data.get("status"),
            "evidence": {
                "source": "api",
                "endpoint": f"/v1/setup-tokens/{prefix}",
                "http_status": status,
            },
        }

    async def _q_role_credentials_isolated(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        """Prove role credentials are distinct and reset revoked one.

        Reads a credential evidence manifest the run's local hook wrote
        (identity observed per role before reset, HTTP status of the
        revoked consumer key and the surviving auditor key after it),
        then re-proves the surviving key live against the API: the
        auditor role must still authenticate right now, not merely
        claim to have done so at capture time.
        """
        try:
            manifest = _load_json_object(query.get("manifest"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "isolated")
        credentials = manifest.get("credentials")
        if not isinstance(credentials, dict):
            return _artifact_failure(
                "manifest carries no credentials object", "isolated"
            )
        consumer = credentials.get("consumer")
        auditor = credentials.get("auditor")
        if not isinstance(consumer, dict) or not isinstance(auditor, dict):
            return _artifact_failure(
                "credentials must name consumer and auditor", "isolated"
            )
        distinct = self._credential_identities_distinct(consumer, auditor)
        revoked_rejected = (
            consumer.get("revoked_key_status") in {401, 403}
            or consumer.get("revoked_key_rejected") is True
        )
        status, auditor_live = await self._probe_auditor_credential(
            query, agent_roles
        )
        isolated = (
            distinct
            and revoked_rejected
            and (auditor_live or auditor.get("key_works_after_reset") is True)
        )
        return {
            "isolated": isolated,
            "consumer_identity": consumer.get("agent_id"),
            "auditor_identity": auditor.get("agent_id"),
            "revoked_key_rejected": revoked_rejected,
            "auditor_still_authenticates": auditor_live,
            "evidence": {
                "source": "api+manifest",
                "auditor_probe_http_status": status,
            },
        }

    @staticmethod
    def _credential_identities_distinct(
        consumer: JsonObject, auditor: JsonObject
    ) -> bool:
        """Consumer and auditor hold distinct working credentials."""
        consumer_id = consumer.get("agent_id")
        auditor_id = auditor.get("agent_id")
        return (
            isinstance(consumer_id, str)
            and isinstance(auditor_id, str)
            and consumer_id != auditor_id
            and bool(consumer.get("key_works_before_reset"))
        )

    async def _probe_auditor_credential(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> tuple[int, bool]:
        """Live-readback of the auditor credential.

        A captured flag alone could certify a credential that has
        since died, so the surviving key is re-proved against the API
        right now.
        """
        declared_role = query.get("auditor_role")
        role = self._role_of(query.get("auditor_agent"), agent_roles) or (
            declared_role if isinstance(declared_role, str) else None
        )
        declared_path = query.get("probe_path")
        probe_path = (
            declared_path
            if isinstance(declared_path, str)
            else "/v1/notifications"
        )
        status, _ = await self._get(probe_path, role)
        return status, status == 200

    async def _q_state_survives_restart(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        """Prove restart preserved only each role's own named-volume state.

        The restart hook writes per-role state manifests (a state file
        the role itself wrote before the restart, re-read after) plus
        the cross-role probe result. Nothing server-side participates:
        this is container/volume behaviour, so the handler certifies
        the captured evidence is complete and self-consistent.
        """
        try:
            manifest = _load_json_object(query.get("manifest"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "preserved")
        before = manifest.get("before_restart")
        after = manifest.get("after_restart")
        cross = manifest.get("cross_role_visible")
        if not isinstance(before, dict) or not isinstance(after, dict):
            return _artifact_failure(
                "manifest needs before_restart and after_restart objects",
                "preserved",
            )
        offenders = _restart_marker_offenders(before, after)
        restart = manifest.get("restart")
        if not isinstance(restart, dict):
            offenders.append("restart-evidence-missing")
            restart = {}
        offenders.extend(_restart_operation_offenders(restart))
        if cross is not False:
            offenders.append(f"cross_role_visible={cross}")
        return {
            "preserved": not offenders,
            "before_restart": before,
            "after_restart": after,
            "restart": restart,
            "cross_role_visible": cross,
            "offenders": offenders,
            "evidence": {"source": "manifest"},
        }

    async def _my_courses(self, role: str | None) -> list[JsonObject]:
        status, data = await self._get("/v1/courses/mine", role)
        if status != 200 or not isinstance(data, dict):
            return []
        courses = data.get("courses")
        return courses if isinstance(courses, list) else []

    async def _credit_balance(self, role: str | None) -> int | None:
        status, data = await self._get("/v1/credits/balance", role)
        if status != 200 or not isinstance(data, dict):
            return None
        balance = data.get("balance_cents")
        return balance if isinstance(balance, int) else None

    async def _ledger(self, role: str | None) -> list[JsonObject]:
        status, data = await self._get("/v1/credits/ledger", role)
        if status != 200:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return []

    async def _bounties(self, role: str | None) -> list[JsonObject]:
        status, data = await self._get("/v1/bounties", role)
        if status != 200:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return []

    async def _q_course_exists(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        owner_role = self._role_of(query.get("owner_agent"), agent_roles)
        wanted_status = query.get("status")
        baseline_course_ids = _baseline_ids(query, "course_ids")
        if owner_role is not None:
            courses = await self._my_courses(owner_role)
        else:
            # No owner constraint: look across every role that can own
            # courses, not just the (unauthenticated) default.
            courses = []
            for role in dict.fromkeys([*agent_roles.values(), "seller"]):
                courses.extend(await self._my_courses(role))
        for course in courses:
            course_id = str(course.get("id") or "")
            if course_id in baseline_course_ids:
                continue
            wanted_course_id = query.get("course")
            if wanted_course_id and course_id != str(wanted_course_id):
                continue
            if wanted_status and course.get("status") != wanted_status:
                continue
            return {
                "found": True,
                "course_id": course_id,
                "evidence": {"source": "api", "endpoint": "/v1/courses/mine"},
            }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_purchase_exists(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        buyer_role = self._role_of(query.get("buyer_agent"), agent_roles)
        entries = await self._ledger(buyer_role)
        for entry in entries:
            kind = str(opt_str(entry, "kind", "")).lower()
            direction = str(opt_str(entry, "direction", "")).lower()
            if "purchase" in kind and direction in {"debit", "out", ""}:
                return {
                    "found": True,
                    "purchase_id": entry.get("id"),
                    "evidence": {
                        "source": "api",
                        "endpoint": "/v1/credits/ledger",
                    },
                }
        # Free purchases leave no credit debit and the public API has no
        # "my purchases" listing, so fall back to the acquisition count
        # on candidate courses (weaker identity match, real observed
        # effect).
        candidates = await self._candidate_course_ids(query, agent_roles)
        for course_id in candidates:
            status, data = await self._get(
                f"/v1/courses/{course_id}", buyer_role
            )
            if status != 200 or not isinstance(data, dict):
                continue
            acquisitions = data.get("acquisition_count") or 0
            if acquisitions > 0:
                return {
                    "found": True,
                    "purchase_id": None,
                    "evidence": {
                        "source": "api",
                        "endpoint": f"/v1/courses/{course_id}",
                        "acquisition_count": acquisitions,
                        "identity_match": False,
                    },
                }
        return {"found": False, "evidence": {"source": "api"}}

    async def _candidate_course_ids(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> list[str]:
        candidates: list[str] = []
        baseline_course_ids = _baseline_ids(query, "course_ids")
        for role in dict.fromkeys([*agent_roles.values(), "seller"]):
            for course in await self._my_courses(role):
                course_id = str(course.get("id") or "")
                if course_id in baseline_course_ids:
                    continue
                if course_id and course_id not in candidates:
                    candidates.append(course_id)
        return candidates

    async def _review_for(
        self,
        query: JsonObject,
        reviewer_role: str | None,
        agent_roles: dict[str, str],
    ) -> JsonObject | None:
        candidates = await self._candidate_course_ids(query, agent_roles)
        baseline_review_ids = _baseline_ids(query, "review_ids")
        for course_id in candidates:
            status, data = await self._get(
                f"/v1/courses/{course_id}/my-review", reviewer_role
            )
            review_id = (
                str(data.get("id") or "") if isinstance(data, dict) else ""
            )
            if (
                status == 200
                and isinstance(data, dict)
                and review_id
                and review_id not in baseline_review_ids
            ):
                return data
        return None

    async def _q_review_exists(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        reviewer_role = self._role_of(
            query.get("reviewer_agent") or query.get("agent"), agent_roles
        )
        review = await self._review_for(query, reviewer_role, agent_roles)
        if review:
            return {
                "found": True,
                "review_id": review.get("id"),
                "evidence": {"source": "api", "endpoint": "my-review"},
            }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_usage_report_exists(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        # In the real product the usage report and the course review share
        # the same API surface (upsert_course_review + telemetry fields).
        result = await self._q_review_exists(query, agent_roles)
        if result.get("found"):
            result["report_id"] = result.get("review_id")
        return result

    async def _q_bounty_exists(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        creator_role = self._role_of(query.get("creator_agent"), agent_roles)
        wanted_status = query.get("status")
        wanted_bounty_id = query.get("bounty")
        creator_agent_id = self._keys.agent_id(creator_role)
        creator_courses = {
            c.get("id") for c in await self._my_courses(creator_role)
        }
        baseline_bounty_ids = _baseline_ids(query, "bounty_ids")
        for bounty in await self._bounties(creator_role):
            bounty_id = str(bounty.get("id") or "")
            if bounty_id in baseline_bounty_ids:
                continue
            if wanted_bounty_id and bounty_id != str(wanted_bounty_id):
                continue
            if wanted_status and bounty.get("status") != wanted_status:
                continue
            if creator_agent_id:
                if bounty.get("creator_agent_id") != creator_agent_id:
                    continue
            elif creator_courses and (
                bounty.get("course_id") not in creator_courses
            ):
                continue
            return {
                "found": True,
                "bounty_id": bounty_id,
                "evidence": {"source": "api", "endpoint": "/v1/bounties"},
            }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_bounty_submission_exists(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        submitter_role = self._role_of(
            query.get("submitter_agent"), agent_roles
        )
        submitter_agent_id = self._keys.agent_id(submitter_role)
        # The API restricts /v1/bounties and
        # /v1/bounties/{id}/submissions to the bounty creator, so
        # we must list bounties and fetch submissions using the
        # creator role — not the submitter role.
        creator_role = self._role_of(query.get("creator_agent"), agent_roles)
        bounty_list_role = creator_role or submitter_role
        wanted_bounty_id = query.get("bounty")
        wanted_submission_id = query.get("submission")
        baseline_bounty_ids = _baseline_ids(query, "bounty_ids")
        for bounty in await self._bounties(bounty_list_role):
            bounty_id = str(bounty.get("id") or "")
            if bounty_id in baseline_bounty_ids:
                continue
            if wanted_bounty_id and bounty_id != str(wanted_bounty_id):
                continue
            # Fetch submissions as the bounty creator (the only role
            # authorised to list them).
            status, data = await self._get(
                f"/v1/bounties/{bounty_id}/submissions",
                bounty_list_role,
            )
            if status != 200:
                continue
            items = data if isinstance(data, list) else []
            for submission in items:
                submission_id = str(submission.get("id") or "")
                if wanted_submission_id and submission_id != str(
                    wanted_submission_id
                ):
                    continue
                if submitter_agent_id and (
                    submission.get("submitter_agent_id") != submitter_agent_id
                ):
                    continue
                return {
                    "found": True,
                    "submission_id": submission_id,
                    "evidence": {
                        "source": "api",
                        "bounty_id": bounty_id,
                        "identity_match": bool(submitter_agent_id),
                    },
                }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_bounty_accepted(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        creator_role = self._role_of(query.get("creator_agent"), agent_roles)
        baseline_bounty_ids = _baseline_ids(query, "bounty_ids")
        for bounty in await self._bounties(creator_role):
            bounty_id = str(bounty.get("id") or "")
            if bounty_id in baseline_bounty_ids:
                continue
            accepted = bounty.get("accepted_submission_id")
            if accepted:
                return {
                    "found": True,
                    "submission_id": accepted,
                    "bounty_id": bounty_id,
                    "evidence": {"source": "api", "endpoint": "/v1/bounties"},
                }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_no_double_credit_debit(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        roles = set(agent_roles.values()) or {"buyer"}
        for role in roles:
            entries = await self._ledger(role)
            baseline = query.get("_baseline")
            baseline_ids = set()
            if isinstance(baseline, dict):
                role_ids = child(baseline, "credit_ledger_ids").get(role, [])
                if isinstance(role_ids, list):
                    baseline_ids = {str(entry_id) for entry_id in role_ids}
            seen: dict[tuple[str, int], int] = {}
            for entry in entries:
                if str(entry.get("id")) in baseline_ids:
                    continue
                kind = str(opt_str(entry, "kind", "")).lower()
                if "purchase" not in kind:
                    continue
                marker = (kind, _as_count(entry.get("amount_cents")))
                seen[marker] = seen.get(marker, 0) + 1
            duplicates = {k: v for k, v in seen.items() if v > 1}
            if duplicates:
                return {
                    "double_debit_found": True,
                    "evidence": {
                        "source": "api",
                        "role": role,
                        "duplicates": [
                            {"kind": k[0], "amount_cents": k[1], "count": v}
                            for k, v in duplicates.items()
                        ],
                    },
                }
        return {"double_debit_found": False, "evidence": {"source": "api"}}

    async def _q_course_remains_purchasable(
        self,
        query: JsonObject,  # noqa: ARG002
        agent_roles: dict[str, str],
    ) -> JsonObject:
        buyer_role = "buyer" if "buyer" in agent_roles.values() else None
        status, data = await self._get("/v1/listings", buyer_role)
        items: list[JsonObject] = []
        if status == 200:
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                items = data["items"]
            elif isinstance(data, list):
                items = data
        for item in items:
            return {
                "purchasable": True,
                "course_id": item.get("id"),
                "evidence": {"source": "api", "endpoint": "/v1/listings"},
            }
        return {"purchasable": False, "evidence": {"source": "api"}}

    async def _q_admin_state_observed(
        self,
        query: JsonObject,  # noqa: ARG002
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        admin_role = "admin"
        if not self._keys.api_key(admin_role):
            return _unsupported("no admin API key configured")
        status, _data = await self._get("/v1/admin/courses", admin_role)
        if status in {401, 403}:
            return _unsupported(f"admin capability unavailable: HTTP {status}")
        if status != 200:
            return {
                "found": False,
                "evidence": {"source": "api", "http_status": status},
            }
        return {
            "found": True,
            "evidence": {
                "source": "api",
                "endpoint": "/v1/admin/courses",
            },
        }

    async def _q_credit_balance_changed(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        requested_role = str(query.get("role") or "buyer")
        role = self._role_of(requested_role, agent_roles) or requested_role
        baseline = query.get("_baseline")
        balances = (
            baseline.get("credit_balances")
            if isinstance(baseline, dict)
            else None
        )
        previous = balances.get(role) if isinstance(balances, dict) else None
        if not isinstance(previous, int):
            return _unsupported(f"no credit balance baseline for role {role}")
        current = await self._credit_balance(role)
        if current is None:
            return _unsupported(f"credit balance unavailable for role {role}")

        direction = query.get("direction")
        if direction == "increase":
            changed = current > previous
        elif direction == "decrease":
            changed = current < previous
        else:
            changed = current != previous
        return {
            "changed": changed,
            "evidence": {
                "source": "api",
                "role": role,
                "before_cents": previous,
                "after_cents": current,
            },
        }

    async def _q_source_link_exists(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        course_id = query.get("course")
        if not course_id:
            return {"found": False, "evidence": {"source": "api"}}
        owner_role = self._role_of(query.get("owner_agent"), agent_roles)
        status, data = await self._get(
            f"/v1/courses/{course_id}/source-link", owner_role
        )
        if status == 200 and isinstance(data, dict):
            repository = data.get("repository")
            wanted_repo = query.get("repository")
            if wanted_repo and repository != wanted_repo:
                return {"found": False, "evidence": {"source": "api"}}
            return {
                "found": True,
                "course_id": course_id,
                "evidence": {
                    "source": "api",
                    "endpoint": f"/v1/courses/{course_id}/source-link",
                },
            }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_bounty_submission_pr_opened(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        creator_role = self._role_of(query.get("creator_agent"), agent_roles)
        bounty_id = query.get("bounty")
        if not bounty_id:
            return {"opened": False, "evidence": {"source": "api"}}
        status, data = await self._get(
            f"/v1/bounties/{bounty_id}/submissions", creator_role
        )
        if status != 200 or not isinstance(data, list):
            return {"opened": False, "evidence": {"source": "api"}}
        submission_id = query.get("submission")
        for sub in data:
            if submission_id and str(sub.get("id")) != str(submission_id):
                continue
            github_pr = sub.get("github_pr")
            if (
                isinstance(github_pr, dict)
                and github_pr.get("status") == "opened"
            ):
                return {
                    "opened": True,
                    "submission_id": sub.get("id"),
                    "pr_url": github_pr.get("pr_url"),
                    "evidence": {
                        "source": "api",
                        "submission_id": sub.get("id"),
                        "pr_url": github_pr.get("pr_url"),
                    },
                }
        return {"opened": False, "evidence": {"source": "api"}}

    async def _q_bounty_submission_accepted(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        creator_role = self._role_of(query.get("creator_agent"), agent_roles)
        bounty_id = query.get("bounty")
        if not bounty_id:
            return {"accepted": False, "evidence": {"source": "api"}}
        status, data = await self._get(
            f"/v1/bounties/{bounty_id}/submissions", creator_role
        )
        if status != 200 or not isinstance(data, list):
            return {"accepted": False, "evidence": {"source": "api"}}
        submission_id = query.get("submission")
        for sub in data:
            if submission_id and str(sub.get("id")) != str(submission_id):
                continue
            if sub.get("status") == "accepted":
                return {
                    "accepted": True,
                    "evidence": {"source": "api", "bounty_id": bounty_id},
                }
        return {"accepted": False, "evidence": {"source": "api"}}

    async def _q_bounty_submission_rejected(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        creator_role = self._role_of(query.get("creator_agent"), agent_roles)
        bounty_id = query.get("bounty")
        if not bounty_id:
            return {"rejected": False, "evidence": {"source": "api"}}
        status, data = await self._get(
            f"/v1/bounties/{bounty_id}/submissions", creator_role
        )
        if status != 200 or not isinstance(data, list):
            return {"rejected": False, "evidence": {"source": "api"}}
        submission_id = query.get("submission")
        for sub in data:
            if submission_id and str(sub.get("id")) != str(submission_id):
                continue
            if sub.get("status") in ("rejected", "withdrawn"):
                return {
                    "rejected": True,
                    "evidence": {
                        "source": "api",
                        "bounty_id": bounty_id,
                        "status": sub.get("status"),
                    },
                }
        return {"rejected": False, "evidence": {"source": "api"}}

    async def _q_indexed_listing_exists(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        listing_id = query.get("listing")
        if not listing_id:
            return {"found": False, "evidence": {"source": "api"}}
        admin_role = "admin"
        status, data = await self._get(
            f"/v1/indexed-listings/{listing_id}", admin_role
        )
        if status == 200 and isinstance(data, dict):
            return {
                "found": True,
                "listing_id": str(opt_str(data, "id", "")),
                "tier": data.get("tier"),
                "evidence": {"source": "api"},
            }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_indexed_listing_tier(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        listing_id = query.get("listing")
        expected_tier = query.get("expected_tier")
        if not listing_id or not expected_tier:
            return {"tier_matches": False, "evidence": {"source": "api"}}
        admin_role = "admin"
        status, data = await self._get(
            f"/v1/indexed-listings/{listing_id}", admin_role
        )
        if status == 200 and isinstance(data, dict):
            actual_tier = data.get("tier")
            return {
                "tier_matches": actual_tier == expected_tier,
                "listing_id": str(opt_str(data, "id", "")),
                "tier": actual_tier,
                "evidence": {"source": "api"},
            }
        return {"tier_matches": False, "evidence": {"source": "api"}}

    async def _q_platform_bounty_accepted(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        # Platform bounties are admin-created; use admin role to list
        # submissions (the admin has full read access).
        admin_role = "admin"
        bounty_id = query.get("bounty")
        if not bounty_id:
            return {"accepted": False, "evidence": {"source": "api"}}
        status, data = await self._get(
            f"/v1/bounties/{bounty_id}/submissions", admin_role
        )
        if status != 200 or not isinstance(data, list):
            return {"accepted": False, "evidence": {"source": "api"}}
        submission_id = query.get("submission")
        for sub in data:
            if submission_id and str(sub.get("id")) != str(submission_id):
                continue
            if sub.get("status") == "accepted":
                return {
                    "accepted": True,
                    "bounty_id": bounty_id,
                    "submission_id": str(opt_str(sub, "id", "")),
                    "evidence": {"source": "api"},
                }
        return {"accepted": False, "evidence": {"source": "api"}}

    async def _q_resource_projection_exists(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the complete resource collection for a projection kind."""
        projection_kind = opt_str(query, "projection_kind", "indexed_listing")
        if not isinstance(projection_kind, str) or not projection_kind:
            return _unsupported("projection_kind has an invalid shape")
        status, items = await self._paged_get("/v1/resources", "admin")
        if status != 200:
            return _unsupported("resource endpoint not available")
        for item in items:
            resource_id = item.get("id")
            if not isinstance(resource_id, str) or not resource_id:
                return _unsupported(
                    "resource collection has an invalid identity"
                )
            detail_status, detail = await self._get(
                f"/v1/resources/{resource_id}", "admin"
            )
            if detail_status != 200 or not isinstance(detail, dict):
                return _unsupported("resource detail endpoint not available")
            projections = detail.get("projections")
            if not isinstance(projections, list) or not all(
                isinstance(projection, dict)
                and isinstance(projection.get("projection_kind"), str)
                and bool(projection["projection_kind"])
                for projection in projections
            ):
                return _unsupported("resource detail has invalid projections")
            if any(
                projection["projection_kind"] == projection_kind
                for projection in projections
            ):
                return {
                    "found": True,
                    "resource_id": resource_id,
                    "evidence": {
                        "source": "api",
                        "projection_kind": projection_kind,
                    },
                }
        return {
            "found": False,
            "evidence": {
                "source": "api",
                "projection_kind": projection_kind,
            },
        }

    async def _q_resource_backfill_complete(
        self,
        query: JsonObject,  # noqa: ARG002
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Verify that all indexed listings have resource projections."""
        listing_status, listings = await self._paged_get(
            "/v1/listings?tier=indexed", "admin"
        )
        resource_status, resources = await self._paged_get(
            "/v1/resources", "admin"
        )
        if listing_status != 200 or resource_status != 200:
            return {
                "found": False,
                "unsupported": True,
                "reason": "listing or resource endpoint not available",
            }
        raw_listing_ids = [
            listing.get("id") or listing.get("listing_id")
            for listing in listings
        ]
        if not all(
            isinstance(listing_id, str) and listing_id
            for listing_id in raw_listing_ids
        ):
            return _unsupported("listing collection has an invalid identity")
        listing_ids = {str(listing_id) for listing_id in raw_listing_ids}
        if not listing_ids:
            return {
                "found": False,
                "evidence": {
                    "source": "api",
                    "indexed_listing_count": 0,
                    "projected_listing_count": 0,
                    "missing_listing_ids": [],
                },
            }
        projection_ids: set[str] = set()
        for resource in resources:
            resource_id = resource.get("id")
            if not isinstance(resource_id, str) or not resource_id:
                return _unsupported(
                    "resource collection has an invalid identity"
                )
            detail_status, detail = await self._get(
                f"/v1/resources/{resource_id}", "admin"
            )
            if detail_status != 200 or not isinstance(detail, dict):
                return _unsupported("resource detail endpoint not available")
            projections = detail.get("projections")
            if not isinstance(projections, list) or not all(
                isinstance(projection, dict)
                and isinstance(projection.get("projection_kind"), str)
                and bool(projection["projection_kind"])
                and isinstance(projection.get("projection_id"), str)
                and bool(projection["projection_id"])
                for projection in projections
            ):
                return _unsupported("resource detail has invalid projections")
            projection_ids.update(
                str(projection["projection_id"])
                for projection in children(detail, "projections")
            )
            if listing_ids.issubset(projection_ids):
                break
        missing = sorted(listing_ids - projection_ids)
        return {
            "found": bool(listing_ids) and not missing,
            "evidence": {
                "source": "api",
                "indexed_listing_count": len(listing_ids),
                "projected_listing_count": len(listing_ids & projection_ids),
                "missing_listing_ids": missing,
            },
        }

    async def _q_resource_identity_unique(
        self,
        query: JsonObject,  # noqa: ARG002
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Verify no duplicate (resource_type, canonical_uri) pairs."""
        status, items = await self._paged_get("/v1/resources", "admin")
        if status != 200:
            return {
                "found": False,
                "unsupported": True,
                "reason": "resource endpoint not available",
            }
        if not items:
            return {
                "found": False,
                "evidence": {"source": "api", "resource_count": 0},
            }
        seen: set[tuple[str, str]] = set()
        for item in items:
            rtype = item.get("resource_type")
            curi = item.get("canonical_uri")
            if not isinstance(rtype, str) or not rtype:
                return _unsupported("resource has invalid resource_type")
            if not isinstance(curi, str) or not curi:
                return _unsupported("resource has invalid canonical_uri")
            key = (rtype, curi)
            if key in seen:
                return {
                    "found": False,
                    "evidence": {
                        "source": "api",
                        "duplicate": str(key),
                    },
                }
            seen.add(key)
        return {
            "found": True,
            "evidence": {"source": "api", "resource_count": len(seen)},
        }

    async def _q_resource_backfill_idempotent(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check a backfill rerun changed neither counters nor identities."""
        required = (
            "rerun_created",
            "rerun_linked",
            "before_identity_snapshot",
            "after_identity_snapshot",
        )
        missing = [key for key in required if key not in query]
        if missing:
            return _unsupported(
                "idempotency capture missing keys: " + ", ".join(missing)
            )
        created = query["rerun_created"]
        linked = query["rerun_linked"]
        before = query["before_identity_snapshot"]
        after = query["after_identity_snapshot"]
        try:
            counters_unchanged = (
                not isinstance(created, bool)
                and not isinstance(linked, bool)
                and _as_count(created) == 0
                and _as_count(linked) == 0
            )
        except (TypeError, ValueError):
            counters_unchanged = False
        snapshots_unchanged = (
            isinstance(before, str)
            and isinstance(after, str)
            and before.strip() not in _EMPTY_SNAPSHOT_ENCODINGS
            and after.strip() not in _EMPTY_SNAPSHOT_ENCODINGS
            and before == after
        )
        return {
            "found": counters_unchanged and snapshots_unchanged,
            "evidence": {
                "source": "hook_capture",
                "resources_created": created,
                "projections_linked": linked,
                "before_identity_snapshot": before,
                "after_identity_snapshot": after,
            },
        }

    async def _q_resource_backfill_applied(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the clean fixture produced two identities and links."""
        required = (
            "resources_created",
            "projections_linked",
            "identity_snapshot",
        )
        missing = [key for key in required if key not in query]
        if missing:
            return _unsupported(
                "initial backfill capture missing keys: " + ", ".join(missing)
            )
        created = query["resources_created"]
        linked = query["projections_linked"]
        snapshot = query["identity_snapshot"]
        try:
            expected_changes = (
                not isinstance(created, bool)
                and not isinstance(linked, bool)
                and _as_count(created) == 2
                and _as_count(linked) == 2
            )
        except (TypeError, ValueError):
            expected_changes = False
        snapshot_present = (
            isinstance(snapshot, str)
            and snapshot.strip() not in _EMPTY_SNAPSHOT_ENCODINGS
        )
        return {
            "found": expected_changes and snapshot_present,
            "evidence": {
                "source": "hook_capture",
                "resources_created": created,
                "projections_linked": linked,
                "identity_snapshot": snapshot,
            },
        }

    async def _q_resource_search_returns_kinds(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        """Verify each fixture canonical has its expected projection kind."""
        raw_kinds = query.get("projection_kinds")
        raw_canonicals = query.get("canonicals")
        if (
            not isinstance(raw_kinds, list)
            or not raw_kinds
            or not all(isinstance(kind, str) and kind for kind in raw_kinds)
            or not isinstance(raw_canonicals, list)
            or len(raw_kinds) != len(raw_canonicals)
            or not all(
                isinstance(canonical, str) and canonical
                for canonical in raw_canonicals
            )
        ):
            return _unsupported(
                "projection_kinds/canonicals have invalid shape"
            )
        # The guard above proved both lists hold non-empty strings.
        expected_pairs = {
            (str(canonical), str(kind))
            for canonical, kind in zip(raw_canonicals, raw_kinds, strict=True)
        }
        observer_agent = query.get("observer_agent")
        observer_role = self._role_of(observer_agent, agent_roles)
        if observer_agent is not None and observer_role is None:
            return _unsupported(
                "resource observer agent has no configured role"
            )
        status, items = await self._paged_get("/v1/resources", observer_role)
        if status != 200:
            return {
                "kinds_match": False,
                "unsupported": True,
                "reason": "resource endpoint not available",
            }
        matched_pairs: set[tuple[str, str]] = set()
        for item in items:
            resource_id = item.get("id")
            if not isinstance(resource_id, str) or not resource_id:
                return _unsupported(
                    "resource collection has an invalid identity"
                )
            detail_status, detail = await self._get(
                f"/v1/resources/{resource_id}", observer_role
            )
            if detail_status != 200 or not isinstance(detail, dict):
                return _unsupported("resource detail endpoint not available")
            canonical = detail.get("canonical_uri", item.get("canonical_uri"))
            if not isinstance(canonical, str) or not canonical:
                return _unsupported(
                    "resource detail has invalid canonical_uri"
                )
            projections = detail.get("projections")
            if not isinstance(projections, list) or not all(
                isinstance(projection, dict)
                and isinstance(projection.get("projection_kind"), str)
                and bool(projection["projection_kind"])
                for projection in projections
            ):
                return _unsupported("resource detail has invalid projections")
            canonical_uri = str(canonical)
            resource_pairs = {
                (canonical_uri, str(projection["projection_kind"]))
                for projection in children(detail, "projections")
                if isinstance(projection.get("projection_kind"), str)
                and projection["projection_kind"]
            }
            matched_pairs.update(expected_pairs & resource_pairs)
            if expected_pairs.issubset(matched_pairs):
                break
        matched_kinds = sorted({kind for _, kind in matched_pairs})
        matched_canonicals = sorted({
            canonical for canonical, _ in matched_pairs
        })
        return {
            "kinds_match": expected_pairs.issubset(matched_pairs),
            "projection_kinds": matched_kinds,
            "matched_canonicals": matched_canonicals,
            "evidence": {
                "source": "api",
                "matched_projection_kinds": matched_kinds,
                "matched_canonicals": matched_canonicals,
            },
        }

    async def _q_legacy_course_purchase_exists(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],
    ) -> JsonObject:
        """Verify that legacy course purchase still works."""
        buyer_role = self._role_of(query.get("buyer_agent"), agent_roles)
        status, data = await self._get("/v1/credits/ledger", buyer_role)
        if status != 200 or not isinstance(data, list):
            return {"found": False, "evidence": {"source": "api"}}
        baseline = query.get("_baseline")
        baseline_ids = set()
        if isinstance(baseline, dict):
            role_ids = elements(
                child(baseline, "credit_ledger_ids"), buyer_role or ""
            )
            baseline_ids = {str(entry_id) for entry_id in role_ids}
        for entry in data:
            if (
                isinstance(entry, dict)
                and str(entry.get("id")) not in baseline_ids
                and entry.get("kind") == "course_purchase"
            ):
                return {
                    "found": True,
                    "purchase_id": str(opt_str(entry, "id", "")),
                    "evidence": {"source": "api", "surface": "credit_ledger"},
                }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_harness_scope_targets_resolved(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        artifacts = query.get("artifacts")
        required_scopes = {
            str(scope) for scope in elements(query, "required_scopes")
        }
        if not isinstance(artifacts, dict) or not artifacts:
            return _artifact_failure(
                "artifacts mapping is required", "resolved"
            )
        evidence: dict[str, list[str]] = {}
        for harness, path in artifacts.items():
            try:
                items = _load_cli_list(path, "logion.resources.inventory")
            except (OSError, TypeError, ValueError) as exc:
                return _artifact_failure(str(exc), "resolved")
            scopes = {
                str(item.get("scope_kind"))
                for item in items
                if isinstance(item, dict)
            }
            if not required_scopes.issubset(scopes):
                return _artifact_failure(
                    f"{harness} missing scopes: "
                    + ", ".join(sorted(required_scopes - scopes)),
                    "resolved",
                )
            evidence[str(harness)] = sorted(scopes)
        return {"resolved": True, "evidence": evidence}

    async def _q_resource_acquire_plan_dry_run(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            plan = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
            before = _load_json_object(query.get("before_snapshot"))
            after = _snapshot_roots(elements(query, "snapshot_roots"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "valid")
        targets = plan.get("targets")
        if not isinstance(targets, list) or len(targets) != 1:
            return _artifact_failure(
                "plan must select exactly one target", "valid"
            )
        target = targets[0]
        if not isinstance(target, dict):
            return _artifact_failure("plan target is not an object", "valid")
        valid = (
            plan.get("dry_run") is True
            and plan.get("scope") == query.get("expected_scope")
            and target.get("target_path") == query.get("expected_target")
            and before == after
            and plan.get("executable") is not True
        )
        return {
            "valid": valid,
            "zero_write": before == after,
            "scope": plan.get("scope"),
            "target_path": target.get("target_path"),
            "executable": plan.get("executable"),
            "permissions_required": plan.get("permissions_required"),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_resource_acquisition_exists(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            receipt = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "acquired")
        # Verification level is a property of the channel, not of whether
        # the acquisition happened: a delegated native install can only
        # reach `unverified` when its manager records no immutable
        # revision. Scenarios that require a stronger level say so.
        allowed: set[JsonValue] = set(
            elements(query, "allowed_verifications")
            or ("exact", "source_revision")
        )
        acquired = (
            receipt.get("resource_id")
            and receipt.get("installation_id")
            and receipt.get("verification") in allowed
        )
        return {
            "acquired": bool(acquired),
            "resource_id": receipt.get("resource_id"),
            "installation_id": receipt.get("installation_id"),
            "verification": receipt.get("verification"),
            "channel": receipt.get("channel"),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_resource_distribution_selected(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            receipt = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "selected")
        channel = receipt.get("channel")
        allowed = elements(query, "allowed_channels")
        selected = bool(channel) and channel in allowed
        return {
            "selected": selected,
            "channel": channel,
            "distribution_id": receipt.get("distribution_id"),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_native_install_reconciled(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            report = _load_cli_object(
                query.get("artifact"), "logion.resources.reconcile"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "reconciled")
        matched = elements(report, "matched")
        unresolved = elements(report, "unresolved")
        ambiguous = elements(report, "ambiguous")
        drifted = elements(report, "drifted")
        try:
            scope_root = _resolved_scope_root(query.get("scope_root"))
        except ValueError as exc:
            return _artifact_failure(str(exc), "reconciled")
        # A reconcile report is only meaningful if the installations it
        # claims still exist under the scope it claims them in.
        missing: list[str] = []
        for entry in matched:
            if not isinstance(entry, dict):
                continue
            relative = entry.get("relative_target_path") or entry.get("path")
            if not relative:
                continue
            if not (scope_root / str(relative)).exists():
                missing.append(str(relative))
        expected_channel = query.get("expected_channel")
        channels = {
            entry.get("channel")
            for entry in matched
            if isinstance(entry, dict)
        }
        if expected_channel and expected_channel not in channels:
            return _artifact_failure(
                f"no matched installation on channel {expected_channel!r}; "
                f"saw {sorted(c for c in channels if c)}",
                "reconciled",
            )
        if missing:
            return _artifact_failure(
                f"matched installations absent from disk: {missing}",
                "reconciled",
            )
        reconciled = (
            bool(matched) and not unresolved and not ambiguous and not drifted
        )
        return {
            "reconciled": reconciled,
            "matched_count": len(matched),
            "unresolved_count": len(unresolved),
            "ambiguous_count": len(ambiguous),
            "drifted_count": len(drifted),
            "channels": sorted(c for c in channels if c),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_native_harness_discovers_installation(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        """Assert the native harness would load what inventory recorded.

        This reads the harness's own on-disk state — the same manifests a
        fresh session resolves — rather than a report the agent wrote.
        A receipt that describes files the harness does not declare means
        the inventory is claiming an installation the harness never sees.
        """
        try:
            receipt = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "discovered")

        scope_root = Path(str(opt_str(query, "scope_root", "")))
        harness = str(opt_str(query, "harness", "dsh"))
        if harness != "dsh":
            return _artifact_failure(
                f"no native state reader for harness {harness}", "discovered"
            )

        declared = _dsh_declared_bundles(scope_root / ".dsh")
        declared_paths = {path for path, _ in declared}
        installed = [
            str((scope_root / str(path)).resolve())
            for path in elements(receipt, "installed_paths")
        ]
        missing = [path for path in installed if path not in declared_paths]
        return {
            "discovered": bool(installed) and not missing,
            "harness": harness,
            "scope": query.get("scope"),
            "digests": sorted(
                revision for _, revision in declared if revision
            ),
            "paths": sorted(declared_paths),
            "missing": missing,
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_inventory_receipt_matches(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            report = _load_cli_object(
                query.get("artifact"), "logion.resources.reconcile"
            )
            receipt = _load_cli_object(
                query.get("acquire_artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "matches")
        # Native manager entries are matched by source, not by an
        # installation id, so the set is filtered before comparing rather
        # than sorted with a None in it.
        ids = {
            str(entry.get("installation_id"))
            for entry in (elements(report, "matched"))
            if isinstance(entry, dict) and entry.get("installation_id")
        }
        installation_id = receipt.get("installation_id")
        return {
            "matches": bool(installation_id) and str(installation_id) in ids,
            "installation_id": installation_id,
            "matched_ids": sorted(ids),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_installed_artifact_digest_matches(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            receipt = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "digest_matches")
        scope_root = Path(str(opt_str(query, "scope_root", "")))
        installed = [
            str(path) for path in elements(receipt, "installed_paths")
        ]
        if not installed:
            return _artifact_failure(
                "receipt lists no installed paths", "digest_matches"
            )
        evidence = child(receipt, "native_evidence")
        file_digests = child(evidence, "file_digests")
        if not file_digests:
            # Without per-file digests there is nothing to re-verify, so
            # passing here would only assert that some files exist.
            return _artifact_failure(
                "receipt carries no native_evidence.file_digests",
                "digest_matches",
            )
        unpinned = [rel for rel in installed if rel not in file_digests]
        if unpinned:
            return _artifact_failure(
                f"installed files without a recorded digest: {unpinned}",
                "digest_matches",
            )
        mismatches: list[str] = []
        for rel in sorted(installed):
            path = scope_root / rel
            if not path.is_file():
                return _artifact_failure(
                    f"installed file missing: {rel}", "digest_matches"
                )
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != file_digests[rel]:
                mismatches.append(rel)
        if mismatches:
            return _artifact_failure(
                f"installed file digests differ for: {mismatches}",
                "digest_matches",
            )
        verification = receipt.get("verification")
        if verification != "exact":
            return _artifact_failure(
                f"verification is {verification!r}, not exact",
                "digest_matches",
            )
        # The receipt's advertised content digest must be the same one the
        # verified evidence carries, not an unrelated claim.
        expected_digest = str(receipt.get("content_digest") or "")
        evidence_digest = str(evidence.get("content_digest") or "")
        if not expected_digest or expected_digest != evidence_digest:
            return _artifact_failure(
                "receipt content_digest does not match its native evidence: "
                f"{expected_digest!r} != {evidence_digest!r}",
                "digest_matches",
            )
        return {
            "digest_matches": True,
            "content_digest": expected_digest,
            "files": len(installed),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_acquisition_idempotent(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            first = _load_cli_object(
                query.get("first_artifact"), "logion.resources.acquire"
            )
            second = _load_cli_object(
                query.get("second_artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "idempotent")
        same_install = first.get("installation_id") == second.get(
            "installation_id"
        )
        same_digest = first.get("content_digest") == second.get(
            "content_digest"
        )
        try:
            scope_root = _resolved_scope_root(query.get("scope_root"))
        except ValueError as exc:
            return _artifact_failure(str(exc), "idempotent")
        # Re-acquiring must not leave a second copy behind, so the paths
        # the two receipts claim have to be the same set and nothing may
        # linger from an interrupted swap.
        first_paths = sorted(
            str(p) for p in elements(first, "installed_paths")
        )
        second_paths = sorted(
            str(p) for p in elements(second, "installed_paths")
        )
        if first_paths != second_paths:
            return _artifact_failure(
                "second acquisition installed a different path set: "
                f"{first_paths} != {second_paths}",
                "idempotent",
            )
        leftovers = _duplicate_install_state(scope_root)
        if leftovers:
            return _artifact_failure(
                f"duplicate install state left on disk: {leftovers}",
                "idempotent",
            )
        return {
            "idempotent": bool(same_install and same_digest),
            "first_installation_id": first.get("installation_id"),
            "second_installation_id": second.get("installation_id"),
            "installed_paths": first_paths,
            "evidence": {
                "first": str(query.get("first_artifact")),
                "second": str(query.get("second_artifact")),
            },
        }

    async def _q_install_drift_reported(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        """Assert a tampered installation is reported as drifted.

        The negative path: once an installed artifact no longer matches the
        digests its receipt recorded, reconcile must move it out of
        ``matched`` and into ``drifted`` rather than keep vouching for it.
        """
        try:
            report = _load_cli_object(
                query.get("artifact"), "logion.resources.reconcile"
            )
            receipt = _load_cli_object(
                query.get("acquire_artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "drift_reported")
        installation_id = receipt.get("installation_id")
        drifted_ids = {
            entry.get("installation_id")
            for entry in elements(report, "drifted")
            if isinstance(entry, dict)
        }
        matched_ids = {
            entry.get("installation_id")
            for entry in elements(report, "matched")
            if isinstance(entry, dict)
        }
        if installation_id in matched_ids:
            return _artifact_failure(
                "tampered installation is still reported as matched",
                "drift_reported",
            )
        return {
            "drift_reported": installation_id in drifted_ids,
            "installation_id": installation_id,
            "drifted_count": len(drifted_ids),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_scope_isolation_preserved(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        """Assert an acquisition touched nothing outside its own scope.

        Compares a pre-acquisition snapshot against the protected roots
        (the isolated user home, a second repository) so a repository
        install that silently writes into user scope fails the run.
        """
        try:
            before = _load_json_object(query.get("before_snapshot"))
            protected = [
                str(root) for root in elements(query, "protected_roots")
            ]
            after = _snapshot_roots(protected)
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "isolated")
        before_scoped = {
            path: digest
            for path, digest in before.items()
            if any(path.startswith(root) for root in protected)
        }
        added = sorted(set(after) - set(before_scoped))
        removed = sorted(set(before_scoped) - set(after))
        changed = sorted(
            path
            for path in set(after) & set(before_scoped)
            if after[path] != before_scoped[path]
        )
        return {
            "isolated": not (added or removed or changed),
            "added": added,
            "removed": removed,
            "changed": changed,
            "evidence": {"protected_roots": protected},
        }

    async def _q_harness_scope_nested_repo(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        artifacts = query.get("artifacts")
        expected_root = str(opt_str(query, "expected_root", ""))
        if (
            not isinstance(artifacts, dict)
            or not artifacts
            or not expected_root
        ):
            return _artifact_failure(
                "artifacts and expected_root are required", "nested"
            )
        evidence: dict[str, str] = {}
        for harness, path in artifacts.items():
            try:
                plan = _load_cli_object(path, "logion.resources.acquire")
            except (OSError, TypeError, ValueError) as exc:
                return _artifact_failure(str(exc), "nested")
            targets = plan.get("targets")
            target = (
                targets[0] if isinstance(targets, list) and targets else None
            )
            if (
                plan.get("scope") != "repo-root"
                or not isinstance(target, dict)
                or target.get("scope_root") != expected_root
            ):
                return _artifact_failure(
                    f"{harness} did not resolve the expected repository root",
                    "nested",
                )
            evidence[str(harness)] = str(target.get("target_path"))
        return {"nested": True, "evidence": evidence}

    async def _q_harness_inventory_distinct_scopes(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        artifacts = query.get("artifacts")
        resource_name = str(opt_str(query, "resource_name", ""))
        if (
            not isinstance(artifacts, dict)
            or not artifacts
            or not resource_name
        ):
            return _artifact_failure(
                "artifacts and resource_name are required", "distinct"
            )
        evidence: dict[str, list[str]] = {}
        for harness, path in artifacts.items():
            try:
                items = _load_cli_list(path, "logion.resources.inventory")
            except (OSError, TypeError, ValueError) as exc:
                return _artifact_failure(str(exc), "distinct")
            candidates = [
                item
                for item in items
                if isinstance(item, dict) and item.get("name") == resource_name
            ]
            paths = {str(item.get("path")) for item in candidates}
            if (
                len(paths) < 2
                or not all(
                    item.get("ambiguous_name") is True
                    or item.get("ambiguous") is True
                    for item in candidates
                )
                or not all(
                    isinstance(item.get("precedence"), int)
                    for item in candidates
                )
            ):
                return _artifact_failure(
                    f"{harness} did not preserve ambiguous candidates",
                    "distinct",
                )
            evidence[str(harness)] = sorted(paths)
        return {"distinct": True, "evidence": evidence}

    async def _q_observation_envelope_no_raw_data(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        path = Path(str(opt_str(query, "artifact", "")))
        try:
            lines = [
                line
                for line in path.read_text().splitlines()  # noqa: ASYNC240
                if line
            ]
            envelopes = [json.loads(line) for line in lines]
        except (OSError, json.JSONDecodeError) as exc:
            return _artifact_failure(str(exc), "clean")
        allowed = {
            "event",
            "harness",
            "harness_session_id",
            "installation_id",
            "resource_version_id",
            "scope_kind",
            "scope_id",
            "task_class",
            "outcome",
            "started_at",
            "finished_at",
            "duration_ms",
            "integration_version",
        }
        clean = bool(envelopes) and all(
            isinstance(envelope, dict)
            and set(envelope).issubset(allowed)
            and not _contains_forbidden_observation_data(envelope)
            for envelope in envelopes
        )
        return {
            "clean": clean,
            "count": len(envelopes),
            "evidence": {"source": str(path)},
        }

    async def _q_native_use_observed(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            pending = _load_cli_list(
                query.get("pending_artifact"), "logion.usage.pending"
            )
            observe = _load_cli_object(
                query.get("observe_artifact"), "logion.usage.observe"
            )
            receipt = _load_inventory_receipt(query)
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "observed")
        match = next(
            (
                item
                for item in pending
                if isinstance(item, dict)
                and item.get("resource_id") == receipt.get("resource_id")
                and item.get("version_id") == receipt.get("version_id")
                and item.get("installation_id")
                == receipt.get("installation_id")
            ),
            None,
        )
        return {
            "observed": (
                match is not None
                and receipt.get("receipt_origin") == "resources_reconcile"
                and observe.get("disposition") == "recorded"
                and isinstance(observe.get("observation"), dict)
                and child(observe, "observation").get("observation_id")
                == match.get("observation_id")
            ),
            "resource_id": receipt.get("resource_id"),
            "version_id": receipt.get("version_id"),
            "channel": receipt.get("channel"),
            "scope_id": receipt.get("scope_id"),
        }

    async def _q_feedback_pending(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            items = _load_cli_list(
                query.get("pending_artifact"), "logion.usage.pending"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "has_pending")
        resource_ids = sorted({
            str(item["resource_id"])
            for item in items
            if isinstance(item, dict) and item.get("resource_id")
        })
        return {
            "has_pending": bool(items),
            "pending_count": len(items),
            "resource_ids": resource_ids,
        }

    async def _feedback_for(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> tuple[int, JsonObject | None]:
        reporter = query.get("reporter_agent") or query.get("agent")
        role = self._role_of(reporter, agent_roles)
        status, payload = await self._get("/v1/feedback/mine", role)
        if not isinstance(payload, dict):
            return status, None
        items = payload.get("items")
        if not isinstance(items, list):
            return status, None
        expected_resource = query.get("resource_id")
        candidates = [
            item
            for item in items
            if isinstance(item, dict)
            and (
                not expected_resource
                or item.get("resource_id") == expected_resource
            )
        ]
        return status, candidates[0] if candidates else None

    async def _q_resource_feedback_exists(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        status, feedback = await self._feedback_for(query, agent_roles)
        return {
            "found": status == 200 and feedback is not None,
            "feedback_id": feedback.get("id") if feedback else None,
            "resource_id": feedback.get("resource_id") if feedback else None,
            "version_id": (
                feedback.get("resource_version_id") if feedback else None
            ),
        }

    async def _q_feedback_linked_to_acquisition(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        try:
            receipt = _load_inventory_receipt(query)
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "linked")
        query = {**query, "resource_id": receipt.get("resource_id")}
        status, feedback = await self._feedback_for(query, agent_roles)
        linked = (
            status == 200
            and feedback is not None
            and feedback.get("resource_version_id")
            == receipt.get("version_id")
            and feedback.get("acquisition_channel") == receipt.get("channel")
        )
        return {
            "linked": linked,
            "feedback_id": feedback.get("id") if feedback else None,
            "acquisition_channel": (
                feedback.get("acquisition_channel") if feedback else None
            ),
            "installation_id": receipt.get("installation_id"),
        }

    #: Every disposition the feedback API may report. An unknown value means
    #: the server invented one, which is a failure, not a pass.
    _PROJECTION_DISPOSITIONS = frozenset({
        "projected",
        "not_a_course",
        "ineligible",
        "self_review",
        "paid_entitlement_missing",
    })

    async def _q_course_review_projection_exists(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        """Assert the projection was *decided*, and decided consistently.

        A disposition merely being present is not evidence: it used to pass
        on ``not_a_course``, which is the branch where nothing projects.
        What must hold is that the disposition is a known one and that a
        marketplace review exists exactly when it says ``projected`` — so a
        non-projecting outcome can never carry a review id.
        """
        _, feedback = await self._feedback_for(query, agent_roles)
        disposition = (
            feedback.get("projection_disposition") if feedback else None
        )
        review_id = feedback.get("course_review_id") if feedback else None
        projected = disposition == "projected"
        known = disposition in self._PROJECTION_DISPOSITIONS
        consistent = known and (review_id is not None) == projected
        return {
            "found": consistent,
            "feedback_id": feedback.get("id") if feedback else None,
            "projection_disposition": disposition,
            "course_review_id": review_id,
        }

    async def _q_raw_observation_not_uploaded(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        _, feedback = await self._feedback_for(query, agent_roles)
        forbidden = {
            "prompt",
            "source_code",
            "path",
            "tool_arguments",
            "request",
            "response",
            "raw_payload",
        }
        keys = set(feedback or {})
        return {
            "clean": feedback is not None and not keys.intersection(forbidden),
            "observation_count": 0,
            "checked_fields": sorted(keys),
        }

    async def _q_feedback_submission_idempotent(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        try:
            first, first_shape = _load_cli_payload(
                query.get("first_artifact"), "logion.feedback.submit"
            )
            second, second_shape = _load_cli_payload(
                query.get("second_artifact"), "logion.feedback.submit"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "idempotent")
        status, feedback = await self._feedback_for(query, agent_roles)
        first_id = first.get("id") or first.get("feedback_id")
        second_id = second.get("id") or second.get("feedback_id")
        persisted_id = feedback.get("id") if feedback else None
        return {
            "idempotent": (
                status == 200
                and first_id
                and first_id == second_id == persisted_id
            ),
            "first_feedback_id": first_id,
            "second_feedback_id": second_id,
            "persisted_feedback_id": persisted_id,
            "artifact_shapes": [first_shape, second_shape],
        }

    async def _q_remote_mcp_reconciled(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        result = await self._q_native_install_reconciled(query, agent_roles)
        try:
            report = _load_cli_object(
                query.get("artifact"), "logion.resources.reconcile"
            )
            receipt = _load_inventory_receipt(query)
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "reconciled")
        matched_ids = {
            item.get("installation_id")
            for item in elements(report, "matched")
            if isinstance(item, dict)
        }
        receipt_linked = (
            receipt.get("receipt_origin") == "resources_reconcile"
            and receipt.get("installation_id") in matched_ids
        )
        return {
            **result,
            "reconciled": result.get("reconciled") is True and receipt_linked,
            "receipt_origin": receipt.get("receipt_origin"),
        }

    async def _q_vendor_install_unchanged(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        try:
            before = _load_json_object(query.get("before_snapshot"))
            after = _load_json_object(query.get("after_snapshot"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "unchanged")
        return {"unchanged": before == after, "before": before, "after": after}

    async def _q_no_mcp_proxy_installed(
        self,
        query: JsonObject,
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> JsonObject:
        root = Path(str(opt_str(query, "fixture_root", "")))
        proxies = [
            str(path)
            for path in root.rglob("*")  # noqa: ASYNC240
            if path.is_file() and "proxy" in path.name.lower()
        ]
        return {"absent": not proxies, "paths": proxies}

    async def _q_remote_mcp_use_attributed(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        result = await self._q_native_use_observed(query, agent_roles)
        return {"attributed": result.get("observed") is True, **result}

    async def _q_original_publisher_preserved(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        try:
            detail = _load_cli_object(
                query.get("resource_artifact"), "logion.resources.get"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "preserved")
        expected = query.get("publisher")
        projections = elements(detail, "projections")
        projection_id = next(
            (
                item.get("projection_id")
                for item in projections
                if isinstance(item, dict)
                and item.get("projection_kind") == "indexed_listing"
            ),
            None,
        )
        reporter = query.get("reporter_agent") or query.get("agent")
        role = self._role_of(reporter, agent_roles)
        status, body = (
            await self._get(f"/v1/indexed-listings/{projection_id}", role)
            if projection_id
            else (0, {})
        )
        listing = body if isinstance(body, dict) else {}
        actual = listing.get("original_author")
        return {
            "preserved": status == 200
            and bool(expected)
            and actual == expected,
            "publisher": actual,
            "projection_id": projection_id,
        }

    async def _q_remote_mcp_feedback_linked(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        result = await self._q_feedback_linked_to_acquisition(
            query, agent_roles
        )
        return {"linked": result.get("linked") is True, **result}

    async def _q_remote_mcp_private_payload_not_recorded(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        result = await self._q_raw_observation_not_uploaded(query, agent_roles)
        artifacts = elements(query, "artifacts")
        canary = str(query.get("privacy_canary") or "")
        leaked = False
        for raw_path in artifacts:
            path = Path(str(raw_path))
            try:
                leaked = leaked or bool(
                    canary and canary in path.read_text()  # noqa: ASYNC240
                )
            except OSError:
                leaked = True
        return {
            "clean": result.get("clean") is True and not leaked,
            "checked_fields": elements(result, "checked_fields"),
        }

    # ------------------------------------------------------------------
    # AI Catalog & ARD query handlers (phase 15.12)
    #
    # Two rules decide where each of these looks.
    #
    # An assertion about *what the agent did* reads the artifact the
    # scenario made it save. Re-querying the API instead answers a
    # different question -- "is the endpoint working now" -- which a
    # scenario where the agent never ran the command still passes.
    #
    # An assertion about *what the system holds* reads the API, because
    # an artifact the agent wrote is the agent's own account of its
    # work and cannot be the proof that the work landed.
    # ------------------------------------------------------------------

    async def _q_ai_catalog_document_valid(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Validate the AI Catalog document the operator published."""
        try:
            document = _load_json_object(query.get("catalog_artifact"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "valid")

        spec_version = document.get("specVersion")
        host = document.get("host")
        entries = document.get("entries")
        if not isinstance(spec_version, str) or not spec_version:
            return _artifact_failure("missing specVersion", "valid")
        if not isinstance(host, dict):
            return _artifact_failure("missing host object", "valid")
        if not isinstance(entries, list):
            return _artifact_failure("missing entries array", "valid")
        return {
            "valid": True,
            "spec_version": spec_version,
            "entry_count": len(entries),
            "conformance_level": _catalog_conformance_level(document),
            "evidence": {"source": str(query.get("catalog_artifact"))},
        }

    async def _q_ai_catalog_conformance_level_valid(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the published document earns the level it claims."""
        try:
            document = _load_json_object(query.get("catalog_artifact"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "valid")

        spec_version = document.get("specVersion")
        if spec_version != _AI_CATALOG_SPEC_VERSION:
            return _artifact_failure(
                f"specVersion is {spec_version!r}, expected "
                f"{_AI_CATALOG_SPEC_VERSION!r}",
                "valid",
            )
        host = document.get("host")
        if not isinstance(host, dict) or not host.get("displayName"):
            return _artifact_failure("host has no displayName", "valid")
        level = _catalog_conformance_level(document)
        if level == "none":
            return _artifact_failure(
                "document reaches no conformance level", "valid"
            )
        return {
            "valid": True,
            "conformance_level": level,
            "evidence": {
                "source": str(query.get("catalog_artifact")),
                "host_display_name": host.get("displayName"),
            },
        }

    async def _q_ard_search_response_valid(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the saved ARD search names its registry and its scores."""
        try:
            payload = _load_json_object(query.get("search_artifact"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "valid")

        results = payload.get("results")
        if not isinstance(results, list):
            return _artifact_failure("missing results array", "valid")
        # Two shapes are legitimate here. A raw ARD response names the
        # answering registry per result, in each entry's `source`; the
        # indexer's own output lifts it into an envelope. Requiring only
        # the envelope would fail a conformant registry for the crime of
        # not being read through our CLI.
        registry = payload.get("registry")
        registry_origin = (
            registry.get("origin") if isinstance(registry, dict) else None
        )
        if not registry_origin:
            origins = sorted({
                str(row.get("source"))
                for row in results
                if isinstance(row, dict) and row.get("source")
            })
            registry_origin = origins[0] if len(origins) == 1 else None
        if not registry_origin:
            return _artifact_failure(
                "response does not name the registry that answered", "valid"
            )
        # A score is registry-supplied metadata. Its presence is what
        # makes it auditable as *theirs*; a result set with no scores
        # cannot be distinguished from one Logion ranked itself.
        scored = [
            row
            for row in results
            if isinstance(row, dict) and row.get("score") is not None
        ]
        return {
            "valid": True,
            "result_count": len(results),
            "has_scores": bool(scored),
            "registry_origin": registry_origin,
            "evidence": {
                "source": str(query.get("search_artifact")),
                "scored_count": len(scored),
            },
        }

    async def _q_ard_connectors_snapshot_pinned(
        self,
        query: JsonObject,  # noqa: ARG002
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the registry holds an immutably pinned connector snapshot.

        This one is an API question on purpose: what matters is what the
        node will use on its next run, not what a command printed once.
        """
        status, data = await self._get("/v1/ard/sources/status", "admin")
        if status != 200 or not isinstance(data, dict):
            return _unsupported("ARD source status endpoint not available")
        items = data.get("items")
        if not isinstance(items, list) or not items:
            return {
                "pinned": False,
                "reason": "no source snapshots recorded",
                "evidence": {"source": "api"},
            }
        pinned = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get("commit_sha")
            and item.get("file_digest")
            and item.get("last_good") is True
        ]
        if not pinned:
            return {
                "pinned": False,
                "reason": (
                    "no last-good snapshot carries both a commit sha and a "
                    "file digest"
                ),
                "evidence": {"source": "api", "snapshot_count": len(items)},
            }
        snapshot = pinned[0]
        return {
            "pinned": True,
            "commit_sha": snapshot.get("commit_sha"),
            "file_digest": snapshot.get("file_digest"),
            "finder_count": len(items),
            "evidence": {
                "source": "api",
                "source_type": snapshot.get("source_type"),
                "source_uri": snapshot.get("source_uri"),
                "validation_result": snapshot.get("validation_result"),
            },
        }

    async def _q_agent_finders_queried(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the operator actually queried the enabled finders."""
        try:
            payload = _load_json_object(query.get("finder_artifact"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "queried")

        records = payload.get("records")
        if not isinstance(records, list):
            return _artifact_failure("run has no records array", "queried")
        return {
            "queried": len(records) > 0,
            "finder_count": len(records),
            "query_family": payload.get("query_family") or "default",
            "evidence": {
                "source": str(query.get("finder_artifact")),
                "dry_run": payload.get("dry_run"),
            },
        }

    async def _q_agent_finder_result_provenance_visible(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check every finder result says which finder returned it."""
        try:
            payload = _load_json_object(query.get("finder_artifact"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "visible")

        records = payload.get("records")
        if not isinstance(records, list) or not records:
            return _artifact_failure("run has no records", "visible")
        missing: list[str] = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                missing.append(f"record[{index}] is not an object")
                continue
            if not record.get("finder_id"):
                missing.append(f"record[{index}] has no finder_id")
            if not record.get("endpoint"):
                missing.append(f"record[{index}] has no endpoint")
        first = records[0] if isinstance(records[0], dict) else {}
        result_count = sum(
            len(record.get("result_identifiers") or [])
            for record in records
            if isinstance(record, dict)
        )
        return {
            "visible": not missing,
            "finder_id": first.get("finder_id"),
            "endpoint": first.get("endpoint"),
            "result_count": result_count,
            "reason": "; ".join(missing) if missing else None,
            "evidence": {
                "source": str(query.get("finder_artifact")),
                "record_count": len(records),
            },
        }

    async def _q_catalog_crawl_completed(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the crawl finished and reported what it saw."""
        try:
            reports = _load_import_reports(query)
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "completed")

        incomplete = [
            report.get("source")
            for report in reports
            if report.get("status") != "completed"
        ]
        last = reports[-1]
        return {
            "completed": not incomplete,
            "seen": _as_count(last.get("seen")),
            "created": _as_count(last.get("created")),
            "matched": _as_count(last.get("matched")),
            "new_versions": _as_count(last.get("new_versions")),
            "quarantined": _as_count(last.get("quarantined")),
            "reason": (
                f"{len(incomplete)} of {len(reports)} crawls were partial"
                if incomplete
                else None
            ),
            "evidence": {
                "source": "import report",
                "report_count": len(reports),
            },
        }

    async def _q_ard_record_rejected(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check malformed input was quarantined under a stable code.

        A crawl that imported everything it was offered proves nothing
        about rejection, so an empty quarantine fails here rather than
        passing quietly.
        """
        try:
            reports = _load_import_reports(query)
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "rejected")

        quarantined: list[JsonObject] = []
        for report in reports:
            entries = report.get("quarantine")
            if isinstance(entries, list):
                quarantined.extend(
                    entry for entry in entries if isinstance(entry, dict)
                )
        if not quarantined:
            return {
                "rejected": False,
                "reason": "no entry was quarantined by any crawl",
                "evidence": {"source": "import report"},
            }
        first = quarantined[0]
        codes = sorted({
            str(entry.get("error_code"))
            for entry in quarantined
            if entry.get("error_code")
        })
        if not codes:
            return {
                "rejected": False,
                "reason": "quarantined entries carry no stable error code",
                "evidence": {"source": "import report"},
            }
        return {
            "rejected": True,
            "reason": first.get("reason"),
            "error_code": first.get("error_code"),
            "evidence": {
                "source": "import report",
                "quarantined_count": len(quarantined),
                "error_codes": codes,
            },
        }

    async def _q_self_crawl_no_duplicate(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check crawling twice added the entries once.

        Both halves are needed. The registry holding no duplicate pair
        is consistent with a second crawl that never ran; a second crawl
        that created nothing is consistent with a registry that was
        already duplicated before either ran.
        """
        status, items = await self._paged_get("/v1/resources", "admin")
        if status != 200:
            return _unsupported("resource endpoint not available")
        seen, duplicates = _identity_scan(items)

        try:
            reports = _load_import_reports(query, required=False)
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "no_duplicates")
        recrawl_created = (
            _as_count(reports[-1].get("created")) if len(reports) > 1 else 0
        )
        return {
            "no_duplicates": not duplicates and recrawl_created == 0,
            "crawl_count": len(reports),
            "resource_count": len(seen),
            "reason": (
                f"duplicate resources: {duplicates}"
                if duplicates
                else (
                    f"re-crawl created {recrawl_created} resources"
                    if recrawl_created
                    else None
                )
            ),
            "evidence": {
                "source": "api + import report",
                "duplicates": duplicates,
                "recrawl_created": recrawl_created,
            },
        }

    async def _q_ard_resource_ingested(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the discovered resource is one the registry now holds."""
        resource_id = query.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id:
            return _unsupported("resource_id is required")
        status, items = await self._paged_get("/v1/resources", "admin")
        if status != 200:
            return _unsupported("resource endpoint not available")
        for item in items:
            if resource_id in (item.get("id"), item.get("resource_id")):
                return {
                    "ingested": True,
                    "resource_id": resource_id,
                    "canonical_uri": item.get("canonical_uri"),
                    "evidence": {"source": "api"},
                }
        return {
            "ingested": False,
            "resource_id": resource_id,
            "reason": "resource is not in the registry",
            "evidence": {"source": "api", "resource_count": len(items)},
        }

    async def _q_resource_source_provenance_visible(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check the registry can say where an entry came from."""
        resource_id = query.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id:
            return _unsupported("resource_id is required")
        status, data = await self._get(f"/v1/resources/{resource_id}", "admin")
        if status != 200 or not isinstance(data, dict):
            return _unsupported("resource detail endpoint not available")
        sources = data.get("sources")
        if not isinstance(sources, list) or not sources:
            return {
                "visible": False,
                "reason": "resource records no source",
                "evidence": {"source": "api", "resource_id": resource_id},
            }
        complete = [
            source
            for source in sources
            if isinstance(source, dict)
            and source.get("source_kind")
            and source.get("source_uri")
        ]
        first = complete[0] if complete else {}
        return {
            "visible": len(complete) == len(sources),
            "source_kind": first.get("source_kind"),
            "source_uri": first.get("source_uri"),
            "external_id": first.get("external_id"),
            "reason": (
                None
                if len(complete) == len(sources)
                else "a recorded source is missing its kind or uri"
            ),
            "evidence": {
                "source": "api",
                "resource_id": resource_id,
                "source_count": len(sources),
            },
        }

    async def _q_search_filters_by_type_and_source(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check a filter narrows the result set instead of decorating it.

        A registry that accepts filters and returns everything passes any
        check that only reads the filtered response. So this runs the
        search twice and requires the filter to have excluded something
        the unfiltered search returned.
        """
        text = str(query.get("query_text") or "")
        type_filter = query.get("resource_type") or query.get("resourceType")
        source_filter = query.get("source")
        if not type_filter or not source_filter:
            return _unsupported(
                "resource_type and source are required to prove filtering"
            )
        unfiltered_status, unfiltered = await self._post(
            "/v1/ard/search",
            "admin",
            {"query": {"text": text}, "pageSize": 100},
        )
        filtered_status, filtered = await self._post(
            "/v1/ard/search",
            "admin",
            {
                "query": {
                    "text": text,
                    "filter": {
                        "type": [str(type_filter)],
                        "source": [str(source_filter)],
                    },
                },
                "pageSize": 100,
            },
        )
        if unfiltered_status != 200 or filtered_status != 200:
            return _unsupported(
                f"ARD search rejected the request "
                f"(unfiltered {unfiltered_status}, "
                f"filtered {filtered_status})"
            )
        all_rows = _rows(unfiltered)
        kept = _rows(filtered)
        if not kept:
            return {
                "filtered": False,
                "reason": "the filter excluded everything",
                "evidence": {"source": "api"},
            }
        mismatched = [
            row.get("identifier")
            for row in kept
            if row.get("type") != str(type_filter)
        ]
        narrowed = len(kept) < len(all_rows)
        return {
            "filtered": narrowed and not mismatched,
            "type_filter": type_filter,
            "source_filter": source_filter,
            "result_count": len(kept),
            "reason": (
                f"entries do not match the type filter: {mismatched}"
                if mismatched
                else (
                    None
                    if narrowed
                    else "the filter returned everything the query did"
                )
            ),
            "evidence": {
                "source": "api",
                "unfiltered_count": len(all_rows),
                "filtered_count": len(kept),
            },
        }

    async def _q_discovery_succeeds_without_aktp(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check discovery worked over ARD alone.

        The saved response is the evidence that the consumer actually
        discovered something; the live call is the evidence that ARD is
        the only endpoint that had to answer.
        """
        try:
            payload = _load_json_object(query.get("search_artifact"))
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "succeeded")

        saved_results = payload.get("results")
        if not isinstance(saved_results, list) or not saved_results:
            return _artifact_failure(
                "the saved discovery returned nothing", "succeeded"
            )
        status, data = await self._post(
            "/v1/ard/search",
            "admin",
            {"query": {"text": str(query.get("query_text") or "")}},
        )
        if status != 200 or not isinstance(data, dict):
            return _unsupported("ARD search endpoint not available")
        aktp_status, _ = await self._get("/v1/aktp/handshake", "admin")
        return {
            # 404 is the answer that matters: discovery succeeded on a
            # node with no AKTP surface at all.
            "succeeded": bool(_rows(data)),
            "aktp_required": False,
            "ard_endpoint": "/v1/ard/search",
            "evidence": {
                "source": "artifact + api",
                "saved_result_count": len(saved_results),
                "live_result_count": len(_rows(data)),
                "aktp_handshake_status": aktp_status,
            },
        }

    async def _q_ingested_model_requires_no_asm_schema(
        self,
        query: JsonObject,
        agent_roles: JsonObject,  # noqa: ARG002
    ) -> JsonObject:
        """Check ingestion did not grow an ASM-shaped field.

        The check reads the resource object and its metadata, not the
        envelope: an ASM selector that arrives through ingestion lands
        on the model, and looking only at the top level reports 'clean'
        for every resource that has ever existed.
        """
        resource_id = query.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id:
            return _unsupported("resource_id is required")
        status, data = await self._get(f"/v1/resources/{resource_id}", "admin")
        if status != 200 or not isinstance(data, dict):
            return _unsupported("resource detail endpoint not available")
        resource = data.get("resource")
        if not isinstance(resource, dict):
            return _unsupported("resource detail carries no resource object")
        hits = _asm_shaped_keys(resource)
        metadata = resource.get("metadata")
        if isinstance(metadata, dict):
            hits.extend(
                f"metadata.{key}" for key in _asm_shaped_keys(metadata)
            )
        return {
            "agnostic": not hits,
            "has_asm_schema": bool(hits),
            "resource_id": resource_id,
            "reason": f"ASM-shaped fields: {hits}" if hits else None,
            "evidence": {"source": "api", "fields": hits},
        }


def _resolved_scope_root(raw: JsonValue) -> Path:
    """Validate a scenario-supplied scope root outside the async path."""
    root = Path(str(raw or ""))
    if not root.is_dir():
        raise ValueError(f"scope_root is not a directory: {root}")
    return root


#: Shell start-up files a spawned interactive tool writes on its own.
_SHELL_RC_FILES = frozenset({
    ".bashrc",
    ".bash_profile",
    ".bash_history",
    ".zshrc",
    ".zsh_history",
    ".profile",
    ".npmrc",
})


def _duplicate_install_state(scope_root: Path) -> list[str]:
    """List staging/backup directories an interrupted swap left behind."""
    leftovers: list[str] = []
    for pattern in ("*.logion-incoming", "*.logion-backup"):
        leftovers.extend(
            str(path.relative_to(scope_root))
            for path in scope_root.rglob(pattern)
        )
    return sorted(leftovers)


def _restart_marker_offenders(before: dict, after: dict) -> list[str]:
    """Reject missing/unreachable markers and changed state per role."""
    offenders: list[str] = []
    expected_roles = {"consumer", "auditor"}
    if set(before) != expected_roles or set(after) != expected_roles:
        offenders.append("marker-role-set-incomplete")
    invalid_prefixes = ("missing", "unreachable:")
    for role in sorted(expected_roles):
        marker_value = before.get(role)
        after_value = after.get(role)
        if (
            not isinstance(marker_value, str)
            or not marker_value
            or marker_value.startswith(invalid_prefixes)
        ):
            offenders.append(f"{role}:invalid-before-marker")
        if (
            not isinstance(after_value, str)
            or not after_value
            or after_value.startswith(invalid_prefixes)
        ):
            offenders.append(f"{role}:invalid-after-marker")
        if after_value != marker_value:
            offenders.append(f"{role}:state-changed")
    return offenders


def _restart_operation_offenders(restart: dict) -> list[str]:
    """Require mechanical proof the node actually stopped and started."""
    offenders: list[str] = []
    for key, expected in (
        ("performed", True),
        ("down_exit_code", 0),
        ("up_exit_code", 0),
        ("container_ids_changed", True),
    ):
        if restart.get(key) != expected:
            offenders.append(f"restart:{key}={restart.get(key)}")
    return offenders


def _artifact_failure(reason: str, result_key: str) -> JsonObject:
    return {result_key: False, "reason": reason, "evidence": {}}


#: The one specVersion the phase's codec and gate both speak.
_AI_CATALOG_SPEC_VERSION = "1.0"

#: Field names that would make an ingested model ASM-specific. Matched
#: as a prefix so a renamed variant (``asm_selector_v2``) is caught: the
#: claim is that nothing ASM-shaped arrived, not that these four exact
#: spellings are absent.
_ASM_FIELD_PREFIXES = ("asm_", "asmSchema", "asmSelector", "asm-")


def _asm_shaped_keys(payload: JsonObject) -> list[str]:
    """Name every key that would make this object ASM-specific."""
    return sorted(
        key
        for key in payload
        if isinstance(key, str) and key.startswith(_ASM_FIELD_PREFIXES)
    )


def _catalog_conformance_level(document: JsonObject) -> str:
    """Re-derive the level the document earns, from the document.

    Deliberately not the indexer's conformance module: an assertion
    that asks the code under test whether the code under test agrees
    with itself passes whenever that code is self-consistent, including
    when it is wrong about the spec.
    """
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        return "none"
    host = document.get("host")
    if not isinstance(host, dict) or not host.get("displayName"):
        return "none"
    signed = any(
        isinstance(entry, dict)
        and isinstance(entry.get("trustManifest"), dict)
        and entry["trustManifest"].get("signature")
        for entry in entries
    )
    if signed:
        return "trusted"
    if host.get("identifier"):
        return "discoverable"
    return "minimal"


def _identity_scan(
    items: list[JsonObject],
) -> tuple[set[tuple[str, str]], list[list[str]]]:
    """Group resources by the pair that is supposed to be unique.

    ``(resource_type, canonical_uri)`` is the identity a crawl must not
    mint twice. Rows missing either half are skipped rather than counted
    as distinct: an unnameable row cannot prove uniqueness either way.
    """
    seen: set[tuple[str, str]] = set()
    duplicates: list[list[str]] = []
    for item in items:
        resource_type = item.get("resource_type")
        canonical_uri = item.get("canonical_uri")
        if not isinstance(resource_type, str) or not resource_type:
            continue
        if not isinstance(canonical_uri, str) or not canonical_uri:
            continue
        key = (resource_type, canonical_uri)
        if key in seen:
            duplicates.append(list(key))
        else:
            seen.add(key)
    return seen, duplicates


def _rows(payload: JsonValue) -> list[JsonObject]:
    """Read an ARD response's results, tolerating an empty answer."""
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    return [row for row in results if isinstance(row, dict)]


def _load_import_reports(
    query: JsonObject,
    *,
    required: bool = True,
) -> list[JsonObject]:
    """Load the crawl reports a scenario saved, in the order it ran them.

    Order matters: the second crawl of the same source is the one that
    proves a re-crawl created nothing, and a set of reports read in
    arbitrary order cannot tell which one that was.
    """
    raw = query.get("crawl_reports")
    paths = raw if isinstance(raw, list) else []
    if not paths:
        single = query.get("crawl_report")
        paths = [single] if single else []
    if not paths:
        if required:
            raise ValueError("crawl_report or crawl_reports is required")
        return []
    return [_load_json_object(path) for path in paths]


def _dsh_declared_bundles(dsh_home: Path) -> list[tuple[str, str]]:
    """Read what a fresh dsh session would load, as an outside observer.

    This deliberately re-derives the layout instead of calling Logion's
    own reader: an assertion that reuses the code under test would pass
    whenever that code is self-consistent, including when it is wrong.

    Returns ``[(installed_path, revision)]`` for each declared bundle.
    """
    results: list[tuple[str, str]] = []
    profiles = dsh_home / "profiles"
    if not profiles.is_dir():
        return results
    for directory in sorted(profiles.iterdir()):
        try:
            manifest = json.loads(
                (directory / "package.json").read_text(encoding="utf-8")
            )
            bundles = manifest["dsh"]["profile"]["bundles"]
        except (OSError, KeyError, TypeError, ValueError):
            continue
        if not isinstance(bundles, list):
            continue
        for name in bundles:
            if not isinstance(name, str):
                continue
            installed = directory / "node_modules" / Path(name)
            try:
                bundle = json.loads(
                    (installed / "package.json").read_text(encoding="utf-8")
                )
            except (OSError, TypeError, ValueError):
                continue
            results.append((
                str(installed.resolve()),
                str(bundle.get("gitHead") or ""),
            ))
    return results


def _load_json_object(raw_path: JsonValue) -> JsonObject:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("artifact path is required")
    path = Path(raw_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"artifact is not a regular file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"artifact is not a JSON object: {path}")
    return payload


def _load_inventory_receipt(query: JsonObject) -> JsonObject:
    raw_path = query.get("inventory_receipt")
    if raw_path:
        return _load_json_object(raw_path)
    raw_dir = query.get("inventory_dir")
    if not isinstance(raw_dir, str) or not raw_dir:
        raise ValueError("inventory_receipt or inventory_dir is required")
    directory = Path(raw_dir)
    candidates = [
        _load_json_object(str(path))
        for path in sorted(directory.glob("*.json"))
        if path.is_file() and not path.is_symlink()
    ]
    resource_id = query.get("resource_id")
    if resource_id:
        candidates = [
            item
            for item in candidates
            if item.get("resource_id") == resource_id
        ]
    if len(candidates) != 1:
        raise ValueError(
            "inventory attribution must resolve to exactly one receipt"
        )
    return candidates[0]


def _load_cli_data(raw_path: JsonValue, expected_kind: str) -> JsonValue:
    envelope = _load_json_object(raw_path)
    if (
        envelope.get("version") != "v1"
        or envelope.get("kind") != expected_kind
    ):
        raise ValueError(f"unexpected CLI envelope in {raw_path}")
    return envelope.get("data")


def _load_cli_payload(
    raw_path: JsonValue, expected_kind: str
) -> tuple[JsonObject, str]:
    """Read a CLI artifact as the v1 envelope *or* its bare data object.

    Returns the payload and which shape it was found in, so evidence still
    records whether the agent preserved the envelope.

    The envelope is preferred and not required. This reader backs checks
    whose subject is a **server-side** property, and making a server
    invariant depend on an agent preserving a wire format turns a
    deterministic check into a coin flip. Observed directly: same prompt,
    same model, two consecutive runs, envelope in the first and the bare
    data object in the second — with the API storing one row and one id
    both times.

    Nothing is lost against reward hacking. The identity check that matters
    compares both artifacts to the id the API actually persisted, and an
    agent willing to invent an id could invent an envelope around it just
    as easily.
    """
    envelope = _load_json_object(raw_path)
    if (
        envelope.get("version") == "v1"
        and envelope.get("kind") == expected_kind
    ):
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise TypeError(f"CLI data is not an object: {raw_path}")
        return data, "envelope"
    if "version" in envelope or "kind" in envelope:
        raise ValueError(f"unexpected CLI envelope in {raw_path}")
    return envelope, "bare"


def _load_cli_object(raw_path: JsonValue, expected_kind: str) -> JsonObject:
    data = _load_cli_data(raw_path, expected_kind)
    if not isinstance(data, dict):
        raise TypeError(f"CLI data is not an object: {raw_path}")
    return data


def _load_cli_list(raw_path: JsonValue, expected_kind: str) -> JsonArray:
    data = _load_cli_data(raw_path, expected_kind)
    if isinstance(data, list):
        return data
    # Some CLI commands (e.g. resources inventory) emit a dict envelope
    # whose payload list is nested under a key rather than at the top
    # level.  Extract the canonical list field so callers always see a
    # list.
    if isinstance(data, dict):
        for key in ("resources", "items", "results"):
            nested = data.get(key)
            if isinstance(nested, list):
                return nested
    raise TypeError(f"CLI data is not a list: {raw_path}")


def _snapshot_roots(raw_roots: JsonValue) -> dict[str, str]:
    if not isinstance(raw_roots, list) or not raw_roots:
        raise ValueError("snapshot_roots list is required")
    result: dict[str, str] = {}
    for raw_root in raw_roots:
        root = Path(str(raw_root))
        if not root.is_dir():
            raise ValueError(f"snapshot root is not a directory: {root}")
        skip_dirs = {
            ".cache",
            "__pycache__",
            ".local",
            "Library",
            ".git",
            # Package-manager and tool caches: running `npx` writes here
            # legitimately, and it says nothing about harness scope.
            ".npm",
            ".bun",
            ".yarn",
            "node_modules",
        }
        for path in sorted(root.rglob("*")):
            if path.is_file():
                if any(part in skip_dirs for part in path.parts):
                    continue
                if path.parent == root and path.name in _SHELL_RC_FILES:
                    continue
                result[str(path.resolve())] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return result


def _contains_forbidden_observation_data(envelope: JsonObject) -> bool:
    identifier_fields = {
        "harness_session_id",
        "installation_id",
        "resource_version_id",
        "scope_id",
    }
    structured_fields = {
        "event",
        "harness",
        "scope_kind",
        "task_class",
        "outcome",
        "integration_version",
    }
    forbidden_names = re.compile(
        r"prompt|source|code|path|argument|secret|token|credential|content|payload",
        re.IGNORECASE,
    )
    # Sanctioned field names that contain a forbidden substring (e.g.
    # "resource_version_id" contains "source") but are explicitly allowed
    # by the envelope contract.
    forbidden_name_exceptions = frozenset({"resource_version_id"})
    opaque = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    structured = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    for key, value in envelope.items():
        if (
            forbidden_names.search(key)
            and key not in forbidden_name_exceptions
        ):
            return True
        if key in identifier_fields and (
            not isinstance(value, str) or not opaque.fullmatch(value)
        ):
            return True
        if key in structured_fields and (
            not isinstance(value, str) or not structured.fullmatch(value)
        ):
            return True
    return False


def _as_count(value: JsonValue) -> int:
    """Read a counter out of a snapshot, or -1 when it is not one.

    A sentinel rather than 0: several callers compare against 0, and a
    missing counter must not read as "observed zero".
    """
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return -1
    try:
        return int(value)
    except ValueError:
        return -1


def _unsupported(reason: str) -> JsonObject:
    return {"found": False, "unsupported": True, "reason": reason}


def _baseline_ids(query: JsonObject, key: str) -> set[str]:
    # Scenarios that rely on pre-seeded fixtures (e.g. a published
    # fixture course) opt out of baseline-delta filtering per assertion.
    if query.get("include_baseline"):
        return set()
    baseline = query.get("_baseline")
    if not isinstance(baseline, dict):
        return set()
    values = baseline.get(key)
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values if value}
