# Claude Code Integration

The Logion Marketplace Companion can be used with
[Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Installation

Copy or symlink the companion into the project's `.claude/` directory or
the global Claude Code skills directory.

## Usage

Claude Code agents should:

1. Read `SKILL.md` as the bootstrap context.
2. Use local recall to check for previously-used capabilities.
3. Only search the marketplace when local recall is insufficient.
4. Load reference files on demand, not all at once.

## Safety

All confirmation gates (`requires_confirmation` in `capabilities.yaml`)
must be respected. Claude Code agents should never auto-approve paid
checkouts, installs, or publications.