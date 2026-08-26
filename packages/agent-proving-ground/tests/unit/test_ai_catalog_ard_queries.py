"""What the phase 15.12 assertions actually prove.

Every one of these handlers shipped once already, dispatching correctly
and returning ``{"found": ...}`` while its assertion class read
``valid``/``pinned``/``queried``. They were structurally present,
registered, reachable -- and could not pass. Nothing tested them, which
is the only reason that survived review.

So these tests check the two things a structural audit cannot: the
handler answers under the key its assertion reads, and it fails when the
claim is false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from agent_proving_ground._json import JsonValue
from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)

GetResponse = tuple[int, JsonValue]

CATALOG = {
    "specVersion": "1.0",
    "host": {"displayName": "Fixture Node", "identifier": "urn:air:fixture"},
    "entries": [
        {
            "identifier": "urn:air:fixture:skill:linter",
            "type": "application/agent-skills+json",
            "url": "https://fixture.test/linter",
        }
    ],
}


def _queries() -> LogionApiQueries:
    return LogionApiQueries(
        "http://devrig.test",
        RoleKeyStore({"admin": {"api_key": "redacted"}}),
    )


def _write(tmp_path: Path, name: str, payload: object) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestCatalogDocument:
    async def test_valid_document_answers_under_the_assertions_key(
        self, tmp_path: Path
    ) -> None:
        result = await _queries()._q_ai_catalog_document_valid(
            {"catalog_artifact": _write(tmp_path, "c.json", CATALOG)}, {}
        )

        assert result["valid"] is True
        assert result["entry_count"] == 1
        assert result["spec_version"] == "1.0"

    async def test_missing_artifact_is_named_as_the_cause(self) -> None:
        # "the agent never saved the file" must not read as "the
        # product produced an invalid document".
        result = await _queries()._q_ai_catalog_document_valid(
            {"catalog_artifact": "/nonexistent/c.json"}, {}
        )

        assert result["valid"] is False
        assert "artifact" in str(result["reason"])

    async def test_document_without_host_fails(self, tmp_path: Path) -> None:
        payload = {**CATALOG}
        del payload["host"]
        result = await _queries()._q_ai_catalog_document_valid(
            {"catalog_artifact": _write(tmp_path, "c.json", payload)}, {}
        )

        assert result["valid"] is False

    async def test_conformance_level_is_derived_not_asked_for(
        self, tmp_path: Path
    ) -> None:
        # The document does not declare a level; it earns one. A
        # catalog whose host is identified is discoverable.
        result = await _queries()._q_ai_catalog_conformance_level_valid(
            {"catalog_artifact": _write(tmp_path, "c.json", CATALOG)}, {}
        )

        assert result["valid"] is True
        assert result["conformance_level"] == "discoverable"

    async def test_signed_entry_reaches_trusted(self, tmp_path: Path) -> None:
        payload = json.loads(json.dumps(CATALOG))
        payload["entries"][0]["trustManifest"] = {"signature": "sig"}
        result = await _queries()._q_ai_catalog_conformance_level_valid(
            {"catalog_artifact": _write(tmp_path, "c.json", payload)}, {}
        )

        assert result["conformance_level"] == "trusted"

    async def test_wrong_spec_version_fails(self, tmp_path: Path) -> None:
        payload = {**CATALOG, "specVersion": "0.9"}
        result = await _queries()._q_ai_catalog_conformance_level_valid(
            {"catalog_artifact": _write(tmp_path, "c.json", payload)}, {}
        )

        assert result["valid"] is False


class TestARDSearchArtifact:
    async def test_envelope_origin_is_accepted(self, tmp_path: Path) -> None:
        payload = {
            "registry": {"origin": "http://localhost:8000"},
            "results": [{"identifier": "urn:a", "score": "90"}],
        }
        result = await _queries()._q_ard_search_response_valid(
            {"search_artifact": _write(tmp_path, "s.json", payload)}, {}
        )

        assert result["valid"] is True
        assert result["has_scores"] is True
        assert result["registry_origin"] == "http://localhost:8000"

    async def test_raw_ard_response_names_origin_per_result(
        self, tmp_path: Path
    ) -> None:
        # A conformant registry answering directly puts the origin in
        # each result, not in an envelope our CLI adds.
        payload = {
            "results": [
                {
                    "identifier": "urn:a",
                    "score": 90,
                    "source": "http://localhost:8000",
                }
            ]
        }
        result = await _queries()._q_ard_search_response_valid(
            {"search_artifact": _write(tmp_path, "s.json", payload)}, {}
        )

        assert result["valid"] is True
        assert result["registry_origin"] == "http://localhost:8000"

    async def test_response_that_names_no_registry_fails(
        self, tmp_path: Path
    ) -> None:
        payload = {"results": [{"identifier": "urn:a"}]}
        result = await _queries()._q_ard_search_response_valid(
            {"search_artifact": _write(tmp_path, "s.json", payload)}, {}
        )

        assert result["valid"] is False


class TestFinderRun:
    RUN: ClassVar[dict] = {
        "dry_run": True,
        "records": [
            {
                "finder_id": "finder-a",
                "endpoint": "https://finder.test/search",
                "result_identifiers": ["urn:a"],
            }
        ],
    }

    async def test_queried_counts_the_records(self, tmp_path: Path) -> None:
        result = await _queries()._q_agent_finders_queried(
            {"finder_artifact": _write(tmp_path, "f.json", self.RUN)}, {}
        )

        assert result["queried"] is True
        assert result["finder_count"] == 1

    async def test_no_records_means_no_finder_was_queried(
        self, tmp_path: Path
    ) -> None:
        result = await _queries()._q_agent_finders_queried(
            {"finder_artifact": _write(tmp_path, "f.json", {"records": []})},
            {},
        )

        assert result["queried"] is False

    async def test_provenance_requires_every_record_to_be_attributable(
        self, tmp_path: Path
    ) -> None:
        run = {"records": [*self.RUN["records"], {"finder_id": "finder-b"}]}
        result = await _queries()._q_agent_finder_result_provenance_visible(
            {"finder_artifact": _write(tmp_path, "f.json", run)}, {}
        )

        # One anonymous result is enough to lose the claim: provenance
        # that holds for most results is not provenance.
        assert result["visible"] is False
        assert "endpoint" in str(result["reason"])


def _report(**overrides: object) -> dict:
    base = {
        "source": "http://localhost:8000/.well-known/ai-catalog.json",
        "status": "completed",
        "seen": 2,
        "created": 1,
        "matched": 0,
        "new_versions": 0,
        "quarantined": 1,
        "quarantine": [
            {
                "identifier": "urn:broken",
                "error_code": "ai_catalog_entry_invalid",
                "reason": "url and data are mutually exclusive",
            }
        ],
    }
    base.update(overrides)
    return base


class TestCrawlReports:
    async def test_completed_reads_the_report_the_agent_saved(
        self, tmp_path: Path
    ) -> None:
        result = await _queries()._q_catalog_crawl_completed(
            {"crawl_reports": [_write(tmp_path, "c1.json", _report())]}, {}
        )

        assert result["completed"] is True
        assert result["seen"] == 2

    async def test_partial_crawl_is_not_completed(
        self, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, "c1.json", _report(status="partial"))
        result = await _queries()._q_catalog_crawl_completed(
            {"crawl_reports": [path]}, {}
        )

        assert result["completed"] is False

    async def test_rejection_needs_a_stable_code(self, tmp_path: Path) -> None:
        result = await _queries()._q_ard_record_rejected(
            {"crawl_reports": [_write(tmp_path, "c1.json", _report())]}, {}
        )

        assert result["rejected"] is True
        assert result["error_code"] == "ai_catalog_entry_invalid"

    async def test_importing_everything_does_not_prove_rejection(
        self, tmp_path: Path
    ) -> None:
        clean = _report(quarantined=0, quarantine=[])
        result = await _queries()._q_ard_record_rejected(
            {"crawl_reports": [_write(tmp_path, "c1.json", clean)]}, {}
        )

        assert result["rejected"] is False

    async def test_uncoded_quarantine_does_not_count(
        self, tmp_path: Path
    ) -> None:
        # A quarantine with no stable code cannot be grouped across
        # runs, which is the whole point of quarantining by code.
        uncoded = _report(quarantine=[{"identifier": "x", "reason": "bad"}])
        result = await _queries()._q_ard_record_rejected(
            {"crawl_reports": [_write(tmp_path, "c1.json", uncoded)]}, {}
        )

        assert result["rejected"] is False


class TestSelfCrawl:
    async def _run(self, monkeypatch, tmp_path, rows, second) -> dict:
        queries = _queries()

        async def fake_paged_get(_path: str, _role: str | None):
            return 200, rows

        monkeypatch.setattr(queries, "_paged_get", fake_paged_get)
        return await queries._q_self_crawl_no_duplicate(
            {
                "crawl_reports": [
                    _write(tmp_path, "c1.json", _report()),
                    _write(tmp_path, "c2.json", _report(**second)),
                ]
            },
            {},
        )

    async def test_second_crawl_creating_nothing_is_the_claim(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        rows = [{"resource_type": "skill", "canonical_uri": "air:a"}]
        result = await self._run(monkeypatch, tmp_path, rows, {"created": 0})

        assert result["no_duplicates"] is True
        assert result["crawl_count"] == 2

    async def test_second_crawl_creating_again_fails(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        # The registry can hold no duplicate pair and still have been
        # re-imported, if the second crawl wrote under a new identity.
        rows = [{"resource_type": "skill", "canonical_uri": "air:a"}]
        result = await self._run(monkeypatch, tmp_path, rows, {"created": 1})

        assert result["no_duplicates"] is False

    async def test_duplicate_pair_in_the_registry_fails(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        rows = [
            {"resource_type": "skill", "canonical_uri": "air:a"},
            {"resource_type": "skill", "canonical_uri": "air:a"},
        ]
        result = await self._run(monkeypatch, tmp_path, rows, {"created": 0})

        assert result["no_duplicates"] is False


class TestProvenanceAndASM:
    DETAIL: ClassVar[dict] = {
        "resource": {
            "id": "r1",
            "resource_type": "skill",
            "canonical_uri": "air:a",
            "metadata": {"tags": ["fixture"]},
        },
        "sources": [
            {
                "source_kind": "ai-catalog",
                "source_uri": "http://localhost:8000/.well-known/x.json",
                "external_id": "urn:air:fixture:skill:linter",
            }
        ],
    }

    async def _detail(self, monkeypatch, payload) -> LogionApiQueries:
        queries = _queries()

        async def fake_get(_path: str, _role: str | None) -> GetResponse:
            return 200, payload

        monkeypatch.setattr(queries, "_get", fake_get)
        return queries

    async def test_provenance_reads_the_sources_the_api_returns(
        self, monkeypatch
    ) -> None:
        queries = await self._detail(monkeypatch, self.DETAIL)
        result = await queries._q_resource_source_provenance_visible(
            {"resource_id": "r1"}, {}
        )

        assert result["visible"] is True
        assert result["source_kind"] == "ai-catalog"

    async def test_resource_with_no_source_is_not_provenanced(
        self, monkeypatch
    ) -> None:
        queries = await self._detail(
            monkeypatch, {**self.DETAIL, "sources": []}
        )
        result = await queries._q_resource_source_provenance_visible(
            {"resource_id": "r1"}, {}
        )

        assert result["visible"] is False

    async def test_asm_check_looks_inside_the_resource(
        self, monkeypatch
    ) -> None:
        queries = await self._detail(monkeypatch, self.DETAIL)
        result = await queries._q_ingested_model_requires_no_asm_schema(
            {"resource_id": "r1"}, {}
        )

        assert result["agnostic"] is True

    async def test_asm_field_on_the_model_is_caught(self, monkeypatch) -> None:
        # Checking the envelope instead of the model reports "clean"
        # for every resource that has ever existed.
        payload = json.loads(json.dumps(self.DETAIL))
        payload["resource"]["asm_selector"] = {"path": "$.x"}
        queries = await self._detail(monkeypatch, payload)
        result = await queries._q_ingested_model_requires_no_asm_schema(
            {"resource_id": "r1"}, {}
        )

        assert result["agnostic"] is False
        assert "asm_selector" in str(result["reason"])

    async def test_asm_field_in_metadata_is_caught(self, monkeypatch) -> None:
        payload = json.loads(json.dumps(self.DETAIL))
        payload["resource"]["metadata"]["asm_schema"] = {"v": 1}
        queries = await self._detail(monkeypatch, payload)
        result = await queries._q_ingested_model_requires_no_asm_schema(
            {"resource_id": "r1"}, {}
        )

        assert result["agnostic"] is False


class TestSnapshotPinned:
    async def _status(self, monkeypatch, payload) -> LogionApiQueries:
        queries = _queries()

        async def fake_get(_path: str, _role: str | None) -> GetResponse:
            return 200, payload

        monkeypatch.setattr(queries, "_get", fake_get)
        return queries

    async def test_pinned_reads_the_items_the_endpoint_returns(
        self, monkeypatch
    ) -> None:
        payload = {
            "items": [
                {
                    "source_type": "ard-connectors",
                    "source_uri": "https://example.test/agent-finders.json",
                    "commit_sha": "abc123",
                    "file_digest": "sha256:deadbeef",
                    "last_good": True,
                    "validation_result": "valid",
                }
            ],
            "total": 1,
        }
        queries = await self._status(monkeypatch, payload)
        result = await queries._q_ard_connectors_snapshot_pinned({}, {})

        assert result["pinned"] is True
        assert result["commit_sha"] == "abc123"

    async def test_snapshot_without_a_digest_is_not_pinned(
        self, monkeypatch
    ) -> None:
        # A commit alone does not pin content: the file at that commit
        # is what the node will run.
        payload = {
            "items": [
                {
                    "source_type": "ard-connectors",
                    "commit_sha": "abc123",
                    "last_good": True,
                }
            ]
        }
        queries = await self._status(monkeypatch, payload)
        result = await queries._q_ard_connectors_snapshot_pinned({}, {})

        assert result["pinned"] is False

    async def test_no_snapshot_at_all_is_not_pinned(self, monkeypatch) -> None:
        queries = await self._status(monkeypatch, {"items": [], "total": 0})
        result = await queries._q_ard_connectors_snapshot_pinned({}, {})

        assert result["pinned"] is False


class TestFilterNarrows:
    async def _search(self, monkeypatch, unfiltered, filtered):
        queries = _queries()

        async def fake_post(_path: str, _role: str | None, body: dict):
            has_filter = bool(body.get("query", {}).get("filter"))
            return 200, (filtered if has_filter else unfiltered)

        monkeypatch.setattr(queries, "_post", fake_post)
        return await queries._q_search_filters_by_type_and_source(
            {
                "query_text": "fixture",
                "resource_type": "application/agent-skills+json",
                "source": "http://localhost:8000",
            },
            {},
        )

    async def test_a_filter_that_excludes_nothing_is_not_filtering(
        self, monkeypatch
    ) -> None:
        rows = {
            "results": [
                {"identifier": "a", "type": "application/agent-skills+json"},
                {"identifier": "b", "type": "application/agent-skills+json"},
            ]
        }
        result = await self._search(monkeypatch, rows, rows)

        assert result["filtered"] is False
        assert "everything" in str(result["reason"])

    async def test_narrowing_to_matching_entries_passes(
        self, monkeypatch
    ) -> None:
        unfiltered = {
            "results": [
                {"identifier": "a", "type": "application/agent-skills+json"},
                {
                    "identifier": "b",
                    "type": "application/mcp-server-card+json",
                },
            ]
        }
        filtered = {
            "results": [
                {"identifier": "a", "type": "application/agent-skills+json"}
            ]
        }
        result = await self._search(monkeypatch, unfiltered, filtered)

        assert result["filtered"] is True
        assert result["result_count"] == 1

    async def test_a_filter_that_leaks_a_mismatch_fails(
        self, monkeypatch
    ) -> None:
        unfiltered = {"results": [{"identifier": "a"}, {"identifier": "b"}]}
        filtered = {
            "results": [
                {"identifier": "b", "type": "application/mcp-server-card+json"}
            ]
        }
        result = await self._search(monkeypatch, unfiltered, filtered)

        assert result["filtered"] is False

    async def test_missing_filter_params_are_unsupported_not_passing(
        self,
    ) -> None:
        queries = _queries()
        result = await queries._q_search_filters_by_type_and_source({}, {})

        assert result["unsupported"] is True


@pytest.mark.parametrize(
    ("saved", "expected"),
    [({"results": [{"identifier": "a"}]}, True), ({"results": []}, False)],
)
async def test_discovery_without_aktp_requires_a_real_discovery(
    monkeypatch, tmp_path: Path, saved: dict, expected: bool
) -> None:
    queries = _queries()

    async def fake_post(_path: str, _role: str | None, _body: dict):
        return 200, {"results": [{"identifier": "a"}]}

    async def fake_get(_path: str, _role: str | None) -> GetResponse:
        return 404, None

    monkeypatch.setattr(queries, "_post", fake_post)
    monkeypatch.setattr(queries, "_get", fake_get)
    result = await queries._q_discovery_succeeds_without_aktp(
        {
            "search_artifact": _write(tmp_path, "s.json", saved),
            "query_text": "fixture",
        },
        {},
    )

    assert result.get("succeeded", False) is expected
