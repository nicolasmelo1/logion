"""Discovery adapter for Git-hosted dsh bundles.

dsh distribution is registry-less: a bundle is a Git repository whose
``package.json`` declares ``dsh.bundle.patch``. This adapter reads those
manifests at one immutable revision and never executes plugin code.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from logion_indexer._json import JsonObject

from ..canonical import CanonicalResourceId
from ..models import DiscoveredResource, DiscoveryChannel
from ..transport import Transport

#: The manifest key a dsh bundle declares itself with. A repository that
#: does not carry it is not a bundle and is skipped, never guessed at.
SUPPORTED_MANIFEST_KEY = "bundle"

_MANIFEST_NAME = "package.json"
_REVISION_LENGTH = 40


class DshHubAdapter:
    """Discover package manifests without executing plugin code."""

    hub_slug = "dsh_hub"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def discover(
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

        # Resolve HEAD once. Reading manifests at a mutable ref and
        # pinning a separately-resolved revision can describe two
        # different trees; every read below uses this one commit.
        revision = self._resolve_head(owner, repo)
        tree = self._read_tree(owner, repo, revision)

        count = 0
        for path in tree:
            if limit is not None and count >= limit:
                return
            manifest = self._read_manifest(owner, repo, revision, path)
            if manifest is None:
                continue
            resource = self._to_resource(owner, repo, revision, path, manifest)
            if resource is None:
                continue
            yield resource
            count += 1

    def _resolve_head(self, owner: str, repo: str) -> str:
        response = self.transport.get(
            f"https://api.github.com/repos/{owner}/{repo}/commits/HEAD"
        )
        if response.status != 200:
            raise RuntimeError(
                f"dsh hub revision lookup failed: HTTP {response.status}"
            )
        data = response.json()
        revision = data.get("sha") if isinstance(data, dict) else None
        if not isinstance(revision, str) or len(revision) != _REVISION_LENGTH:
            raise TypeError("dsh hub returned no immutable revision")
        return revision

    def _read_tree(self, owner: str, repo: str, revision: str) -> list[str]:
        response = self.transport.get(
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/git/trees/{revision}?recursive=1"
        )
        if response.status != 200:
            raise RuntimeError(
                f"dsh hub tree lookup failed: HTTP {response.status}"
            )
        data = response.json()
        tree = data.get("tree") if isinstance(data, dict) else None
        if not isinstance(tree, list):
            raise TypeError("dsh hub returned an invalid tree")
        return [
            str(item["path"])
            for item in tree
            if isinstance(item, dict)
            and str(item.get("path", "")).rsplit("/", 1)[-1] == _MANIFEST_NAME
        ]

    def _read_manifest(
        self, owner: str, repo: str, revision: str, path: str
    ) -> JsonObject | None:
        response = self.transport.get(
            f"https://raw.githubusercontent.com/{owner}/{repo}"
            f"/{revision}/{path}"
        )
        if response.status != 200:
            return None
        try:
            manifest = json.loads(response.text)
        except (TypeError, ValueError):
            return None
        return manifest if isinstance(manifest, dict) else None

    def _to_resource(
        self,
        owner: str,
        repo: str,
        revision: str,
        path: str,
        manifest: JsonObject,
    ) -> DiscoveredResource | None:
        dsh_metadata = manifest.get("dsh")
        bundle = (
            dsh_metadata.get(SUPPORTED_MANIFEST_KEY)
            if isinstance(dsh_metadata, dict)
            else None
        )
        if not isinstance(bundle, dict) or not isinstance(
            bundle.get("patch"), str
        ):
            return None

        resource_path = path.removesuffix(_MANIFEST_NAME).rstrip("/")
        uri = f"gh:{owner}/{repo}"
        if resource_path:
            uri += f"#{resource_path}"
        return DiscoveredResource(
            canonical=CanonicalResourceId("plugin", uri),
            resource_type="plugin",
            canonical_uri=uri,
            title=str(manifest.get("name") or path),
            summary=str(manifest.get("description") or ""),
            original_author=owner,
            license_spdx=str(manifest.get("license"))
            if manifest.get("license")
            else None,
            source_commit=revision,
            declared_capabilities=_declared_capabilities(manifest, bundle),
            npm_distribution=self._npm_distribution(manifest),
            channels=(
                DiscoveryChannel(
                    self.hub_slug, f"https://github.com/{owner}/{repo}"
                ),
            ),
        )

    def _npm_distribution(self, manifest: JsonObject) -> JsonObject | None:
        """Record an npm distribution only if that version really exists.

        dsh installs registry-hosted bundles too — its own base bundle is
        one — but a manifest can name a version that was never published.
        Confirming it against the registry keeps the catalog from
        offering an acquisition that cannot resolve.
        """
        name = manifest.get("name")
        version = manifest.get("version")
        if manifest.get("private") is True:
            return None
        if not isinstance(name, str) or not isinstance(version, str):
            return None
        response = self.transport.get(
            f"https://registry.npmjs.org/{name}/{version}"
        )
        if response.status != 200:
            return None
        data = response.json()
        if not isinstance(data, dict) or data.get("version") != version:
            return None
        return {"name": name, "version": version}


def _declared_capabilities(
    manifest: JsonObject, bundle: JsonObject
) -> JsonObject:
    """Carry what the publisher declares, labelled as a claim.

    Cordis bundles declare their dependencies statically, which is what
    the acquisition plan shows under `permissions`. Nothing here is
    verified — it is the manifest's own words, recorded verbatim.
    """
    dependencies = manifest.get("dependencies")
    peer = manifest.get("peerDependencies")
    declared = sorted(
        set(dependencies if isinstance(dependencies, dict) else {})
        | set(peer if isinstance(peer, dict) else {})
    )
    return {
        "tools": declared,
        "patch": str(bundle.get("patch") or ""),
    }
