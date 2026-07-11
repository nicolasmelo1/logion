---
summary: Understand credit-funded bounties and referral rewards.
---
# Bounties and Referrals

Bounties fund improvements or work with credits. Funding a bounty spends
credits and therefore always requires explicit user approval. A contributor may
submit work; acceptance creates eligible contributor earnings that can be paid
through Stripe Connect. Cancellation and payout behavior depend on the bounty
state shown by the CLI.

A submission on a bounty whose course has a linked GitHub repository can be
materialized as a draft pull request with `logion bounties submissions open-pr
BOUNTY_ID SUBMISSION_ID --yes`. When the repository requires a fork, the
command prints the branch to push to; open the PR from the fork (keeping the
Logion marker in the body) and attach it with `logion bounties submissions
register-pr BOUNTY_ID SUBMISSION_ID --pr-number N --yes`. Both commands mutate
state and require `--yes`. Merging the PR on GitHub only triggers Logion's
normal acceptance policy — a merge alone is neither publication nor payout.

Referral links and codes may award credits under the referral program. Before
sharing a referral, show the user the course and the referral code or link, then
obtain explicit approval. Self-referrals, duplicate-account abuse, and automated
signups for rewards are prohibited.

Use `logion bounties --help`, `logion referrals --help`, and the legal articles
`credits-terms` and `referral-terms` for complete rules.
