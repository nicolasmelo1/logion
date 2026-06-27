# SPDX-License-Identifier: MIT
"""Generate the Open Graph / social-card image (``static/og-image.png``).

The card mirrors the live site's **dark theme**: a near-black background
(``#050608``), the gold gradient lambda seal + ``LOGION`` wordmark, the
``Smarter, together.`` motto in Baskerville italic, a mono description, and
the install command in a bordered pill — over a faint matrix-rain glyph
texture (the brand motif). It is the canonical, auditable record of how the
committed ``og-image.png`` was produced.

Design tokens are taken from the ``design.palette.dark`` block in
``content/site.yaml`` so the card cannot silently drift from the brand:
``bg #050608``, ``fg #e9eef5``, ``accent #c9a76a``, ``accent_bright #f5d68a``.
The lambda path is copied verbatim from ``static/brand/logion-mark.svg``.

Fonts: rendered with cairosvg using the closest system matches to the brand
stacks — **Baskerville** for the serif motto (the brand serif is Libre
Baskerville; Baskerville is the nearest macOS system face) and **Menlo** for
the mono wordmark/body/command (Menlo is the brand mono fallback). cairosvg
cannot decode the self-hosted woff2 (no brotli), so the committed PNG is the
canonical artifact; regenerate on a host that has Baskerville + Menlo.

Run:
  uv run --with cairosvg \
    python packages/landing/scripts/gen_og_image.py
"""

from __future__ import annotations

from pathlib import Path

import cairosvg

W, H = 1200, 630
BG = "#050608"
FG = "#e9eef5"
ACCENT = "#c9a76a"
BRIGHT = "#f5d68a"

OUT = (
    Path(__file__).resolve().parents[1] / "landing" / "static" / "og-image.png"
)

# Brand lambda seal, copied verbatim from static/brand/logion-mark.svg
# (256x256 viewBox); fills swapped to the gold gradient defined below.
_LAMBDA = (
    '<circle cx="128" cy="128" r="90" fill="none" stroke="url(#gold)" '
    'stroke-width="22"/>'
    '<circle cx="128" cy="128" r="72" fill="none" stroke="url(#gold)" '
    'stroke-width="3"/>'
    '<path transform="translate(128 128) scale(0.0805 -0.0805) '
    'translate(-514 -702.5)" fill="url(#gold)" '
    'd="M967 288H1003Q1003 130 951.5 58.0Q900 -14 823 -14Q760 -14 702.0 33.5'
    "Q644 81 598 288L512 676L214 0H25L453 922Q419 1101 371.0 1187.0"
    "Q323 1273 252 1273Q195 1273 152.5 1229.5Q110 1186 105 1095H69"
    "Q72 1242 128.0 1330.5Q184 1419 268 1419Q322 1419 370.5 1374.5"
    "Q419 1330 454.5 1222.5Q490 1115 565 777L636 460Q679 263 726.5 196.5"
    'Q774 130 840 130Q952 130 967 288Z"/>'
)


def _rain() -> str:
    """Faint matrix-rain glyph columns (brand motif), low opacity."""
    glyphs = "λΛΟΓΙΟΝ01{}=π√+≡#//"
    cells: list[str] = []
    for i in range(46):
        x = 70 + i * 24
        seed = (i * 37) % len(glyphs)
        for j in range(20):
            y = 40 + j * 30 + ((i * 53) % 30)
            if y > H - 20:
                continue
            ch = glyphs[(seed + j * 3) % len(glyphs)]
            op = 0.05 if (i + j) % 5 else 0.10
            cells.append(
                f'<text x="{x}" y="{y}" font-family="Menlo,monospace" '
                f'font-size="15" fill="{ACCENT}" fill-opacity="{op}">'
                f"{ch}</text>"
            )
    return "".join(cells)


def build_svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" \
height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{BRIGHT}"/>
      <stop offset="0.55" stop-color="{ACCENT}"/>
      <stop offset="1" stop-color="#8a6a2b"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.28" cy="0.30" r="0.9">
      <stop offset="0" stop-color="#1a1407" stop-opacity="0.9"/>
      <stop offset="0.55" stop-color="{BG}" stop-opacity="0.0"/>
    </radialGradient>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}"/>
  <g>{_rain()}</g>
  <rect width="{W}" height="{H}" fill="url(#glow)"/>

  <g stroke="{ACCENT}" stroke-opacity="0.55" stroke-width="2" fill="none">
    <path d="M48 78 L48 48 L78 48"/>
    <path d="M{W - 78} 48 L{W - 48} 48 L{W - 48} 78"/>
    <path d="M48 {H - 78} L48 {H - 48} L78 {H - 48}"/>
    <path d="M{W - 78} {H - 48} L{W - 48} {H - 48} L{W - 48} {H - 78}"/>
  </g>

  <text x="92" y="108" font-family="Menlo,monospace" font-size="22" \
letter-spacing="6" fill="{ACCENT}" fill-opacity="0.85">\
&#9679; &#923;&#927;&#915;&#921;&#927;&#925; // AGENT-NATIVE MARKETPLACE</text>

  <g transform="translate(92 150) scale(0.62)">{_LAMBDA}</g>

  <text x="285" y="248" font-family="Menlo,monospace" font-weight="bold" \
font-size="118" letter-spacing="6" fill="url(#gold)">LOGION</text>

  <text x="96" y="338" font-family="Baskerville,Georgia,serif" \
font-style="italic" font-size="50" fill="{BRIGHT}">Smarter, together.</text>

  <text x="96" y="408" font-family="Menlo,monospace" font-size="31" \
fill="{FG}">An agent-native marketplace for operational</text>
  <text x="96" y="450" font-family="Menlo,monospace" font-size="31" \
fill="{FG}">knowledge &#8212; reviewed, versioned course bundles.</text>

  <rect x="92" y="498" width="894" height="74" rx="10" fill="#0c0e12" \
stroke="{ACCENT}" stroke-opacity="0.7" stroke-width="2"/>
  <text x="118" y="544" font-family="Menlo,monospace" font-size="26" \
fill="{ACCENT}" fill-opacity="0.7">&#9656;</text>
  <text x="150" y="544" font-family="Menlo,monospace" font-size="26" \
fill="{BRIGHT}">curl -fsSL https://logion.sh/install.sh | sh</text>

  <text x="{W - 60}" y="556" text-anchor="end" font-family="Menlo,monospace" \
font-size="24" letter-spacing="3" fill="{ACCENT}">logion.sh</text>
</svg>"""


def main() -> None:
    cairosvg.svg2png(
        bytestring=build_svg().encode("utf-8"),
        write_to=str(OUT),
        output_width=W,
        output_height=H,
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
