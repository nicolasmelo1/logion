# Payments and Checkout

Buyer-side checkout and order tracking, plus creator-side Stripe onboarding.
Paid actions are in `safety.requires_confirmation` — the agent must obtain
explicit user approval before invoking checkout.

## Buyer-side: starting a paid checkout

```bash
logion payments checkout COURSE_ID --price-cents 1900 --json
```

`COURSE_ID` is positional and required. Optional `--price-cents` lets the
agent assert the expected price (in cents); omit to use the course's stored
price. Output carries the order id and the Stripe checkout URL (or, for
free courses, an immediate paid order with no Stripe redirect).

Confirmation rule: ALWAYS confirm `course_id` and price with the user before
invoking checkout. Reproduce the price as `$X.YY` in the confirmation
prompt; never charge silently.

## Buyer-side: checking an order

```bash
logion payments orders get ORDER_ID --json
```

Returns the order status (`pending` / `paid` / `failed` / `refunded`),
linked `course_id` and `version_id`, `entitlement_id` when paid, and the
checkout URL when still pending.

## Buyer-side: wait until terminal

```bash
logion payments orders wait ORDER_ID --wait-timeout 120 --interval 5 --json
```

Polls `orders get` until terminal. Exit codes: `0` paid, `1` failed or
refunded, `2` timeout. `--wait-timeout` capped at 600 seconds server-side;
`--interval` defaults to 5 seconds. Use after a Stripe checkout to detect
settlement without manual refresh.

## Creator-side: seller readiness

```bash
logion payments seller-readiness --json
```

Returns `is_ready`, `onboarding_status`, `charges_enabled`,
`payouts_enabled`, `details_submitted`, `currently_due`, `disabled_reason`.
Required check before creating a paid course; if `is_ready` is false, defer
to the next step.

## Creator-side: Stripe onboarding link

```bash
logion payments onboarding-link --json
```

Returns a single-use `onboarding_url` plus the `connected_account_id`.
Surface the URL to the user once; never persist it to recall or re-emit it
in conversation history.

## Safety rules

- `paid_checkout` is in `safety.requires_confirmation`. Confirm price and
  course before invoking checkout.
- Never auto-retry a failed checkout. Surface the error and ask the user
  whether to retry or pick a different course.
- Never echo the Stripe onboarding URL in subsequent turns; it expires and
  contains user-bound identity.
