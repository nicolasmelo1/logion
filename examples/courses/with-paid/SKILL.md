---
name: with-paid
description: Paid-course example showing how to package a self-contained Logion bundle with the marketplace paid license. Use as a starting point when you want a benign course that reads local artifacts, produces a structured report, and exercises the paid publication path end to end.
version: 1.0.0
author: logion-examples
license: Logion Standard Course License v1.0
platforms: [linux]
compatibility: Requires python3 on the host.
metadata:
  hermes:
    tags: [reporting, audit, paid-course]
    category: operations
    related_skills:
      - minimal
      - with-references-and-scripts
---

# With-Paid Skill

This is a benign paid-course example. It exists to demonstrate the paid bundle
contract: self-contained files, explicit capabilities, and the Logion Standard
Course License v1.0.

## When to Use

- You want a reference paid bundle to test create -> upload -> complete.
- You need a simple course that reads local notes and writes a structured
  report.
- You want an example that exercises the paid-license enforcement path without
  introducing risky operational content.

## Prerequisites

- `file` and `terminal` tools.
- `python3` available on the host.

## How to Run

```bash
python3 scripts/render_report.py ./inputs/findings.txt ./outputs/report.md
```

## Output

The script reads a plain-text findings list and writes a normalized markdown
report under `outputs/`.
