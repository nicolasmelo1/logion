---
summary: Learn how credits, free courses, paid purchases, and approvals work.
---
# Credits and Purchases

Logion has no platform subscription gate. Free courses cost zero credits. Paid
course purchases spend Logion credits and grant an entitlement without a Stripe
redirect for each purchase.

Credits top up at 100 credits per US dollar. Top-up payment is processed by
Stripe. Credits are non-cash usage rights: buyers cannot transfer them to other
users or redeem them for money.

An agent must never spend credits or top up automatically. Before purchase,
show the user the course, exact price, and expected resulting balance, then wait
for explicit approval. Insufficient balance is a reason to suggest a top-up,
not permission to perform one.

Useful commands:

```bash
logion credits balance --json
logion courses get COURSE_ID
logion courses purchase COURSE_ID --expected-price-cents N --yes --json
logion credits ledger --json
```

Creators keep 85% of paid course revenue and the platform fee is 15%. Eligible
creator and contributor earnings are paid separately through Stripe Connect;
that payout is not buyer credit redemption.
