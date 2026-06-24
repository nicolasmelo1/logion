<!-- SPDX-License-Identifier: MIT -->
# Self-hosted brand fonts

These woff2 files are **self-hosted** so the landing page renders the brand
typefaces with **no external font fetch** (no Google Fonts `@import` /
`fonts.googleapis.com` / `fonts.gstatic.com`). They are loaded via `@font-face`
in `../styles.css`, `local()`-first with `font-display: swap`, behind the
`--mono` / `--serif` system fallback stacks.

## Files

| File | Family | Style / weight | Source |
| --- | --- | --- | --- |
| `JetBrainsMono-Regular.woff2` | JetBrains Mono | normal 400 | [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono) v2.304 |
| `JetBrainsMono-Bold.woff2` | JetBrains Mono | normal 700 | same |
| `LibreBaskerville-Regular.woff2` | Libre Baskerville | normal 400 | [google/fonts `ofl/librebaskerville`](https://github.com/google/fonts/tree/main/ofl/librebaskerville) |
| `LibreBaskerville-Italic.woff2` | Libre Baskerville | italic 400 | same |

## Subsetting

The originals are subset to the glyphs the page actually uses to keep bytes
small (~180 KB total). Mono keeps Latin-1 + General Punctuation + Greek (the
`ΛΟΓΙΟΝ` ornament) + block-element / geometric / check glyphs (ASCII art and the
`█` cursor); Bold is display-only (Latin + Greek + punctuation); serif is
Latin-only. Code ligatures (`liga`/`calt`) are dropped so the install command
renders literally. Libre Baskerville is a variable font instanced to `wght=400`
before subsetting. The exact, reproducible build is
`packages/landing/scripts/subset_brand_fonts.py`:

```
uv run --with "fonttools[woff]" python packages/landing/scripts/subset_brand_fonts.py
```

## License

Both families are licensed **SIL Open Font License 1.1**. The full license
texts are included verbatim:

- `OFL-JetBrainsMono.txt`
- `OFL-LibreBaskerville.txt`
