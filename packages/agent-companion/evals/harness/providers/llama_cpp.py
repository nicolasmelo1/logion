# SPDX-License-Identifier: MIT
"""llama.cpp provider for live local evals.

The provider loads ``SKILL.md`` as the system prompt and exposes the real
``logion`` CLI commands as OpenAI-compatible tools. The user prompt carries
only the scenario request — the catalog must be discovered via
``logion_listings_search`` rather than handed to the model. This way the eval
actually tests whether the published skill drives the right behavior, not
whether the model can follow a hand-authored eval contract.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

import yaml

from evals.harness._json import JsonObject, JsonValue
from evals.harness.schema import (
    Catalog,
    Scenario,
    ToolCall,
    Trace,
)

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_RETRIES = 1
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 900
DEFAULT_SEED = 42
MAX_VALIDATION_ERROR_CHARS = 800
MAX_TOOL_ROUNDS = 8

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
SKILL_MD_PATH = PACKAGE_ROOT / "SKILL.md"

OUTPUT_CONTRACT = (
    "After all required tool calls, return ONLY strict JSON in message "
    "content with these keys: final_answer (string), selected_course_ids "
    "(array of catalog course ids), loaded_skill_ids (array of installed "
    "skill ids). No prose, no markdown fences, no `calls` field — tool "
    "calls belong in the OpenAI tool_calls channel."
)


def _load_skill_md() -> str:
    text = SKILL_MD_PATH.read_text(encoding="utf-8")
    if text.startswith("---"):
        # Drop the YAML frontmatter — the model only needs the prose policy.
        _, _, body = text[3:].partition("\n---")
        text = body.lstrip("\n")
    return text.strip()


class LlamaCppProviderError(RuntimeError):
    """Raised when the local llama.cpp provider cannot produce a trace."""


class LlamaCppTransportError(LlamaCppProviderError):
    """Raised for HTTP/timeout failures talking to llama-server.

    Distinguishing transport from contract errors lets the run loop avoid
    feeding network errors back to the model as "your response was invalid"
    validation feedback.
    """


@dataclass(frozen=True)
class LlamaCppProviderConfig:
    name: str
    base_url: str
    api_key: str
    timeout_seconds: int
    retries: int
    validation_retries: int
    temperature: float
    max_tokens: int
    seed: int | None


@dataclass(frozen=True)
class ToolSpec:
    """OpenAI-compatible function spec using the CLI trace name."""

    name: str
    description: str
    parameters: JsonObject


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="logion_recall_search",
        description=(
            "Run `logion recall search QUERY --limit N` (read-only). "
            "Always run this before logion_listings_search."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_listings_search",
        description=(
            "Run `logion listings search` to search the marketplace. "
            "Use --category and --tag for structured filtering; use "
            "--query for free-text search. Use only if local recall is "
            "insufficient."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
                "tag": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1},
                "include_indexed": {
                    "type": "boolean",
                    "description": (
                        "Also include indexed external listings that have not "
                        "been claimed or published as courses."
                    ),
                },
                "tier": {
                    "type": "string",
                    "enum": ["indexed", "improving", "published"],
                    "description": "Filter by listing tier.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_indexed_get",
        description=(
            "Run `logion indexed get LISTING_ID` to inspect an indexed "
            "external listing. Indexed listings are read-only discovery "
            "items and cannot be installed directly."
        ),
        parameters={
            "type": "object",
            "properties": {"listing_id": {"type": "string"}},
            "required": ["listing_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_get",
        description=(
            "Run `logion courses get COURSE_ID` to inspect a marketplace "
            "course before recommending or installing it."
        ),
        parameters={
            "type": "object",
            "properties": {"course_id": {"type": "string"}},
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_create",
        description=(
            "Run `logion courses create --title TITLE --slug SLUG ...` to "
            "draft course metadata. Free drafts with supplied metadata may "
            "proceed directly; paid pricing requires explicit confirmation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "slug": {"type": "string"},
                "description": {"type": "string"},
                "price_cents": {"type": "integer", "minimum": 0},
                "currency": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "language": {"type": "string"},
                "short_summary": {"type": "string"},
                "visibility": {
                    "type": "string",
                    "enum": ["public", "unlisted", "private"],
                },
            },
            "required": ["title", "slug"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_update",
        description=(
            "Run `logion courses update COURSE_ID ...` to edit course "
            "metadata. Price or visibility changes require confirmation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "price_cents": {"type": "integer", "minimum": 0},
                "currency": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "language": {"type": "string"},
                "short_summary": {"type": "string"},
                "visibility": {
                    "type": "string",
                    "enum": ["public", "unlisted", "private"],
                },
            },
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_capabilities_validate",
        description=(
            "Run `logion courses capabilities validate --bundle-dir DIR` "
            "before upload or publication."
        ),
        parameters={
            "type": "object",
            "properties": {"bundle_dir": {"type": "string"}},
            "required": ["bundle_dir"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_capabilities_print",
        description=(
            "Run `logion courses capabilities print --bundle-dir DIR` to "
            "inspect normalized capability metadata."
        ),
        parameters={
            "type": "object",
            "properties": {"bundle_dir": {"type": "string"}},
            "required": ["bundle_dir"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_uploads_create",
        description=(
            "Run `logion courses uploads create COURSE_ID --file PATH` to "
            "start an upload session. Requires explicit confirmation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "files": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["course_id", "files"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_uploads_push",
        description=(
            "Run `logion courses uploads push COURSE_ID VERSION_ID "
            "--session-file FILE --file PATH` after approval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "version_id": {"type": "string"},
                "session_file": {"type": "string"},
                "files": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["course_id", "version_id", "session_file"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_uploads_complete",
        description=(
            "Run `logion courses uploads complete COURSE_ID VERSION_ID` "
            "after files have been uploaded."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "version_id": {"type": "string"},
            },
            "required": ["course_id", "version_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_publication_request",
        description=(
            "Run `logion courses publication request COURSE_ID` to request "
            "publication review. Requires explicit confirmation."
        ),
        parameters={
            "type": "object",
            "properties": {"course_id": {"type": "string"}},
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_publication_latest",
        description=(
            "Run `logion courses publication latest COURSE_ID` to inspect "
            "the latest publication review status."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "include_pass": {"type": "boolean"},
            },
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_feedback",
        description=(
            "Run `logion courses feedback COURSE_ID` to retrieve review "
            "feedback for a course."
        ),
        parameters={
            "type": "object",
            "properties": {"course_id": {"type": "string"}},
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_courses_report_usage",
        description=(
            "Run `logion courses report-usage COURSE_ID VERSION_ID "
            "--rating N ...` to file a usage review after completing a "
            "course-driven task. Tier B self-report only; rating is "
            "required, all other fields optional."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "version_id": {"type": "string"},
                "rating": {"type": "integer", "minimum": 1, "maximum": 5},
                "usefulness": {"type": "number"},
                "reliability": {"type": "number"},
                "tool_safety": {"type": "number"},
                "token_efficiency": {"type": "number"},
                "completed_task": {"type": "boolean"},
                "body": {"type": "string"},
            },
            "required": ["course_id", "version_id", "rating"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_payments_orders_get",
        description=(
            "Run `logion payments orders get ORDER_ID` to retrieve "
            "the status of a payment order."
        ),
        parameters={
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_payments_seller_readiness",
        description=(
            "Run `logion payments seller-readiness` to check whether the "
            "creator can sell paid courses."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_payments_onboarding_link",
        description=(
            "Run `logion payments onboarding-link` to create seller "
            "onboarding. Requires explicit user confirmation."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_skills_install",
        description=(
            "Run `logion skills install --course-id COURSE_ID --version-id "
            "VERSION_ID --source ./BUNDLE`. Requires explicit user approval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "version_id": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_skills_updates",
        description=(
            "Run `logion skills updates` to list available updates for "
            "installed skills (read-only)."
        ),
        parameters={
            "type": "object",
            "properties": {"course_id": {"type": "string"}},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_skills_update",
        description=(
            "Run `logion skills update COURSE_ID --version-id VERSION_ID "
            "--source ./BUNDLE`. Requires explicit user approval, especially "
            "when price, permissions, required tools, or execution policy "
            "change."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "version_id": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_skills_inspect",
        description=(
            "Run `logion skills inspect COURSE_ID` to read an already-"
            "installed skill artifact into context."
        ),
        parameters={
            "type": "object",
            "properties": {"course_id": {"type": "string"}},
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_skills_permission_expand",
        description=(
            "Request expanded permissions for an installed skill. Requires "
            "explicit user approval in the final answer."
        ),
        parameters={
            "type": "object",
            "properties": {
                "capability_id": {"type": "string"},
                "scope": {"type": "string"},
            },
            "required": ["capability_id", "scope"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_notifications_unread_count",
        description=(
            "Run `logion notifications unread-count` before listing "
            "notifications."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_notifications_list",
        description=(
            "Run `logion notifications list --unread-only --limit N` after "
            "checking unread count."
        ),
        parameters={
            "type": "object",
            "properties": {
                "unread_only": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_course_reviews_list",
        description=(
            "Run `logion course-reviews list COURSE_ID` to inspect trust "
            "signals before recommending a course."
        ),
        parameters={
            "type": "object",
            "properties": {"course_id": {"type": "string"}},
            "required": ["course_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_credits_top_up",
        description=(
            "Run `logion credits top-up --amount AMOUNT_CENTS --yes` to "
            "create a Stripe Checkout session for credit top-up."
        ),
        parameters={
            "type": "object",
            "properties": {"amount_cents": {"type": "integer"}},
            "required": ["amount_cents"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_bounties_ls",
        description=(
            "Run `logion bounties ls` to discover marketplace bounties."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_bounties_create",
        description=(
            "Create a draft bounty on a course. Requires explicit user "
            "approval before creating."
        ),
        parameters={
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
                "title": {"type": "string"},
                "reward_cents": {"type": "integer"},
            },
            "required": ["course_id", "title"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_bounties_open",
        description=("Open a funded bounty to accept submissions."),
        parameters={
            "type": "object",
            "properties": {
                "bounty_id": {"type": "string"},
            },
            "required": ["bounty_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_bounties_get",
        description="Run `logion bounties get BOUNTY_ID` for bounty details.",
        parameters={
            "type": "object",
            "properties": {"bounty_id": {"type": "string"}},
            "required": ["bounty_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_bounties_submission_create",
        description=(
            "Create a bounty submission draft. Requires explicit user "
            "approval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "bounty_id": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["bounty_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_bounties_fund",
        description=(
            "Start the hosted funding flow for a bounty. Do not bypass the "
            "checkout flow."
        ),
        parameters={
            "type": "object",
            "properties": {
                "bounty_id": {"type": "string"},
                "amount_usd": {"type": "number"},
            },
            "required": ["bounty_id"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="logion_reports_create",
        description=(
            "Run `logion reports create ...` only on explicit user direction."
        ),
        parameters={
            "type": "object",
            "properties": {
                "target_type": {"type": "string"},
                "target_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["target_type", "target_id"],
            "additionalProperties": False,
        },
    ),
)
KNOWN_TOOL_NAMES = frozenset(spec.name for spec in TOOL_SPECS)


@dataclass(frozen=True)
class LlamaCppModelConfig:
    id: str
    provider: str
    repo: str
    file: str
    quant: str | None
    context: int
    server_args: tuple[str, ...]
    chat_template_kwargs: tuple[tuple[str, JsonValue], ...] = ()

    def chat_template_kwargs_dict(self) -> JsonObject:
        return dict(self.chat_template_kwargs)


@dataclass(frozen=True)
class LlamaCppProvider:
    model: LlamaCppModelConfig
    config: LlamaCppProviderConfig
    config_path: Path | None = None

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def base_url(self) -> str:
        return self.config.base_url.rstrip("/")

    def report_metadata(self) -> JsonObject:
        quant = self.model.quant or infer_quant_from_filename(self.model.file)
        return {
            "provider": self.name,
            "model_id": self.model.id,
            "base_url": self.base_url,
            "repo": self.model.repo,
            "file": self.model.file,
            "quant": quant,
            "context": self.model.context,
            "validation_retries": self.config.validation_retries,
            "server_args": list(self.model.server_args),
            "config_path": (
                str(self.config_path) if self.config_path is not None else None
            ),
        }

    def run(self, scenario: Scenario, catalog: Catalog) -> Trace:
        last_error: LlamaCppProviderError | None = None
        previous_response: str | None = None
        validation_feedback: str | None = None
        attempts = self.config.validation_retries + 1
        for _attempt in range(1, attempts + 1):
            messages = self._build_messages(
                scenario,
                catalog,
                previous_response=previous_response,
                validation_feedback=validation_feedback,
            )
            calls: list[ToolCall] = []
            token_estimate = {"input": 0, "output": 0}
            last_response: JsonObject | None = None
            try:
                for _round in range(1, MAX_TOOL_ROUNDS + 1):
                    response = self._post_json(
                        self._build_payload_from_messages(messages)
                    )
                    last_response = response
                    message = extract_response_message(response)
                    token_estimate = merge_token_estimates(
                        token_estimate,
                        usage_to_token_estimate(response.get("usage")),
                    )
                    round_calls = list(
                        parse_tool_calls(message.get("tool_calls"))
                    )
                    calls.extend(round_calls)
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return self._trace_from_message_content(
                            content,
                            scenario.id,
                            tuple(calls),
                            token_estimate,
                        )
                    if not round_calls:
                        messages.append(build_final_json_reminder(scenario))
                        continue
                    messages.append(message_for_history(message))
                    for index, call in enumerate(round_calls):
                        raw_call = message["tool_calls"][index]
                        messages.append(
                            build_tool_result_message(
                                raw_call, call, scenario, catalog
                            )
                        )
                raise_tool_loop_exceeded()
            except LlamaCppTransportError:
                # Transport failures already retried inside _post_json; let
                # them propagate rather than feeding "your response was
                # invalid" back to the model as validation feedback.
                raise
            except LlamaCppProviderError as exc:
                last_error = exc
                previous_response = extract_message_content(
                    last_response or {}
                )
                validation_feedback = self._validation_feedback(exc)
        if last_error is None:
            raise LlamaCppProviderError(
                "llama.cpp validation retry loop exhausted without an error"
            )
        raise last_error

    def _build_payload(
        self,
        scenario: Scenario,
        catalog: Catalog,
        *,
        previous_response: str | None = None,
        validation_feedback: str | None = None,
    ) -> JsonObject:
        return self._build_payload_from_messages(
            self._build_messages(
                scenario,
                catalog,
                previous_response=previous_response,
                validation_feedback=validation_feedback,
            )
        )

    def _build_payload_from_messages(
        self, messages: list[JsonObject]
    ) -> JsonObject:
        payload: JsonObject = {
            "model": self.model.id,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
            "tools": build_openai_tools(),
            "tool_choice": "auto",
        }
        if self.config.seed is not None:
            payload["seed"] = self.config.seed
        chat_template_kwargs = self.model.chat_template_kwargs_dict()
        if chat_template_kwargs:
            payload["chat_template_kwargs"] = chat_template_kwargs
        return payload

    def _build_messages(
        self,
        scenario: Scenario,
        catalog: Catalog,  # noqa: ARG002 - kept for API parity; catalog is no longer inlined
        *,
        previous_response: str | None = None,
        validation_feedback: str | None = None,
    ) -> list[JsonObject]:
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._build_user_prompt(scenario)},
        ]
        if validation_feedback is not None:
            if previous_response:
                messages.append({
                    "role": "assistant",
                    "content": previous_response,
                })
            messages.append({
                "role": "user",
                "content": validation_feedback,
            })
        return messages

    def _system_prompt(self) -> str:
        tool_names = ", ".join(spec.name for spec in TOOL_SPECS)
        return (
            f"{_load_skill_md()}\n\n"
            "## Eval execution contract\n\n"
            "You are driving the Logion Marketplace Companion described "
            "above. Take CLI actions via OpenAI tool_calls. Available "
            f"functions (use these exact names): {tool_names}.\n\n"
            f"{OUTPUT_CONTRACT}"
        )

    def _build_user_prompt(self, scenario: Scenario) -> str:
        payload = {
            "user_request": scenario.prompt,
            "installed_capabilities": list(scenario.installed_capabilities),
            "local_recall_hits": list(scenario.local_recall),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _validation_feedback(self, exc: LlamaCppProviderError) -> str:
        details = truncate_validation_error(str(exc))
        return (
            f"Your previous answer failed validation: {details}. "
            f"Retry now. {OUTPUT_CONTRACT}"
        )

    def _post_json(self, payload: JsonObject) -> JsonObject:
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        body = json.dumps(payload).encode("utf-8")
        attempts = self.config.retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            req = request.Request(
                endpoint,
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(  # nosec B310 - local llama-server URL only
                    req,
                    timeout=self.config.timeout_seconds,
                ) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise LlamaCppTransportError(
                        "llama-server returned a non-object JSON response"
                    )
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                last_error = LlamaCppTransportError(
                    f"llama-server at {self.base_url} returned HTTP "
                    f"{exc.code}: {details}"
                )
            except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = LlamaCppTransportError(
                    f"Could not reach llama-server at {self.base_url}. "
                    "Start it with `llama-server ... --port 8080` and retry. "
                    f"Underlying error: {exc}"
                )
            else:
                return data
            if attempt < attempts:
                time.sleep(0.5 * attempt)
        if last_error is None:
            raise LlamaCppTransportError(
                "llama-server request failed without a captured error"
            )
        raise last_error

    def _trace_from_message_content(
        self,
        content: JsonValue,
        scenario_id: str,
        calls: tuple[ToolCall, ...],
        token_estimate: dict[str, int],
    ) -> Trace:
        trace_payload = parse_trace_metadata(content)
        return Trace(
            scenario_id=scenario_id,
            model=self.model.id,
            calls=calls,
            final_answer=str(trace_payload.get("final_answer", "")),
            selected_course_ids=_as_str_tuple(
                trace_payload.get("selected_course_ids")
            ),
            loaded_skill_ids=_as_str_tuple(
                trace_payload.get("loaded_skill_ids")
            ),
            token_estimate=token_estimate,
        )


def load_llama_cpp_provider(
    config_path: Path, model_id: str
) -> LlamaCppProvider:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LlamaCppProviderError(f"Config {config_path} must be a mapping")
    providers_raw = raw.get("providers")
    models_raw = raw.get("models")
    if not isinstance(providers_raw, dict) or not providers_raw:
        raise LlamaCppProviderError(
            f"Config {config_path} must declare providers"
        )
    if not isinstance(models_raw, list) or not models_raw:
        raise LlamaCppProviderError(
            f"Config {config_path} must declare at least one model"
        )

    selected_model_raw: JsonObject | None = None
    for entry in models_raw:
        if isinstance(entry, dict) and entry.get("id") == model_id:
            selected_model_raw = entry
            break
    if selected_model_raw is None:
        raise LlamaCppProviderError(
            f"Model {model_id!r} not found in {config_path}"
        )

    provider_name = selected_model_raw.get("provider")
    if not isinstance(provider_name, str) or not provider_name:
        raise LlamaCppProviderError(
            f"Model {model_id!r} is missing a provider reference"
        )
    provider_raw = providers_raw.get(provider_name)
    if not isinstance(provider_raw, dict):
        raise LlamaCppProviderError(
            f"Provider {provider_name!r} not found in {config_path}"
        )

    provider_config = LlamaCppProviderConfig(
        name=provider_name,
        base_url=str(provider_raw.get("base_url", "http://127.0.0.1:8080/v1")),
        api_key=str(provider_raw.get("api_key", "not-needed")),
        timeout_seconds=_coerce_positive_int(
            provider_raw.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
            kind="timeout_seconds",
        ),
        retries=_coerce_non_negative_int(
            provider_raw.get("retries", DEFAULT_RETRIES),
            kind="retries",
        ),
        validation_retries=_coerce_non_negative_int(
            provider_raw.get("validation_retries", 1),
            kind="validation_retries",
        ),
        temperature=_coerce_float(
            provider_raw.get("temperature", DEFAULT_TEMPERATURE),
            kind="temperature",
        ),
        max_tokens=_coerce_positive_int(
            provider_raw.get("max_tokens", DEFAULT_MAX_TOKENS),
            kind="max_tokens",
        ),
        seed=_coerce_optional_int(provider_raw.get("seed", DEFAULT_SEED)),
    )
    model_config = LlamaCppModelConfig(
        id=model_id,
        provider=provider_name,
        repo=_coerce_non_empty_str(
            selected_model_raw.get("repo"),
            kind="repo",
        ),
        file=_coerce_non_empty_str(
            selected_model_raw.get("file"),
            kind="file",
        ),
        quant=_coerce_optional_str(selected_model_raw.get("quant")),
        context=_coerce_positive_int(
            selected_model_raw.get("context", 8192), kind="context"
        ),
        server_args=_coerce_str_tuple(selected_model_raw.get("server_args")),
        chat_template_kwargs=_coerce_template_kwargs(
            selected_model_raw.get("chat_template_kwargs")
        ),
    )
    return LlamaCppProvider(
        model=model_config,
        config=provider_config,
        config_path=config_path,
    )


def build_openai_tools() -> list[JsonObject]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }
        for spec in TOOL_SPECS
    ]


def raise_tool_loop_exceeded() -> None:
    raise LlamaCppProviderError(
        f"llama.cpp tool loop exceeded {MAX_TOOL_ROUNDS} rounds"
    )


def extract_response_message(response: JsonObject) -> JsonObject:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LlamaCppProviderError("llama-server response has no choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise LlamaCppProviderError(
            "llama-server response choice is missing message"
        )
    return message


def message_for_history(message: JsonObject) -> JsonObject:
    history = {"role": "assistant"}
    content = message.get("content")
    history["content"] = content if isinstance(content, str) else ""
    tool_calls = message.get("tool_calls")
    if tool_calls is not None:
        history["tool_calls"] = tool_calls
    return history


def build_final_json_reminder(
    scenario: Scenario,  # noqa: ARG001 - kept for backwards-compat signature
) -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            f"No more tools are needed. {OUTPUT_CONTRACT} "
            "Apply the policy from the system prompt — do not wait for "
            "scenario-specific instructions."
        ),
    }


def build_tool_result_message(
    raw_call: JsonObject,
    call: ToolCall,
    scenario: Scenario,
    catalog: Catalog,
) -> JsonObject:
    return {
        "role": "tool",
        "tool_call_id": str(raw_call.get("id") or call.tool),
        "name": call.tool,
        "content": json.dumps(
            execute_synthetic_tool(call, scenario, catalog),
            ensure_ascii=False,
        ),
    }


def _tool_recall_search(
    call: ToolCall,
    scenario: Scenario,
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_recall_search`` synthetic tool call."""
    limit = _tool_limit(call.args.get("limit"), default=5)
    return {
        "results": list(scenario.local_recall)[:limit],
        "installed_capabilities": list(scenario.installed_capabilities),
    }


