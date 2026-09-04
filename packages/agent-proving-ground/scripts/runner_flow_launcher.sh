#!/bin/sh
# Versioned fixture: the host-side launcher the driven node operator runs for
# the isolated runner evidence. run_runner_evidence.py copies this file into
# the prepared evidence directory verbatim with the two paths substituted, so
# the executed workflow is reviewable here, not generated at prepare time.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RECORD="$ROOT/launcher-command.json"
set +e
"@@OPERATOR_PYTHON@@" "@@@EVIDENCE_SCRIPT@@@" operator "$ROOT"
CODE=$?
set -e
python3 - "$RECORD" "$CODE" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(
    json.dumps({"command": "prepared public logion-node workflow", "exit_code": int(sys.argv[2])}) + "\n"
)
PY
exit "$CODE"