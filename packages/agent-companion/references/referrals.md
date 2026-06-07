# Referrals

The referral program uses a **two-way model** with two lanes:

- **Product lane** — rewards attributed when a new user signs up via
  any referral link on the platform.
- **Creator lane** — rewards attributed when a buyer purchases a
  course using a creator's referral link for that specific course.

## Commands

### `logion referrals code [--json]`

Show your default referral code. This code is embedded in every
referral link you generate and identifies you as the referrer across
both lanes.

### `logion referrals link COURSE_ID --yes [--json]`

Generate a referral link for a specific course. The link contains
your referral code and the course identifier so that purchases through
it are attributed to you in the **creator lane**.

**Safety requirement:** This command requires the `--yes` flag before
it will share a referral link. Without `--yes`, the command refuses to
run and suggests re-running with confirmation. This guard prevents
accidental link disclosure in automated workflows.

### `logion referrals stats [--json]`

Show aggregate referral statistics for the authenticated user,
including counts for both the product and creator lanes.

### `logion referrals attributions [--json]`

List individual referral attributions — each record represents a
user who was referred and attributed to your account, along with the
lane (product or creator) and timestamp.

## Safety

- Always confirm before sharing referral links. The `link` subcommand
  requires `--yes` to prevent accidental disclosure.
- Review the generated link and the course it targets before
  distributing it.
- Referral links are tied to your identity — treat them like
  credentials.
