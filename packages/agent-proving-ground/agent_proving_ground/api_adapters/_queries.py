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

    async def _q_publisher_receipt_exact_resource_version(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        """Verify the stored receipt names the exact version
        and all attributions.

        Reads the receipt artifact the consumer saved and checks it
        carries the resource_id, resource_version, publisher identity,
        distribution_digest, profile_digest, and integration_version
        the publisher's generator produced.
        """
        try:
            receipt = _load_json_object(query.get("receipt_artifact"))
        except (OSError, TypeError, ValueError) as exc:
            # Fall back to API-side feedback record.
            _, feedback = await self._feedback_for(query, agent_roles)
            if feedback is None:
                return _artifact_failure(str(exc), "exact")
            receipt = feedback
        expected_resource = query.get("resource_id")
        expected_version = query.get("version_id")
        expected_publisher = query.get("publisher_identity")
        resource_id = receipt.get("resource_id")
        resource_version = (
            receipt.get("resource_version")
            or receipt.get("resource_version_id")
            or receipt.get("version_id")
        )
        publisher = None
        pub = receipt.get("publisher")
        if isinstance(pub, dict):
            publisher = pub.get("identity")
        distribution_digest = receipt.get("distribution_digest")
        profile_digest = receipt.get("profile_digest")
        integration_version = receipt.get("integration_version")
        exact = (
            bool(resource_id)
            and str(resource_id) == str(expected_resource or "")
            and bool(resource_version)
            and str(resource_version) == str(expected_version or "")
            and bool(publisher)
            and (not expected_publisher or publisher == expected_publisher)
            and bool(distribution_digest)
            and bool(profile_digest)
            and bool(integration_version)
        )
        return {
            "exact": exact,
            "resource_id": resource_id,
            "resource_version": resource_version,
            "publisher_identity": publisher,
            "distribution_digest": distribution_digest,
            "profile_digest": profile_digest,
            "integration_version": integration_version,
        }

    async def _q_install_not_counted_as_use(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        """Verify install produced no activation and no terminal outcome.

        An install is not a use. The stored receipt must carry an
        activation event count of zero and no terminal outcome.
        """
        reporter = query.get("reporter_agent") or query.get("agent")
        role = self._role_of(reporter, agent_roles)
        # Check feedback records — an install that was counted as use
        # would appear as a feedback/usage entry with event=install
        # or with a terminal outcome.
        status, feedback = await self._feedback_for(query, agent_roles)
        activation_count = 0
        terminal_outcome_count = 0
        if status == 200 and feedback is not None:
            # If feedback exists for the resource and carries an
            # activation event or terminal outcome, the install was
            # counted as use.
            event = feedback.get("event") or feedback.get("first_event")
            if event and event != "install":
                activation_count = 1
            outcome = feedback.get("outcome")
            if outcome and outcome not in ("", "unknown", None):
                terminal_outcome_count = 1
        # Also check any artifact the consumer saved
        try:
            receipt = _load_json_object(query.get("receipt_artifact"))
            if receipt.get("event") and receipt.get("event") != "install":
                activation_count += 1
            outcome = receipt.get("outcome")
            if outcome and outcome not in ("", "unknown", None):
                terminal_outcome_count += 1
        except (OSError, TypeError, ValueError):
            pass  # Artifact is optional for this query.
        # Baseline-aware: if we have a baseline, any pre-existing
        # feedback records are not from this run.
        baseline = query.get("_baseline")
        if isinstance(baseline, dict):
            baseline_feedback = baseline.get("feedback_ids", [])
            if baseline_feedback and feedback is not None:
                # Feedback pre-existed; don't count it.
                activation_count = 0
                terminal_outcome_count = 0
        separated = activation_count == 0 and terminal_outcome_count == 0
        return {
            "separated": separated,
            "activation_count": activation_count,
            "terminal_outcome_count": terminal_outcome_count,
            "evidence": {"source": "api", "role": role},
        }

    async def _q_private_payload_absent(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        """Verify no excluded category appears in the stored record or API log.

        Checks the feedback record and any saved artifacts for prompt,
        file content, path, tool arguments, tool results, secrets, or
        user identity.
        """
        _, feedback = await self._feedback_for(query, agent_roles)
        forbidden = {
            "prompt",
            "source_code",
            "path",
            "tool_arguments",
            "tool_result",
            "request",
            "response",
            "raw_payload",
            "secret",
            "user_identity",
            "credential",
            "token",
            "content",
        }
        checked_fields: list[str] = []
        clean = True
        if feedback is not None:
            keys = set(feedback)
            checked_fields = sorted(keys)
            leaked = keys.intersection(forbidden)
            if leaked:
                clean = False
        # Also check artifacts for privacy canaries
        checked_artifacts: list[str] = []
        canary = str(query.get("privacy_canary") or "")
        for raw_path in elements(query, "artifacts"):
            path = Path(str(raw_path))
            try:
                text = path.read_text()  # noqa: ASYNC240
                checked_artifacts.append(str(path))
                if canary and canary in text:
                    clean = False
            except OSError:
                continue
        return {
            "clean": clean,
            "checked_fields": checked_fields,
            "checked_artifacts": checked_artifacts,
        }

    async def _q_disabled_use_zero_receipts(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        """Verify zero receipts server-side for the disabled leg.

        Not merely a suppressed upload — the server must have no
        record. Compares the current feedback count against the
        baseline to detect any new receipt.
        """
        await self._feedback_for(query, agent_roles)
        baseline = query.get("_baseline")
        baseline_count = 0
        if isinstance(baseline, dict):
            baseline_ids = baseline.get("feedback_ids", [])
            if isinstance(baseline_ids, list):
                baseline_count = len(baseline_ids)
        # Count current feedback records for this resource
        reporter = query.get("reporter_agent") or query.get("agent")
        role = self._role_of(reporter, agent_roles)
        status, payload = await self._get("/v1/feedback/mine", role)
        receipt_count = 0
        if status == 200 and isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                expected_resource = query.get("resource_id")
                for item in items:
                    if isinstance(item, dict) and (
                        not expected_resource
                        or item.get("resource_id") == expected_resource
                    ):
                        receipt_count += 1
        # If the only feedback record is the one from the enabled leg,
        # the disabled leg produced zero new receipts.
        new_receipts = max(0, receipt_count - baseline_count)
        # If feedback exists but predates the disabled leg, it's from
        # the enabled leg — that's expected and not a violation.
        zero_receipts = new_receipts == 0
        return {
            "zero_receipts": zero_receipts,
            "receipt_count": receipt_count,
            "baseline_receipt_count": baseline_count,
            "new_receipts": new_receipts,
            "evidence": {"source": "api"},
        }

    async def _q_publisher_receipt_never_rates_or_funds(
        self, query: JsonObject, agent_roles: dict[str, str]
    ) -> JsonObject:
        """Verify no rating, review, eval, bounty, or ledger row resulted.

        A publisher receipt can inform scorecards and improvement
        candidates but cannot create a rating, a review, an eval
        result, bounty funding, or a payment.
        """
        reporter = query.get("reporter_agent") or query.get("agent")
        role = self._role_of(reporter, agent_roles)
        baseline = query.get("_baseline")
        baseline_ids = self._extract_baseline_ids(baseline)
        # Check feedback for a rating/review
        _, feedback = await self._feedback_for(query, agent_roles)
        feedback_count, course_review_count = self._count_feedback_reviews(
            feedback, baseline_ids["review"]
        )
        bounty_count = self._count_new_bounties(
            await self._bounties(role), baseline_ids["bounty"]
        )
        ledger_count = self._count_new_ledger_payments(
            await self._ledger(role), baseline_ids["ledger"]
        )
        eval_count = self._count_eval_projections(feedback)
        clean = (
            course_review_count == 0
            and bounty_count == 0
            and ledger_count == 0
            and eval_count == 0
        )
        return {
            "clean": clean,
            "feedback_count": feedback_count,
            "course_review_count": course_review_count,
            "eval_count": eval_count,
            "bounty_count": bounty_count,
            "ledger_count": ledger_count,
        }

    @staticmethod
    def _extract_baseline_ids(
        baseline: JsonValue,
    ) -> dict[str, set[str]]:
        """Extract review, bounty, and ledger id sets from the baseline."""
        review_ids: set[str] = set()
        bounty_ids: set[str] = set()
        ledger_ids: set[str] = set()
        if isinstance(baseline, dict):
            review_raw = baseline.get("review_ids", [])
            if isinstance(review_raw, list):
                review_ids = {str(rid) for rid in review_raw}
            bounty_raw = baseline.get("bounty_ids", [])
            if isinstance(bounty_raw, list):
                bounty_ids = {str(bid) for bid in bounty_raw}
            ledger = baseline.get("credit_ledger_ids", {})
            if isinstance(ledger, dict):
                for role_ledger in ledger.values():
                    if isinstance(role_ledger, list):
                        ledger_ids.update(str(lid) for lid in role_ledger)
        return {
            "review": review_ids,
            "bounty": bounty_ids,
            "ledger": ledger_ids,
        }

    @staticmethod
    def _count_feedback_reviews(
        feedback: JsonObject | None,
        baseline_review_ids: set[str],
    ) -> tuple[int, int]:
        """Count feedback records and new course reviews."""
        feedback_count = 0
        course_review_count = 0
        if feedback is not None:
            feedback_count = 1
            if feedback.get("course_review_id"):
                review_id = str(feedback.get("course_review_id"))
                if review_id not in baseline_review_ids:
                    course_review_count = 1
        return feedback_count, course_review_count

    @staticmethod
    def _count_new_bounties(
        bounties: list[JsonObject], baseline_bounty_ids: set[str]
    ) -> int:
        """Count bounties not present in the baseline."""
        bounty_count = 0
        for bounty in bounties:
            bounty_id = str(bounty.get("id") or "")
            if bounty_id and bounty_id not in baseline_bounty_ids:
                bounty_count += 1
        return bounty_count

    @staticmethod
    def _count_new_ledger_payments(
        ledger: list[JsonObject], baseline_ledger_ids: set[str]
    ) -> int:
        """Count ledger payment rows not present in the baseline."""
        ledger_count = 0
        for entry in ledger:
            entry_id = str(entry.get("id") or "")
            if entry_id and entry_id not in baseline_ledger_ids:
                kind = str(opt_str(entry, "kind", "")).lower()
                if any(
                    word in kind
                    for word in ("payment", "payout", "bounty", "reward")
                ):
                    ledger_count += 1
        return ledger_count

    @staticmethod
    def _count_eval_projections(feedback: JsonObject | None) -> int:
        """Count eval projections carried by a feedback record."""
        eval_count = 0
        if feedback is not None:
            disposition = feedback.get("projection_disposition")
            if disposition == "projected" and feedback.get("course_review_id"):
                # A projected course review from a publisher receipt is
                # the eval path — it should not exist.
                eval_count = 1
        return eval_count


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


def _artifact_failure(reason: str, result_key: str) -> JsonObject:
    return {result_key: False, "reason": reason, "evidence": {}}


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
