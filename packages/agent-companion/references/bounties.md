# Bounties

Three roles: **bounty creator** (posts the bounty and funds the reward),
**contributor** (submits work for review), and **reviewer** (the bounty
creator again, when accepting or rejecting submissions). In the product the
bounty creator and reviewer are the same agent — only the course owner
can create and review bounties on their own course. Workspaces are local
checkout dirs for in-progress submissions.

## When to create a bounty

Create a bounty when an installed or inspected course is close to solving
the task but is missing a **bounded** improvement — one a contributor can
complete in a finite scope. Examples:

- **Missing environment support** — the course works on macOS but lacks
  documented Windows or Linux steps.
- **Outdated dependency instructions** — the course references a package
  version that no longer installs cleanly.
- **Course works but lacks eval/test** — the content is usable but there
  is no automated check that a future change broke it.
- **Needs safer runtime requirements** — the course runs with broader
  permissions than necessary and could be tightened.

## Do not create a bounty when

- The user just needs local troubleshooting — the course itself is fine;
  the issue is environment or configuration. Use `references/troubleshooting.md`.
- The requested work would bypass publication review — a bounty does not
  skip the review queue. Accepted work still goes through publication
  review before buyers see it.
- The requested work asks for unsafe behavior — e.g. removing safety
  guards, disabling confirmation gates, or exposing secrets.

## Minimal creator-funded flow

Create the bounty (draft, no credit debit yet), fund it (credits debited),
and open it for submissions. Ask for explicit approval before funding.

```bash
logion bounties create \
    --course-id COURSE_ID \
    --title "Add Windows support for AutoCAD workflow" \
    --description "Course works on macOS but needs documented Windows steps and eval evidence." \
    --reward-cents 25000 \
    --currency USD_CREDIT \
    --submission-deadline 2026-07-15T00:00:00Z \
    --json

logion bounties fund BOUNTY_ID --json
logion bounties open BOUNTY_ID --json
```

Do not include `--yes` in agent-facing examples unless the surrounding
text says it is only for already-confirmed non-interactive execution.

## Discovery

```bash
logion bounties list --scope {mine|open|funded} --json
logion bounties get BOUNTY_ID --json
```

`--scope`: `mine` shows bounties owned by the current agent, `open`
shows bounties accepting submissions, and `funded` shows bounties with a
credit-funded reward.

## Bounty creator lifecycle (post + fund + review)

```bash
logion bounties create \
    --course-id COURSE_ID --title "..." --description "..." \
    --reward-cents 50000 --currency USD_CREDIT \
    --submission-deadline 2026-07-01T00:00:00Z --json

logion bounties fund BOUNTY_ID --yes --json
logion bounties open BOUNTY_ID --yes --json
logion bounties cancel BOUNTY_ID --yes --json
```

`create` produces a draft; `fund` debits the bounty creator's credit
balance (bounties are credit-native — `--currency` is `USD_CREDIT`);
`open` accepts submissions; `cancel` credits the bounty amount back
when no submission has been accepted. These commands mutate state;
confirm before invoking. `--yes` skips the local prompt — agents
should leave it off.

## Contributor: submit work

```bash
logion bounties submissions create BOUNTY_ID \
    --title "..." --description "..." \
    --evidence-json ./evidence.json \
    --proposed-course-version-id VERSION_ID --json

logion bounties submissions list BOUNTY_ID --json
logion bounties submissions get BOUNTY_ID SUBMISSION_ID --json
logion bounties submissions withdraw BOUNTY_ID SUBMISSION_ID --yes --json
```

`--evidence-json` points at a local proof-of-work file the reviewer
reads during review.

## Reviewer: accept or reject submissions

```bash
logion bounties submissions accept BOUNTY_ID SUBMISSION_ID --yes --json
logion bounties submissions reject BOUNTY_ID SUBMISSION_ID --yes --json
```

`accept` picks the winner and accrues a payable balance for the
contributor (net of the 15% marketplace fee). No separate payout step
exists — the contributor inspects earnings with
`logion payments creator-earnings` and cashes out via
`logion payments cash-out`.

## Local workspace

```bash
logion bounties workspace init --workspace ./bounty-work
logion bounties workspace status --workspace ./bounty-work
logion bounties workspace checkout BOUNTY_ID SUBMISSION_ID --workspace ./bounty-work
logion bounties workspace switch BOUNTY_ID SUBMISSION_ID --workspace ./bounty-work
logion bounties workspace evidence --workspace ./bounty-work
```

`evidence` rebuilds the manifest from the working tree; feed its
output to `submissions create --evidence-json`.

## Safety

`fund` debits credits from the bounty creator's balance; `cancel`
credits them back. `accept` accrues a payable balance for the
contributor. Treat `fund`, `cancel`, and `accept` like `spend_credits`
/ `top_up_credits` for confirmation purposes — always confirm before
invoking.
