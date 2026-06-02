# SPDX-License-Identifier: MIT
"""Verify that the release manifest matches published packages.

Reads ``releases/manifest-{channel}.json``, then checks:
- PyPI: every ``cli``/``client`` package version exists and is not
  yanked.
- npm: the ``@logion/cli`` version exists on the npm registry.
- GitHub Release: the companion bundle asset is reachable.

With ``--deep``, every ``sha256`` field is re-downloaded and verified.

Exit 0 on success, exit 1 on any mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GITHUB_REPO = "nicolasmelo1/logion"


def _pypi_versions(package: str) -> dict[str, bool]:
    """Return {version: yanked} from the PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package}/json"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read())
    releases: dict[str, list[dict]] = data.get("releases", {})
    result: dict[str, bool] = {}
    for version, files in releases.items():
        yanked = any(f.get("yanked", False) for f in files)
        result[version] = yanked
    return result


def _npm_versions(package: str) -> list[str]:
    """Return available versions from the npm registry."""
    url = f"https://registry.npmjs.org/{package}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read())
    return list(data.get("versions", {}).keys())


def _github_release_asset_url(tag: str, filename: str) -> str:
    """Build the download URL for a release asset."""
    base = f"https://github.com/{GITHUB_REPO}/releases/download"
    return f"{base}/{tag}/{filename}"


def _check_url_reachable(url: str) -> bool:
    """HEAD the URL and return True if 200 with content."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        return False


def _download_sha256(url: str) -> str:
    """Download a file and return its sha256 hex digest."""
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read()
    return hashlib.sha256(data).hexdigest()


def _check_pypi(
    pypi_name: str,
    version: str,
    errors: list[str],
) -> None:
    """Assert a version exists on PyPI and is not yanked."""
    try:
        versions = _pypi_versions(pypi_name)
    except Exception as exc:
        errors.append(f"ERROR: PyPI check for {pypi_name}: {exc}")
        return
    if version not in versions:
        errors.append(f"FAIL: {pypi_name} {version} not on PyPI")
    elif versions[version]:
        errors.append(f"FAIL: {pypi_name} {version} yanked on PyPI")
    else:
        print(f"OK: {pypi_name} {version} on PyPI")


def _check_npm(
    npm_name: str,
    version: str,
    errors: list[str],
) -> None:
    """Assert a version exists on the npm registry."""
    try:
        versions = _npm_versions(npm_name)
    except Exception as exc:
        errors.append(f"ERROR: npm check for {npm_name}: {exc}")
        return
    if version not in versions:
        errors.append(f"FAIL: {npm_name} {version} not on npm")
    else:
        print(f"OK: {npm_name} {version} on npm")


def _check_companion(
    tag: str,
    version: str,
    errors: list[str],
) -> None:
    """Assert the companion bundle asset exists on GitHub Releases."""
    filename = f"logion-marketplace-companion-{version}.tar.gz"
    url = _github_release_asset_url(tag, filename)
    if not _check_url_reachable(url):
        errors.append(f"FAIL: companion bundle not reachable at {url}")
    else:
        print(f"OK: companion bundle reachable at {url}")


def _check_deep_sha256(
    name: str,
    tag: str,
    asset_key: str,
    asset_info: dict,
    errors: list[str],
) -> None:
    """Re-download an asset and verify its sha256."""
    asset_url = asset_info.get("url", "")
    expected_sha = asset_info.get("sha256", "")
    if asset_url.startswith("release://"):
        filename = asset_url[len("release://") :]
        dl_url = _github_release_asset_url(tag, filename)
    else:
        dl_url = asset_url
    try:
        actual_sha = _download_sha256(dl_url)
    except Exception as exc:
        errors.append(f"ERROR: sha256 for {name} {asset_key}: {exc}")
        return
    if actual_sha != expected_sha:
        errors.append(
            f"FAIL: {name} {asset_key} sha256 mismatch "
            f"expected {expected_sha[:12]}… got {actual_sha[:12]}…"
        )
    else:
        print(f"OK: {name} {asset_key} sha256 verified")


def check_conformance(channel: str, deep: bool) -> bool:
    """Return True if all checks pass."""
    manifest_path = REPO_ROOT / "releases" / f"manifest-{channel}.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} does not exist")
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packages = manifest.get("packages", {})
    errors: list[str] = []

    for name, entry in packages.items():
        version = entry["version"]
        tag = entry["tag"]

        pypi_name = entry.get("pypi_name")
        if pypi_name:
            _check_pypi(pypi_name, version, errors)

        npm_name = entry.get("npm_name")
        if npm_name:
            _check_npm(npm_name, version, errors)

        if name == "logion-companion":
            _check_companion(tag, version, errors)

        if deep:
            for asset_key in ("wheel", "sdist", "skill_md", "bundle"):
                asset_info = entry.get(asset_key)
                if asset_info and isinstance(asset_info, dict):
                    _check_deep_sha256(
                        name,
                        tag,
                        asset_key,
                        asset_info,
                        errors,
                    )

    for err in errors:
        print(err, file=sys.stderr)
    return len(errors) == 0


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=("Verify release manifest matches published packages"),
    )
    parser.add_argument(
        "--channel",
        choices=["stable", "latest"],
        default="stable",
        help="Manifest channel to verify (default: stable)",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Re-download assets and verify sha256 checksums",
    )
    args = parser.parse_args()

    if check_conformance(args.channel, args.deep):
        print("Conformance check passed.")
        sys.exit(0)
    else:
        print("Conformance check FAILED.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
