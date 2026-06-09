# PR Review Checklist

When reviewing a code diff, walk through every category below. For each category, either confirm the diff is clean or flag the specific lines that violate.

Each category has a stable code (`category:subcategory`). When you flag an issue, **always include the category code verbatim** in your review — the eval scorer relies on these codes.

## Security

- **security:sql-injection** — any SQL query built via string concatenation, f-string, or `%` formatting with values that could include user-controlled input. Parameterized queries (`?` placeholders, named parameters, or ORM equivalents) are the only acceptable form.
- **security:hardcoded-secret** — API keys, tokens, passwords, private keys, or session secrets appearing as string literals in source code. Must come from environment variables, a secrets manager, or a config file outside version control.
- **security:unvalidated-input** — user-supplied data flowing into shell commands, file paths, deserialization, or `eval`-like sinks without validation.

## Reliability

- **reliability:missing-error-handling** — network calls, file I/O, or subprocess invocations without `try`/`except` (or the language equivalent). Failures must either be handled explicitly or allowed to propagate by design — not silently dropped.
- **reliability:resource-leak** — file handles, sockets, or database connections opened without `with` (or the language's equivalent cleanup mechanism). Long-running processes will starve.

## Correctness

- **correctness:off-by-one** — `range(n + 1)` where `range(n)` is correct, or vice versa. Indexing past the end of a list. Loops that miss the first or last element. Slice bounds that include/exclude the wrong endpoint.
- **correctness:wrong-comparison** — `==` between mismatched types (e.g. `str` vs `int`), `is` used for value comparison instead of identity, mutable default arguments shared across calls.

## Style (advisory)

- **style:unclear-name** — variable or function names that don't explain intent.
- **style:dead-code** — unreachable branches, unused imports, commented-out blocks.

Style findings are advisory — they should be noted but do not block.

## Output format

For each issue found, write one line in this format:

```
<category-code> <path>:<line> — <short description>
```

Example:

```
security:sql-injection users/dao.py:7 — query built via string concatenation with user-supplied `email`
```

If no issues at all, write a single line:

```
no issues
```

This output format is what the eval scorer reads. Deviations (missing category codes, paraphrasing the codes, etc.) will fail the eval.
