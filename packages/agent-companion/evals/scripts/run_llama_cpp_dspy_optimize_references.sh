#!/usr/bin/env bash
# Phase 6.11: boot a local llama.cpp server from the eval provider
# config, then run DSPy offline optimisation for the reference-routing
# signature against it.  Mirror of
# ``run_llama_cpp_dspy_optimize.sh`` adapted for the second
# optimisation target (no catalog, single scenarios YAML, no split
# file — splitting is deterministic in-process on (seed, ids)).
set -euo pipefail

# See phase-6.10 follow-up note.
ulimit -n 4096 2>/dev/null || true

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

CONFIG_PATH_INPUT="${1:-${LOGION_LLAMACPP_CONFIG:-evals/providers/llama_cpp_local.example.yaml}}"
MODEL_ID="${2:-${LOGION_LLAMACPP_MODEL_ID:-qwen3-4b-q4km}}"
OPTIMIZER="${3:-${LOGION_DSPY_OPTIMIZER:-bootstrap_few_shot}}"
SCENARIOS_INPUT="${LOGION_REF_ROUTING_SCENARIOS:-evals/scenarios_reference_routing/scenarios.yaml}"
OUTPUT_INPUT="${LOGION_DSPY_REF_OUTPUT:-evals/optimizers/dspy/generated_candidates/ref-candidate-${MODEL_ID}-${OPTIMIZER}.json}"
SEED="${LOGION_DSPY_SEED:-42}"
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-llama-server}"

cd "$ROOT_DIR"

for tool in python3 uv curl "$LLAMA_SERVER_BIN"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "$tool not found in PATH" >&2
    exit 1
  fi
done

resolve_path() {
  local value="$1"
  python3 - <<'PY' "$ROOT_DIR" "$value"
from pathlib import Path
import sys
root = Path(sys.argv[1])
value = Path(sys.argv[2]).expanduser()
if not value.is_absolute():
    value = root / value
print(value.resolve())
PY
}

CONFIG_PATH="$(resolve_path "$CONFIG_PATH_INPUT")"
SCENARIOS_PATH="$(resolve_path "$SCENARIOS_INPUT")"
OUTPUT_PATH="$(resolve_path "$OUTPUT_INPUT")"

if [[ ! -f "$SCENARIOS_PATH" ]]; then
  echo "Scenarios file not found: $SCENARIOS_PATH" >&2
  exit 1
fi

LLAMA_SERVER_ARGS=()
while IFS= read -r arg; do
  LLAMA_SERVER_ARGS+=("$arg")
done < <(
  uv run python - <<'PY' "$CONFIG_PATH" "$MODEL_ID"
from pathlib import Path
import sys
from evals.harness.providers.llama_cpp import load_llama_cpp_provider
provider = load_llama_cpp_provider(Path(sys.argv[1]), sys.argv[2])
for arg in provider.model.server_args:
    print(arg)
PY
)

if [[ ${#LLAMA_SERVER_ARGS[@]} -eq 0 ]]; then
  echo "No server_args found for model $MODEL_ID in $CONFIG_PATH" >&2
  exit 1
fi

BASE_URL="$(
  uv run python - <<'PY' "$CONFIG_PATH" "$MODEL_ID"
from pathlib import Path
import sys
from evals.harness.providers.llama_cpp import load_llama_cpp_provider
provider = load_llama_cpp_provider(Path(sys.argv[1]), sys.argv[2])
print(provider.base_url)
PY
)"

HEALTH_URL="$(
  uv run python - <<'PY' "$CONFIG_PATH" "$MODEL_ID"
from pathlib import Path
import sys
from urllib.parse import urlsplit, urlunsplit
from evals.harness.providers.llama_cpp import load_llama_cpp_provider
provider = load_llama_cpp_provider(Path(sys.argv[1]), sys.argv[2])
parts = urlsplit(provider.base_url)
print(urlunsplit((parts.scheme, parts.netloc, "/health", "", "")))
PY
)"

MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-.models}"
MODEL_FILE_REL="$(
  uv run python - <<'PY' "$CONFIG_PATH" "$MODEL_ID" "$MODEL_CACHE_DIR"
