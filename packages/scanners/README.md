# logion-scanners

Deterministic course-scanning engine for Logion publication review.

This package extracts the scanner logic that runs during automated
publication review into a standalone, installable tool. It contains
no API or database dependencies — all configuration is injected or
loaded from the bundled policy YAML.

## Install

```bash
pip install logion-scanners
```

## CLI

```bash
logion-scanners scan <bundle-path> --policy publication-v1 [--format human|json] [--scanner agent|trivy|osv]
```

Exit codes: 0 = allowed, 1 = blocked, 2 = execution error.

## Programmatic

```python
from logion_scanners import (
    AgentScanner,
    OsvScanner,
    TrivyScanner,
    ScanPolicy,
    load_policy,
    run_scan,
)

policy = load_policy("publication-v1")
report = run_scan(
    bundle=Path("./my-course"), policy=policy, adapters=[AgentScanner()]
)
print(report.decision.allowed)
```

## Scanners

- **Agent scanner** — static analysis for agent-specific risks (no
  Docker required).
- **Trivy scanner** — filesystem vulnerability scan via Docker.
- **OSV scanner** — open-source vulnerability scan via Docker.

## Policy

The default policy (`publication-v1`) encodes the current hosted
review blocking rules. Policy files are immutable; behavior changes
require a new policy version.