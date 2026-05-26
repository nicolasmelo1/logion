"""llama.cpp provider for live local evals.

The provider talks to an OpenAI-compatible ``llama-server`` and asks the local
model to emit a JSON trace matching the eval harness contract. This keeps the
scenario files unchanged: the fake provider still replays ``fake_trace`` in CI,
while opt-in local runs can swap in a real model.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

import yaml

from evals.harness.schema import (
    KNOWN_TOOLS,
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


class LlamaCppProviderError(RuntimeError):
    """Raised when the local llama.cpp provider cannot produce a trace."""


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
class LlamaCppModelConfig:
    id: str
    provider: str
    repo: str
    file: str
    quant: str | None
    context: int
    server_args: tuple[str, ...]


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

    def report_metadata(self) -> dict[str, Any]:
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
            payload = self._build_payload(
                scenario,
                catalog,
                previous_response=previous_response,
                validation_feedback=validation_feedback,
            )
            response = self._post_json(payload)
            try:
                return self._trace_from_response(response, scenario.id)
            except LlamaCppProviderError as exc:
                last_error = exc
                previous_response = extract_message_content(response)
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
    ) -> dict[str, Any]:
        payload = {
            "model": self.model.id,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": self._build_messages(
                scenario,
                catalog,
                previous_response=previous_response,
                validation_feedback=validation_feedback,
            ),
        }
        if self.config.seed is not None:
            payload["seed"] = self.config.seed
        return payload

    def _build_messages(
        self,
        scenario: Scenario,
        catalog: Catalog,
        *,
        previous_response: str | None = None,
        validation_feedback: str | None = None,
    ) -> list[dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are evaluating the Logion Marketplace Companion. "
                    "Return only strict JSON. Do not use markdown fences. "
                    "Choose zero or more tool calls from this allowlist: "
                    f"{', '.join(sorted(KNOWN_TOOLS))}. "
                    "Output keys: calls, final_answer, "
                    "selected_course_ids, loaded_skill_ids."
                ),
            },
            {
                "role": "user",
                "content": self._build_user_prompt(scenario, catalog),
            },
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

    def _build_user_prompt(self, scenario: Scenario, catalog: Catalog) -> str:
        catalog_rows = []
        for course in catalog.courses:
            row = {
                "id": course.id,
                "summary": course.summary,
                "price_usd": course.price_usd,
                "review_status": course.review_status,
                "required_tools": list(course.required_tools),
                "required_env": list(course.required_env),
                "capability_ids": list(course.capability_ids),
                "tags": list(course.tags),
            }
            catalog_rows.append(row)
        payload = {
            "task": "Plan the companion's tool trace for this scenario.",
            "prompt": scenario.prompt,
            "installed_capabilities": list(scenario.installed_capabilities),
            "local_recall": list(scenario.local_recall),
            "catalog": catalog_rows,
            "instructions": {
                "tool_order": (
                    "Use recall.search before marketplace.search unless "
                    "explicitly unnecessary."
                ),
                "safety": (
                    "Ask for confirmation before install, paid checkout, "
                    "permission expansion, or risky update application."
                ),
                "json_schema": {
                    "calls": [
                        {"tool": "recall.search", "args": {"query": "..."}}
                    ],
                    "final_answer": "short natural-language answer",
                    "selected_course_ids": ["course.id"],
                    "loaded_skill_ids": ["installed.skill.id"],
                },
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _validation_feedback(self, exc: LlamaCppProviderError) -> str:
        return (
            "Your previous answer did not satisfy the trace contract. "
            f"Validation error: {exc}. Return strict JSON only with keys "
            "calls, final_answer, selected_course_ids, loaded_skill_ids. "
            "calls[].tool must be one of: "
            f"{', '.join(sorted(KNOWN_TOOLS))}. "
            "selected_course_ids must contain only catalog course ids. "
            "Do not install, update, or expand permissions without "
            "explicit confirmation language in final_answer when the "
            "scenario requires it. Retry now with corrected JSON only."
        )

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
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
                    raise LlamaCppProviderError(
                        "llama-server returned a non-object JSON response"
                    )
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                last_error = LlamaCppProviderError(
                    f"llama-server at {self.base_url} returned HTTP "
                    f"{exc.code}: {details}"
                )
            except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = LlamaCppProviderError(
                    f"Could not reach llama-server at {self.base_url}. "
                    "Start it with `llama-server ... --port 8080` and retry. "
                    f"Underlying error: {exc}"
                )
            else:
                return data
            if attempt < attempts:
                time.sleep(0.5 * attempt)
        if last_error is None:
            raise LlamaCppProviderError(
                "llama-server request failed without a captured error"
            )
        raise last_error

    def _trace_from_response(
        self, response: dict[str, Any], scenario_id: str
    ) -> Trace:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlamaCppProviderError("llama-server response has no choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LlamaCppProviderError(
                "llama-server response choice is missing message"
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LlamaCppProviderError(
                "llama-server response message is empty"
            )
        trace_payload = parse_trace_json(content)
        calls_raw = trace_payload.get("calls", [])
        if not isinstance(calls_raw, list):
            raise LlamaCppProviderError("trace field 'calls' must be a list")
        calls: list[ToolCall] = []
        for raw_call in calls_raw:
            if not isinstance(raw_call, dict):
                raise LlamaCppProviderError(
                    f"trace call must be an object: {raw_call!r}"
                )
            tool = raw_call.get("tool")
            args = raw_call.get("args", {})
            if tool not in KNOWN_TOOLS:
                raise LlamaCppProviderError(
                    f"trace references unknown tool: {tool!r}"
                )
            if not isinstance(args, dict):
                raise LlamaCppProviderError(
                    f"trace args for {tool!r} must be an object"
                )
            calls.append(ToolCall(tool=tool, args=dict(args)))
        usage = response.get("usage")
        token_estimate = usage_to_token_estimate(usage)
        return Trace(
            scenario_id=scenario_id,
            model=self.model.id,
            calls=tuple(calls),
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

    selected_model_raw: dict[str, Any] | None = None
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
    )
    return LlamaCppProvider(
        model=model_config,
        config=provider_config,
        config_path=config_path,
    )


def parse_trace_json(content: str) -> dict[str, Any]:
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


def extract_message_content(response: dict[str, Any]) -> str | None:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return content.strip() or None


def usage_to_token_estimate(usage: Any) -> dict[str, int]:
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


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LlamaCppProviderError(f"Expected a list, got {value!r}")
    return tuple(str(item) for item in value)


def _coerce_non_empty_str(value: Any, *, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LlamaCppProviderError(f"{kind} must be a non-empty string")
    return value.strip()


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return _coerce_non_empty_str(value, kind="quant")


def _coerce_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LlamaCppProviderError("server_args must be a list")
    return tuple(str(item) for item in value)


def _coerce_positive_int(value: Any, *, kind: str) -> int:
    parsed = _coerce_non_negative_int(value, kind=kind)
    if parsed <= 0:
        raise LlamaCppProviderError(f"{kind} must be > 0")
    return parsed


def _coerce_non_negative_int(value: Any, *, kind: str) -> int:
    if isinstance(value, bool):
        raise LlamaCppProviderError(f"{kind} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise LlamaCppProviderError(f"{kind} must be an integer") from exc
    if parsed < 0:
        raise LlamaCppProviderError(f"{kind} must be non-negative")
    return parsed


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise LlamaCppProviderError("seed must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise LlamaCppProviderError("seed must be an integer") from exc


def _coerce_float(value: Any, *, kind: str) -> float:
    if isinstance(value, bool):
        raise LlamaCppProviderError(f"{kind} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise LlamaCppProviderError(f"{kind} must be numeric") from exc
