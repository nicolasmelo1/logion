#!/usr/bin/env python3
"""Hash the vendor profile after Logion reconciliation and observation."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    snapshot = {
        str(path.relative_to(root)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    output.write_text(json.dumps(snapshot, sort_keys=True) + "\n")
    sys.stdout.write(json.dumps({"vendor_after": str(output)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
