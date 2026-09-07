#!/bin/sh
# Versioned fixture: the exact public CLI workflow the driven node operator
# executes for the eval contract evidence. run_eval_evidence.py copies this
# file into the consumer role verbatim; any change to the measured commands
# happens here, in review, not at seed time.
set -u
root=/workspace/task/eval-flow
raw="$root/raw"
mkdir -p "$raw"
commands="$raw/commands.jsonl"
: > "$commands"
run() {
  name=$1
  shift
  "$@" > "$raw/$name.json"
  status=$?
  python - "$commands" "$status" "$@" <<'PY'
import json
import sys
with open(sys.argv[1], "a", encoding="utf-8") as handle:
    json.dump({"command": " ".join(sys.argv[3:]), "exit_code": int(sys.argv[2])}, handle)
    handle.write("\n")
PY
  return "$status"
}
run validate logion-node eval validate "$root/contract.json" || exit $?
run run-one logion-node eval run --subject "$root/subject.json" "$root/contract.json" || exit $?
run run-two logion-node eval run --subject "$root/subject.json" "$root/contract.json" || exit $?
python - "$raw/run-one.json" "$raw/result-one.json" <<'PY'
import json
import sys
json.dump(json.load(open(sys.argv[1], encoding="utf-8"))["result"], open(sys.argv[2], "w", encoding="utf-8"))
PY
python - "$raw/run-two.json" "$raw/result-two.json" <<'PY'
import json
import sys
json.dump(json.load(open(sys.argv[1], encoding="utf-8"))["result"], open(sys.argv[2], "w", encoding="utf-8"))
PY
run run-summary logion-node eval compare "$raw/result-one.json" "$raw/result-two.json" || exit $?
python - "$commands" "$raw/launcher-record.json" <<'PY'
import json
import sys
commands = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
json.dump({"commands": commands}, open(sys.argv[2], "w", encoding="utf-8"))
PY