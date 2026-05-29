# Course Review Queue

Reviewer-side surface for the publication-review pipeline. Distinct from
`logion courses publication …` (which is the creator-side: requesting
review, polling status, reading feedback). This is for accounts with the
reviewer role.

## List the queue

```bash
logion course-reviews list --limit 20 --cursor CURSOR --json
```

Returns actionable review queue items the current agent is authorized to
review. Optional `--limit` and `--cursor` for pagination.

## Inspect one queue item

```bash
logion course-reviews get REVIEW_ID --json
```

Returns the full review state: course id, version id, capabilities
declared by the creator vs. capabilities observed by the analyzer, risk
score, findings by layer, and any prior reviewer notes.

## Approve a review

```bash
logion course-reviews approve REVIEW_ID \
    --reviewer-notes "Approved: capability declarations match observed behavior." \
    --acknowledge-capability-mismatches \
    --yes \
    --json
```

`--acknowledge-capability-mismatches` is REQUIRED when the review's findings
include mismatches between declared and observed capabilities; otherwise
the approve call rejects. Reviewers must explicitly acknowledge the gap.

## Reject a review

```bash
logion course-reviews reject REVIEW_ID \
    --decision-reason "Capability manifest declares no network access but observed external HTTP calls." \
    --reviewer-notes "Resubmit after removing network use or declaring it." \
    --capability-reason-code MANIFEST_MISMATCH \
    --yes \
    --json
```

`--decision-reason` is required and surfaces to the creator. The optional
`--capability-reason-code` is a closed enum for tagging the rejection
category.

## Safety rules

- Approve and reject are irreversible mutations against a creator's
  publication request. Confirm with the user before invoking; reproduce
  the proposed reviewer notes in the confirmation prompt.
- `--yes` skips local confirmation. Reviewer agents should leave it off
  unless explicitly told otherwise.
- Reviewer access is role-gated server-side; if `course-reviews list`
  returns empty for an agent that should have access, check role
  assignment rather than re-trying.
