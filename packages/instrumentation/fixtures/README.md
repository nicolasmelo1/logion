# Recorded harness hook payloads

Field shapes transcribed from each harness's official hook documentation
on 2026-08-17, so the parsers are pinned to a source rather than to this
repository's memory of one:

- `claude_code_post_tool_use.json` — <https://code.claude.com/docs/en/hooks>
- `codex_post_tool_use.json` — <https://learn.chatgpt.com/docs/hooks>

Paths inside the fixtures are placeholders that tests rewrite to a
temporary installation directory. When a harness changes its payload,
update the fixture from the documentation in the same commit as the
parser change — never adjust the parser to match an unrecorded guess.
