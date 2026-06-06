# Credits and Payments

Credit balance, top-ups, ledger, and creator-side seller onboarding.
Paid and credit-spending actions are in `safety.requires_confirmation` — the
agent must obtain explicit user approval before invoking any of them.

## Credit balance

```bash
logion credits balance --json
```

Returns the current credit balance and currency unit. Use this to confirm
sufficient credits before any spend.

## Available credit packs

```bash
logion credits packs --json
```

Lists pack codes, credit amounts, and prices. Show these to the user when
suggesting a top-up.

## Credit top-up

```bash
logion credits top-up --pack PACK_CODE --json
```

Creates a Stripe Checkout session for the given pack. Returns a `top_up_id`
and `checkout_url`. Surface the URL to the user — do not open or follow it
automatically.

```bash
logion credits top-ups get TOP_UP_ID --json
```

Returns top-up status (`pending` / `paid` / `failed` / `expired` / `cancelled` / `disputed` / `reversed`).

```bash
logion credits top-ups wait TOP_UP_ID
```

Polls until the top-up reaches a terminal state (`paid`, `failed`,
`expired`, `cancelled`, `disputed`, or `reversed`). Use this after the user completes checkout so you can confirm
the new balance.

## Credit ledger

```bash
logion credits ledger --json
```

Returns recent ledger entries (credits in, credits out, running balance).
Useful for auditing spend or confirming a top-up posted.

## Creator-side: seller readiness

```bash
logion payments seller-readiness --json
```

Returns `is_ready`, `onboarding_status`, `charges_enabled`,
`payouts_enabled`, `details_submitted`, `currently_due`, `disabled_reason`.
Required check before creating a paid course; if `is_ready` is false, defer
to the onboarding link below.

## Creator-side: Stripe Connect onboarding link

```bash
logion payments onboarding-link --json
```

Returns a single-use `onboarding_url` plus the `connected_account_id`.
Surface the URL to the user once; never persist it to recall or re-emit it
in conversation history.

## Safety rules

- **NEVER spend credits without explicit user approval.** Before any
  credit-spending action, show the cost in credits and the resulting balance
  change, then wait for the user to confirm.
- **NEVER top up credits without explicit user approval.** Always show the
  pack details (credits, price) and ask before creating a checkout session.
- **NEVER cash out without explicit creator approval.** This applies to
  future cash-out commands as well — document this rule now.
- **Do not auto-top-up on insufficient credits.** When a balance is too low
  for an action, inform the user and suggest a top-up instead of silently
  triggering one.
- **Before spending, always show the cost in credits and the resulting
  balance change** so the user can make an informed decision.
- Never auto-retry a failed top-up. Surface the error and ask the user
  whether to retry or pick a different pack.
- Never echo the Stripe onboarding URL in subsequent turns; it expires and
  contains user-bound identity.