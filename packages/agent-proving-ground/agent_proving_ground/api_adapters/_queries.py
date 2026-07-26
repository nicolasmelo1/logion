from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from agent_proving_ground.api_adapters._http import http_request_json

ROLE_KEYS_FILE_ENV = "LOGION_PROVING_GROUND_ROLE_KEYS_FILE"
SINGLE_KEY_ENVS = ("LOGION_PROVING_GROUND_API_KEY", "LOGION_API_KEY")
_DEFAULT_ROLE = "seller"


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
        empty_snapshots = {"", "[]", "{}", "null", "None"}
        snapshots_unchanged = (
            isinstance(before, str)
            and isinstance(after, str)
            and before.strip() not in empty_snapshots
            and after.strip() not in empty_snapshots
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
        snapshot_present = isinstance(snapshot, str) and bool(snapshot.strip())
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
        agent_roles: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Verify fixture identities and kinds through resource details."""
        raw_kinds = query.get("projection_kinds")
        raw_canonicals = query.get("canonicals", [])
        if (
            not isinstance(raw_kinds, list)
            or not raw_kinds
            or not all(isinstance(kind, str) and kind for kind in raw_kinds)
            or not isinstance(raw_canonicals, list)
            or not all(
                isinstance(canonical, str) and canonical
                for canonical in raw_canonicals
            )
        ):
            return _unsupported(
                "projection_kinds/canonicals have invalid shape"
            )
        expected_kinds = set(raw_kinds)
        expected_canonicals = set(raw_canonicals)
        status, items = await self._paged_get("/v1/resources", "admin")
        if status != 200:
            return {
                "kinds_match": False,
                "unsupported": True,
                "reason": "resource endpoint not available",
            }
        found_kinds: set[str] = set()
        found_canonicals: set[str] = set()
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
            found_canonicals.add(canonical)
            found_kinds.update(
                str(projection["projection_kind"])
                for projection in projections
                if isinstance(projection.get("projection_kind"), str)
                and projection["projection_kind"]
            )
            if expected_kinds.issubset(
                found_kinds
            ) and expected_canonicals.issubset(found_canonicals):
                break
        matched_kinds = sorted(expected_kinds & found_kinds)
        matched_canonicals = sorted(expected_canonicals & found_canonicals)
        return {
            "kinds_match": expected_kinds.issubset(found_kinds)
            and expected_canonicals.issubset(found_canonicals),
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
