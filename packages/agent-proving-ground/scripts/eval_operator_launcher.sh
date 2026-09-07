#!/bin/sh
# Versioned fixture: the host-side launcher the driven node operator runs for
# the eval contract evidence. run_eval_evidence.py copies this file into the
# prepared evidence directory verbatim with the operator surface substituted,
# so the executed workflow is reviewable here, not generated at seed time.
# Everything it drives is the shipped node operator surface: no compose flag,
# no image name, and no repository path is spelled out again here.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
NODE_OPERATOR="@@NODE_OPERATOR@@"
RAW="$ROOT/raw"
mkdir -p "$RAW"
set +e
"$NODE_OPERATOR" agent consumer sh -c \
  'sh /workspace/task/eval-flow/run-eval-flow.sh'
CODE=$?
set -e
if [ "$CODE" -eq 0 ]; then
  "$NODE_OPERATOR" cp consumer:/workspace/task/eval-flow/raw/. "$RAW"
fi
python3 - "$RAW/launcher-command.json" "$CODE" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(
    json.dumps({"command": "prepared public logion-node eval workflow", "exit_code": int(sys.argv[2])}) + "\n"
)
PY
exit "$CODE"
