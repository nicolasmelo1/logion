#!/usr/bin/env bash
# Thin entrypoint. Lists the authenticated user's Gmail labels.
set -euo pipefail
COURSE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec env PYTHONPATH="$COURSE_DIR/src:${PYTHONPATH:-}" python -m gmailcli labels "$@"
