# Bounties

Three roles: **buyer** (post + fund), **creator** (submit work), **owner**
(review and pay out). Workspaces are local checkout dirs for in-progress
submissions.

## Discovery

```bash
logion bounties list --scope {mine|open|funded} --json
logion bounties get BOUNTY_ID --json
```

`--scope`: `mine` owns, `open` accepting submissions, `funded` has
credit-funded reward.

## Buyer lifecycle

```bash
logion bounties create \
    --course-id COURSE_ID --title "..." --description "..." \
    --reward-cents 50000 --currency USD \
    --submission-deadline 2026-07-01T00:00:00Z --json

logion bounties fund BOUNTY_ID --yes --json
logion bounties open BOUNTY_ID --yes --json
logion bounties cancel BOUNTY_ID --yes --json
```

`create` produces a draft; `fund` debits the buyer's credit balance;
`open` accepts submissions; `cancel` credits the bounty amount back when
no submission has been accepted. All mutating; confirm before invoking.
`--yes` skips the local prompt — agents should leave it off.

## Creator: submit work

```bash
logion bounties submissions create BOUNTY_ID \
    --title "..." --description "..." \
    --evidence-json ./evidence.json \
    --proposed-course-version-id VERSION_ID --json

logion bounties submissions list BOUNTY_ID --json
logion bounties submissions get BOUNTY_ID SUBMISSION_ID --json
logion bounties submissions withdraw BOUNTY_ID SUBMISSION_ID --yes --json
```

`--evidence-json` points at a local proof-of-work file the buyer
reads during review.

## Owner: review and payout

```bash
logion bounties submissions accept BOUNTY_ID SUBMISSION_ID --yes --json
logion bounties submissions reject BOUNTY_ID SUBMISSION_ID --yes --json
logion bounties payout BOUNTY_ID --yes --json
```

`accept` picks the winner and accrues creator earnings for the
contributor (net of marketplace fee); `payout` records the payout.
Contributors can inspect earnings with `logion payments creator-earnings`
and cash out via `logion payments cash-out`.

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

`fund` debits credits from the buyer's balance; `cancel` credits them
back. `accept` accrues a payable balance for the contributor.
`payout` records the payout event. Treat `fund`, `cancel`, `accept`,
and `payout` like `spend_credits` / `top_up_credits` for confirmation
purposes — always confirm before invoking.