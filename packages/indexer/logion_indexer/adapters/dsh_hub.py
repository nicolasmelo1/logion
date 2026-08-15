"""Discovery adapter for Git-hosted dsh profile bundles."""

from __future__ import annotations

import json
from collections.abc import Iterable

from ..canonical import CanonicalResourceId
from ..models import DiscoveredResource, DiscoveryChannel
from ..transport import Transport

SUPPORTED_MANIFEST = "dsh.bundle"


class DshHubAdapter:
    """Discover package manifests without executing plugin code."""

    hub_slug = "dsh_hub"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def discover(  # noqa: C901 - validates an untrusted remote manifest
        self,
        target: str,
        *,
        limit: int | None = None,
        mode: str = "repo",
        subpath: str = "",
    ) -> Iterable[DiscoveredResource]:
        del subpath
        if mode != "repo" or "/" not in target:
            raise ValueError("dsh hub requires an owner/repository target")
        owner, repo = target.split("/", 1)
        api = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        response = self.transport.get(api)
        if response.status != 200:
            raise RuntimeError(
                f"dsh hub tree lookup failed: HTTP {response.status}"
            )
        data = response.json()
        tree = data.get("tree") if isinstance(data, dict) else None
        if not isinstance(tree, list):
            raise TypeError("dsh hub returned an invalid tree")
        count = 0
        for item in tree:
            if limit is not None and count >= limit:
                return
            if (
                not isinstance(item, dict)
                or item.get("path") != "package.json"
            ):
                continue
            path = str(item["path"])
            raw_url = (
                f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
            )
            manifest_response = self.transport.get(raw_url)
            if manifest_response.status != 200:
                continue
            try:
                package = json.loads(manifest_response.text)
            except (TypeError, ValueError):
                continue
            if not isinstance(package, dict):
                continue
            dsh_metadata = package.get("dsh")
            bundle = (
                dsh_metadata.get("bundle")
                if isinstance(dsh_metadata, dict)
                else None
            )
            if not isinstance(bundle, dict) or not isinstance(
                bundle.get("patch"), str
            ):
                continue
            revision_response = self.transport.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits/HEAD"
            )
            revision_data = (
                revision_response.json()
                if revision_response.status == 200
                else {}
            )
            revision = (
                revision_data.get("sha")
                if isinstance(revision_data, dict)
                else None
            )
            if not isinstance(revision, str) or len(revision) != 40:
                continue
            resource_path = path.removesuffix("package.json").rstrip("/")
            uri = f"gh:{owner}/{repo}"
            if resource_path:
                uri += f"#{resource_path}"
            yield DiscoveredResource(
                canonical=CanonicalResourceId("plugin", uri),
                resource_type="plugin",
                canonical_uri=uri,
                title=str(package.get("name") or path),
                summary=str(package.get("description") or ""),
                original_author=owner,
                license_spdx=str(package.get("license"))
                if package.get("license")
                else None,
                source_commit=revision,
                channels=(
                    DiscoveryChannel(
                        self.hub_slug, f"https://github.com/{owner}/{repo}"
                    ),
                ),
            )
            count += 1