from pathlib import Path
import sys
from evals.harness.providers.llama_cpp import load_llama_cpp_provider
cfg, model_id, cache = sys.argv[1:4]
provider = load_llama_cpp_provider(Path(cfg), model_id)
repo_dir = Path(provider.model.repo).name
print(str(Path(cache) / repo_dir / provider.model.file))
PY
)"
MODEL_FILE_PATH="$(resolve_path "$MODEL_FILE_REL")"

if [[ ! -f "$MODEL_FILE_PATH" ]]; then
  echo "Model file not found: $MODEL_FILE_PATH" >&2
  echo "Run 'make download-models' first." >&2
  exit 1
fi

# Same ctx-size override as the sibling script; reference-routing
# inputs are small but optimised demos can bloat under GEPA.
DSPY_CTX_SIZE="${LOGION_DSPY_CTX_SIZE:-16384}"
NEW_ARGS=()
i=0
while [[ $i -lt ${#LLAMA_SERVER_ARGS[@]} ]]; do
  arg="${LLAMA_SERVER_ARGS[$i]}"
  if [[ "$arg" == "--ctx-size" || "$arg" == "-c" ]]; then
    i=$((i + 2))
    continue
  fi
  NEW_ARGS+=("$arg")
  i=$((i + 1))
done
LLAMA_SERVER_ARGS=("${NEW_ARGS[@]}" "--ctx-size" "$DSPY_CTX_SIZE")

has_model=0
has_alias=0
for arg in "${LLAMA_SERVER_ARGS[@]}"; do
  case "$arg" in
    -m|--model) has_model=1 ;;
    --alias) has_alias=1 ;;
  esac
done
if [[ $has_model -eq 0 ]]; then
  LLAMA_SERVER_ARGS+=("-m" "$MODEL_FILE_PATH")
fi
if [[ $has_alias -eq 0 ]]; then
  LLAMA_SERVER_ARGS+=("--alias" "$MODEL_ID")
fi

if [[ -n "${LLAMA_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  EXTRA=($LLAMA_EXTRA_ARGS)
  LLAMA_SERVER_ARGS+=("${EXTRA[@]}")
fi
if [[ $# -gt 3 ]]; then
  shift 3
  LLAMA_SERVER_ARGS+=("$@")
fi

LLAMA_SERVER_PID=""
cleanup() {
  if [[ -n "$LLAMA_SERVER_PID" ]] && kill -0 "$LLAMA_SERVER_PID" >/dev/null 2>&1; then
    kill "$LLAMA_SERVER_PID" >/dev/null 2>&1 || true
    wait "$LLAMA_SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

"$LLAMA_SERVER_BIN" "${LLAMA_SERVER_ARGS[@]}" &
LLAMA_SERVER_PID=$!

echo "Started $LLAMA_SERVER_BIN pid=$LLAMA_SERVER_PID for model=$MODEL_ID"
echo "DSPy will target $BASE_URL via openai/$MODEL_ID (signature=reference_routing)"

for _attempt in $(seq 1 60); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
  echo "llama-server did not become healthy at $HEALTH_URL" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"

DSPY_LM="openai/$MODEL_ID" \
DSPY_API_BASE="$BASE_URL" \
DSPY_API_KEY="${DSPY_API_KEY:-sk-local}" \
DSPY_REFLECTION_LM="${DSPY_REFLECTION_LM:-openai/$MODEL_ID}" \
DSPY_REFLECTION_API_BASE="${DSPY_REFLECTION_API_BASE:-$BASE_URL}" \
DSPY_REFLECTION_API_KEY="${DSPY_REFLECTION_API_KEY:-${DSPY_API_KEY:-sk-local}}" \
uv run --group dspy python evals/optimizers/dspy/optimize_references.py \
  --scenarios "$SCENARIOS_PATH" \
  --optimizer "$OPTIMIZER" \
  --seed "$SEED" \
  --output "$OUTPUT_PATH"

echo "candidate report: $OUTPUT_PATH"
