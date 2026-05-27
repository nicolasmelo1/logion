#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

if ! command -v hf >/dev/null 2>&1; then
  echo "hf CLI not found. Install huggingface_hub CLI first." >&2
  exit 1
fi

MODEL_CACHE_DIR="${LOGION_MODEL_CACHE_DIR:-${ROOT_DIR}/.models}"
mkdir -p "$MODEL_CACHE_DIR"

hf_download() {
  local repo="$1"
  local file="$2"
  local target_dir="$3"
  local -a cmd=(hf download "$repo" "$file" --local-dir "$target_dir")
  if [[ -n "${HF_TOKEN:-}" ]]; then
    cmd+=(--token "$HF_TOKEN")
  fi
  echo "==> Downloading $repo :: $file"
  "${cmd[@]}"
}

if [[ "${LOGION_DOWNLOAD_QWEN3_4B:-1}" == "1" ]]; then
  hf_download \
    "${QWEN3_4B_REPO:-Qwen/Qwen3-4B-GGUF}" \
    "${QWEN3_4B_FILE:-Qwen3-4B-Q4_K_M.gguf}" \
    "$MODEL_CACHE_DIR/Qwen3-4B-GGUF"
fi

if [[ "${LOGION_DOWNLOAD_QWEN3_8B:-1}" == "1" ]]; then
  hf_download \
    "${QWEN3_8B_REPO:-Qwen/Qwen3-8B-GGUF}" \
    "${QWEN3_8B_FILE:-Qwen3-8B-Q4_K_M.gguf}" \
    "$MODEL_CACHE_DIR/Qwen3-8B-GGUF"
fi

if [[ "${LOGION_DOWNLOAD_GEMMA3_4B:-1}" == "1" ]]; then
  hf_download \
    "${GEMMA3_4B_REPO:-unsloth/gemma-3-4b-it-GGUF}" \
    "${GEMMA3_4B_FILE:-gemma-3-4b-it-Q4_K_M.gguf}" \
    "$MODEL_CACHE_DIR/gemma-3-4b-it-GGUF"
fi

echo "Downloads complete under $MODEL_CACHE_DIR"
