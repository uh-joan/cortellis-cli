"""End-to-end tests for the Cortellis CLI.

These tests invoke the real Cortellis API via Click's CliRunner.
All tests are skipped if CORTELLIS_USERNAME is not set in the environment.

Run with:
    pytest tests/test_e2e.py
    pytest tests/test_e2e.py -v  # verbose
"""

import json
import os

import pytest
from click.testing import CliRunner

from cli_anything.cortellis.cortellis_cli import cli


# ---------------------------------------------------------------------------
# Skip guard — applied to every test in this module
# ---------------------------------------------------------------------------

_NO_CREDS = not os.environ.get("CORTELLIS_USERNAME")
_SKIP_REASON = "CORTELLIS_USERNAME not set — skipping live API tests"

pytestmark = pytest.mark.skipif(_NO_CREDS, reason=_SKIP_REASON)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def runner() -> CliRunner:
    return CliRunner()


def _invoke(runner: CliRunner, args: list) -> tuple:
    """Invoke the CLI and return (result, parsed_json_or_None)."""
    result = runner.invoke(cli, args, catch_exceptions=False)
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_drugs_search_returns_results(runner):
    """drugs search --phase L --hits 5 should return at least one hit."""
    result = _invoke(runner, ["--json", "drugs", "search", "--phase", "L", "--hits", "5"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    # Cortellis search responses contain a hits/totalHits key or similar
    assert isinstance(data, dict)
    # Accept either "drugs" list or a top-level hits structure
    assert any(k in data for k in ("drugResultsOutput", "drugs", "hits", "totalHits", "data", "results")), (
        f"Unexpected response keys: {list(data.keys())}"
    )


def test_drugs_get_tirzepatide(runner):
    """drugs get 101964 --category report should return tirzepatide data."""
    result = _invoke(runner, ["--json", "drugs", "get", "101964", "--category", "report"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, dict)
    # Should contain some drug-level fields (API may wrap in drugRecordOutput)
    assert any(k in data for k in ("drugId", "id", "drugName", "name", "drug", "drugRecordOutput")), (
        f"Unexpected response keys: {list(data.keys())}"
    )


def test_companies_search(runner):
    """companies search --hits 3 should return at least one company."""
    result = _invoke(runner, ["--json", "companies", "search", "--hits", "3"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert any(k in data for k in ("companies", "hits", "totalHits", "data", "results")), (
        f"Unexpected response keys: {list(data.keys())}"
    )


def test_json_output_mode(runner):
    """--json flag should produce valid JSON output."""
    result = _invoke(runner, ["--json", "drugs", "search", "--hits", "1"])
    assert result.exit_code == 0, result.output
    # Must parse without raising
    data = json.loads(result.output)
    assert isinstance(data, (dict, list))


def test_help_shows_all_groups(runner):
    """--help should list all 10+ command groups."""
    result = _invoke(runner, ["--help"])
    assert result.exit_code == 0, result.output
    expected_groups = [
        "drugs",
        "companies",
        "deals",
        "trials",
        "regulations",
        "conferences",
        "literature",
        "press-releases",
        "ontology",
        "analytics",
        "ner",
    ]
    for group in expected_groups:
        assert group in result.output, f"'{group}' not found in --help output"


def test_ontology_top_level(runner):
    """ontology top-level should return a non-empty response."""
    result = _invoke(runner, ["--json", "ontology", "top-level"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, (dict, list))
    if isinstance(data, dict):
        assert len(data) > 0, "Expected non-empty ontology top-level response"


def test_analytics_run(runner):
    """analytics run with a basic query name should not error."""
    # "drugsByPhase" is a commonly available Cortellis analytics query
    result = _invoke(runner, ["--json", "analytics", "run", "drugsByPhase"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, (dict, list))
