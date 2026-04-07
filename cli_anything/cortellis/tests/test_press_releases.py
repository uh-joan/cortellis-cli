"""Unit tests for enrich_press_releases.py.

No real API calls — all Cortellis interactions are mocked.

Run with:
    pytest cli_anything/cortellis/tests/test_press_releases.py -v
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Allow import of the recipe module from tests directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases import (
    extract_press_release,
    generate_press_releases_markdown,
    get_top_company_names,
    search_press_releases_for_company,
    write_press_releases_csv,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def landscape_dir(tmp_path):
    """Create a minimal landscape directory with strategic_scores.csv."""
    scores_path = tmp_path / "strategic_scores.csv"
    scores_path.write_text(
        "company,cpi_score,cpi_tier\n"
        "Novo Nordisk,85.0,A\n"
        "Eli Lilly,78.5,A\n"
        "AstraZeneca,62.0,B\n",
        encoding="utf-8",
    )
    return str(tmp_path)


@pytest.fixture()
def sample_releases():
    return [
        {
            "company_name": "Novo Nordisk",
            "title": "Novo Nordisk reports strong Q1 2026 results driven by obesity portfolio",
            "date": "2026-03",
            "summary": "Novo Nordisk reported record revenues...",
        },
        {
            "company_name": "Novo Nordisk",
            "title": "Novo Nordisk expands semaglutide manufacturing capacity",
            "date": "2026-01",
            "summary": "New manufacturing site announced...",
        },
        {
            "company_name": "Eli Lilly",
            "title": "Eli Lilly receives FDA approval for tirzepatide in heart failure",
            "date": "2025-11",
            "summary": "FDA approval expands tirzepatide label...",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: get_top_company_names
# ---------------------------------------------------------------------------

class TestGetTopCompanyNames:
    def test_reads_strategic_scores(self, landscape_dir):
        names = get_top_company_names(landscape_dir)
        assert names[0] == "Novo Nordisk"
        assert names[1] == "Eli Lilly"
        assert names[2] == "AstraZeneca"

    def test_caps_at_max_companies(self, landscape_dir):
        names = get_top_company_names(landscape_dir, max_companies=2)
        assert len(names) == 2

    def test_deduplicates_names(self, tmp_path):
        (tmp_path / "strategic_scores.csv").write_text(
            "company,cpi_score\nAcme,80\nAcme,75\n", encoding="utf-8"
        )
        names = get_top_company_names(str(tmp_path))
        assert names.count("Acme") == 1

    def test_missing_csv_returns_empty(self, tmp_path):
        names = get_top_company_names(str(tmp_path))
        assert names == []

    def test_returns_all_when_under_max(self, landscape_dir):
        names = get_top_company_names(landscape_dir, max_companies=10)
        assert len(names) == 3


# ---------------------------------------------------------------------------
# Tests: extract_press_release
# ---------------------------------------------------------------------------

class TestExtractPressRelease:
    def test_extracts_title(self):
        record = {"title": "Q1 Results", "date": "2026-03-01"}
        pr = extract_press_release(record)
        assert pr["title"] == "Q1 Results"

    def test_extracts_date_trims_to_yyyy_mm(self):
        record = {"title": "Test", "date": "2026-03-15"}
        pr = extract_press_release(record)
        assert pr["date"] == "2026-03"

    def test_extracts_date_yyyy_mm_unchanged(self):
        record = {"title": "Test", "date": "2026-03"}
        pr = extract_press_release(record)
        assert pr["date"] == "2026-03"

    def test_extracts_summary_field(self):
        record = {"title": "Test", "summary": "Company announces milestone."}
        pr = extract_press_release(record)
        assert pr["summary"] == "Company announces milestone."

    def test_extracts_snippet_as_fallback(self):
        record = {"title": "Test", "snippet": "Snippet text here."}
        pr = extract_press_release(record)
        assert pr["summary"] == "Snippet text here."

    def test_summary_truncated_at_200(self):
        long_text = "x" * 300
        record = {"title": "Test", "summary": long_text}
        pr = extract_press_release(record)
        assert len(pr["summary"]) <= 203
        assert pr["summary"].endswith("...")

    def test_short_summary_not_truncated(self):
        record = {"title": "Test", "summary": "Short text."}
        pr = extract_press_release(record)
        assert pr["summary"] == "Short text."

    def test_handles_empty_record(self):
        pr = extract_press_release({})
        assert pr["title"] == ""
        assert pr["date"] == ""
        assert pr["summary"] == ""

    def test_handles_non_dict(self):
        pr = extract_press_release("not a dict")
        assert pr == {}

    def test_uses_alternate_title_field(self):
        record = {"headline": "Alt headline", "date": "2026-01"}
        pr = extract_press_release(record)
        assert pr["title"] == "Alt headline"

    def test_uses_alternate_date_field(self):
        record = {"title": "Test", "publishDate": "2026-02-10"}
        pr = extract_press_release(record)
        assert pr["date"] == "2026-02"


# ---------------------------------------------------------------------------
# Tests: generate_press_releases_markdown
# ---------------------------------------------------------------------------

class TestGeneratePressReleasesMarkdown:
    def test_contains_heading(self, sample_releases):
        md = generate_press_releases_markdown(sample_releases, "Obesity")
        assert "## Recent Press Releases: Obesity" in md

    def test_contains_table_header(self, sample_releases):
        md = generate_press_releases_markdown(sample_releases, "Obesity")
        assert "| Company | Title | Date | Summary |" in md

    def test_contains_company_names(self, sample_releases):
        md = generate_press_releases_markdown(sample_releases, "Obesity")
        assert "Novo Nordisk" in md
        assert "Eli Lilly" in md

    def test_contains_summary_section(self, sample_releases):
        md = generate_press_releases_markdown(sample_releases, "Obesity")
        assert "### Summary" in md

    def test_summary_release_count(self, sample_releases):
        md = generate_press_releases_markdown(sample_releases, "Obesity")
        assert "3 press releases" in md

    def test_summary_most_active(self, sample_releases):
        md = generate_press_releases_markdown(sample_releases, "Obesity")
        # Novo Nordisk has 2 releases
        assert "Novo Nordisk" in md
        assert "Most active" in md

    def test_summary_most_recent(self, sample_releases):
        md = generate_press_releases_markdown(sample_releases, "Obesity")
        assert "Most recent" in md
        assert "2026-03" in md

    def test_valid_markdown_table(self, sample_releases):
        md = generate_press_releases_markdown(sample_releases, "Obesity")
        lines = md.split("\n")
        table_lines = [l for l in lines if l.startswith("|")]
        assert len(table_lines) >= 4  # header + separator + at least 3 rows


# ---------------------------------------------------------------------------
# Tests: empty results
# ---------------------------------------------------------------------------

class TestEmptyResults:
    def test_empty_releases_markdown(self):
        md = generate_press_releases_markdown([], "Oncology")
        assert "## Recent Press Releases: Oncology" in md
        assert "No press releases found" in md or "0 press releases" in md

    def test_empty_summary_section_present(self):
        md = generate_press_releases_markdown([], "Oncology")
        assert "### Summary" in md

    def test_empty_write_csv_header_only(self, tmp_path):
        path = str(tmp_path / "press_releases_summary.csv")
        write_press_releases_csv([], path)
        assert os.path.exists(path)
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows == []


# ---------------------------------------------------------------------------
# Tests: write_press_releases_csv (round-trip)
# ---------------------------------------------------------------------------

class TestWritePressReleasesCsv:
    def test_round_trip(self, tmp_path, sample_releases):
        path = str(tmp_path / "press_releases_summary.csv")
        write_press_releases_csv(sample_releases, path)
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3

    def test_correct_field_values(self, tmp_path, sample_releases):
        path = str(tmp_path / "press_releases_summary.csv")
        write_press_releases_csv(sample_releases, path)
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["company_name"] == "Novo Nordisk"
        assert rows[0]["date"] == "2026-03"

    def test_all_fieldnames_present(self, tmp_path):
        path = str(tmp_path / "pr.csv")
        write_press_releases_csv([], path)
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        expected = {"company_name", "title", "date", "summary"}
        assert expected.issubset(set(fieldnames))


# ---------------------------------------------------------------------------
# Tests: search_press_releases_for_company (mocked)
# ---------------------------------------------------------------------------

class TestSearchPressReleasesForCompany:
    def _make_client(self):
        return MagicMock()

    def test_returns_records_from_api(self):
        client = self._make_client()
        mock_hit = {
            "title": "Novo Nordisk Q1 Results",
            "date": "2026-03",
            "summary": "Record revenues reported.",
        }
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases.press_releases.search",
            return_value={"pressReleaseList": {"pressRelease": [mock_hit]}},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases.time.sleep"
        ):
            records = search_press_releases_for_company("Novo Nordisk", client)

        assert len(records) == 1
        assert records[0]["title"] == "Novo Nordisk Q1 Results"

    def test_handles_empty_results_gracefully(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases.press_releases.search",
            return_value={},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases.time.sleep"
        ):
            records = search_press_releases_for_company("UnknownCo", client)

        assert records == []

    def test_handles_api_exception_gracefully(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases.press_releases.search",
            side_effect=Exception("network error"),
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases.time.sleep"
        ):
            records = search_press_releases_for_company("SomeCo", client)

        assert records == []

    def test_sleeps_after_call(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases.press_releases.search",
            return_value={},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_press_releases.time.sleep"
        ) as mock_sleep:
            search_press_releases_for_company("AcmeCorp", client)

        mock_sleep.assert_called_once_with(2)
