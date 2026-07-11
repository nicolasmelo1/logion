# logion-bot

Public surface for the Logion issue-mention bot (`@logion-bot`):
command grammar, pure parser, and reply templates.

This package deliberately defines only **what the bot says and what it
understands**. It does **not** implement webhook handling, thread state,
credit balances, bounty services, or any policy about *who* may open a
bounty. Those decisions live server-side in the private backend and are
not configurable from this package, so public contributions to the bot's
language can never weaken the money rules by construction.

All amounts shown by the bot are denominated in **credits**. No reply
template renders a dollar sign (`$`) or the string "USD".

## Modules

- `logion_bot.commands` — pinned grammar constants (verbs, amount
  format, course disambiguator, thread states).
- `logion_bot.parser` — `parse_issue_bot_command`, a pure, zero-I/O
  function that turns one comment/issue body into at most one command.
- `logion_bot.replies` — reply templates rendered by the private
  backend when it posts issue comments.

## Usage

```python
from logion_bot.parser import parse_issue_bot_command

cmd = parse_issue_bot_command("@logion-bot bounty 250", bot_login="logion-bot")
assert cmd.kind == "bounty"
assert cmd.amount_credits == 250
```
