#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

CONFIG_PATH_INPUT="${1:-${LOGION_LLAMACPP_CONFIG:-evals/providers/llama_cpp_local.example.yaml}}"
MODEL_ID="${2:-${LOGION_LLAMACPP_MODEL_ID:-qwen3-8b-q5km}}"
SCENARIOS_INPUT="${LOGION_EVAL_SCENARIOS:-evals/scenarios}"
CATALOG_INPUT="${LOGION_EVAL_CATALOG:-evals/catalogs/fake-marketplace.yaml}"
REPORT_INPUT="${LOGION_EVAL_REPORT:-evals/reports/last-run.json}"
LLAMA_SERVER_BIN="${LLAMA_SERVER_BIN:-llama-server}"

cd "$ROOT_DIR"

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
CATALOG_PATH="$(resolve_path "$CATALOG_INPUT")"
REPORT_PATH="$(resolve_path "$REPORT_INPUT")"

if ! command -v "$LLAMA_SERVER_BIN" >/dev/null 2>&1; then
  echo "$LLAMA_SERVER_BIN not found in PATH" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found in PATH" >&2
  exit 1
fi

mapfile -t LLAMA_SERVER_ARGS < <(
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

for _attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
  echo "llama-server did not become healthy on 127.0.0.1:8080" >&2
  exit 1
fi

uv run python evals/run_eval.py \
  --provider llama_cpp_local \
  --config "$CONFIG_PATH" \
  --model "$MODEL_ID" \
  --scenarios "$SCENARIOS_PATH" \
  --catalog "$CATALOG_PATH" \
  --report "$REPORT_PATH"
