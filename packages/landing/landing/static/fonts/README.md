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
before subsetting. The build is `packages/landing/scripts/subset_brand_fonts.py`,
which pins both upstream sources to immutable revisions and verifies them by
sha256 on fetch:

```
uv run --with "fonttools[woff]" python packages/landing/scripts/subset_brand_fonts.py
```

## Reproducibility

Inputs are pinned and checksum-verified, so they cannot silently drift or be
tampered with. The woff2 output, however, is not guaranteed bit-identical on
regeneration: fontTools' subsetter and variable-font instancer serialize some
tables in a run-dependent order. The committed files below are therefore the
canonical artifact — verify them by sha256:

```
7b3eee70bd903eaf324278c224bc10b73395f271d0914001d5d5d4ca4a5329c0  JetBrainsMono-Bold.woff2
82aed51e97c56aaf04e02805a64e0bbdea926f1f8255b121144b54de2b34b7ed  JetBrainsMono-Regular.woff2
52afc0dcd9948b21c3b96e01eb91a3568e370de3b100dbd9ca890418560a1365  LibreBaskerville-Italic.woff2
ba17a35fc0f1fc3d5ce462c25bdaa8dc2f23f482d502c23fb562581264e81ff8  LibreBaskerville-Regular.woff2
```

## License

Both families are licensed **SIL Open Font License 1.1**. The full license
texts are included verbatim:

- `OFL-JetBrainsMono.txt`
- `OFL-LibreBaskerville.txt`
