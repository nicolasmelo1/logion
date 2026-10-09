<!-- Generated from Logion's canonical planning source. Public pull requests are welcome; see CONTRIBUTING.md. -->

# Driven actor performs the measured flow

> **Honesty boundary:** a scenario's agent roster is what its gate claims met the
> product. Today, in two sealed scenarios, a ~1000-line Python script performs
> the flow and a driven agent stands next to it saying nothing.

Status: open. Blocks nothing that is already merged; blocks the merge of
`logion#317` only if the driven-actor rule ships in that PR.

Exit condition: `python3 scripts/check_scenario_actors.py` (in `logion`) exits 0 with
`isolated_runner_node.yaml:node_operator` and
`eval_contract_reference_runner.yaml:node_operator` absent from
`scripts/allowed_mute_actors.txt`, and the resealed
`artifacts/phase-gates/phase-15.15.json` and `phase-16.1.json` each record a
real-agent run whose `node_operator` phase carries a non-empty goal.

## What is actually wrong

The driven-actor rule — `scripts/check_scenario_actors.py`, new in
`logion#317` — reports two findings:

```
eval_contract_reference_runner.yaml:node_operator: declares a driver but no phase gives it a goal
isolated_runner_node.yaml:node_operator: declares a driver but no phase gives it a goal
```

Both scenarios have the same shape. `node_operator` declares `driver: codex`,
its phases carry `goal: ""`, and the work happens in a `local_hook`:

| scenario | phase | hook | assertions |
| --- | --- | --- | --- |
| `isolated_runner_node` | `execute_runner_evidence` | `run_runner_evidence.py` (1066 lines) | 0 |
| | `collect_runner_evidence` | `capture_runner_evidence.py` | 7 |
| | `verify_api_logs` (actor `auditor`, real goal) | — | 1 |
| `eval_contract_reference_runner` | `execute_eval_evidence` | `run_eval_evidence.py` (857 lines) | 0 |
| | `collect_eval_evidence` | `capture_eval_evidence.py` | 8 |
| | `verify_api_logs` (actor `auditor`, real goal) | — | 1 |

`isolated_runner_node` additionally lists `consumer`, `evaluator`,
`contributor` and `sponsor` as driven agents with no phase at all; those four
are already frozen in `scripts/allowed_mute_actors.txt`. So of six declared
driven roles, exactly one speaks, and its only job is `logs.no_500s`.

The hooks drive the flow the assertions measure: `httpx` straight at the API for
enrolment, contract upload, result submission and the rejection classes, plus
`subprocess` for wheel builds, fresh venvs and Docker. That is the shape the
rule's `why` describes as "a replay filed as evidence about an outcome".

## Two moves that look like fixes and are not

**Do not add the two keys to `scripts/allowed_mute_actors.txt`.** That file's own
header forbids it: the baseline was taken from `main` at the commit that
introduced the rule, "deliberately not from the branch that added it: freezing
the branch would have grandfathered the two violations the rule was written to
catch." Adding a key there is the one move the file exists to make visible in
review.

**Do not install the runner wheel into the devrig role tree.** Putting
`logion-node` on an agent's PATH via `scripts/devrig/build_artifacts.py` invents
a distribution path no customer has, which is exactly the customer-fidelity
violation [the phase gate](agent-proving-ground-phase-gate.md) forbids: "start
from the public entry point a customer would have". It is not needed either —
see the next section.

## Verified facts, so this is not re-investigated

Established 2026-09-04 against `logion` at `refs/remotes/pr/317`:

- **`logion-node` is already on the role image's PATH, by a real path.**
  `deploy/local-node/node.sh:159` runs `uv build --all-packages --wheel --out-dir
  dist-wheels`; `packages/runner` is a workspace member declaring
  `logion-node = "logion_runner.cli:main"`; `Dockerfile.role:19-20` copies
  `dist-wheels/` and `pip install`s every wheel. This is why the compose
  `runner` service can declare `entrypoint: ["logion-node"]` over the same
  `LOGION_NODE_IMAGE` that `consumer` and `auditor` use.
- **`consumer` and `auditor` are long-running, so `docker compose exec` works.**
  They inherit the `x-role-base` command (`timeout ... sleep infinity`). Only
  the `runner` service is `run --once` and exits, and it sits behind
  `profiles: [runner]`. The agent-operates-a-role idiom is already proven by
  `local_multi_agent_node.yaml`'s `consumer_repo_scoped_install` phase.
- **No eval subcommand needs Docker.** `execute_eval_contract` uses
  `LocalTestBackend(python_executable=sys.executable)`
  (`packages/runner/logion_runner/evals/executor.py:246`), so
  `logion-node eval validate | run | inspect-result | compare` all work inside a
  read-only role container with a `tmpfs` `/tmp`.