def _tool_listings_search(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,
) -> JsonObject:
    """Answer the ``logion_listings_search`` synthetic tool call."""
    query = str(call.args.get("query", ""))
    return {"results": search_catalog(query, catalog)}


def _tool_skills_updates(
    call: ToolCall,  # noqa: ARG001
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_skills_updates`` synthetic tool call."""
    return {"ok": True, "updates": []}


def _tool_notifications_unread_count(
    call: ToolCall,  # noqa: ARG001
    scenario: Scenario,
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_notifications_unread_count`` synthetic tool call."""
    count = 0 if "no-noise-when-zero" in scenario.id else 2
    return {"ok": True, "count": count}


def _tool_notifications_list(
    call: ToolCall,  # noqa: ARG001
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_notifications_list`` synthetic tool call."""
    return {
        "ok": True,
        "notifications": [
            {"id": "notif-1", "title": "New review on browser.automation"},
            {
                "id": "notif-2",
                "title": "Publication feedback on video.editor",
            },
        ],
    }


def _tool_course_reviews_list(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,
) -> JsonObject:
    """Answer the ``logion_course_reviews_list`` synthetic tool call."""
    course_id = str(call.args.get("course_id", ""))
    course = catalog.by_id(course_id)
    if course is None:
        return {"ok": False, "error": f"unknown course_id: {course_id}"}
    return {
        "ok": True,
        "course_id": course_id,
        "rating_avg": course.rating_avg,
        "rating_count": course.rating_count,
        "reviews": [],
    }


def _tool_bounties_ls(
    call: ToolCall,  # noqa: ARG001
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_bounties_ls`` synthetic tool call."""
    return {
        "ok": True,
        "results": [
            {
                "id": "bounty-ocr-1",
                "title": "OCR receipt cleanup",
                "reward_usd": 300,
                "tags": ["ocr", "documents"],
            }
        ],
    }


def _tool_bounties_get(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_bounties_get`` synthetic tool call."""
    bounty_id = str(call.args.get("bounty_id", ""))
    return {
        "ok": True,
        "bounty": {
            "id": bounty_id or "bounty-ocr-1",
            "title": "OCR receipt cleanup",
            "reward_usd": 300,
            "status": "open",
        },
    }


def _tool_bounties_submission_create(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_bounties_submission_create`` synthetic tool call."""
    return {
        "ok": True,
        "submission_id": "submission-1",
        "bounty_id": str(call.args.get("bounty_id", "")),
        "status": "draft",
    }


def _tool_bounties_fund(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_bounties_fund`` synthetic tool call."""
    return {
        "ok": True,
        "checkout_provider": "stripe",
        "bounty_id": str(call.args.get("bounty_id", "")),
    }


def _tool_reports_create(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_reports_create`` synthetic tool call."""
    return {
        "ok": True,
        "report_id": "report-1",
        "target_type": str(call.args.get("target_type", "")),
        "target_id": str(call.args.get("target_id", "")),
    }


def _tool_payments_orders_get(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_payments_orders_get`` synthetic tool call."""
    return {
        "ok": True,
        "order_id": str(call.args.get("order_id", "")),
        "status": "paid",
    }


def _tool_skills_inspect(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_skills_inspect`` synthetic tool call."""
    course_id = str(call.args.get("course_id", ""))
    return {"ok": True, "course_id": course_id, "loaded": True}


def _tool_skills_permission_expand(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_skills_permission_expand`` synthetic tool call."""
    return {
        "ok": True,
        "capability_id": str(call.args.get("capability_id", "")),
        "scope": str(call.args.get("scope", "")),
        "granted": False,
    }


def _tool_courses_create(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_courses_create`` synthetic tool call."""
    return {
        "ok": True,
        "course": {
            "id": "creator.draft",
            "title": str(call.args.get("title", "Untitled course")),
            "slug": str(call.args.get("slug", "untitled-course")),
            "review_status": "draft",
        },
    }


def _tool_courses_report_usage(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_courses_report_usage`` synthetic tool call."""
    return {
        "ok": True,
        "review_id": "review-synthetic-001",
        "course_id": str(call.args.get("course_id", "")),
        "version_id": str(call.args.get("version_id", "")),
        "rating": call.args.get("rating"),
        "persisted_fields": sorted(call.args.keys()),
    }


def _tool_payments_seller_readiness(
    call: ToolCall,  # noqa: ARG001
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_payments_seller_readiness`` synthetic tool call."""
    return {"ok": True, "ready": False, "missing": ["onboarding"]}


def _tool_payments_onboarding_link(
    call: ToolCall,  # noqa: ARG001
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_payments_onboarding_link`` synthetic tool call."""
    return {
        "ok": True,
        "url": "https://payments.example.test/onboarding/session",
    }


def _tool_credits_top_up(
    call: ToolCall,
    scenario: Scenario,  # noqa: ARG001
    catalog: Catalog,  # noqa: ARG001
) -> JsonObject:
    """Answer the ``logion_credits_top_up`` synthetic tool call."""
    amount_cents = int(call.args.get("amount_cents", 0))
    return {
        "ok": True,
        "top_up_id": "topup-synthetic-001",
        "amount_cents": amount_cents,
        "status": "pending",
        "checkout_url": "https://checkout.stripe.test/session/topup-synthetic",
    }


def execute_synthetic_tool(
    call: ToolCall, scenario: Scenario, catalog: Catalog
) -> JsonObject:
    """Answer one synthetic tool call from the fake catalog.

    Each tool is a function registered in ``_SYNTHETIC_TOOLS``, so
    adding one does not grow this dispatcher.
    """
    handler = _SYNTHETIC_TOOLS.get(call.tool)
    if handler is not None:
        return handler(call, scenario, catalog)
    if call.tool in {
        "logion_courses_capabilities_validate",
        "logion_courses_capabilities_print",
    }:
        return {
            "ok": True,
            "bundle_dir": str(call.args.get("bundle_dir", "")),
            "capabilities": ["terminal", "file"],
        }
    if call.tool in {
        "logion_courses_update",
        "logion_courses_uploads_create",
        "logion_courses_uploads_push",
        "logion_courses_uploads_complete",
        "logion_courses_publication_request",
        "logion_courses_publication_latest",
        "logion_courses_feedback",
    }:
        course_id = str(call.args.get("course_id", ""))
        return {
            "ok": True,
            "course_id": course_id,
            "version_id": str(call.args.get("version_id", "version-draft-1")),
            "status": "in_review",
            "feedback": "Address reviewer notes before publication.",
        }
    if call.tool in {
        "logion_courses_get",
        "logion_skills_install",
        "logion_skills_update",
    }:
        course_id = str(call.args.get("course_id", ""))
        course = catalog.by_id(course_id)
        if course is None:
            return {"ok": False, "error": f"unknown course_id: {course_id}"}
        return {"ok": True, "course": course_to_payload(course)}
    return {"ok": False, "error": f"unsupported tool: {call.tool}"}


#: Tool name -> handler, defined after the functions so each name
#: is already bound.
_SYNTHETIC_TOOLS: dict[
    str, Callable[[ToolCall, Scenario, Catalog], JsonObject]
] = {
    "logion_recall_search": _tool_recall_search,
    "logion_listings_search": _tool_listings_search,
    "logion_skills_updates": _tool_skills_updates,
    "logion_notifications_unread_count": _tool_notifications_unread_count,
    "logion_notifications_list": _tool_notifications_list,
    "logion_course_reviews_list": _tool_course_reviews_list,
    "logion_bounties_ls": _tool_bounties_ls,
    "logion_bounties_get": _tool_bounties_get,
    "logion_bounties_submission_create": _tool_bounties_submission_create,
    "logion_bounties_fund": _tool_bounties_fund,
    "logion_reports_create": _tool_reports_create,
    "logion_payments_orders_get": _tool_payments_orders_get,
    "logion_skills_inspect": _tool_skills_inspect,
    "logion_skills_permission_expand": _tool_skills_permission_expand,
    "logion_courses_create": _tool_courses_create,
    "logion_courses_report_usage": _tool_courses_report_usage,
    "logion_payments_seller_readiness": _tool_payments_seller_readiness,
    "logion_payments_onboarding_link": _tool_payments_onboarding_link,
    "logion_credits_top_up": _tool_credits_top_up,
}


def search_catalog(query: str, catalog: Catalog) -> list[JsonObject]:
    terms = {term for term in re.findall(r"[a-z0-9]+", query.lower()) if term}
    scored: list[tuple[int, JsonObject]] = []
    for course in catalog.courses:
        haystack = " ".join([
            course.id,
            course.name,
            course.summary,
            " ".join(course.required_tools),
            " ".join(course.capability_ids),
            " ".join(course.tags),
        ]).lower()
        score = sum(1 for term in terms if term in haystack)
        if score > 0:
            scored.append((score, course_to_payload(course)))
    if not scored:
        scored = [(0, course_to_payload(course)) for course in catalog.courses]
    scored.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [payload for _score, payload in scored[:5]]


def course_to_payload(course: JsonValue) -> JsonObject:
    return {
        "id": course.id,
        "name": course.name,
        "summary": course.summary,
        "price_usd": course.price_usd,
        "review_status": course.review_status,
        "required_tools": list(course.required_tools),
        "required_env": list(course.required_env),
        "capability_ids": list(course.capability_ids),
        "tags": list(course.tags),
        "rating_avg": course.rating_avg,
        "rating_count": course.rating_count,
        "latest_version_review_status": course.latest_version_review_status,
    }


def merge_token_estimates(
    left: dict[str, int], right: dict[str, int]
) -> dict[str, int]:
    return {
        "input": left.get("input", 0) + right.get("input", 0),
        "output": left.get("output", 0) + right.get("output", 0),
    }


def _tool_limit(value: JsonValue, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def parse_trace_metadata(content: JsonValue) -> JsonObject:
    if not isinstance(content, str) or not content.strip():
        raise LlamaCppProviderError(
            "llama-server response message content must be non-empty JSON"
        )
    data = parse_trace_json(content)
    if "calls" in data:
        raise LlamaCppProviderError(
            "message content must not include calls; use OpenAI tool_calls"
        )
    return data


def parse_tool_calls(tool_calls: JsonValue) -> tuple[ToolCall, ...]:
    if tool_calls is None:
        return ()
    if not isinstance(tool_calls, list):
        raise LlamaCppProviderError("message tool_calls must be a list")
    calls: list[ToolCall] = []
    for raw_call in tool_calls:
        if not isinstance(raw_call, dict):
            raise LlamaCppProviderError(
                f"tool_call must be an object: {raw_call!r}"
            )
        function = raw_call.get("function")
        if not isinstance(function, dict):
            raise LlamaCppProviderError("tool_call is missing function")
        tool_name = function.get("name")
        if not isinstance(tool_name, str):
            raise LlamaCppProviderError(
                "tool_call function.name must be a string"
            )
        if tool_name not in KNOWN_TOOL_NAMES:
            raise LlamaCppProviderError(
                f"tool_call references unknown function: {tool_name!r}"
            )
        arguments = function.get("arguments", "{}")
        args = parse_tool_arguments(arguments, tool_name)
        calls.append(ToolCall(tool=tool_name, args=args))
    return tuple(calls)


def parse_tool_arguments(arguments: JsonValue, tool_name: str) -> JsonObject:
    if arguments in (None, ""):
        return {}
    if isinstance(arguments, dict):
        return dict(arguments)
    if not isinstance(arguments, str):
        raise LlamaCppProviderError(
            f"arguments for {tool_name!r} must be a JSON object string"
        )
    try:
        data = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise LlamaCppProviderError(
            f"arguments for {tool_name!r} are not valid JSON"
        ) from exc
    if not isinstance(data, dict):
        raise LlamaCppProviderError(
            f"arguments for {tool_name!r} must decode to an object"
        )
    return data


def parse_trace_json(content: str) -> JsonObject:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlamaCppProviderError(
            f"Model response is not valid JSON: {content!r}"
        ) from exc
    if not isinstance(data, dict):
        raise LlamaCppProviderError("Model response JSON must be an object")
    return data


def truncate_validation_error(message: str) -> str:
    if len(message) <= MAX_VALIDATION_ERROR_CHARS:
        return message
    omitted = len(message) - MAX_VALIDATION_ERROR_CHARS
    return (
        f"{message[:MAX_VALIDATION_ERROR_CHARS]}... "
        f"[truncated {omitted} chars]"
    )


def extract_message_content(response: JsonObject) -> str | None:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    tool_calls = message.get("tool_calls")
    if tool_calls is not None:
        return json.dumps(
            {
                "content": content if isinstance(content, str) else "",
                "tool_calls": tool_calls,
            },
            ensure_ascii=False,
        )
    if not isinstance(content, str):
        return None
    return content.strip() or None


def usage_to_token_estimate(usage: JsonValue) -> dict[str, int]:
    if not isinstance(usage, dict):
        return {"input": 0, "output": 0}
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    return {
        "input": _coerce_non_negative_int(prompt_tokens, kind="prompt_tokens"),
        "output": _coerce_non_negative_int(
            completion_tokens, kind="completion_tokens"
        ),
    }


def infer_quant_from_filename(filename: str) -> str | None:
    match = re.search(r"(Q\d(?:_[A-Z]){1,3})", filename)
    if match is None:
        return None
    return match.group(1)


def _as_str_tuple(value: JsonValue) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LlamaCppProviderError(f"Expected a list, got {value!r}")
    return tuple(str(item) for item in value)


def _coerce_non_empty_str(value: JsonValue, *, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LlamaCppProviderError(f"{kind} must be a non-empty string")
    return value.strip()


def _coerce_optional_str(value: JsonValue) -> str | None:
    if value is None:
        return None
    return _coerce_non_empty_str(value, kind="quant")


def _coerce_str_tuple(value: JsonValue) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LlamaCppProviderError("server_args must be a list")
    return tuple(str(item) for item in value)


def _coerce_template_kwargs(
    value: JsonValue,
) -> tuple[tuple[str, JsonValue], ...]:
    if value is None:
        return ()
    if not isinstance(value, dict):
        raise LlamaCppProviderError("chat_template_kwargs must be a mapping")
    return tuple((str(key), val) for key, val in value.items())


def _coerce_positive_int(value: JsonValue, *, kind: str) -> int:
    parsed = _coerce_non_negative_int(value, kind=kind)
    if parsed <= 0:
        raise LlamaCppProviderError(f"{kind} must be > 0")
    return parsed


def _coerce_non_negative_int(value: JsonValue, *, kind: str) -> int:
    if isinstance(value, bool):
        raise LlamaCppProviderError(f"{kind} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise LlamaCppProviderError(f"{kind} must be an integer") from exc
    if parsed < 0:
        raise LlamaCppProviderError(f"{kind} must be non-negative")
    return parsed


def _coerce_optional_int(value: JsonValue) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise LlamaCppProviderError("seed must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise LlamaCppProviderError("seed must be an integer") from exc


def _coerce_float(value: JsonValue, *, kind: str) -> float:
    if isinstance(value, bool):
        raise LlamaCppProviderError(f"{kind} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise LlamaCppProviderError(f"{kind} must be numeric") from exc
