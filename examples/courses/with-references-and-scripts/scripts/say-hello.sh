#!/usr/bin/env bash
# Stand-in script for a real skill helper. Prints a greeting with a
# UTC timestamp prefix. Safe to run anywhere; touches no files.
set -euo pipefail
NAME="${1:-world}"
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "[$TS] hello, $NAME!"
