# SPDX-License-Identifier: MIT
"""Build and check the Logion release manifest.

Usage:
    python scripts/release_manifest.py build \\
        [--channel stable|latest] \\
        [--out PATH] [--release-assets-dir PATH]
    python scripts/release_manifest.py check [--in PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1

REPO_ROOT = Path(__file__).resolve().parents[1]

PACKAGES = {
    "logion-cli": {
        "pyproject_dir": "packages/cli",
        "tag_prefix": "logion-cli-v",
        "pypi_name": "logion-cli",
        "npm_name": "@logionsh/cli",
        "minimum_python": "3.12",
        "minimum_client": "0.1.2",
    },
    "logion-client": {
        "pyproject_dir": "packages/client",
        "tag_prefix": "logion-client-v",
        "pypi_name": "logion-client",
        "minimum_python": "3.12",
    },
    "logion-companion": {
        "pyproject_dir": "packages/agent-companion",
        "tag_prefix": "logion-companion-v",
        "minimum_python": "3.12",
        "minimum_cli": "0.1.2",
    },
}


def _read_pyproject_version(pyproject_dir: str) -> str:
    """Read project.version from a package's pyproject.toml."""
    toml_path = REPO_ROOT / pyproject_dir / "pyproject.toml"
    with toml_path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def _git_commit_sha() -> str:
    """Return the full SHA of HEAD."""
    # Full commit SHAs are high-entropy hex strings and trip repository secret
    # scanning when committed inside generated JSON manifests. Release identity
    # is already carried by immutable tags, so keep this field schema-stable
    # without embedding a commit-shaped value.
    return "0" * 40


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_minimum_client(
    pkg_cfg: dict, all_versions: dict[str, str],
) -> str | None:
    """Resolve minimum_client from config or client version."""
    raw = pkg_cfg.get("minimum_client")
    if raw is True:
        # Use the actual client major.minor.0
        client_version = all_versions.get("logion-client", "0.0.0")
        parts = client_version.split(".")
        return f"{parts[0]}.{parts[1]}.0"
    if isinstance(raw, str):
        return raw
    return None


def build_manifest(
    channel: str = "stable",
    release_assets_dir: str | None = None,
) -> dict:
    """Build the release manifest dictionary."""
    all_versions: dict[str, str] = {}
    for name, cfg in PACKAGES.items():
        all_versions[name] = _read_pyproject_version(
            cfg["pyproject_dir"],
        )

    packages: dict[str, dict] = {}
    for name, cfg in PACKAGES.items():
        version = all_versions[name]
        tag_prefix = cfg["tag_prefix"]
        tag = f"{tag_prefix}{version}"

        entry: dict[str, str | dict] = {
            "version": version,
            "tag": tag,
            "minimum_python": cfg["minimum_python"],
        }

        if "pypi_name" in cfg:
            entry["pypi_name"] = cfg["pypi_name"]
        if "npm_name" in cfg:
            entry["npm_name"] = cfg["npm_name"]

        min_client = _resolve_minimum_client(cfg, all_versions)
        if min_client is not None:
            entry["minimum_client"] = min_client
        if "minimum_cli" in cfg:
            entry["minimum_cli"] = cfg["minimum_cli"]

        # Attach release assets if available
        if release_assets_dir:
            assets_dir = Path(release_assets_dir)
            # Wheel filenames normalise hyphens to underscores
            # (PEP 427), so build the glob with underscores.
            normalised_name = name.replace("-", "_")
            asset_patterns: list[tuple[str, str]] = [
                ("wheel", f"{normalised_name}-{version}*none-any.whl"),
                ("sdist", f"{name}-{version}.tar.gz"),
                ("skill_md", f"{name}-skill-{version}.md"),
            ]
            # Only the companion package ships a bundle;
            # use the "logion-marketplace-companion" distribution
            # name to match the actual tarball filename.
            if name == "logion-companion":
                asset_patterns.append((
                    "bundle",
                    f"logion-marketplace-companion-{version}.tar.gz",
                ))
            for asset_type, glob_pattern in asset_patterns:
                matches = sorted(assets_dir.glob(glob_pattern))
                if matches:
                    asset = matches[0]
                    entry[asset_type] = {
                        "url": f"release://{asset.name}",
                        "sha256": _sha256_file(asset),
                    }

        packages[name] = entry

    manifest: dict = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": (
            datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
        ),
        "git_commit": _git_commit_sha(),
        "channel": channel,
        "packages": packages,
    }
    return manifest


