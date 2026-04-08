"""Tests for the drug profile wiki compiler."""

import importlib.util
import json
import os
import sys

import pytest

# drug-profile directory has a hyphen so it cannot be imported as a package.
# Load compile_drug directly from its file path.
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
sys.path.insert(0, _PROJECT_ROOT)

_COMPILE_DRUG_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "skills",
    "drug-profile",
    "recipes",
    "compile_drug.py",
)
_spec = importlib.util.spec_from_file_location("compile_drug", _COMPILE_DRUG_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

compile_drug_article = _mod.compile_drug_article
extract_drug_overview = _mod.extract_drug_overview
extract_deals_summary = _mod.extract_deals_summary
extract_trials_summary = _mod.extract_trials_summary
extract_competitors = _mod.extract_competitors
read_json_safe = _mod.read_json_safe
from cli_anything.cortellis.utils.wiki import (
    article_path,
    load_index_entries,
    update_index,
    wiki_root,
    write_article,
    read_article,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RECORD = {
    "drugRecordOutput": {
        "@id": "12345",
        "DrugName": "Semaglutide",
        "PhaseHighest": {"$": "Launched"},
        "CompanyOriginator": {"$": "Novo Nordisk"},
        "IndicationsPrimary": {
            "Indication": [
                {"$": "obesity"},
                {"$": "diabetes"},
                {"$": "cardiovascular"},
            ]
        },
        "ActionsPrimary": {
            "Action": [{"$": "GLP-1 receptor agonist"}]
        },
        "Technologies": {
            "Technology": [{"$": "Peptide"}]
        },
        "TherapyAreas": {
            "TherapyArea": ["Endocrinology", "Cardiovascular"]
        },
    }
}

COMPETITORS = {
    "drugResultsOutput": {
        "SearchResults": {
            "Drug": [
                {
                    "@name": "Tirzepatide",
                    "@phaseHighest": "Launched",
                    "CompanyOriginator": {"$": "Eli Lilly"},
                    "ActionsPrimary": {"Action": [{"$": "GLP-1 receptor agonist"}]},
                },
                {
                    "@name": "Dulaglutide",
                    "@phaseHighest": "Launched",
                    "CompanyOriginator": {"$": "Eli Lilly"},
                    "ActionsPrimary": {"Action": [{"$": "GLP-1 receptor agonist"}]},
                },
            ]
        }
    }
}

DEALS = {
    "dealResultsOutput": {
        "@totalResults": "2",
        "SearchResults": {
            "Deal": [
                {
                    "Title": "Semaglutide licensing deal",
                    "CompanyPartner": "AstraZeneca",
                    "Type": "Licensing",
                    "StartDate": "2023-01-15",
                },
                {
                    "Title": "Semaglutide co-promotion",
                    "CompanyPartner": "Pfizer",
                    "Type": "Co-promotion",
                    "StartDate": "2022-06-01",
                },
            ]
        },
    }
}

TRIALS = {
    "trialResultsOutput": {
        "@totalResults": "5",
        "SearchResults": {
            "Trial": [
                {
                    "TitleDisplay": "SUSTAIN-1: Semaglutide in T2D",
                    "Phase": "Phase 3",
                    "RecruitmentStatus": "Recruiting",
                    "PatientCountEnrollment": "3000",
                },
                {
                    "TitleDisplay": "SELECT: CV outcomes trial",
                    "Phase": "Phase 3",
                    "RecruitmentStatus": "Completed",
                    "PatientCountEnrollment": "17604",
                },
            ]
        },
    }
}

SWOT = {
    "drugSwotsOutput": {
        "Strengths": "Market leader in GLP-1 class with strong efficacy data.",
        "Weaknesses": "High cost limits access in some markets.",
        "Opportunities": "Expanding to MASH and CKD indications.",
        "Threats": "Increasing competition from tirzepatide.",
    }
}

HISTORY = {
    "ChangeHistory": {
        "Change": [
            {
                "Date": "2021-06-04",
                "Reason": {"$": "Highest status change"},
                "FieldsChanged": {
                    "Field": {"@oldValue": "Registered", "@newValue": "Launched"}
                },
            },
            {
                "Date": "2017-12-05",
                "Reason": {"$": "Highest status change"},
                "FieldsChanged": {
                    "Field": {"@oldValue": "Phase 3", "@newValue": "Registered"}
                },
            },
        ]
    }
}


def write_mock_files(drug_dir, include_swot=True, include_history=True,
                     include_deals=True, include_trials=True, include_competitors=True):
    """Write mock JSON files to drug_dir."""
    os.makedirs(drug_dir, exist_ok=True)
    with open(os.path.join(drug_dir, "record.json"), "w") as f:
        json.dump(RECORD, f)
    if include_swot:
        with open(os.path.join(drug_dir, "swot.json"), "w") as f:
            json.dump(SWOT, f)
    if include_history:
        with open(os.path.join(drug_dir, "history.json"), "w") as f:
            json.dump(HISTORY, f)
    if include_deals:
        with open(os.path.join(drug_dir, "deals.json"), "w") as f:
            json.dump(DEALS, f)
    if include_trials:
        with open(os.path.join(drug_dir, "trials.json"), "w") as f:
            json.dump(TRIALS, f)
    if include_competitors:
        with open(os.path.join(drug_dir, "competitors.json"), "w") as f:
            json.dump(COMPETITORS, f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCompileCreatesDrugArticle:
    def test_compile_creates_drug_article(self, tmp_path):
        drug_dir = str(tmp_path / "raw" / "semaglutide")
        write_mock_files(drug_dir)
        base_dir = str(tmp_path)

        meta, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")
        drug_path = article_path("drugs", "semaglutide", base_dir)
        write_article(drug_path, meta, body)

        assert os.path.exists(drug_path)
        art = read_article(drug_path)
        assert art is not None
        assert art["meta"]["title"] == "Semaglutide"
        assert art["meta"]["slug"] == "semaglutide"

    def test_article_path_is_under_wiki_drugs(self, tmp_path):
        drug_dir = str(tmp_path / "raw" / "semaglutide")
        write_mock_files(drug_dir)
        base_dir = str(tmp_path)

        meta, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")
        drug_path = article_path("drugs", "semaglutide", base_dir)
        write_article(drug_path, meta, body)

        expected = os.path.join(base_dir, "wiki", "drugs", "semaglutide.md")
        assert drug_path == expected
        assert os.path.exists(expected)


class TestFrontmatterFields:
    def test_frontmatter_fields(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        meta, _ = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert meta["type"] == "drug"
        assert meta["phase"] == "Launched"
        assert meta["originator"] == "Novo Nordisk"
        assert meta["mechanism"] == "GLP-1 receptor agonist"
        assert meta["slug"] == "semaglutide"
        assert meta["compiled_at"] != ""

    def test_indication_count_and_list(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        meta, _ = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert meta["indication_count"] == 3
        assert "obesity" in meta["indications"]
        assert "diabetes" in meta["indications"]

    def test_related_includes_originator_slug(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        meta, _ = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "novo-nordisk" in meta["related"]


class TestBodyHasSections:
    def test_body_has_overview_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## Overview" in body

    def test_body_has_competitive_landscape_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## Competitive Landscape" in body

    def test_body_has_data_sources_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## Data Sources" in body

    def test_body_has_deals_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## Deals" in body

    def test_body_has_clinical_trials_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## Clinical Trials" in body


class TestOptionalSectionsSkipped:
    def test_no_swot_json_means_no_swot_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir, include_swot=False)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## SWOT" not in body

    def test_no_history_json_means_no_history_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir, include_history=False)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## Development History" not in body

    def test_no_deals_json_means_no_deals_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir, include_deals=False)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## Deals" not in body

    def test_no_trials_json_means_no_trials_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir, include_trials=False)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "## Clinical Trials" not in body


class TestUpdatesIndex:
    def test_updates_index(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)
        base_dir = str(tmp_path)

        meta, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")
        drug_path = article_path("drugs", "semaglutide", base_dir)
        write_article(drug_path, meta, body)

        w_dir = wiki_root(base_dir)
        entries = load_index_entries(w_dir)
        update_index(w_dir, entries)

        index_path = os.path.join(w_dir, "INDEX.md")
        assert os.path.exists(index_path)
        content = open(index_path).read()
        assert "semaglutide" in content.lower()

    def test_index_contains_drug_section(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)
        base_dir = str(tmp_path)

        meta, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")
        drug_path = article_path("drugs", "semaglutide", base_dir)
        write_article(drug_path, meta, body)

        w_dir = wiki_root(base_dir)
        entries = load_index_entries(w_dir)
        update_index(w_dir, entries)

        index_path = os.path.join(w_dir, "INDEX.md")
        content = open(index_path).read()
        assert "## Drugs" in content


class TestWikilinksForCompanies:
    def test_wikilinks_for_originator(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert r"[[novo-nordisk\|Novo Nordisk]]" in body

    def test_wikilinks_for_competitor_companies(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert r"[[eli-lilly\|Eli Lilly]]" in body

    def test_wikilinks_for_indications(self, tmp_path):
        drug_dir = str(tmp_path / "drug")
        write_mock_files(drug_dir)

        _, body = compile_drug_article(drug_dir, "Semaglutide", "semaglutide")

        assert "[[obesity]]" in body
        assert "[[diabetes]]" in body
