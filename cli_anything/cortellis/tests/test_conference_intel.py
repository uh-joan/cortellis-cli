"""Unit tests for conference_briefing.py and conference-intel skill router triggers.

No real API calls — all data is constructed in-memory.

Run with:
    pytest cli_anything/cortellis/tests/test_conference_intel.py -v
"""
from __future__ import annotations

import json
import os
import sys

import pytest

import importlib.util

# Ensure the project root is on the path for skill_router import
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
sys.path.insert(0, _PROJECT_ROOT)

# conference-intel directory has a hyphen so it cannot be imported as a package.
# Load the briefing module directly from its file path.
_BRIEFING_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "skills",
    "conference-intel",
    "recipes",
    "conference_briefing.py",
)
_spec = importlib.util.spec_from_file_location("conference_briefing", _BRIEFING_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

generate_briefing = _mod.generate_briefing
cross_reference_wiki = _mod.cross_reference_wiki
load_conference_data = _mod.load_conference_data

from cli_anything.cortellis.core.skill_router import detect_skill


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_conferences():
    return [
        {
            "id": "conf001",
            "name": "ASCO 2026 Annual Meeting",
            "dates": "2026-06-01",
            "location": "Chicago, IL",
            "presentations": [
                {
                    "title": "Phase 3 results for semaglutide in obesity",
                    "drug": "semaglutide",
                    "company": "Novo Nordisk",
                },
                {
                    "title": "Tirzepatide cardiovascular outcomes",
                    "drug": "tirzepatide",
                    "company": "Eli Lilly",
                },
            ],
        },
        {
            "id": "conf002",
            "name": "ESMO Congress 2026",
            "dates": "2026-09-15",
            "location": "Barcelona, Spain",
        },
    ]


@pytest.fixture()
def wiki_dir(tmp_path):
    """Create a minimal wiki directory with indication and company articles."""
    wiki = tmp_path / "wiki"
    indications = wiki / "indications"
    companies = wiki / "companies"
    indications.mkdir(parents=True)
    companies.mkdir(parents=True)

    (indications / "obesity.md").write_text(
        "---\ntitle: Obesity\n---\n\n## Overview\nsemaglutide is a leading drug in obesity.\n",
        encoding="utf-8",
    )
    (companies / "novo-nordisk.md").write_text(
        "---\ntitle: Novo Nordisk\n---\n\n## Overview\nNovo Nordisk leads in GLP-1 therapies.\n",
        encoding="utf-8",
    )
    return str(wiki)


# ---------------------------------------------------------------------------
# Tests: generate_briefing
# ---------------------------------------------------------------------------

class TestGenerateBriefing:
    def test_contains_whats_new_section(self, sample_conferences):
        md = generate_briefing(sample_conferences, {}, "ASCO 2026")
        assert "## What's New" in md

    def test_contains_so_what_section(self, sample_conferences):
        md = generate_briefing(sample_conferences, {}, "ASCO 2026")
        assert "## So What" in md

    def test_contains_whats_next_section(self, sample_conferences):
        md = generate_briefing(sample_conferences, {}, "ASCO 2026")
        assert "## What's Next" in md

    def test_conference_names_in_output(self, sample_conferences):
        md = generate_briefing(sample_conferences, {}, "ASCO 2026")
        assert "ASCO 2026 Annual Meeting" in md
        assert "ESMO Congress 2026" in md

    def test_query_in_heading(self, sample_conferences):
        md = generate_briefing(sample_conferences, {}, "obesity conferences")
        assert "obesity conferences" in md

    def test_cross_refs_highlighted(self, sample_conferences):
        cross_refs = {"semaglutide": ["obesity"], "Novo Nordisk": ["novo-nordisk"]}
        md = generate_briefing(sample_conferences, cross_refs, "ASCO 2026")
        assert "semaglutide" in md
        assert "Novo Nordisk" in md
        assert "## Cross-References with Compiled Knowledge" in md

    def test_conference_count_in_output(self, sample_conferences):
        md = generate_briefing(sample_conferences, {}, "ASCO 2026")
        assert "2" in md  # 2 conferences found

    def test_presentation_titles_shown(self, sample_conferences):
        md = generate_briefing(sample_conferences, {}, "ASCO 2026")
        assert "semaglutide" in md


# ---------------------------------------------------------------------------
# Tests: cross_reference_wiki
# ---------------------------------------------------------------------------

class TestCrossReferenceWiki:
    def test_finds_drug_in_wiki(self, sample_conferences, wiki_dir):
        cross_refs = cross_reference_wiki(sample_conferences, wiki_dir)
        # semaglutide appears in the obesity wiki article
        assert "semaglutide" in cross_refs

    def test_finds_company_in_wiki(self, sample_conferences, wiki_dir):
        cross_refs = cross_reference_wiki(sample_conferences, wiki_dir)
        assert "Novo Nordisk" in cross_refs

    def test_empty_wiki_dir_returns_empty(self, sample_conferences, tmp_path):
        cross_refs = cross_reference_wiki(sample_conferences, str(tmp_path / "nonexistent"))
        assert cross_refs == {}

    def test_returns_dict(self, sample_conferences, wiki_dir):
        cross_refs = cross_reference_wiki(sample_conferences, wiki_dir)
        assert isinstance(cross_refs, dict)

    def test_values_are_lists(self, sample_conferences, wiki_dir):
        cross_refs = cross_reference_wiki(sample_conferences, wiki_dir)
        for val in cross_refs.values():
            assert isinstance(val, list)


# ---------------------------------------------------------------------------
# Tests: empty conferences
# ---------------------------------------------------------------------------

class TestEmptyConferences:
    def test_empty_produces_message(self):
        md = generate_briefing([], {}, "oncology")
        assert "No conference data found" in md or "No recent conference activity" in md

    def test_empty_still_has_sections(self):
        md = generate_briefing([], {}, "oncology")
        assert "## What's New" in md
        assert "## So What" in md
        assert "## What's Next" in md

    def test_load_conference_data_nonexistent_dir(self, tmp_path):
        confs = load_conference_data(str(tmp_path / "nonexistent"))
        assert confs == []

    def test_load_conference_data_reads_json_files(self, tmp_path):
        data = {"name": "Test Conference", "id": "tc001"}
        (tmp_path / "conference_tc001.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        confs = load_conference_data(str(tmp_path))
        assert len(confs) == 1
        assert confs[0]["name"] == "Test Conference"

    def test_load_conference_data_handles_search_result_shape(self, tmp_path):
        data = {
            "conferenceList": {
                "conference": [
                    {"name": "Conf A", "id": "a1"},
                    {"name": "Conf B", "id": "b2"},
                ]
            }
        }
        (tmp_path / "search_results.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        confs = load_conference_data(str(tmp_path))
        assert len(confs) == 2


# ---------------------------------------------------------------------------
# Tests: skill router conference triggers
# ---------------------------------------------------------------------------

class TestSkillRouterConferenceTriggers:
    def test_asco_routes_to_conference_intel(self):
        result = detect_skill("ASCO 2026 annual meeting highlights")
        assert result is not None
        assert "conference-intel" in result

    def test_esmo_routes_to_conference_intel(self):
        result = detect_skill("What was presented at ESMO this year?")
        assert result is not None
        assert "conference-intel" in result

    def test_ash_routes_to_conference_intel(self):
        result = detect_skill("ASH 2025 key abstracts")
        assert result is not None
        assert "conference-intel" in result

    def test_conference_keyword_routes(self):
        result = detect_skill("obesity conferences 2026")
        assert result is not None
        assert "conference-intel" in result

    def test_congress_keyword_routes(self):
        result = detect_skill("European congress on cardiovascular disease")
        assert result is not None
        assert "conference-intel" in result

    def test_abstracts_keyword_routes(self):
        result = detect_skill("late-breaking abstracts in oncology")
        assert result is not None
        assert "conference-intel" in result

    def test_explicit_command_not_rerouted(self):
        # User already typed /landscape — should not be overridden
        result = detect_skill("/landscape obesity")
        assert result is None
