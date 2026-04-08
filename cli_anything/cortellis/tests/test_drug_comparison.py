"""
Tests for drug_comparison_generator.py and skill_router drug-comparison routing.
No real API calls — all data is mocked inline.
"""

import json
import os
import sys
import tempfile

import importlib.util

import pytest

# Ensure the project root is on the path for skill_router import
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
sys.path.insert(0, _PROJECT_ROOT)

# drug-comparison directory has a hyphen so it cannot be imported as a package.
# Load the generator module directly from its file path.
_GENERATOR_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "skills",
    "drug-comparison",
    "recipes",
    "drug_comparison_generator.py",
)
_spec = importlib.util.spec_from_file_location("drug_comparison_generator", _GENERATOR_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

discover_drugs = _mod.discover_drugs
extract_drug_profile = _mod.extract_drug_profile
extract_trial_summary = _mod.extract_trial_summary
extract_deal_summary = _mod.extract_deal_summary
identify_differentiators = _mod.identify_differentiators
generate_comparison_markdown = _mod.generate_comparison_markdown

from cli_anything.cortellis.core.skill_router import detect_skill


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

MOCK_DRUG_RECORD = {
    "drug": {
        "drugNameDisplay": "Tirzepatide",
        "highestPhaseDisplay": "Launched",
        "indications": [
            {"indicationDisplay": "Type 2 diabetes mellitus"},
            {"indicationDisplay": "Obesity"},
            {"indicationDisplay": "Heart failure"},
            {"indicationDisplay": "Sleep apnoea"},
        ],
        "actions": [{"actionDisplay": "GIP receptor agonist; GLP-1 receptor agonist"}],
        "technologies": [{"technologyDisplay": "Peptide"}],
        "originators": [{"companyNameDisplay": "Eli Lilly"}],
    }
}

MOCK_TRIALS_JSON = {
    "totalResults": 45,
    "hits": [
        {"trialStatusDisplay": "Recruiting", "trialPhaseDisplay": "Phase 3"},
        {"trialStatusDisplay": "Recruiting", "trialPhaseDisplay": "Phase 2"},
        {"trialStatusDisplay": "Completed", "trialPhaseDisplay": "Phase 3"},
        {"trialStatusDisplay": "Enrolling", "trialPhaseDisplay": "Phase 3"},
    ],
}

MOCK_DEALS_JSON = {
    "totalResults": 14,
    "hits": [
        {
            "dealDateStartDisplay": "2024-03",
            "dealTypeDisplay": "Licensing",
        },
        {
            "dealDateStartDisplay": "2023-11",
            "dealTypeDisplay": "Co-development",
        },
    ],
}


# ---------------------------------------------------------------------------
# test_discover_drugs
# ---------------------------------------------------------------------------


def test_discover_drugs():
    with tempfile.TemporaryDirectory() as tmpdir:
        for n in (1, 2, 3):
            with open(os.path.join(tmpdir, f"drug_{n}.json"), "w") as fh:
                json.dump({}, fh)
        # Extra file that should NOT be picked up
        with open(os.path.join(tmpdir, "trials_1.json"), "w") as fh:
            json.dump({}, fh)

        indices = discover_drugs(tmpdir)

    assert indices == [1, 2, 3]


# ---------------------------------------------------------------------------
# test_extract_drug_profile
# ---------------------------------------------------------------------------


def test_extract_drug_profile():
    profile = extract_drug_profile(MOCK_DRUG_RECORD)

    assert profile["name"] == "Tirzepatide"
    assert profile["phase"] == "Launched"
    assert profile["company"] == "Eli Lilly"
    assert profile["technology"] == "Peptide"
    assert profile["indication_count"] == 4
    assert "GIP" in profile["mechanism"] or "GLP-1" in profile["mechanism"]


# ---------------------------------------------------------------------------
# test_extract_trial_summary
# ---------------------------------------------------------------------------


def test_extract_trial_summary():
    summary = extract_trial_summary(MOCK_TRIALS_JSON)

    assert summary["total"] == 45
    # Recruiting + Enrolling = 3
    assert summary["recruiting"] == 3
    # Phase 3 count in hits = 3
    assert summary["phase3"] == 3


# ---------------------------------------------------------------------------
# test_identify_differentiators
# ---------------------------------------------------------------------------


def test_identify_differentiators():
    profiles = [
        {
            "name": "DrugA",
            "phase": "Launched",
            "mechanism": "GLP-1 agonist",
            "technology": "Peptide",
            "indication_count": 4,
            "indications": [],
            "company": "Novo Nordisk",
        },
        {
            "name": "DrugB",
            "phase": "Phase 3",
            "mechanism": "GLP-1 agonist",
            "technology": "Peptide",
            "indication_count": 2,
            "indications": [],
            "company": "Eli Lilly",
        },
    ]

    bullets = identify_differentiators(profiles)

    # Phase difference should produce a bullet
    phase_bullets = [b for b in bullets if "Launched" in b and "Phase 3" in b]
    assert phase_bullets, f"Expected phase-difference bullet, got: {bullets}"

    # Indication breadth should produce a bullet
    indication_bullets = [b for b in bullets if "indications" in b.lower()]
    assert indication_bullets, f"Expected indication-breadth bullet, got: {bullets}"


# ---------------------------------------------------------------------------
# test_generate_comparison_two_drugs
# ---------------------------------------------------------------------------


def test_generate_comparison_two_drugs():
    profiles = [
        {
            "name": "DrugA",
            "phase": "Launched",
            "mechanism": "GLP-1 agonist",
            "technology": "Peptide",
            "indication_count": 4,
            "indications": [],
            "company": "Novo Nordisk",
        },
        {
            "name": "DrugB",
            "phase": "Phase 3",
            "mechanism": "GIP/GLP-1 dual agonist",
            "technology": "Peptide",
            "indication_count": 2,
            "indications": [],
            "company": "Eli Lilly",
        },
    ]
    trial_summaries = [
        {"total": 45, "recruiting": 12, "phase3": 6},
        {"total": 28, "recruiting": 8, "phase3": 4},
    ]
    deal_summaries = [
        {"total": 14, "latest_date": "2024-03", "deal_types": "Licensing"},
        {"total": 8, "latest_date": "2023-11", "deal_types": "Co-development"},
    ]

    md = generate_comparison_markdown(profiles, trial_summaries, deal_summaries)

    # Title
    assert "# Drug Comparison: DrugA vs DrugB" in md
    # Overview table headers
    assert "| Attribute | DrugA | DrugB |" in md
    # Phase row
    assert "Launched" in md
    assert "Phase 3" in md
    # Clinical Trials section
    assert "## Clinical Trials" in md
    assert "| Total Trials | 45 | 28 |" in md
    # Deal Activity section
    assert "## Deal Activity" in md
    assert "| Total Deals | 14 | 8 |" in md
    # Differentiators section
    assert "## Key Differentiators" in md


# ---------------------------------------------------------------------------
# test_skill_router_vs_triggers
# ---------------------------------------------------------------------------


def test_skill_router_vs_triggers():
    questions = [
        "tirzepatide vs semaglutide",
        "compare drugs tirzepatide and semaglutide",
        "drug comparison: ozempic versus wegovy",
        "head to head tirzepatide semaglutide",
        "tirzepatide vs. semaglutide efficacy",
    ]
    for q in questions:
        result = detect_skill(q)
        assert result is not None, f"Expected drug-comparison routing for: {q!r}"
        assert "drug-comparison" in result, (
            f"Expected /drug-comparison directive for: {q!r}, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# test_skill_router_landscape_not_captured
# ---------------------------------------------------------------------------


def test_skill_router_landscape_not_captured():
    questions = [
        "obesity landscape",
        "competitive landscape for NASH",
        "GLP-1 landscape report",
    ]
    for q in questions:
        result = detect_skill(q)
        assert result is not None, f"Expected a skill routing for: {q!r}"
        assert "landscape" in result, (
            f"Expected /landscape routing for: {q!r}, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# TestExtractTrialSummary
# ---------------------------------------------------------------------------


class TestExtractTrialSummary:
    def test_counts_trials(self):
        """Mock trial JSON with hits list, verify total/recruiting/phase3 counts."""
        trials_json = {
            "totalResults": 25,
            "hits": [
                {"trialStatusDisplay": "Recruiting", "trialPhaseDisplay": "Phase 3"},
                {"trialStatusDisplay": "Recruiting", "trialPhaseDisplay": "Phase 2"},
                {"trialStatusDisplay": "Completed", "trialPhaseDisplay": "Phase 3"},
                {"trialStatusDisplay": "Not yet recruiting", "trialPhaseDisplay": "Phase 1"},
            ],
        }
        summary = extract_trial_summary(trials_json)
        assert summary["total"] == 25
        assert summary["recruiting"] == 2
        assert summary["phase3"] == 2

    def test_empty_trials(self):
        """Empty hits list returns zeros."""
        trials_json = {"totalResults": 0, "hits": []}
        summary = extract_trial_summary(trials_json)
        assert summary["total"] == 0
        assert summary["recruiting"] == 0
        assert summary["phase3"] == 0


# ---------------------------------------------------------------------------
# TestExtractDealSummary
# ---------------------------------------------------------------------------


class TestExtractDealSummary:
    def test_counts_deals(self):
        """Mock deal JSON with hits, verify total and type counts."""
        deals_json = {
            "totalResults": 5,
            "hits": [
                {"dealDateStartDisplay": "2024-03", "dealTypeDisplay": "Licensing"},
                {"dealDateStartDisplay": "2023-11", "dealTypeDisplay": "Co-development"},
                {"dealDateStartDisplay": "2024-01", "dealTypeDisplay": "Licensing"},
            ],
        }
        summary = extract_deal_summary(deals_json)
        assert summary["total"] == 5
        assert summary["latest_date"] == "2024-03"
        assert "Licensing" in summary["deal_types"]

    def test_empty_deals(self):
        """Empty hits returns zeros."""
        deals_json = {"totalResults": 0, "hits": []}
        summary = extract_deal_summary(deals_json)
        assert summary["total"] == 0
        assert summary["latest_date"] is None
        assert summary["deal_types"] is None


# ---------------------------------------------------------------------------
# TestGenerateComparisonFiveDrugs
# ---------------------------------------------------------------------------


class TestGenerateComparisonFiveDrugs:
    def test_five_drug_table(self):
        """Generate comparison with 5 drugs, verify table has 5 columns beyond the attribute column."""
        drug_names = ["DrugA", "DrugB", "DrugC", "DrugD", "DrugE"]
        profiles = [
            {
                "name": name,
                "phase": "Phase 3",
                "mechanism": f"Mechanism {i}",
                "technology": "Small molecule",
                "indication_count": i + 1,
                "indications": [],
                "company": f"Company {i}",
            }
            for i, name in enumerate(drug_names)
        ]
        trial_summaries = [{"total": i * 10, "recruiting": i, "phase3": i} for i in range(5)]
        deal_summaries = [{"total": i, "latest_date": None, "deal_types": None} for i in range(5)]

        md = generate_comparison_markdown(profiles, trial_summaries, deal_summaries)

        # Header row should contain all 5 drug name columns
        header_line = next(line for line in md.splitlines() if "| Attribute |" in line)
        for name in drug_names:
            assert name in header_line, f"{name} missing from table header: {header_line}"
        # Verify there are exactly 5 drug columns (split by | gives attribute + 5 names + trailing)
        cols = [c.strip() for c in header_line.split("|") if c.strip()]
        drug_cols = [c for c in cols if c != "Attribute"]
        assert len(drug_cols) == 5


# ---------------------------------------------------------------------------
# TestSkipEmptySections
# ---------------------------------------------------------------------------


class TestSkipEmptySections:
    def test_skips_when_no_trials(self):
        """If all drugs have zero trial totals, Clinical Trials section should show zeros."""
        profiles = [
            {
                "name": "DrugX",
                "phase": "Phase 2",
                "mechanism": "Kinase inhibitor",
                "technology": "Small molecule",
                "indication_count": 1,
                "indications": [],
                "company": "Acme",
            },
            {
                "name": "DrugY",
                "phase": "Phase 2",
                "mechanism": "Kinase inhibitor",
                "technology": "Small molecule",
                "indication_count": 1,
                "indications": [],
                "company": "Beta",
            },
        ]
        trial_summaries = [{"total": 0, "recruiting": 0, "phase3": 0}] * 2
        deal_summaries = [{"total": 0, "latest_date": None, "deal_types": None}] * 2

        md = generate_comparison_markdown(profiles, trial_summaries, deal_summaries)

        # Clinical Trials section must still be present but with zero values
        assert "## Clinical Trials" in md
        assert "| Total Trials | 0 | 0 |" in md
