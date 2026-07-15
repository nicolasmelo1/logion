"""GitHub source: repo metadata, license, HEAD sha, tree -> skillmap.infer().

Fetches repo metadata, license info, the latest commit SHA, and the
git/trees payload, then calls ``logion_skillmap.infer()`` with a
blob-fetcher backed by the GitHub contents API.  Inference is cached
per ``(owner, repo, sha)`` — a repo listed on four hubs is inferred once.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass, field

from logion_skillmap import (
    InferenceResult,
    InferredComponent,
    TreeEntry,
    infer,
)

from .canonical import CanonicalSkillId
from .transport import Transport


@dataclass
class RepoMetadata:
    """GitHub repository metadata relevant to indexing."""

    owner: str
    repo: str
    head_sha: str = ""
    license_spdx: str | None = None
    default_branch: str = "main"
    size_bytes: int = 0


@dataclass
class InferredSkill:
    """One canonical skill from a repo's inference result."""

    canonical: CanonicalSkillId
    name: str
    root: str
    entrypoint: str
    summary: str
    content_sha256: str
    inferred_map: dict
    map_flags: tuple[str, ...]


@dataclass
class GithubSource:
    """Fetches and caches GitHub repo data for skill inference.

    Inference is cached per ``(owner, repo, sha)``: a repo listed on
    multiple hubs triggers a single ``infer()`` call.
    """

    transport: Transport
    _cache: dict[tuple[str, str, str], InferenceResult] = field(
        default_factory=dict
    )

    def fetch_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
        """Fetch repo metadata from the GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        resp = self.transport.get(url)
        if resp.status != 200:
            return RepoMetadata(owner=owner, repo=repo)
        data = resp.json()
        if not isinstance(data, dict):
            return RepoMetadata(owner=owner, repo=repo)
        license_info = data.get("license") or {}
        license_spdx = None
        if isinstance(license_info, dict):
            license_spdx = license_info.get("spdx_id") or None
        return RepoMetadata(
            owner=owner,
            repo=repo,
            default_branch=data.get("default_branch", "main") or "main",
            size_bytes=data.get("size", 0) or 0,
            license_spdx=license_spdx,
        )

    def fetch_head_sha(self, owner: str, repo: str) -> str:
        """Fetch the HEAD SHA of the default branch."""
        meta = self.fetch_repo_metadata(owner, repo)
        branch = meta.default_branch
        url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}"
        resp = self.transport.get(url)
        if resp.status != 200:
            return ""
        data = resp.json()
        if not isinstance(data, dict):
            return ""
        commit = data.get("commit") or {}
        return commit.get("sha", "") if isinstance(commit, dict) else ""

    def fetch_tree(self, owner: str, repo: str, sha: str) -> list[TreeEntry]:
        """Fetch the recursive git/trees payload."""
        url = (
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/git/trees/{sha}?recursive=1"
        )
        resp = self.transport.get(url)
        if resp.status != 200:
            return []
        data = resp.json()
        if not isinstance(data, dict):
            return []
        tree_raw = data.get("tree") or []
        if not isinstance(tree_raw, list):
            return []
        entries: list[TreeEntry] = []
        for item in tree_raw:
            if not isinstance(item, dict):
                continue
            entries.append(
                TreeEntry(
                    path=item.get("path", ""),
                    type=item.get("type", "blob"),
                    size=item.get("size"),
                )
            )
        return entries

    def _make_blob_fetcher(
        self, owner: str, repo: str, sha: str
    ) -> Callable[[str], bytes]:
        """Create a blob-fetcher backed by the GitHub contents API."""

        def fetch_blob(path: str) -> bytes:
            url = (
                f"https://api.github.com/repos/{owner}/{repo}"
                f"/contents/{path}?ref={sha}"
            )
            resp = self.transport.get(url)
            if resp.status != 200:
                return b""
            data = resp.json()
            if not isinstance(data, dict):
                return b""
            content = data.get("content", "")
            encoding = data.get("encoding", "base64")
            if encoding == "base64" and content:
                return base64.b64decode(content)
            if isinstance(content, str):
                return content.encode("utf-8")
            return b""

        return fetch_blob

    def infer_skills(
        self,
        owner: str,
        repo: str,
        sha: str | None = None,
        subpath: str = "",
    ) -> tuple[InferenceResult | None, list[InferredSkill]]:
        """Run skillmap inference on a repo, cached per sha.

        When ``subpath`` is given, filter the inference result to
        components under that subpath rather than running a scoped scan.

        Returns ``(InferenceResult | None, list[InferredSkill])``.
        """
        if not sha:
            sha = self.fetch_head_sha(owner, repo)
        if not sha:
            return None, []

        cache_key = (owner.lower(), repo.lower(), sha)
        if cache_key not in self._cache:
            tree = self.fetch_tree(owner, repo, sha)
            if not tree:
                return None, []
            blob_fetcher = self._make_blob_fetcher(owner, repo, sha)
            self._cache[cache_key] = infer(tree, blob_fetcher)

        result = self._cache[cache_key]

        # Build per-component inferred skills, filtered by subpath.
        skills: list[InferredSkill] = []
        for comp in result.components:
            if subpath and not comp.root.startswith(
                subpath.strip("/").lower()
            ):
                continue

            canonical = CanonicalSkillId(
                owner=owner,
                repo=repo,
                subpath=comp.root,
            )

            # Build the inferred_map fragment (15.3 schema restricted
            # to this component).
            inferred_map = _build_component_fragment(result, comp)
            map_flags = tuple(flag.code for flag in result.needs_review)

            skills.append(
                InferredSkill(
                    canonical=canonical,
                    name=comp.name,
                    root=comp.root,
                    entrypoint=comp.entrypoint,
                    summary=comp.summary,
                    content_sha256=comp.content_sha256,
                    inferred_map=inferred_map,
                    map_flags=map_flags,
                )
            )

        return result, skills

    def fetch_license(self, owner: str, repo: str) -> str | None:
        """Fetch the SPDX license identifier for a repo."""
        meta = self.fetch_repo_metadata(owner, repo)
        return meta.license_spdx


def _build_component_fragment(
    result: InferenceResult,
    comp: InferredComponent,
) -> dict:
    """Build the per-component inferred_map fragment.

    Serializes the inference result as the 15.3 schema restricted to a
    single component: ``version``, ``package.slug`` from the component
    name, single ``components.capabilities`` entry, and
    ``runtime.include`` = the component subtree.
    """
    pm = result.package_map
    include_pattern = f"{comp.root}/**" if comp.root else "**"

    return {
        "version": pm.version,
        "package": {"slug": comp.name},
        "components": {
            "capabilities": {
                comp.name: {
                    "entrypoint": comp.entrypoint,
                },
            },
            "runtime": {
                "include": [include_pattern],
                "entrypoint": comp.entrypoint,
            },
        },
    }


def is_permissive_license(license_spdx: str | None) -> bool:
    """Return True for permissive licenses (MIT, Apache-2.0, BSD, etc.)."""
    if not license_spdx:
        return False
    permissive = {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "0BSD",
        "Unlicense",
        "MPL-2.0",
    }
    return license_spdx in permissive


BUNDLE_SIZE_CAP_BYTES = 25 * 1024 * 1024  # 25 MB
