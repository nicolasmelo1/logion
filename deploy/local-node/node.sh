#!/usr/bin/env bash
# Operator surface for the bounded local multi-agent node.
set -euo pipefail

NODE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${NODE_DIR}/../.." && pwd)"
NODE_ENV_FILE="${NODE_DIR}/.env"
WORKSPACE_ROOT="${LOGION_WORKSPACE_ROOT:-}"

load_node_env() {
  if [[ -f "${NODE_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${NODE_ENV_FILE}"
    set +a
  fi
  : "${LOGION_NODE_IMAGE:=logion-local-node-role:latest}"
  : "${LOGION_BASE_URL:=http://localhost:8000}"
  : "${ROLE_WALL_TIME_SECONDS:=3600}"
  : "${CODEX_AUTH_SOURCE:=${HOME}/.codex/auth.json}"
  export LOGION_NODE_IMAGE LOGION_BASE_URL ROLE_WALL_TIME_SECONDS
}

select_runtime() {
  if [[ -n "${CONTAINER_RUNTIME:-}" ]]; then
    RUNTIME="${CONTAINER_RUNTIME}"
  elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    RUNTIME=docker
  elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
    RUNTIME=podman
  else
    echo "ERROR: no working Docker Desktop or Podman runtime." >&2
    return 1
  fi
  "${RUNTIME}" compose version >/dev/null 2>&1 || {
    echo "ERROR: ${RUNTIME} compose is unavailable." >&2
    return 1
  }
  if [[ -z "${LOGION_CONTAINER_BASE_URL:-}" ]]; then
    if [[ "${RUNTIME}" == "podman" ]]; then
      LOGION_CONTAINER_BASE_URL=http://host.containers.internal:8000
    else
      LOGION_CONTAINER_BASE_URL=http://host.docker.internal:8000
    fi
  fi
  export CONTAINER_RUNTIME="${RUNTIME}" LOGION_CONTAINER_BASE_URL
}

node_compose() {
  load_node_env
  select_runtime
  "${RUNTIME}" compose --project-directory "${NODE_DIR}" \
    -f "${NODE_DIR}/compose.yaml" "$@"
}

validate_disk() {
  local available_kb
  available_kb="$(df -Pk "${NODE_DIR}" | tail -1 | tr -s ' ' | cut -d' ' -f4)"
  if [[ ! "${available_kb}" =~ ^[0-9]+$ ]] || (( available_kb < 5242880 )); then
    echo "ERROR: local node needs at least 5 GiB free disk." >&2
    return 1
  fi
}

health_code() {
  curl -sS -o /dev/null -w '%{http_code}' "${LOGION_BASE_URL%/}/health" 2>/dev/null || true
}

ensure_devrig() {
  if [[ "$(health_code)" == "200" ]]; then
    return
  fi
  if [[ -z "${WORKSPACE_ROOT}" || ! -f "${WORKSPACE_ROOT}/Makefile" ]]; then
    echo "ERROR: API health failed and canonical workspace was not found." >&2
    return 1
  fi
  echo "Local API is not healthy; provisioning the canonical devrig..."
  make -C "${WORKSPACE_ROOT}" dev-up
  if [[ "$(health_code)" != "200" ]]; then
    local log="${WORKSPACE_ROOT}/.devrig/node-api.log"
    mkdir -p "${WORKSPACE_ROOT}/.devrig"
    make -C "${WORKSPACE_ROOT}" dev-api >"${log}" 2>&1 &
    echo $! >"${WORKSPACE_ROOT}/.devrig/node-api.pid"
    for _ in $(seq 1 60); do
      [[ "$(health_code)" == "200" ]] && return
      sleep 1
    done
    echo "ERROR: local API did not become healthy; see ${log}." >&2
    return 1
  fi
}

validate_provider_auth() {
  [[ -s "${CODEX_AUTH_SOURCE}" ]] || {
    echo "ERROR: Codex auth is missing at ${CODEX_AUTH_SOURCE}." >&2
    echo "Run codex login or set CODEX_AUTH_SOURCE to an auth.json file." >&2
    return 1
  }
  python3 - "${CODEX_AUTH_SOURCE}" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
data = json.loads(p.read_text())
if data.get("auth_mode") not in {"chatgpt", "apikey", "api_key"}:
    raise SystemExit("unsupported Codex auth mode")
if not data.get("tokens") and not data.get("OPENAI_API_KEY"):
    raise SystemExit("Codex auth file has no usable credential")
PY
}

provision_role_identity() {
  local role="$1"
  local key_file="${NODE_DIR}/roles/${role}.api_key"
  local identity_file="${NODE_DIR}/roles/${role}.identity.json"
  if [[ -s "${key_file}" && -s "${identity_file}" ]]; then
    return
  fi
  python3 - "${role}" "${LOGION_BASE_URL%/}" "${key_file}" "${identity_file}" <<'PY'
import json, os, pathlib, secrets, sys, urllib.request
role, base, key_path, identity_path = sys.argv[1:]
user_passphrase = "node-" + secrets.token_urlsafe(18)
payload = json.dumps({
    "email": f"{role}-node-{secrets.token_hex(5)}@nodetest.dev",
    "user_password": user_passphrase,
    "agent_name": f"{role}-node",
    "agent_description": f"Disposable {role} role of the local node",
}).encode()
req = urllib.request.Request(base + "/v1/identity/users", data=payload,
    headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as response:
    body = json.load(response)
key = body["api_key"]
kp, ip = pathlib.Path(key_path), pathlib.Path(identity_path)
kp.write_text(key)
ip.write_text(json.dumps({
    "user_password": user_passphrase,
    "user_id": body["user"]["id"],
    "agent_id": body["agent"]["id"],
}, indent=2) + "\n")
os.chmod(kp, 0o600)
os.chmod(ip, 0o600)
PY
}

stage_role_secrets() {
  local roles="$1"
  mkdir -p "${NODE_DIR}/roles"
  for role in ${roles//,/ }; do
    case "${role}" in consumer|auditor) ;; *) echo "ERROR: unknown role ${role}" >&2; return 1;; esac
    provision_role_identity "${role}"
    install -m 600 "${CODEX_AUTH_SOURCE}" "${NODE_DIR}/roles/${role}.codex_auth.json"
  done
}

node_build_image() {
  load_node_env
  select_runtime
  rm -rf "${NODE_DIR}/dist-wheels"
  mkdir -p "${NODE_DIR}/dist-wheels"
  (cd "${REPO_ROOT}" && uv build --all-packages --wheel --out-dir "${NODE_DIR}/dist-wheels")
  "${RUNTIME}" build --platform linux/arm64 \
    -f "${NODE_DIR}/Dockerfile.role" \
    --build-arg "LOGION_BASE_URL=${LOGION_BASE_URL}" \
    -t "${LOGION_NODE_IMAGE}" "${NODE_DIR}"
}

node_up() {
  local roles="${1:-consumer,auditor}"
  load_node_env
  select_runtime
  validate_disk
  ensure_devrig
  validate_provider_auth
  stage_role_secrets "${roles}"
  node_build_image
  local -a role_array
  IFS=',' read -r -a role_array <<<"${roles}"
  node_compose up -d "${role_array[@]}"
  node_status
}

container_id() {
  node_compose ps -q "$1"
}

node_status() {
  load_node_env
  select_runtime
  echo "== local node services =="
  node_compose ps
  echo
  echo "== role runtime evidence =="
  for role in consumer auditor; do
    local cid uid cmd image_id
    cid="$(container_id "${role}" 2>/dev/null || true)"
    if [[ -z "${cid}" ]]; then echo "${role}: stopped"; continue; fi
    uid="$(node_compose exec -T "${role}" id -u 2>/dev/null || echo unreachable)"
    cmd="$("${RUNTIME}" inspect --format '{{json .Config.Cmd}}' "${cid}")"
    image_id="$("${RUNTIME}" inspect --format '{{.Image}}' "${cid}")"
    echo "${role}: uid=${uid} image=${image_id} wall_time=${ROLE_WALL_TIME_SECONDS}s command=${cmd}"
    node_compose exec -T "${role}" sh -c \
      'printf "logion="; logion --version; printf "codex="; codex --version'
    if node_compose exec -T "${role}" test -s "/run/secrets/${role}_api_key"; then
      echo "${role}: Logion credential present; provider credential present"
    fi
  done
  echo "limits: cpus=1.0 memory=1536M pids=256 wall-time=${ROLE_WALL_TIME_SECONDS}s"
  echo "mounts: per-role named home/workspace/spool; no host bind, socket, or keychain"
  echo "cleanup: make node-dev-down | make node-dev-reset ROLE=consumer YES=1"
}

node_agent() {
  local role="$1"; shift
  if [[ "$#" -eq 0 ]]; then
    node_compose exec "${role}" codex-role
  else
    node_compose exec -T "${role}" "$@"
  fi
}

node_down() {
  node_compose down
  rm -rf "${NODE_DIR}/dist-wheels"
}

rotate_role_key() {
  local role="$1"
  local key_file="${NODE_DIR}/roles/${role}.api_key"
  local identity_file="${NODE_DIR}/roles/${role}.identity.json"
  [[ -s "${key_file}" && -s "${identity_file}" ]] || {
    echo "ERROR: role ${role} has no provisioned identity to revoke." >&2
    return 1
  }
  python3 - "${LOGION_BASE_URL%/}" "${key_file}" "${identity_file}" <<'PY'
import json, os, pathlib, sys, time, urllib.request
base, key_path, identity_path = sys.argv[1:]
kp, ip = pathlib.Path(key_path), pathlib.Path(identity_path)
identity = json.loads(ip.read_text())
payload = json.dumps({"user_password": identity["user_password"]}).encode()
url = (f"{base}/v1/identity/users/{identity['user_id']}"
       f"/agents/{identity['agent_id']}/api-keys")
req = urllib.request.Request(url, data=payload,
    headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as response:
    new_key = json.load(response)["api_key"]
retired = kp.with_name(kp.name + f".revoked.{int(time.time())}")
kp.replace(retired)
kp.write_text(new_key)
os.chmod(retired, 0o600)
os.chmod(kp, 0o600)
PY
}

node_reset() {
  local role="$1" yes="${2:-}"
  case "${role}" in consumer|auditor) ;; *) echo "ERROR: exact role required." >&2; return 1;; esac
  [[ "${yes}" == "1" ]] || { echo "ERROR: refusing reset without YES=1." >&2; return 1; }
  load_node_env
  ensure_devrig
  node_compose stop "${role}"
  node_compose rm -f "${role}"
  rotate_role_key "${role}"
  for suffix in home workspace spool; do
    "${RUNTIME}" volume rm -f "logion-local-node_${role}_${suffix}" >/dev/null
  done
  echo "role '${role}': disposable state removed and API key rotated server-side."
  echo "The other role was not stopped, reset, or re-keyed."
}

node_runner_once() {
  load_node_env
  select_runtime
  [[ -s "${NODE_DIR}/roles/runner.api_key" ]] || {
    echo "ERROR: enroll a runner and save its key to ${NODE_DIR}/roles/runner.api_key." >&2
    return 1
  }
  node_compose --profile runner run --rm runner
}

node_doctor() {
  load_node_env
  select_runtime
  node_compose config >/dev/null
  [[ -s "${NODE_DIR}/roles/runner.api_key" ]] || {
    echo "runner key: missing" >&2
    return 1
  }
  echo "local node compose configuration and runner credential are ready"
}

case "${1:-}" in
  up) shift; node_up "${1:-${NODE_ROLES:-consumer,auditor}}" ;;
  status) node_status ;;
  agent) shift; role="$1"; shift; node_agent "${role}" "$@" ;;
  down) node_down ;;
  reset) shift; node_reset "$1" "${2:-}" ;;
  runner-once) node_runner_once ;;
  doctor) node_doctor ;;
  *) echo "usage: node.sh {up|status|agent|down|reset|runner-once|doctor} ..." >&2; exit 2 ;;
esac
