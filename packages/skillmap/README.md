# logion-skillmap

Deterministic package-map inference engine for Logion.

This package is stdlib-only (no external dependencies). It infers a
`PackageMap` from repository trees by checking for:

1. An explicit `logion-package-map.yaml` at the repo root (author map).
2. A `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`
   manifest (plugin manifest).
3. `SKILL.md` / `skill.md` files (skill scan).

## Installation

```bash
pip install logion-skillmap
```

## Usage

```python
from logion_skillmap import infer, parse_package_map, validate_package_map

# Parse and validate an author-provided map
pm = parse_package_map(yaml_text)
warnings = validate_package_map(pm)

# Or infer from a repository tree
result = infer(tree_entries, read_blob_callback)
```