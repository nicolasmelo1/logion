#!/usr/bin/env bash
# Thin entrypoint. Real implementation lives in src/gmailcli/.
# The agent invokes this; this script dispatches to the bundled
# Python module. Bundle is self-contained — no pip install required.
set -euo pipefail
COURSE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec env PYTHONPATH="$COURSE_DIR/src:${PYTHONPATH:-}" python -m gmailcli search "$@"
