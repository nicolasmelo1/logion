# SPDX-License-Identifier: MIT
"""What a crawl refuses, and how it says so.

The claim under test is not "bad input is rejected" -- an exception
does that. It is that one bad entry costs one entry: the rest of the
catalog still imports, the refusal carries a stable code, and the
counters an operator reads add up.
"""

from __future__ import annotations

import json

import pytest

from logion_indexer.adapters.ai_catalog import (
    ERROR_CODE_FETCH_FAILED,
    ERROR_CODE_IDENTITY_MISSING,
    AICatalogAdapter,
)
from logion_indexer.ai_catalog.v1_0.codec import (
    ERROR_CODE_ENTRY_INVALID,
    AICatalogDecodeError,
    AICatalogVersionUnsupported,
    decode_catalog,
    decode_catalog_tolerant,
)
from logion_indexer.import_report import ImportReport, QuarantinedRecord
from logion_indexer.transport import FakeTransport, HttpResponse

CATALOG_URL = "https://example.com/.well-known/ai-catalog.json"

GOOD_ENTRY = {
    "identifier": "urn:air:example.com:mcp:weather",
    "type": "application/mcp-server-card+json",
    "url": "https://api.example.com/mcp/weather",
}
#: Malformed the way a real publisher gets it wrong: the spec's
#: value-or-reference rule violated, not a syntax error.
MALFORMED_ENTRY = {
    "identifier": "urn:air:example.com:mcp:broken",
    "type": "application/mcp-server-card+json",
    "url": "https://api.example.com/mcp/broken",
    "data": {"inline": True},
}


def _document(entries: list[dict]) -> dict:
    return {
        "specVersion": "1.0",
        "host": {"displayName": "Test Host"},
        "entries": entries,
    }


def _transport(document: object, status: int = 200) -> FakeTransport:
    transport = FakeTransport()
    transport.set_response(
        CATALOG_URL,
        HttpResponse(status, json.dumps(document).encode("utf-8")),
    )
    return transport


class TestTolerantDecode:
    def test_one_bad_entry_does_not_cost_the_good_ones(self) -> None:
        catalog, rejected = decode_catalog_tolerant(
            _document([GOOD_ENTRY, MALFORMED_ENTRY])
        )

        assert [e.identifier for e in catalog.entries] == [
            "urn:air:example.com:mcp:weather"
        ]
        assert len(rejected) == 1
        assert rejected[0].error_code == ERROR_CODE_ENTRY_INVALID
        assert rejected[0].identifier == "urn:air:example.com:mcp:broken"

    def test_strict_decode_still_rejects_the_document(self) -> None:
        # The conformance question and the import question are different
        # questions; tolerating entries must not soften the first.
        with pytest.raises(AICatalogDecodeError):
            decode_catalog(_document([GOOD_ENTRY, MALFORMED_ENTRY]))

    def test_unnameable_entry_is_still_reported(self) -> None:
        _, rejected = decode_catalog_tolerant(_document(["not-an-object"]))

        assert len(rejected) == 1
        assert rejected[0].identifier == ""

    def test_envelope_failure_still_raises(self) -> None:
        # Nothing behind a bad specVersion is salvageable, so this is
        # not a quarantine -- it is a refusal to read the document.
        with pytest.raises(AICatalogVersionUnsupported):
            decode_catalog_tolerant({"specVersion": "9.9", "entries": []})

    def test_missing_entries_array_raises(self) -> None:
        with pytest.raises(AICatalogDecodeError):
            decode_catalog_tolerant({"specVersion": "1.0"})


class TestAdapterQuarantine:
    def test_crawl_keeps_good_entries_and_codes_the_bad_one(self) -> None:
        adapter = AICatalogAdapter(
            transport=_transport(_document([GOOD_ENTRY, MALFORMED_ENTRY]))
        )

        result = adapter.crawl(CATALOG_URL)

        assert len(result.resources) == 1
        assert result.errors_by_code == {ERROR_CODE_ENTRY_INVALID: 1}
        assert result.seen == 2

    def test_quarantine_is_visible_in_both_views(self) -> None:
        # A rejection recorded in one list and not the other is how it
        # becomes invisible to half the callers.
        adapter = AICatalogAdapter(
            transport=_transport(_document([MALFORMED_ENTRY]))
        )

        result = adapter.crawl(CATALOG_URL)

        assert len(result.rejected) == 1
        assert len(result.errors) == 1
        assert ERROR_CODE_ENTRY_INVALID in result.errors[0]

    def test_entry_without_identity_is_quarantined_not_dropped(self) -> None:
        adapter = AICatalogAdapter(
            transport=_transport(
                _document([{"identifier": "", "type": "", "url": "u"}])
            )
        )

        result = adapter.crawl(CATALOG_URL)

        assert result.errors_by_code == {ERROR_CODE_IDENTITY_MISSING: 1}

    def test_fetch_failure_is_coded(self) -> None:
        adapter = AICatalogAdapter(
            transport=_transport(_document([]), status=503)
        )

        result = adapter.crawl(CATALOG_URL)

        assert result.errors_by_code == {ERROR_CODE_FETCH_FAILED: 1}


class TestImportReport:
    def _report(self) -> ImportReport:
        return ImportReport(
            source=CATALOG_URL,
            adapter="ai-catalog",
            seen=3,
            created=2,
            matched=0,
            new_versions=0,
            quarantine=[
                QuarantinedRecord("urn:a", ERROR_CODE_ENTRY_INVALID, "bad"),
            ],
        )

    def test_counts_are_written_not_left_derivable(self) -> None:
        payload = self._report().to_dict()

        assert payload["quarantined"] == 1
        assert payload["errors_by_code"] == {ERROR_CODE_ENTRY_INVALID: 1}
        assert payload["seen"] == 3

    def test_quarantine_alone_is_not_a_partial_crawl(self) -> None:
        # Refusing a malformed entry is the crawl working. Only an
        # adapter that failed mid-run makes absent entries meaningless.
        assert self._report().status == "completed"

    def test_partial_run_says_so(self) -> None:
        report = self._report()
        report.partial = True

        assert report.status == "partial"

    def test_report_is_json_serializable(self, tmp_path: object) -> None:
        path = tmp_path / "report.json"  # type: ignore[operator]
        self._report().write(path)

        assert json.loads(path.read_text())["adapter"] == "ai-catalog"
