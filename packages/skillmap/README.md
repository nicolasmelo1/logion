# logion-skillmap

Deterministic package-map inference engine for Logion.

This package depends on [PyYAML](https://pypi.org/project/PyYAML/) as its
single runtime dependency. It infers a `PackageMap` from repository trees
by checking for:

1. An explicit `logion-package-map.yaml` at the repo root (author map).
2. A `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`
   manifest (plugin manifest).
3. `SKILL.md` / `skill.md` files (skill scan).

## Installation

```bash
pip install logion-skillmap
```

## Package map schema

The map is nested (`package` + `components`); `capabilities` is a mapping
keyed by capability name:

```yaml
version: 1
package:
  slug: my-package
components:
  capabilities:
    pr-review:
      entrypoint: skills/pr-review/SKILL.md
      capabilities_manifest: skills/pr-review/course/capabilities.yaml
      dependencies:
        - capability: diff-reading
          reason: "delegates hunk parsing"
    diff-reading:
      entrypoint: skills/diff-reading/SKILL.md
  runtime:
    include: ["skills/**"]
    entrypoint: skills/pr-review/SKILL.md
  source:
    include: ["src/**"]
    exclude: ["**/node_modules/**"]
  evals:
    commands:
      verify: "npm test"   # stored, never executed by this package
```

## Usage

```python
from logion_skillmap import (
    check_unknown_keys_raw,
    infer,
    parse_package_map,
    validate_package_map,
)

# Parse an author-provided map (raises TypeError only for non-mapping YAML).
pm = parse_package_map(yaml_text)

# Validate: check_unknown_keys_raw needs the raw mapping; validate_package_map
# covers everything derivable from the parsed model. Both return MapWarnings.
import yaml

warnings = check_unknown_keys_raw(yaml.safe_load(yaml_text))
warnings += validate_package_map(pm)

# Or infer a map deterministically from a repository tree.
result = infer(tree_entries, read_blob_callback)  # optional: slug=...
```