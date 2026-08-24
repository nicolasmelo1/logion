# logion-instrumentation

Versioned instrumentation profile schema and validator for the Logion
publisher-reporter pipeline.

The profile is the single file the reporter reads. It declares which
usage events a resource emits, which fields are included or excluded,
and where delivery batches are sent. The schema is
`logion.instrumentation/v1`.

## Usage

```bash
# Validate a profile
logion-instrumentation validate path/to/profile.json

# Compute the canonical digest
logion-instrumentation digest path/to/profile.json

# Diff two profile versions
logion-instrumentation diff old.json new.json
```

## Vocabulary reuse

Event, outcome, and duration-bucket enums are extracted from
`packages/cli/cli/usage/observations.py` at build time and embedded in
the JSON Schema. This package does **not** import the CLI. A test
greps both sources to ensure they stay in sync.