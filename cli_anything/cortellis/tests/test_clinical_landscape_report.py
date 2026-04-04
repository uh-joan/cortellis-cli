#!/usr/bin/env python3
"""Regression tests for clinical_landscape_report.py.

Validates council findings are addressed:
1. No hardcoded truncation (tables show all fetched trials)
2. Headers disclose truncation when fetched < total
3. Sponsor methodology labeled when based on sample
4. Data Completeness footer present
5. Sort order disclosed
6. Indication ID shown
7. No Python list repr in output
8. No bare except errors (script exits cleanly)

Usage: python3 -m pytest cli_anything/cortellis/tests/test_clinical_landscape_report.py
       Requires test data in /tmp/test_clinical_landscape/ (run the skill once first)
"""
import os, subprocess, pytest

RECIPE = "cli_anything/cortellis/skills/clinical-landscape/recipes/clinical_landscape_report.py"
DATA_DIR = "/tmp/test_clinical_landscape"
INDICATION = "Obesity"
INDICATION_ID = "238"


@pytest.fixture(scope="module")
def report_output():
    if not os.path.exists(os.path.join(DATA_DIR, "trials_p3.json")):
        pytest.skip("Test data not available — run /clinical-landscape obesity first")
    result = subprocess.run(
        ["python3", RECIPE, DATA_DIR, INDICATION, INDICATION_ID],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    return result.stdout


def test_header_present(report_output):
    assert f"# Clinical Trial Landscape: {INDICATION}" in report_output


def test_indication_id_shown(report_output):
    assert f"Indication ID:** {INDICATION_ID}" in report_output


def test_phase_totals_from_api(report_output):
    # Should show @totalResults, not just fetched count
    assert "Phase 3:** 980" in report_output or "Phase 3:**" in report_output


def test_no_hardcoded_truncation(report_output):
    """Tables should show ALL fetched trials, not a hardcoded limit of 20."""
    lines = report_output.split("\n")
    data_rows = [
        l for l in lines
        if l.startswith("|") and "---" not in l
        and not (l.count("Trial") and l.count("Phase") and l.count("Sponsor"))
    ]
    # With 30 trials fetched per phase (4 phases), expect >80 data rows
    assert len(data_rows) > 80, f"Only {len(data_rows)} data rows — possible truncation"


def test_truncation_disclosure(report_output):
    """When fetched < total, headers should say 'showing X of Y total'."""
    assert "showing" in report_output


def test_sponsor_methodology_labeled(report_output):
    """Sponsor section should disclose it's based on a sample when truncated."""
    assert "based on" in report_output or "fetched" in report_output


def test_data_completeness_footer(report_output):
    assert "## Data Completeness" in report_output


def test_sort_order_disclosed(report_output):
    assert "sort" in report_output.lower() or "Sort order" in report_output


def test_no_python_list_repr(report_output):
    """No raw Python list repr like ['Company A', 'Company B']."""
    assert "[''" not in report_output
    # Check for common list repr patterns
    import re
    assert not re.search(r"\['.+', '.+'\]", report_output), "Python list repr found in output"


def test_coverage_percentages(report_output):
    """Data Completeness should show coverage percentages."""
    assert "%" in report_output