- **The `logion` CLI has no eval surface at all.** Nothing under
  `packages/cli/cli` matches `eval|runner|node`. Driving this through the
  consumer CLI would mean designing and shipping a new command group, which
  16.1 did not ask for.
- **Four eval operations are in the public v1 contract**, so HTTP is a legitimate
  customer entry point for the parts no CLI covers (the phase gate lists
  "public HTTP API" among the acceptable entry points):
  `POST /v1/evals/contracts` (`upload_eval_contract`),
  `GET /v1/evals/contracts/{ref}` (`get_eval_contract`),
  `POST /v1/evals/jobs/validate` (`validate_eval_job`),
  `POST /v1/evals/results` (`submit_eval_result`).
- **A goal cannot name the golden contract.** It lives at
  `packages/eval-contract/tests/fixtures/golden_contract.json`, and both
  `packages/` and `tests/fixtures/` are in
  `customer_fidelity.forbidden_goal_substrings`. The driven phase therefore
  needs a seeding phase first, and the goal must name the in-container path the
  seed created — the same construction `local_multi_agent_node.yaml` uses for
  its fixture skill bundle.
- **`capture_eval_evidence.py` is only 103 lines** and merely assembles a
  manifest from files the run script wrote. All the weight is in
  `run_eval_evidence.py`.

## Work breakdown

The scenario edit and the hook rewrite are **one change, not two**: a real goal
requires seeded fixtures, and seeding is a change to the run script.

1. **Split `run_eval_evidence.py` three ways.** A `seed` mode (build the
   validator wheel, seed contract and subject into the operator's workspace) that
   runs as a phase with no `driver`, so the scenario says plainly that setup is a
   fixture. The middle — validate, upload, the two executions, compare, submit,
   lookup, the five rejection classes — leaves the script. A `collect` mode reads
   the outcome back and types the facts.
2. **Give `node_operator` one phase with a real goal.** One is enough: the
   checker's `voiced` set is per agent, not per phase, so the existing
   hook-only collect phases stay legal. Write it in the
   `local_multi_agent_node.yaml` idiom — `docker compose --project-directory
   deploy/local-node ... exec -T <role> sh -c '<command>'`, in-container paths
   only, with a `success_hint`.
3. **Decide where each fact's authority lives.** This is the hard part and the
   reason the change deserves its own mutation tests. Four of the eight 16.1
   assertions have server-side truth and must read it rather than trust the
   agent. For facts that are only local (`validator_import_root`,
   `validation_exit_code`), apply the provenance shape
   `files.observation_from_live_hook` got in `ef710d4`: the transcript must name
   the session the payload claims, must sit outside every root the agent can
   write, and the payload must carry the harness's own event fields. Without
   this step the change moves forgery from a script to an agent instead of
   removing it.
4. **Repeat 1–3 for `run_runner_evidence.py`.** Its rig-only parts are genuinely
   rig and must end up in undriven phases: the sandbox image build, host-side
   canary planting, the expired-lease sweep, and one adversarial job per
   forbidden effect.
5. **Reseal.** Editing either scenario YAML changes an activation path, so
   `phase-15.15.json` and `phase-16.1.json` both go stale and each needs a fresh
   real-agent run (`codex`/`gpt-5.4-mini`, `api_adapter: local-devrig`).
   `phase-15.14.1.json` is unaffected — neither YAML is in its activation list.

## Sequencing against the merge

**Measured 2026-09-04, after `canonical maintainer workspace#172` and `backend repository#176`
merged and with `logion#317` still open:**

| tree under audit | findings |
| --- | --- |
| `main` as it stands now | **4 CRITICAL** |
| the same, with `logion#317`'s tree | **0** |

The four are the two stale seals (`15.14.1`, `15.15`) plus two the private merge
created: merging `#176` put `packages/api/api/evals/` on private `main`, which
activates `16.1` through its `private_any` path while the public leg has no
scenario and no seal (`PHASE_REQUIRED_SCENARIO_MISSING`,
`PHASE_REAL_EVIDENCE_MISSING`).

So `main` is red until `logion#317` lands, and `logion#317` is the only thing
that makes it green. This plan cannot do it quickly. Land `#317` first with the
driven-actor rule removed, then do this work as its own change with the rule as
its exit criterion. Nothing the rule ships —
`.software-factory/rules/every-actor-has-a-goal.yaml`,
`scripts/check_scenario_actors.py`, `scripts/allowed_mute_actors.txt`,
`docs/factory-rules.md`, the mutation directory — is an activation path of
`15.14.1`, `15.15` or `16.1`, so removing it preserves all three fresh seals and
costs no real-agent run.

Holding `#317` instead is no longer a neutral choice: two of the three legs are
already on `main`, so holding leaves four criticals on `main` for however long
this plan takes, not two.
