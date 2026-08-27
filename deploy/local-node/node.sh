#!/usr/bin/env bash
# Operator entrypoints for the phase 15.14.1 local multi-agent node.
#
# Sourced by the logion/Makefile node-* targets. Every command here is
# operator-side: they manage the Compose stack and never run inside a
# role. A role never receives this script's environment beyond the
# variables Compose itself injects from the service definition.

set -euo pipefail

NODE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NODE_ENV_FILE="${NODE_DIR}/.env"

load_node_env() {
  if [[ -f "${NODE_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${NODE_ENV_FILE}"
    set +a
  fi
  : "${LOGION_NODE_IMAGE:=logion-local-node-role:latest}"
  : "${LOGION_BASE_URL:=http://localhost:8000}"
  export LOGION_NODE_IMAGE LOGION_BASE_URL
}

node_compose() {
  load_node_env
  docker compose --project-directory "${NODE_DIR}" -f "${NODE_DIR}/compose.yaml" "$@"
}

node_build_image() {
  load_node_env
  # The role image copies pre-built wheels from dist-wheels/. Stage
  # them here so a fresh checkout can build the image without a
  # manual pre-step; they are build output, cleaned by node_down.
  if ! ls "${NODE_DIR}"/dist-wheels/*.whl >/dev/null 2>&1; then
    mkdir -p "${NODE_DIR}/dist-wheels"
    (cd "$(dirname "${NODE_DIR}")/.." \
      && uv build --all-packages --wheel --out-dir "${NODE_DIR}/dist-wheels")
  fi
  docker build \
    --platform linux/arm64 \
    -f "${NODE_DIR}/Dockerfile.role" \
    --build-arg "LOGION_BASE_URL=${LOGION_BASE_URL}" \
    -t "${LOGION_NODE_IMAGE}" \
    "${NODE_DIR}"
}

node_validate_runtime() {
  docker info >/dev/null 2>&1 || {
    echo "ERROR: no working container runtime. Start Docker Desktop or Podman machine first." >&2
    return 1
  }
}

# node_up ROLES=consumer,auditor — validate, build, provision role
# credentials, and start the named roles.
node_up() {
  local roles="${1:-consumer,auditor}"
  node_validate_runtime
  mkdir -p "${NODE_DIR}/roles"
  for role in ${roles//,/ }; do
    local key_file="${NODE_DIR}/roles/${role}.api_key"
    if [[ ! -s "${key_file}" ]]; then
      echo "ERROR: roles/${role}.api_key is missing or empty." >&2
      echo "Provision a disposable agent key for the '${role}' role first" >&2
      echo "(seed a devrig agent, then write its key to that file)." >&2
      return 1
    fi
    chmod 600 "${key_file}"
  done
  node_build_image
  node_compose up -d ${roles//,/ }
  node_status
}

node_status() {
  load_node_env
  echo "== local node services =="
  node_compose ps
  echo
  echo "== role identities (non-root UIDs) =="
  for svc in consumer auditor; do
    local uid
    uid="$(node_compose exec -T "${svc}" id -u 2>/dev/null || echo unreachable)"
    echo "${svc}: uid=${uid}"
  done
  echo
  echo "== declared limits =="
  echo "cpus=1.0 memory=1536M pids=256 per role (compose.yaml deploy.resources.limits)"
  echo
  echo "== mounted sources (sanitized) =="
  echo "consumer: consumer_home consumer_workspace consumer_spool (named volumes)"
  echo "auditor:  auditor_home auditor_workspace auditor_spool (named volumes)"
  echo "no host bind mounts, no socket, no host home"
  echo
  echo "== credential status =="
  for svc in consumer auditor; do
    if node_compose exec -T "${svc}" test -s "/run/secrets/${svc}_api_key" 2>/dev/null; then
      echo "${svc}: api key secret present"
    else
      echo "${svc}: api key secret MISSING"
    fi
  done
  echo
  echo "cleanup: make node-dev-down | make node-dev-reset ROLE=consumer YES=1"
}

# node_agent ROLE=consumer -- <command...> — run a one-shot command in
# exactly one named role. Never touches the other role's state.
node_agent() {
  local role="$1"
  shift
  node_compose exec -T "${role}" "$@"
}

node_down() {
  # Stop and remove containers; named role state is preserved. The
  # wheels directory is build output that lives inside the phase's
  # activation glob: leaving it behind makes the local tree digest
  # differ from the committed tree the auditor certifies.
  node_compose down
  rm -rf "${NODE_DIR}/dist-wheels"
}

# node_reset ROLE=consumer YES=1 — remove ONE role's disposable state
# and revoke its credential. Refuses to run without both an exact role
# name and YES=1.
node_reset() {
  local role="$1"
  local yes="${2:-}"
  case "${role}" in
    consumer|auditor) ;;
    *)
      echo "ERROR: node_reset requires an exact role name (consumer or auditor), got '${role}'." >&2
      return 1
      ;;
  esac
  if [[ "${yes}" != "1" ]]; then
    echo "ERROR: refusing to reset role '${role}' without YES=1." >&2
    return 1
  fi
  node_compose stop "${role}"
  node_compose rm -f "${role}"
  # Remove exactly this role's disposable volumes; the other role's
  # containers and volumes stay untouched (never `compose down`, which
  # would stop both roles).
  docker volume rm -f "logion-local-node_${role}_home" \
    "logion-local-node_${role}_workspace" \
    "logion-local-node_${role}_spool" >/dev/null
  if [[ -s "${NODE_DIR}/roles/${role}.api_key" ]]; then
    # Revocation of the live key happens against the devrig API by the
    # operator; here we retire the local copy so a stale key can never
    # be re-mounted silently.
    mv "${NODE_DIR}/roles/${role}.api_key" \
      "${NODE_DIR}/roles/${role}.api_key.revoked.$(date +%s)"
    echo "role '${role}': disposable state removed; local key copy retired."
    echo "Revoke the matching agent key on the devrig API to complete the reset."
  else
    echo "role '${role}': disposable state removed; no local key copy found."
  fi
}

case "${1:-}" in
  up) shift; node_up "${1:-${NODE_ROLES:-consumer,auditor}}" ;;
  status) node_status ;;
  agent) shift; role="$1"; shift; node_agent "${role}" "$@" ;;
  down) node_down ;;
  reset) shift; node_reset "$1" "${2:-}" ;;
  *) echo "usage: node.sh {up|status|agent|down|reset} ..." >&2; exit 2 ;;
esac