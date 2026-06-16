"""Unit tests for the search pagination helper (no HTTP — fake page fetchers)."""
from __future__ import annotations

from cli_anything.cortellis.core.pagination import fetch_all, PAGE_MAX


def _envelope(records, total):
    """Build a Cortellis-shaped search envelope for a page of drug records."""
    return {
        "drugResultsOutput": {
            "@hits": str(len(records)),
            "@offset": "0",
            "@totalResults": str(total),
            "SearchResults": {"Drug": list(records)},
        }
    }


def _make_fetcher(total):
    """Return (fetch_page, calls) that serves `total` synthetic records, capped
    at PAGE_MAX per call — mirroring the real API's silent 500 clamp."""
    all_records = [{"@id": str(i)} for i in range(total)]
    calls: list[tuple[int, int]] = []

    def fetch_page(offset, hits):
        calls.append((offset, hits))
        page_size = min(hits, PAGE_MAX)
        return _envelope(all_records[offset:offset + page_size], total)

    return fetch_page, calls


def test_single_page_when_under_cap():
    fetch_page, calls = _make_fetcher(472)
    result = fetch_all(fetch_page)
    drugs = result["drugResultsOutput"]["SearchResults"]["Drug"]
    assert len(drugs) == 472
    assert len(calls) == 1  # one page suffices
    assert result["drugResultsOutput"]["@hits"] == "472"


def test_stitches_multiple_pages_past_cap():
    fetch_page, calls = _make_fetcher(1203)
    result = fetch_all(fetch_page)
    drugs = result["drugResultsOutput"]["SearchResults"]["Drug"]
    assert len(drugs) == 1203
    assert [c[0] for c in calls] == [0, 500, 1000]  # offsets walked in PAGE_MAX steps
    assert [d["@id"] for d in drugs[:3]] == ["0", "1", "2"]
    assert drugs[-1]["@id"] == "1202"  # full set, in order, no dupes


def test_exact_multiple_of_page_size():
    fetch_page, calls = _make_fetcher(1000)
    result = fetch_all(fetch_page)
    assert len(result["drugResultsOutput"]["SearchResults"]["Drug"]) == 1000
    assert len(calls) == 2  # offset 0 and 500; loop stops at total


def test_single_record_returned_as_dict():
    # API returns a bare dict (not a list) for a one-result page.
    def fetch_page(offset, hits):
        return {
            "drugResultsOutput": {
                "@totalResults": "1",
                "SearchResults": {"Drug": {"@id": "solo"}},
            }
        }

    result = fetch_all(fetch_page)
    assert result["drugResultsOutput"]["SearchResults"]["Drug"] == [{"@id": "solo"}]


def test_zero_results_is_safe():
    def fetch_page(offset, hits):
        return {"drugResultsOutput": {"@totalResults": "0", "SearchResults": {"Drug": []}}}

    result = fetch_all(fetch_page)
    assert result["drugResultsOutput"]["SearchResults"]["Drug"] == []


def test_hard_cap_truncates():
    fetch_page, calls = _make_fetcher(5000)
    result = fetch_all(fetch_page, hard_cap=1000)
    assert len(result["drugResultsOutput"]["SearchResults"]["Drug"]) == 1000
