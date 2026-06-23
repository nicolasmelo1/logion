<!-- SPDX-License-Identifier: MIT -->
# Logion Branding Guide

Canonical source of truth for Logion's visual identity: logo, palette,
typography, voice, and motif. Every value here traces to a real source file in
this repo (`packages/landing/landing/static/styles.css`,
`packages/landing/landing/content/site.yaml`, and `assets/*.svg`) — nothing is
invented. The machine-readable mirror is served at
[`/design.txt`](https://logion.sh/design.txt), generated from the `design:`
block in `site.yaml` so it cannot drift from the page.

## Brand in one line

**Smarter, together.**

Lead with the collective network and the shared capability it creates — a
network of people teaching agents out-learns any lone model. Money is a
consequence of that network, not the hook. This framing carries through the
landing copy in `packages/landing/landing/content/site.yaml`.

## Logo

### The three marks

- **`assets/logion-mark.svg`** — the square seal mark: a gold Greek lambda (λ)
  inside a double circular seal. `viewBox 0 0 256 256`. Use for square /
  avatar / favicon contexts.
- **`assets/logion-wordmark.svg`** — the dark-background wordmark. `viewBox 0 0
  505 160`. The seal at left, "LOGION" set in the mono stack, and the italic
  Greek `λόγιον` to its right.
- **`assets/logion-wordmark-light.svg`** — the light-background wordmark. Same
  `viewBox 0 0 505 160`; swaps the seal to the light-theme accent `#8a6a2b`, the
  "LOGION" text to dark ink `#0c1e22`, and `λόγιον` to `#5b6f6b`.

The standalone `*.svg` wordmark/mark assets are for **external / off-site**
contexts (GitHub README, social, slide decks) where a fixed-color, theme-
agnostic file is needed. The landing page itself does **not** embed these
files: it composes its own brand lockup in `base.html` from an inline,
theme-adaptive mark (`currentColor`) plus the `ΛΟΓΙΟΝ` ornament and the
`logion.sh` latin label. See Wordmark treatment and the reconciliation note.

The canonical source for these three files is the repo-root `assets/` dir; the
landing app also serves byte-identical copies under
`packages/landing/landing/static/brand/` so `/design.txt` can hand agents raw,
fetchable SVG URLs (`https://logion.sh/static/brand/…`) rather than an HTML
repo page. A test keeps the served copies in sync with `assets/`.

The favicon is a separate asset:
`packages/landing/landing/static/favicon.svg` — `viewBox 0 0 64 64`, a rounded
`#0a0a0a` tile (`rx="13"`) with the seal + lambda rendered in the accent
`#c9a76a`.

### When to use each

- **Mark** (`logion-mark.svg`) — square, avatar, and favicon contexts where the
  wordmark would be illegible.
- **Wordmark** (`logion-wordmark.svg`) — on dark surfaces (the default theme).
- **Wordmark, light variant** (`logion-wordmark-light.svg`) — on light surfaces.
  It swaps the `λόγιον` and "LOGION" text to dark ink and the seal to the
  light-theme accent `#8a6a2b` so the mark stays legible against a light
  background. Never place the dark wordmark on a light background.

### Clear-space and minimum sizes

- **Clear-space:** keep clear space equal to the height of the seal's inner
  circle on all sides of the logo.
- **Mark minimum:** 24px. The favicon renders the seal at roughly `r=24` inside
  a 64px tile, which is the smallest size at which the double-circle + lambda
  stays readable.
- **Wordmark minimum:** 120px wide, so "LOGION" stays legible at its
  `font-size="31"` / `letter-spacing="15"` SVG metrics.

### What not to do

- Do not recolor the seal outside the bronze family (see Palette → Logo asset
  hexes).
- Do not set the wordmark on a busy photo or low-contrast texture.
- Do not stretch or distort — preserve the SVG `viewBox` aspect ratio.
- Do not place the dark wordmark on a light background; use
  `logion-wordmark-light.svg` instead.

## Palette

All tokens are CSS custom properties defined in
`packages/landing/landing/static/styles.css`.

### Dark theme (default)

Defined in `:root` (styles.css lines 6-28):

```text
--bg            #050608
--bg-soft       #0a0d12
--fg            #e9eef5
--fg-dim        #7d8794
--muted         #4a525e
--rule          #1b2129
--rule-strong   #2b333d
--accent        #c9a76a   /* aged-bronze (comment in CSS) */
--accent-bright #f5d68a
--bolt          #aed7ff
--focus         #aed7ff
```

### Light theme (prefers-color-scheme: light)

Defined in the `@media (prefers-color-scheme: light)` block (styles.css lines
30-49):

```text
--bg            #f5f2e9
--bg-soft       #ece8db
--fg            #15171a
--fg-dim        #4d5460
--accent        #8a6a2b
--accent-bright #5a4517
--bolt          #1f4a80
--focus         #1f4a80
```

`seo.theme_color` in `site.yaml` is `#0a0a0a` (the favicon tile color), used for
the browser chrome / PWA theme color.

### Logo asset hexes

The standalone SVG asset files bake their own fills (they do not read CSS
variables), but every fill is now drawn from the `--accent` family above:

```text
logion-mark.svg            seal + lambda fill  #c9a76a  (viewBox 0 0 256 256)
logion-wordmark.svg        seal + lambda       #c9a76a; "LOGION" text #ece6d8; "λόγιον" #9db0ae @ .72 opacity
logion-wordmark-light.svg  seal + lambda       #8a6a2b; "LOGION" text #0c1e22; "λόγιον" #5b6f6b
favicon.svg                rounded #0a0a0a tile, seal + lambda #c9a76a  (viewBox 0 0 64 64)
```

### Accent reconciliation note

The seal gold is unified onto the `--accent` token: the dark-context assets
(`logion-mark.svg`, `logion-wordmark.svg`, `favicon.svg`) bake `#c9a76a` and the
light-context `logion-wordmark-light.svg` bakes the light-theme `--accent`
`#8a6a2b`. There is no longer an orphan color outside the documented palette.

On the page, the inline header mark in
`packages/landing/landing/templates/base.html` uses `fill="currentColor"` and
inherits `--accent-bright` plus a `drop-shadow` glow — so it renders the
brighter `#f5d68a` (dark) / `#5a4517` (light). This is an intentional on-page
*treatment* driven by tokens, not a baked divergence: the structural logo color
is `--accent`, and `--accent-bright` is the highlight applied to the glowing
HUD mark and to link hovers.

## Typography

### Type stack

From styles.css (lines 23-25):

```text
--serif  "Libre Baskerville", "Times New Roman", Times, Georgia, serif
--mono   "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace
```

The stacks are **system-font-first**: if "JetBrains Mono" / "Libre Baskerville"
are installed locally they are used, otherwise the page falls back to platform
mono/serif fonts. There is **no external font fetch** — the landing serves no
Google Fonts `@import` and `base.html` carries no `fonts.googleapis.com` /
`fonts.gstatic.com` preconnect, in line with the no-external-deps contract.

### Wordmark treatment

"LOGION" is set in the mono stack, uppercase, with wide tracking — roughly
`0.18em` for the header brand and `letter-spacing="15"` in the SVG wordmark
(`font-size="31"`). It is paired with the italic Greek `λόγιον` set in the serif
stack (`font-size="34"`, `#9db0ae` at `.72` opacity on the dark variant).

### The ΛΟΓΙΟΝ ornament

The all-caps Greek `ΛΟΓΙΟΝ` is used as an ornament in the hero (`hero.greek` in
`site.yaml`) and in the header brand (`.site-brand .greek` in `base.html`,
colored `--accent-bright`, `letter-spacing: 0.34em`). It is a decorative
spelling of the name in Greek capitals, distinct from the italic lowercase
`λόγιον` in the wordmark.

## Voice

Brand voice is **network over money**. Lead copy with the collective network and
the shared capability it creates; money is a consequence, not the hook. The
canonical phrasing lives in `site.yaml` `hero.motto` ("Smarter, together.") and
carries through the section copy and FAQ.

## Motif

Greek + futurism. The visual language pairs Greek thinkers, pillars, and columns
with a terminal / ASCII aesthetic:

- Greek + futurism; Greek thinkers, pillars, columns.
- Falling letters / matrix-rain — the `drawScene` effect in
  `packages/landing/landing/static/app.js`.
- CRT / static effect and a terminal + ASCII aesthetic throughout.
- The ASCII Zeus hero (`packages/landing/landing/static/ascii/zeus.txt`, driven
  by `static/ascii/hero_frames.js`).
- Lightning bolts, expressed through the `--bolt` color token.

## Machine-readable surface (design.txt)

[`logion.sh/design.txt`](https://logion.sh/design.txt) mirrors this guide for
agents and humans in a compact, parseable plain-text form. It is generated from
the `design:` block in `site.yaml` so it cannot drift from the page, and is
discoverable via `sitemap.xml` and `/llms.txt`. Its logo URLs resolve to raw
SVGs served by `logion.sh` (`/static/brand/…`, `/static/favicon.svg`), so a tool
can fetch the bytes directly without parsing an HTML page.

## Related docs

- [`/design.txt`](https://logion.sh/design.txt) — machine-readable mirror of
  this guide.
- [`README.md`](../README.md) — what Logion is and how the pieces fit.
- [`docs/marketplace/concepts.md`](marketplace/concepts.md) — core marketplace
  concepts.
