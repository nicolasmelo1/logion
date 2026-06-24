# SPDX-License-Identifier: MIT
"""Build the self-hosted brand-font woff2 subsets from pinned sources.

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

Sources (both SIL Open Font License 1.1) are pinned to immutable revisions
and verified by sha256 on fetch, so the *inputs* cannot drift or be tampered
with:
  - JetBrains Mono v2.304 (release tag) — github.com/JetBrains/JetBrainsMono
  - Libre Baskerville at google/fonts commit ``GF_REV`` below

The woff2 output is *not* guaranteed bit-identical on regeneration:
fontTools' subsetter and variable-font instancer serialize some tables in a
run-dependent order. The committed woff2 are therefore the canonical artifact;
their sha256 are recorded in ``static/fonts/README.md`` for verification.

Run:
  uv run --with "fonttools[woff]" \
    python packages/landing/scripts/subset_brand_fonts.py
"""

from __future__ import annotations

import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OUT = Path(__file__).resolve().parents[1] / "landing" / "static" / "fonts"

# Pin head.created/modified (OpenType epoch = seconds since 1904-01-01) so the
# fonts are not stamped with the build time — removes one source of build
# nondeterminism. 3786912000 == 2024-01-01T00:00:00Z.
EPOCH = 3786912000

JBM_ZIP = (
    "https://github.com/JetBrains/JetBrainsMono/releases/download/"
    "v2.304/JetBrainsMono-2.304.zip"
)
# Pin Libre Baskerville to an immutable google/fonts commit (not `main`) so
# the upstream bytes — and therefore the generated woff2 — cannot drift.
# (Public commit SHA / checksums below, not secrets.)
GF_REV = "b3d4b3ba7c4d54f15ed2be72d7f58b9097c3b252"  # pragma: allowlist secret
LB_BASE = (
    "https://raw.githubusercontent.com/google/fonts/"
    f"{GF_REV}/ofl/librebaskerville/"
)

# sha256 of the pinned upstream sources, verified on fetch. A silent upstream
# change (or a tampered mirror) fails the build loudly rather than shipping
# different font bytes.
SHA256 = {
    "jbm_zip": "6f6376c6ed2960ea8a963cd7387ec9d76e3f629125bc33d1fdcd7eb7012f7bbf",  # pragma: allowlist secret
    "lb_regular": "05a95421961341c5b2556285e8415df9db27dab4f4abe22b446b3c6a8b916c5d",  # pragma: allowlist secret
    "lb_italic": "223959683dc73ec4437bd61fabaa4b3f22209e22855ffd3aee36ba61a5116e97",  # pragma: allowlist secret
}

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
    if "head" in font:
        font["head"].created = EPOCH
        font["head"].modified = EPOCH
    font.save(str(dest))
    print(f"{dest.name:42s} {dest.stat().st_size:>7d} bytes")


def instanced(src: bytes, wght: int) -> bytes:
    font = TTFont(io.BytesIO(src))
    instantiateVariableFont(font, {"wght": wght}, inplace=True)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def fetch(url: str, expected_sha256: str | None = None) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read()
    if expected_sha256 is not None:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            raise SystemExit(
                f"checksum mismatch for {url}\n"
                f"  expected {expected_sha256}\n"
                f"  got      {actual}"
            )
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    print("Fetching JetBrains Mono…")
    with zipfile.ZipFile(io.BytesIO(fetch(JBM_ZIP, SHA256["jbm_zip"]))) as jbm:
        jbm_reg = jbm.read("fonts/ttf/JetBrainsMono-Regular.ttf")
        jbm_bold = jbm.read("fonts/ttf/JetBrainsMono-Bold.ttf")
        (OUT / "OFL-JetBrainsMono.txt").write_bytes(jbm.read("OFL.txt"))

    print("Fetching Libre Baskerville…")
    lb_reg = fetch(
        LB_BASE + "LibreBaskerville%5Bwght%5D.ttf", SHA256["lb_regular"]
    )
    lb_ital = fetch(
        LB_BASE + "LibreBaskerville-Italic%5Bwght%5D.ttf", SHA256["lb_italic"]
    )
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
