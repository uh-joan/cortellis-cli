"""Unit tests for enrich_literature.py.

No real API calls — all Cortellis interactions are mocked.

Run with:
    pytest cli_anything/cortellis/tests/test_literature.py -v
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

from cli_anything.cortellis.skills.landscape.recipes.enrich_literature import (
    extract_publication,
    generate_publications_markdown,
    get_top_drug_names,
    search_literature_for_drug,
    write_literature_csv,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def landscape_dir(tmp_path):
    """Create a minimal landscape directory with launched.csv and phase3.csv."""
    launched_path = tmp_path / "launched.csv"
    launched_path.write_text(
        "id,name,company,phase\n"
        "101,semaglutide,Novo Nordisk,Launched\n"
        "102,tirzepatide,Eli Lilly,Launched\n",
        encoding="utf-8",
    )
    phase3_path = tmp_path / "phase3.csv"
    phase3_path.write_text(
        "id,name,company,phase\n"
        "201,orforglipron,Eli Lilly,Phase 3\n"
        "202,retatrutide,Eli Lilly,Phase 3\n",
        encoding="utf-8",
    )
    return str(tmp_path)


@pytest.fixture()
def sample_publications():
    return [
        {
            "drug_name": "semaglutide",
            "title": "Phase 3 results for semaglutide in obesity",
            "authors": "Smith JA et al",
            "journal": "NEJM",
            "date": "2026-03",
            "abstract_excerpt": "Semaglutide showed significant weight loss...",
        },
        {
            "drug_name": "semaglutide",
            "title": "Cardiovascular outcomes with semaglutide",
            "authors": "Jones B et al",
            "journal": "Lancet",
            "date": "2026-01",
            "abstract_excerpt": "Cardiovascular risk reduction was observed...",
        },
        {
            "drug_name": "tirzepatide",
            "title": "Tirzepatide vs semaglutide head-to-head",
            "authors": "Brown C et al",
            "journal": "JAMA",
            "date": "2025-11",
            "abstract_excerpt": "A comparative study of dual agonists...",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: get_top_drug_names
# ---------------------------------------------------------------------------

class TestGetTopDrugNames:
    def test_reads_launched_first(self, landscape_dir):
        names = get_top_drug_names(landscape_dir)
        assert names[0] == "semaglutide"
        assert names[1] == "tirzepatide"

    def test_appends_phase3_after_launched(self, landscape_dir):
        names = get_top_drug_names(landscape_dir)
        assert "orforglipron" in names
        assert names.index("semaglutide") < names.index("orforglipron")

    def test_caps_at_max_drugs(self, landscape_dir):
        names = get_top_drug_names(landscape_dir, max_drugs=2)
        assert len(names) == 2

    def test_deduplicates_names(self, tmp_path):
        (tmp_path / "launched.csv").write_text(
            "id,name,company\n101,DrugX,Co\n", encoding="utf-8"
        )
        (tmp_path / "phase3.csv").write_text(
            "id,name,company\n201,DrugX,Co\n", encoding="utf-8"
        )
        names = get_top_drug_names(str(tmp_path))
        assert names.count("DrugX") == 1

    def test_missing_csvs_returns_empty(self, tmp_path):
        names = get_top_drug_names(str(tmp_path))
        assert names == []


# ---------------------------------------------------------------------------
# Tests: extract_publication
# ---------------------------------------------------------------------------

class TestExtractPublication:
    def test_extracts_title(self):
        record = {"title": "Phase 3 results", "authors": [], "journal": "NEJM", "date": "2026-03-01"}
        pub = extract_publication(record)
        assert pub["title"] == "Phase 3 results"

    def test_extracts_journal(self):
        record = {"title": "Test", "journal": "Lancet", "date": "2026-01"}
        pub = extract_publication(record)
        assert pub["journal"] == "Lancet"

    def test_extracts_date_trims_to_yyyy_mm(self):
        record = {"title": "Test", "date": "2026-03-15"}
        pub = extract_publication(record)
        assert pub["date"] == "2026-03"

    def test_extracts_date_yyyy_mm_unchanged(self):
        record = {"title": "Test", "date": "2026-03"}
        pub = extract_publication(record)
        assert pub["date"] == "2026-03"

    def test_extracts_first_author_et_al(self):
        record = {
            "title": "Test",
            "authors": [
                {"lastName": "Smith", "initials": "JA"},
                {"lastName": "Jones", "initials": "B"},
            ],
        }
        pub = extract_publication(record)
        assert "Smith" in pub["authors"]
        assert "et al" in pub["authors"]

    def test_single_author_no_et_al(self):
        record = {
            "title": "Test",
            "authors": [{"lastName": "Solo", "initials": "A"}],
        }
        pub = extract_publication(record)
        assert "et al" not in pub["authors"]
        assert "Solo" in pub["authors"]

    def test_abstract_excerpt_truncated_at_200(self):
        long_abstract = "x" * 300
        record = {"title": "Test", "abstract": long_abstract}
        pub = extract_publication(record)
        assert len(pub["abstract_excerpt"]) <= 203  # 200 + "..."
        assert pub["abstract_excerpt"].endswith("...")

    def test_short_abstract_not_truncated(self):
        short_abstract = "Short abstract."
        record = {"title": "Test", "abstract": short_abstract}
        pub = extract_publication(record)
        assert pub["abstract_excerpt"] == short_abstract

    def test_handles_empty_record(self):
        pub = extract_publication({})
        assert pub["title"] == ""
        assert pub["authors"] == ""
        assert pub["journal"] == ""

    def test_handles_non_dict(self):
        pub = extract_publication("not a dict")
        assert pub == {}

    def test_uses_alternate_field_names(self):
        record = {
            "articleTitle": "Alt title",
            "journalName": "Alt Journal",
            "publicationDate": "2025-06",
        }
        pub = extract_publication(record)
        assert pub["title"] == "Alt title"
        assert pub["journal"] == "Alt Journal"
        assert pub["date"] == "2025-06"


# ---------------------------------------------------------------------------
# Tests: generate_publications_markdown
# ---------------------------------------------------------------------------

class TestGeneratePublicationsMarkdown:
    def test_contains_heading(self, sample_publications):
        md = generate_publications_markdown(sample_publications, "Obesity")
        assert "## Recent Publications: Obesity" in md

    def test_contains_table_header(self, sample_publications):
        md = generate_publications_markdown(sample_publications, "Obesity")
        assert "| Drug | Title | Authors | Journal | Date |" in md

    def test_contains_drug_names(self, sample_publications):
        md = generate_publications_markdown(sample_publications, "Obesity")
        assert "semaglutide" in md
        assert "tirzepatide" in md

    def test_contains_summary_section(self, sample_publications):
        md = generate_publications_markdown(sample_publications, "Obesity")
        assert "### Summary" in md

    def test_summary_publication_count(self, sample_publications):
        md = generate_publications_markdown(sample_publications, "Obesity")
        assert "3 publications" in md

    def test_summary_most_published(self, sample_publications):
        md = generate_publications_markdown(sample_publications, "Obesity")
        # semaglutide has 2 publications
        assert "semaglutide" in md
        assert "Most published" in md

    def test_summary_most_recent(self, sample_publications):
        md = generate_publications_markdown(sample_publications, "Obesity")
        assert "Most recent" in md
        assert "2026-03" in md

    def test_valid_markdown_table(self, sample_publications):
        md = generate_publications_markdown(sample_publications, "Obesity")
        lines = md.split("\n")
        table_lines = [l for l in lines if l.startswith("|")]
        assert len(table_lines) >= 4  # header + separator + at least 3 rows


# ---------------------------------------------------------------------------
# Tests: empty results
# ---------------------------------------------------------------------------

class TestEmptyResults:
    def test_empty_publications_markdown(self):
        md = generate_publications_markdown([], "Oncology")
        assert "## Recent Publications: Oncology" in md
        assert "No publications found" in md or "0 publications" in md

    def test_empty_summary_section_present(self):
        md = generate_publications_markdown([], "Oncology")
        assert "### Summary" in md

    def test_empty_write_csv_header_only(self, tmp_path):
        path = str(tmp_path / "literature_summary.csv")
        write_literature_csv([], path)
        assert os.path.exists(path)
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows == []


# ---------------------------------------------------------------------------
# Tests: write_literature_csv (round-trip)
# ---------------------------------------------------------------------------

class TestWriteLiteratureCsv:
    def test_round_trip(self, tmp_path, sample_publications):
        path = str(tmp_path / "literature_summary.csv")
        write_literature_csv(sample_publications, path)
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3

    def test_correct_field_values(self, tmp_path, sample_publications):
        path = str(tmp_path / "literature_summary.csv")
        write_literature_csv(sample_publications, path)
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["drug_name"] == "semaglutide"
        assert rows[0]["journal"] == "NEJM"
        assert rows[0]["date"] == "2026-03"

    def test_all_fieldnames_present(self, tmp_path):
        path = str(tmp_path / "lit.csv")
        write_literature_csv([], path)
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        expected = {"drug_name", "title", "authors", "journal", "date", "abstract_excerpt"}
        assert expected.issubset(set(fieldnames))


# ---------------------------------------------------------------------------
# Tests: search_literature_for_drug (mocked)
# ---------------------------------------------------------------------------

class TestSearchLiteratureForDrug:
    def _make_client(self):
        return MagicMock()

    def test_returns_records_from_api(self):
        client = self._make_client()
        mock_hit = {
            "title": "Test Publication",
            "journal": "NEJM",
            "date": "2026-03",
        }
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_literature.literature.search",
            return_value={"literatureList": {"literature": [mock_hit]}},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_literature.time.sleep"
        ):
            records = search_literature_for_drug("semaglutide", client)

        assert len(records) == 1
        assert records[0]["title"] == "Test Publication"

    def test_handles_empty_results_gracefully(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_literature.literature.search",
            return_value={},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_literature.time.sleep"
        ):
            records = search_literature_for_drug("UnknownDrug", client)

        assert records == []

    def test_handles_api_exception_gracefully(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_literature.literature.search",
            side_effect=Exception("network error"),
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_literature.time.sleep"
        ):
            records = search_literature_for_drug("DrugY", client)

        assert records == []

    def test_sleeps_after_call(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_literature.literature.search",
            return_value={},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_literature.time.sleep"
        ) as mock_sleep:
            search_literature_for_drug("DrugQ", client)

        mock_sleep.assert_called_once_with(2)
