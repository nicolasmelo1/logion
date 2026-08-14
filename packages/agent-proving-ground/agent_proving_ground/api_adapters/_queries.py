from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
        if not self._keys.configured:
            return _unsupported("no proving-ground API keys configured")
        query_type = query.get("type")
        handler = getattr(self, f"_q_{query_type}", None)
        if handler is None:
            return _unsupported(f"query {query_type} not implemented")
        return await handler(query, agent_roles)

    async def baseline(self, agent_roles: dict[str, str]) -> dict[str, Any]:
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

    async def _get(self, path: str, role: str | None) -> tuple[int, Any]:
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
    ) -> tuple[int, list[dict[str, Any]]]:
        """Collect a cursor-paginated JSON collection without truncation."""
        rows: list[dict[str, Any]] = []
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
        self, agent_id: str | None, agent_roles: dict[str, str]
    ) -> str | None:
        if agent_id is None:
            return None
        return agent_roles.get(agent_id)

    async def _q_github_identity_linked(
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
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
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
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

    async def _my_courses(self, role: str | None) -> list[dict[str, Any]]:
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

    async def _ledger(self, role: str | None) -> list[dict[str, Any]]:
        status, data = await self._get("/v1/credits/ledger", role)
        if status != 200:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return []

    async def _bounties(self, role: str | None) -> list[dict[str, Any]]:
        status, data = await self._get("/v1/bounties", role)
        if status != 200:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        return []

    async def _q_course_exists(
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
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
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
        buyer_role = self._role_of(query.get("buyer_agent"), agent_roles)
        entries = await self._ledger(buyer_role)
        for entry in entries:
            kind = str(entry.get("kind", "")).lower()
            direction = str(entry.get("direction", "")).lower()
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
        self, query: dict[str, Any], agent_roles: dict[str, str]
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
        query: dict[str, Any],
        reviewer_role: str | None,
        agent_roles: dict[str, str],
    ) -> dict[str, Any] | None:
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
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
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
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
        # In the real product the usage report and the course review share
        # the same API surface (upsert_course_review + telemetry fields).
        result = await self._q_review_exists(query, agent_roles)
        if result.get("found"):
            result["report_id"] = result.get("review_id")
        return result

    async def _q_bounty_exists(
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
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
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
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
        self, query: dict[str, Any], agent_roles: dict[str, str]
    ) -> dict[str, Any]:
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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
        roles = set(agent_roles.values()) or {"buyer"}
        for role in roles:
            entries = await self._ledger(role)
            baseline = query.get("_baseline")
            baseline_ids = set()
            if isinstance(baseline, dict):
                role_ids = baseline.get("credit_ledger_ids", {}).get(role, [])
                if isinstance(role_ids, list):
                    baseline_ids = {str(entry_id) for entry_id in role_ids}
            seen: dict[tuple[str, int], int] = {}
            for entry in entries:
                if str(entry.get("id")) in baseline_ids:
                    continue
                kind = str(entry.get("kind", "")).lower()
                if "purchase" not in kind:
                    continue
                marker = (kind, int(entry.get("amount_cents") or 0))
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
        query: dict[str, Any],  # noqa: ARG002
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
        buyer_role = "buyer" if "buyer" in agent_roles.values() else None
        status, data = await self._get("/v1/listings", buyer_role)
        items: list[dict[str, Any]] = []
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
        query: dict[str, Any],  # noqa: ARG002
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
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
                "listing_id": str(data.get("id", "")),
                "tier": data.get("tier"),
                "evidence": {"source": "api"},
            }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_indexed_listing_tier(
        self,
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
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
                "listing_id": str(data.get("id", "")),
                "tier": actual_tier,
                "evidence": {"source": "api"},
            }
        return {"tier_matches": False, "evidence": {"source": "api"}}

    async def _q_platform_bounty_accepted(
        self,
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
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
                    "submission_id": str(sub.get("id", "")),
                    "evidence": {"source": "api"},
                }
        return {"accepted": False, "evidence": {"source": "api"}}

    async def _q_resource_projection_exists(
        self,
        query: dict[str, Any],
        agent_roles: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Check the complete resource collection for a projection kind."""
        projection_kind = query.get("projection_kind", "indexed_listing")
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
        query: dict[str, Any],  # noqa: ARG002
        agent_roles: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
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
            projections = detail.get("projections", [])
            if not isinstance(projections, list) or not all(
                isinstance(projection, dict)
                and isinstance(projection.get("projection_kind"), str)
                and bool(projection["projection_kind"])
                and isinstance(projection.get("projection_id"), str)
                and bool(projection["projection_id"])
                for projection in projections
            ):
                return _unsupported("resource detail has invalid projections")
            for projection in projections:
                projection_ids.add(projection["projection_id"])
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
        query: dict[str, Any],  # noqa: ARG002
        agent_roles: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
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
        query: dict[str, Any],
        agent_roles: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
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
                and int(created) == 0
                and int(linked) == 0
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
        query: dict[str, Any],
        agent_roles: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
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
                and int(created) == 2
                and int(linked) == 2
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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
        """Verify each fixture canonical has its expected projection kind."""
        raw_kinds = query.get("projection_kinds")
        raw_canonicals = query.get("canonicals", [])
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
        expected_pairs = set(zip(raw_canonicals, raw_kinds, strict=True))
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
            resource_pairs = {
                (canonical, str(projection["projection_kind"]))
                for projection in projections
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
        query: dict[str, Any],
        agent_roles: dict[str, str],
    ) -> dict[str, Any]:
        """Verify that legacy course purchase still works."""
        buyer_role = self._role_of(query.get("buyer_agent"), agent_roles)
        status, data = await self._get("/v1/credits/ledger", buyer_role)
        if status != 200 or not isinstance(data, list):
            return {"found": False, "evidence": {"source": "api"}}
        baseline = query.get("_baseline")
        baseline_ids = set()
        if isinstance(baseline, dict):
            role_ids = baseline.get("credit_ledger_ids", {}).get(
                buyer_role, []
            )
            if isinstance(role_ids, list):
                baseline_ids = {str(entry_id) for entry_id in role_ids}
        for entry in data:
            if (
                isinstance(entry, dict)
                and str(entry.get("id")) not in baseline_ids
                and entry.get("kind") == "course_purchase"
            ):
                return {
                    "found": True,
                    "purchase_id": str(entry.get("id", "")),
                    "evidence": {"source": "api", "surface": "credit_ledger"},
                }
        return {"found": False, "evidence": {"source": "api"}}

    async def _q_harness_scope_targets_resolved(
        self,
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        artifacts = query.get("artifacts")
        required_scopes = set(query.get("required_scopes", []))
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        try:
            plan = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
            before = _load_json_object(query.get("before_snapshot"))
            after = _snapshot_roots(query.get("snapshot_roots", []))
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        try:
            receipt = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "acquired")
        acquired = (
            receipt.get("resource_id")
            and receipt.get("installation_id")
            and receipt.get("verification") in {"exact", "source_revision"}
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        try:
            receipt = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "selected")
        channel = receipt.get("channel")
        allowed = query.get("allowed_channels") or []
        selected = bool(channel) and channel in allowed
        return {
            "selected": selected,
            "channel": channel,
            "distribution_id": receipt.get("distribution_id"),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_native_install_reconciled(
        self,
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        try:
            report = _load_cli_object(
                query.get("artifact"), "logion.resources.reconcile"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "reconciled")
        matched = report.get("matched") or []
        unresolved = report.get("unresolved") or []
        ambiguous = report.get("ambiguous") or []
        drifted = report.get("drifted") or []
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

    async def _q_inventory_receipt_matches(
        self,
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        try:
            report = _load_cli_object(
                query.get("artifact"), "logion.resources.reconcile"
            )
            receipt = _load_cli_object(
                query.get("acquire_artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "matches")
        matched = report.get("matched") or []
        ids = {entry.get("installation_id") for entry in matched}
        matches = receipt.get("installation_id") in ids
        return {
            "matches": matches,
            "installation_id": receipt.get("installation_id"),
            "matched_ids": sorted(ids),
            "evidence": {"source": str(query.get("artifact"))},
        }

    async def _q_installed_artifact_digest_matches(
        self,
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        try:
            receipt = _load_cli_object(
                query.get("artifact"), "logion.resources.acquire"
            )
        except (OSError, TypeError, ValueError) as exc:
            return _artifact_failure(str(exc), "digest_matches")
        scope_root = Path(str(query.get("scope_root", "")))
        installed = receipt.get("installed_paths") or []
        if not installed:
            return _artifact_failure(
                "receipt lists no installed paths", "digest_matches"
            )
        evidence = receipt.get("native_evidence") or {}
        file_digests = evidence.get("file_digests") or {}
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
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
            str(p) for p in first.get("installed_paths") or []
        )
        second_paths = sorted(
            str(p) for p in second.get("installed_paths") or []
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
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
            for entry in report.get("drifted") or []
            if isinstance(entry, dict)
        }
        matched_ids = {
            entry.get("installation_id")
            for entry in report.get("matched") or []
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Assert an acquisition touched nothing outside its own scope.

        Compares a pre-acquisition snapshot against the protected roots
        (the isolated user home, a second repository) so a repository
        install that silently writes into user scope fails the run.
        """
        try:
            before = _load_json_object(query.get("before_snapshot"))
            protected = [
                str(root) for root in query.get("protected_roots", [])
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        artifacts = query.get("artifacts")
        expected_root = str(query.get("expected_root", ""))
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        artifacts = query.get("artifacts")
        resource_name = str(query.get("resource_name", ""))
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
        query: dict[str, Any],
        agent_roles: dict[str, str],  # noqa: ARG002
    ) -> dict[str, Any]:
        path = Path(str(query.get("artifact", "")))
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


def _resolved_scope_root(raw: Any) -> Path:
    """Validate a scenario-supplied scope root outside the async path."""
    root = Path(str(raw or ""))
    if not root.is_dir():
        raise ValueError(f"scope_root is not a directory: {root}")
    return root


def _duplicate_install_state(scope_root: Path) -> list[str]:
    """List staging/backup directories an interrupted swap left behind."""
    leftovers: list[str] = []
    for pattern in ("*.logion-incoming", "*.logion-backup"):
        leftovers.extend(
            str(path.relative_to(scope_root))
            for path in scope_root.rglob(pattern)
        )
    return sorted(leftovers)


def _artifact_failure(reason: str, result_key: str) -> dict[str, Any]:
    return {result_key: False, "reason": reason, "evidence": {}}


def _load_json_object(raw_path: Any) -> dict[str, Any]:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("artifact path is required")
    path = Path(raw_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"artifact is not a regular file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"artifact is not a JSON object: {path}")
    return payload


def _load_cli_data(raw_path: Any, expected_kind: str) -> Any:
    envelope = _load_json_object(raw_path)
    if (
        envelope.get("version") != "v1"
        or envelope.get("kind") != expected_kind
    ):
        raise ValueError(f"unexpected CLI envelope in {raw_path}")
    return envelope.get("data")


def _load_cli_object(raw_path: Any, expected_kind: str) -> dict[str, Any]:
    data = _load_cli_data(raw_path, expected_kind)
    if not isinstance(data, dict):
        raise TypeError(f"CLI data is not an object: {raw_path}")
    return data


def _load_cli_list(raw_path: Any, expected_kind: str) -> list[Any]:
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


def _snapshot_roots(raw_roots: Any) -> dict[str, str]:
    if not isinstance(raw_roots, list) or not raw_roots:
        raise ValueError("snapshot_roots list is required")
    result: dict[str, str] = {}
    for raw_root in raw_roots:
        root = Path(str(raw_root))
        if not root.is_dir():
            raise ValueError(f"snapshot root is not a directory: {root}")
        skip_dirs = {".cache", "__pycache__", ".local", "Library", ".git"}
        for path in sorted(root.rglob("*")):
            if path.is_file():
                if any(part in skip_dirs for part in path.parts):
                    continue
                result[str(path.resolve())] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return result


def _contains_forbidden_observation_data(envelope: dict[str, Any]) -> bool:
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


def _unsupported(reason: str) -> dict[str, Any]:
    return {"found": False, "unsupported": True, "reason": reason}


def _baseline_ids(query: dict[str, Any], key: str) -> set[str]:
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