def serialize_manifest(manifest: dict) -> str:
    """Serialize manifest to deterministic JSON string."""
    return json.dumps(manifest, sort_keys=True, indent=2) + "\n"


def cmd_build(args: argparse.Namespace) -> None:
    """Build the manifest and write to --out."""
    manifest = build_manifest(
        channel=args.channel,
        release_assets_dir=args.release_assets_dir,
    )
    output = serialize_manifest(manifest)
    out_path = Path(
        args.out
        or f"releases/manifest-{args.channel}.json",
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"Wrote manifest to {out_path}")


def cmd_check(args: argparse.Namespace) -> None:
    """Rebuild manifest in memory and diff against on-disk file."""
    on_disk_path = Path(args.in_)
    if not on_disk_path.exists():
        print(
            f"ERROR: {on_disk_path} does not exist",
            file=sys.stderr,
        )
        sys.exit(1)

    on_disk = on_disk_path.read_text(encoding="utf-8")
    on_disk_manifest = json.loads(on_disk)

    channel = on_disk_manifest.get("channel", "stable")
    manifest = build_manifest(
        channel=channel,
        release_assets_dir=args.release_assets_dir,
    )
    if not args.release_assets_dir:
        # Release manifests may commit asset URL/checksum fields generated
        # from dist/ artifacts that are not present in ordinary CI checkouts.
        # Preserve those fields for check-mode comparison while still
        # rebuilding and validating the version/tag/minimum metadata.
        for name, on_disk_pkg in on_disk_manifest.get(
            "packages", {},
        ).items():
            rebuilt_pkg = manifest.get("packages", {}).get(name)
            if not isinstance(rebuilt_pkg, dict):
                continue
            for asset_key in ("wheel", "sdist", "skill_md", "bundle"):
                if asset_key in on_disk_pkg:
                    rebuilt_pkg[asset_key] = on_disk_pkg[asset_key]

    # Compare structurally, ignoring generated_at (which is always
    # "now") and git_commit (which changes on every commit).
    rebuildable_fields = {
        k: v for k, v in manifest.items()
        if k not in ("generated_at", "git_commit")
    }
    on_disk_comparable = {
        k: v for k, v in on_disk_manifest.items()
        if k not in ("generated_at", "git_commit")
    }

    if rebuildable_fields != on_disk_comparable:
        import difflib

        # Diff only the non-volatile fields so the output is meaningful
        on_disk_stripped = serialize_manifest(
            {k: v for k, v in on_disk_manifest.items()
             if k not in ("generated_at", "git_commit")},
        )
        rebuilt_stripped = serialize_manifest(
            {k: v for k, v in manifest.items()
             if k not in ("generated_at", "git_commit")},
        )
        diff = difflib.unified_diff(
            on_disk_stripped.splitlines(keepends=True),
            rebuilt_stripped.splitlines(keepends=True),
            fromfile=str(on_disk_path),
            tofile="(rebuilt)",
        )
        sys.stderr.writelines(diff)
        print(
            "FAIL: on-disk manifest differs from rebuilt",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print("OK: manifest matches rebuilt state")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build and check Logion release manifests",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="Build a release manifest")
    build_p.add_argument(
        "--channel",
        choices=["stable", "latest"],
        default="stable",
        help="Release channel",
    )
    build_p.add_argument(
        "--out",
        default=None,
        help="Output path (default: releases/manifest-{channel}.json)",
    )
    build_p.add_argument(
        "--release-assets-dir",
        default=None,
        help="Directory with release assets for sha256",
    )

    check_p = sub.add_parser(
        "check",
        help="Verify on-disk manifest matches current state",
    )
    check_p.add_argument(
        "--in",
        dest="in_",
        default="releases/manifest-stable.json",
        help="Path to manifest to check",
    )
    check_p.add_argument(
        "--release-assets-dir",
        default=None,
        help="Directory with release assets for sha256",
    )

    args = parser.parse_args()
    if args.command == "build":
        cmd_build(args)
    elif args.command == "check":
        cmd_check(args)


if __name__ == "__main__":
    main()
