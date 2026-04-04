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
    assert isinstance(data, dict)
    assert "drugResultsOutput" in data, f"Unexpected response keys: {list(data.keys())}"
    total = int(data["drugResultsOutput"].get("@totalResults", "0"))
    assert total > 0, "Expected at least one drug result"


def test_drugs_get_tirzepatide(runner):
    """drugs get 101964 --category report should return tirzepatide data."""
    result = _invoke(runner, ["--json", "drugs", "get", "101964", "--category", "report"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert "drugRecordOutput" in data, f"Unexpected response keys: {list(data.keys())}"


def test_companies_search(runner):
    """companies search --query should return at least one company."""
    result = _invoke(runner, ["--json", "companies", "search",
                              "--query", "companyNameDisplay:Pfizer", "--hits", "3"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert "companyResultsOutput" in data, f"Unexpected response keys: {list(data.keys())}"
    total = int(data["companyResultsOutput"].get("@totalResults", "0"))
    assert total > 0, "Expected at least one company result"


def test_json_output_mode(runner):
    """--json flag should produce valid JSON output."""
    result = _invoke(runner, ["--json", "drugs", "search", "--phase", "L", "--hits", "1"])
    assert result.exit_code == 0, result.output
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
    """ontology top-level --category indication should return taxonomy tree."""
    result = _invoke(runner, ["--json", "ontology", "top-level", "--category", "indication"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert "ontologyTreeOutput" in data, f"Unexpected response keys: {list(data.keys())}"


def test_ner_match(runner):
    """ner match should recognize a drug entity."""
    result = _invoke(runner, ["--json", "ner", "match", "semaglutide"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert "NamedEntityRecognition" in data, f"Unexpected response keys: {list(data.keys())}"
