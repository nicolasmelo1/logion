"""GitHub direct adapter: repo, repo_subpath, and owner enumeration modes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..github_source import GithubSource, InferredSkill
from ..models import DiscoveredSkill, DiscoveryChannel
from ..transport import Transport


@dataclass
class GithubDirectAdapter:
    """Direct GitHub adapter with three modes.

    Modes:
        repo: Whole repo — one listing per canonical skillmap component.
        repo_subpath: Filter inference to components under the subpath.
        owner: Enumerate the account's repos that contain a SKILL.md.
    """

    transport: Transport
    hub_slug: str = "github"
    _source: GithubSource | None = None

    @property
    def source(self) -> GithubSource:
        if self._source is None:
            self._source = GithubSource(transport=self.transport)
        return self._source

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
        mode: str = "repo",
        subpath: str = "",
    ) -> Iterable[DiscoveredSkill]:
        """Discover skills from a GitHub target.

        Args:
            target: ``owner/repo`` or ``owner`` (for owner mode).
            limit: Maximum items.
            mode: ``repo``, ``repo_subpath``, or ``owner``.
            subpath: Subpath for ``repo_subpath`` mode.
        """
        if mode == "owner":
            yield from self._discover_owner(target, limit=limit)
        elif mode == "repo_subpath":
            yield from self._discover_repo(
                target, subpath=subpath, limit=limit
            )
        else:
            yield from self._discover_repo(target, subpath="", limit=limit)

    def _discover_repo(
        self,
        target: str,
        *,
        subpath: str = "",
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        """Discover skills in a single repo (or subpath)."""
        parts = target.split("/", 1)
        if len(parts) != 2:
            return
        owner, repo = parts
        owner = owner.strip()
        repo = repo.strip()

        # Get HEAD sha and license.
        sha = self.source.fetch_head_sha(owner, repo)
        license_spdx = self.source.fetch_license(owner, repo)

        _, skills = self.source.infer_skills(
            owner, repo, sha=sha, subpath=subpath
        )

        count = 0
        for skill in skills:
            if limit is not None and count >= limit:
                return
            yield from self._emit_skill(
                skill,
                owner=owner,
                repo=repo,
                license_spdx=license_spdx,
                source_commit=sha,
            )
            count += 1  # noqa: SIM113

    def _discover_owner(
        self,
        owner: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        """Enumerate an owner's repos that contain SKILL.md files."""
        owner = owner.strip()
        count = 0
        page = 1
        while True:
            url = (
                f"https://api.github.com/users/{owner}/repos"
                f"?per_page=100&sort=updated&page={page}"
            )
            resp = self.transport.get(url)
            if resp.status != 200:
                return
            data = resp.json()
            if not isinstance(data, list):
                return
            if not data:
                return

            for repo_info in data:
                for skill in self._discover_owner_repo(owner, repo_info):
                    if limit is not None and count >= limit:
                        return
                    yield skill
                    count += 1

            if len(data) < 100:
                return
            page += 1

    def _discover_owner_repo(
        self,
        owner: str,
        repo_info: object,
    ) -> Iterable[DiscoveredSkill]:
        if not isinstance(repo_info, dict):
            return
        repo = repo_info.get("name", "")
        if not isinstance(repo, str) or not repo:
            return
        sha = self.source.fetch_head_sha(owner, repo)
        if not sha:
            return
        _, skills = self.source.infer_skills(owner, repo, sha=sha)
        license_spdx = None
        license_info = repo_info.get("license") or {}
        if isinstance(license_info, dict):
            value = license_info.get("spdx_id")
            if isinstance(value, str):
                license_spdx = value
        for skill in skills:
            yield from self._emit_skill(
                skill,
                owner=owner,
                repo=repo,
                license_spdx=license_spdx,
                source_commit=sha,
            )

    def _emit_skill(
        self,
        skill: InferredSkill,
        *,
        owner: str,
        repo: str,
        license_spdx: str | None,
        source_commit: str,
    ) -> Iterable[DiscoveredSkill]:
        """Emit a DiscoveredSkill from an InferredSkill."""
        channel = DiscoveryChannel(
            hub_slug=self.hub_slug,
            hub_url=f"https://github.com/{owner}/{repo}",
            hub_verified=False,
        )
        yield DiscoveredSkill(
            canonical=skill.canonical,
            title=skill.name,
            summary=skill.summary,
            original_author=owner,
            license_spdx=license_spdx,
            source_commit=source_commit or None,
            tags=(),
            channels=(channel,),
            inferred_map=skill.inferred_map,
            map_flags=skill.map_flags,
        )
