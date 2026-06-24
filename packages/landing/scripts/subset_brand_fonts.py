# SPDX-License-Identifier: MIT
"""Reproducibly build the self-hosted brand-font woff2 subsets.

The landing page renders the brand typefaces with **no external font fetch**
(no Google Fonts stylesheet import, no ``fonts.googleapis.com`` /
``fonts.gstatic.com``). To do that it self-hosts subset woff2 files under
``packages/landing/landing/static/fonts/`` loaded via ``@font-face`` in
``styles.css`` (``local()``-first, ``font-display: swap``, behind the
``--mono`` / ``--serif`` system fallback stacks).

This script fetches the official OFL-1.1 sources, instances the variable
Libre Baskerville to ``wght=400``, subsets each face to only the glyphs the
page uses, and writes the woff2 files plus the license texts. It is the
canonical, auditable record of how those binaries were produced.

Sources (both SIL Open Font License 1.1):
  - JetBrains Mono v2.304 — github.com/JetBrains/JetBrainsMono
  - Libre Baskerville     — github.com/google/fonts (ofl/librebaskerville)

Run:
  uv run --with "fonttools[woff]" \
    python packages/landing/scripts/subset_brand_fonts.py
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OUT = Path(__file__).resolve().parents[1] / "landing" / "static" / "fonts"

JBM_ZIP = (
    "https://github.com/JetBrains/JetBrainsMono/releases/download/"
    "v2.304/JetBrainsMono-2.304.zip"
)
LB_BASE = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/librebaskerville/"
)

# Mono needs Latin-1 + General Punctuation + Greek (the ΛΟΓΙΟΝ ornament) +
# block-element / geometric / check glyphs (ASCII art and the █ cursor).
MONO = (
    "U+0000-00FF,U+0131,U+0152-0153,U+2000-206F,U+2074,U+20AC,U+2122,"
    "U+2190-2193,U+2212,U+2215,U+25A0-25FF,U+2580-259F,U+2660-266F,"
    "U+2713-2714,U+0370-03FF,U+2026"
)
# Bold is display-only (hero heading): Latin + Greek + punctuation.
BOLD = "U+0000-00FF,U+0131,U+0152-0153,U+2000-206F,U+0370-03FF,U+2026"
# Serif is Latin-only (English titles + motto).
SERIF = (
    "U+0000-00FF,U+0131,U+0152-0153,U+2000-206F,U+2074,U+20AC,U+2122,U+2026"
)


def _codepoints(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.replace("U+", "")
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a, 16), int(b, 16) + 1))
        else:
            out.append(int(part, 16))
    return out


def subset(src: bytes | Path, dest: Path, unicodes: str) -> None:
    font = TTFont(io.BytesIO(src) if isinstance(src, bytes) else str(src))
    opts = Options()
    opts.flavor = "woff2"
    opts.desubroutinize = True
    # No liga/calt: code ligatures would alter how the install command renders
    # and they balloon the subset with contextual-alternate glyphs.
    opts.layout_features = ["kern", "ccmp", "locl", "mark", "mkmk"]
    opts.name_IDs = ["*"]
    ss = Subsetter(options=opts)
    ss.populate(unicodes=_codepoints(unicodes))
    ss.subset(font)
    font.save(str(dest))
    print(f"{dest.name:42s} {dest.stat().st_size:>7d} bytes")


def instanced(src: bytes, wght: int) -> bytes:
    font = TTFont(io.BytesIO(src))
    instantiateVariableFont(font, {"wght": wght}, inplace=True)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    print("Fetching JetBrains Mono…")
    jbm = zipfile.ZipFile(io.BytesIO(fetch(JBM_ZIP)))
    jbm_reg = jbm.read("fonts/ttf/JetBrainsMono-Regular.ttf")
    jbm_bold = jbm.read("fonts/ttf/JetBrainsMono-Bold.ttf")
    (OUT / "OFL-JetBrainsMono.txt").write_bytes(jbm.read("OFL.txt"))

    print("Fetching Libre Baskerville…")
    lb_reg = fetch(LB_BASE + "LibreBaskerville%5Bwght%5D.ttf")
    lb_ital = fetch(LB_BASE + "LibreBaskerville-Italic%5Bwght%5D.ttf")
    (OUT / "OFL-LibreBaskerville.txt").write_bytes(fetch(LB_BASE + "OFL.txt"))

    print("Subsetting…")
    subset(jbm_reg, OUT / "JetBrainsMono-Regular.woff2", MONO)
    subset(jbm_bold, OUT / "JetBrainsMono-Bold.woff2", BOLD)
    subset(
        instanced(lb_reg, 400),
        OUT / "LibreBaskerville-Regular.woff2",
        SERIF,
    )
    subset(
        instanced(lb_ital, 400),
        OUT / "LibreBaskerville-Italic.woff2",
        SERIF,
    )
    print("Done.")


if __name__ == "__main__":
    main()
