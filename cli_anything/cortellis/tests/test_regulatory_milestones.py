"""Unit tests for enrich_regulatory_milestones.py.

No real API calls — all Cortellis interactions are mocked.

Run with:
    pytest cli_anything/cortellis/tests/test_regulatory_milestones.py -v
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

from cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones import (
    classify_milestone,
    generate_timeline_markdown,
    get_top_drug_names,
    write_milestones_csv,
    search_regulatory_for_drug,
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
        "101,DrugA,CompanyX,Launched\n"
        "102,DrugB,CompanyY,Launched\n",
        encoding="utf-8",
    )
    phase3_path = tmp_path / "phase3.csv"
    phase3_path.write_text(
        "id,name,company,phase\n"
        "201,DrugC,CompanyZ,Phase 3\n"
        "202,DrugD,CompanyW,Phase 3\n",
        encoding="utf-8",
    )
    return str(tmp_path)


@pytest.fixture()
def sample_events():
    return [
        {
            "event_id": "e1",
            "drug_name": "DrugA",
            "region": "USA",
            "doc_category": "NDA",
            "doc_type": "approval",
            "date": "2022-03-15",
            "title": "DrugA NDA Approval",
            "milestone_type": "approval",
        },
        {
            "event_id": "e2",
            "drug_name": "DrugA",
            "region": "EU",
            "doc_category": "MAA",
            "doc_type": "submission",
            "date": "2021-07-10",
            "title": "DrugA MAA Submission",
            "milestone_type": "submission",
        },
        {
            "event_id": "e3",
            "drug_name": "DrugB",
            "region": "Japan",
            "doc_category": "Label",
            "doc_type": "labeling",
            "date": "2023-11-01",
            "title": "DrugB Label Update",
            "milestone_type": "label_change",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: get_top_drug_names
# ---------------------------------------------------------------------------

class TestGetTopDrugNames:
    def test_reads_launched_first(self, landscape_dir):
        names = get_top_drug_names(landscape_dir)
        assert names[0] == "DrugA"
        assert names[1] == "DrugB"

    def test_appends_phase3_after_launched(self, landscape_dir):
        names = get_top_drug_names(landscape_dir)
        assert "DrugC" in names
        assert "DrugD" in names
        # Launched come before phase3
        assert names.index("DrugA") < names.index("DrugC")

    def test_caps_at_max_drugs(self, landscape_dir):
        names = get_top_drug_names(landscape_dir, max_drugs=2)
        assert len(names) == 2

    def test_deduplicates_names(self, tmp_path):
        # Put the same drug in both files
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

    def test_empty_launched_falls_back_to_phase3(self, tmp_path):
        (tmp_path / "launched.csv").write_text("id,name,company\n", encoding="utf-8")
        (tmp_path / "phase3.csv").write_text(
            "id,name,company\n201,DrugP3,Co\n", encoding="utf-8"
        )
        names = get_top_drug_names(str(tmp_path))
        assert names == ["DrugP3"]


# ---------------------------------------------------------------------------
# Tests: classify_milestone
# ---------------------------------------------------------------------------

class TestClassifyMilestone:
    def test_approval(self):
        event = {"doc_type": "NDA Approval", "doc_category": ""}
        assert classify_milestone(event) == "approval"

    def test_approval_marketing_authorization(self):
        event = {"doc_type": "Marketing Authorization", "doc_category": ""}
        assert classify_milestone(event) == "approval"

    def test_submission_nda(self):
        event = {"doc_type": "NDA Filing", "doc_category": ""}
        assert classify_milestone(event) == "submission"

    def test_submission_bla(self):
        event = {"doc_type": "", "doc_category": "BLA Submission"}
        assert classify_milestone(event) == "submission"

    def test_submission_maa(self):
        event = {"doc_type": "MAA", "doc_category": ""}
        assert classify_milestone(event) == "submission"

    def test_submission_application(self):
        event = {"doc_type": "application", "doc_category": ""}
        assert classify_milestone(event) == "submission"

    def test_label_change_label(self):
        event = {"doc_type": "Label Change", "doc_category": ""}
        assert classify_milestone(event) == "label_change"

    def test_label_change_supplement(self):
        event = {"doc_type": "", "doc_category": "Supplement"}
        assert classify_milestone(event) == "label_change"

    def test_advisory_committee(self):
        event = {"doc_type": "Advisory Committee Meeting", "doc_category": ""}
        assert classify_milestone(event) == "advisory_committee"

    def test_other(self):
        event = {"doc_type": "Orphan Drug Designation", "doc_category": "misc"}
        assert classify_milestone(event) == "other"

    def test_empty_fields(self):
        event = {"doc_type": "", "doc_category": ""}
        assert classify_milestone(event) == "other"

    def test_missing_keys(self):
        assert classify_milestone({}) == "other"


# ---------------------------------------------------------------------------
# Tests: write_milestones_csv
# ---------------------------------------------------------------------------

class TestWriteMilestonesCsv:
    def test_writes_header_only_when_empty(self, tmp_path):
        path = str(tmp_path / "milestones.csv")
        write_milestones_csv([], path)
        assert os.path.exists(path)
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows == []

    def test_writes_all_events(self, tmp_path, sample_events):
        path = str(tmp_path / "milestones.csv")
        write_milestones_csv(sample_events, path)
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3

    def test_row_fields(self, tmp_path, sample_events):
        path = str(tmp_path / "milestones.csv")
        write_milestones_csv(sample_events, path)
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["drug_name"] == "DrugA"
        assert rows[0]["region"] == "USA"
        assert rows[0]["milestone_type"] == "approval"

    def test_classifies_missing_milestone_type(self, tmp_path):
        events = [
            {
                "event_id": "x1",
                "drug_name": "DrugX",
                "region": "USA",
                "doc_category": "NDA",
                "doc_type": "approval",
                "date": "2022-01-01",
                "title": "Test",
                # no milestone_type key
            }
        ]
        path = str(tmp_path / "milestones.csv")
        write_milestones_csv(events, path)
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["milestone_type"] == "approval"


# ---------------------------------------------------------------------------
# Tests: generate_timeline_markdown
# ---------------------------------------------------------------------------

class TestGenerateTimelineMarkdown:
    def test_contains_heading(self, sample_events):
        md = generate_timeline_markdown(sample_events, "Diabetes")
        assert "## Regulatory Timeline: Diabetes" in md

    def test_contains_recent_section(self, sample_events):
        md = generate_timeline_markdown(sample_events, "Test")
        assert "### Recent & Upcoming" in md

    def test_contains_historical_section(self, sample_events):
        md = generate_timeline_markdown(sample_events, "Test")
        assert "### Historical" in md

    def test_contains_summary_section(self, sample_events):
        md = generate_timeline_markdown(sample_events, "Test")
        assert "### Summary" in md

    def test_summary_counts_drugs(self, sample_events):
        md = generate_timeline_markdown(sample_events, "Test")
        # 2 unique drugs (DrugA and DrugB)
        assert "2 drugs with regulatory activity" in md

    def test_summary_counts_approvals_and_submissions(self, sample_events):
        md = generate_timeline_markdown(sample_events, "Test")
        assert "1 approvals" in md
        assert "1 submissions" in md

    def test_summary_coverage(self, sample_events):
        md = generate_timeline_markdown(sample_events, "Test")
        assert "Coverage:" in md
        assert "USA" in md
        assert "EU" in md
        assert "Japan" in md

    def test_empty_events_produces_message(self):
        md = generate_timeline_markdown([], "Oncology")
        assert "## Regulatory Timeline: Oncology" in md
        assert "_No recent or upcoming regulatory events found._" in md
        assert "_No historical regulatory events found._" in md
        assert "0 drugs with regulatory activity" in md

    def test_table_rows_present(self, sample_events):
        md = generate_timeline_markdown(sample_events, "Test")
        # At least some table rows should appear
        assert "DrugA" in md or "DrugB" in md


# ---------------------------------------------------------------------------
# Tests: search_regulatory_for_drug (mocked)
# ---------------------------------------------------------------------------

class TestSearchRegulatoryForDrug:
    def _make_client(self):
        return MagicMock()

    def test_returns_events_from_all_regions(self):
        client = self._make_client()
        mock_hit = {
            "id": "r001",
            "docType": "NDA Approval",
            "docCategory": "approval",
            "date": "2023-01-01",
            "title": "Test Approval",
        }
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.regulatory.search",
            return_value={"regulatoryDocumentList": {"regulatoryDocument": [mock_hit]}},
        ) as mock_search, patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.time.sleep"
        ):
            events = search_regulatory_for_drug("DrugX", client, regions=["USA", "EU"])

        assert mock_search.call_count == 2
        assert len(events) == 2
        assert all(e["drug_name"] == "DrugX" for e in events)
        regions_found = {e["region"] for e in events}
        assert regions_found == {"USA", "EU"}

    def test_handles_empty_results_gracefully(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.regulatory.search",
            return_value={},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.time.sleep"
        ):
            events = search_regulatory_for_drug("UnknownDrug", client, regions=["USA"])

        assert events == []

    def test_handles_api_exception_gracefully(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.regulatory.search",
            side_effect=Exception("network error"),
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.time.sleep"
        ):
            # Should not raise; returns empty
            events = search_regulatory_for_drug("DrugY", client, regions=["USA"])

        assert events == []

    def test_event_fields_populated(self):
        client = self._make_client()
        mock_hit = {
            "id": "abc123",
            "docType": "BLA submission",
            "docCategory": "Biologics",
            "date": "2022-06-15",
            "title": "BLA for DrugZ",
        }
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.regulatory.search",
            return_value={"regulatoryDocumentList": {"regulatoryDocument": [mock_hit]}},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.time.sleep"
        ):
            events = search_regulatory_for_drug("DrugZ", client, regions=["USA"])

        assert len(events) == 1
        e = events[0]
        assert e["event_id"] == "abc123"
        assert e["drug_name"] == "DrugZ"
        assert e["region"] == "USA"
        assert e["doc_type"] == "BLA submission"
        assert e["date"] == "2022-06-15"
        assert e["title"] == "BLA for DrugZ"

    def test_sleeps_between_regions(self):
        client = self._make_client()
        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.regulatory.search",
            return_value={},
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_regulatory_milestones.time.sleep"
        ) as mock_sleep:
            search_regulatory_for_drug("DrugQ", client, regions=["USA", "EU", "Japan"])

        assert mock_sleep.call_count == 3
