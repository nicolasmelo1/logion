# Phase 15.15 dogfood record

## Outcome

Blocked honestly. The mandatory dogfood protocol could not be completed because
this checkout has no available container/sandbox/untrusted-code resource to
recall, inspect, acquire, reconcile, and exercise. No resource was used and no
feedback or review was submitted, which is what the plan requires when
acquisition, exact attribution, consent, or actual use is absent.

## Correction, 2026-09-01

An earlier version of this file ended by claiming that "the phase-15.15
real-agent evidence manifest is intentionally absent" and that "a contract-audit
gate must therefore remain failing until a retained local-devrig run supplies
typed runner facts and its raw report."

That is no longer true, and leaving it in place would misdescribe the gate. The
retained run now exists: `artifacts/phase-gates/phase-15.15.json` seals run
`20260901T171705-phase_15_15_isolated_runner` (driver `claude-code` /
`claude-haiku-4-5`, adapter `local-devrig`) with `status: passed`, no caveats and
no unsupported assertions, and `artifacts/phase-gates/reports/phase-15.15-isolated-runner.json`
carries the typed facts the evidence contract in
`packages/contract-audit/policy/phase-integrity.yaml` recomputes the verdict from.

The missing dogfood above is a separate, still-open fact. A sealed execution gate
says the runner does what the phase claims; it says nothing about whether an
acquired third-party resource was used to build it. Only the first of those two
happened.
