"""Tests for the session insights extractor module."""

import os
from datetime import datetime, timezone


from cli_anything.cortellis.utils.insights_extractor import (
    extract_key_findings,
    extract_scenarios,
    extract_opportunities,
    extract_session_insights,
    write_session_insight,
    load_recent_insights,
    format_insights_for_prompt,
)


# ---------------------------------------------------------------------------
# TestExtractKeyFindings
# ---------------------------------------------------------------------------

class TestExtractKeyFindings:
    def test_extracts_bullets_from_executive_summary(self):
        md = "## Executive Summary\n\n- Finding 1\n- Finding 2\n\n## Next Section\n"
        findings = extract_key_findings(md)
        assert len(findings) == 2
        assert "Finding 1" in findings[0]

    def test_empty_md(self):
        assert extract_key_findings("") == []

    def test_no_executive_summary_section(self):
        md = "## Other Section\n\n- Some bullet\n"
        assert extract_key_findings(md) == []

    def test_fallback_to_text_snippet_when_no_bullets(self):
        md = "## Executive Summary\n\nThis is a plain paragraph with no bullets.\n\n## Next\n"
        findings = extract_key_findings(md)
        assert len(findings) == 1
        assert "plain paragraph" in findings[0]


# ---------------------------------------------------------------------------
# TestExtractScenarios
# ---------------------------------------------------------------------------

class TestExtractScenarios:
    def test_parses_scenario_headers(self):
        md = (
            "## Scenario 1: Top Company Exit \u2014 confidence: MEDIUM\nContent here\n"
            "## Scenario 2: Consolidation \u2014 confidence: HIGH\nMore content\n"
        )
        scenarios = extract_scenarios(md)
        assert len(scenarios) == 2
        assert scenarios[0]["name"] == "Top Company Exit"
        assert scenarios[0]["confidence"] == "MEDIUM"
        assert scenarios[1]["name"] == "Consolidation"
        assert scenarios[1]["confidence"] == "HIGH"

    def test_no_scenarios(self):
        assert extract_scenarios("No scenarios here") == []

    def test_empty_md(self):
        assert extract_scenarios("") == []

    def test_scenario_without_confidence(self):
        md = "## Scenario 1: Merger Wave\nSome content\n"
        scenarios = extract_scenarios(md)
        assert len(scenarios) == 1
        assert scenarios[0]["confidence"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# TestExtractOpportunities
# ---------------------------------------------------------------------------

class TestExtractOpportunities:
    def test_from_narrate_context(self):
        ctx = {
            "top_opportunities": [
                {
                    "mechanism": "MechX",
                    "status": "Emerging",
                    "opportunity_score": 0.8,
                    "companies": 2,
                    "total_drugs": 5,
                },
            ]
        }
        opps = extract_opportunities(ctx)
        assert len(opps) == 1
        assert opps[0]["mechanism"] == "MechX"
        assert opps[0]["status"] == "Emerging"

    def test_empty_context(self):
        assert extract_opportunities({}) == []

    def test_multiple_opportunities(self):
        ctx = {
            "top_opportunities": [
                {"mechanism": "A", "status": "Early", "opportunity_score": 0.5, "companies": 1, "total_drugs": 2},
                {"mechanism": "B", "status": "Mature", "opportunity_score": 0.3, "companies": 3, "total_drugs": 8},
            ]
        }
        opps = extract_opportunities(ctx)
        assert len(opps) == 2


# ---------------------------------------------------------------------------
# TestExtractSessionInsights
# ---------------------------------------------------------------------------

class TestExtractSessionInsights:
    def test_full_extraction(self, tmp_path):
        ld = tmp_path / "raw" / "test-ind"
        ld.mkdir(parents=True)
        (ld / "strategic_briefing.md").write_text(
            "## Executive Summary\n\n- Key finding 1\n- Key finding 2\n\n"
            "## Strategic Implications\n\n- Action 1\n"
        )
        (ld / "scenario_analysis.md").write_text(
            "## Scenario 1: Test \u2014 confidence: HIGH\nScenario content\n"
        )
        (ld / "narrate_context.json").write_text(
            '{"indication": "Test", "top_opportunities": [], "risk_zones": [], '
            '"top_companies": [], "top_mechanisms": []}'
        )

        insights = extract_session_insights("test-ind", str(ld), str(tmp_path))
        assert insights["indication"] == "test-ind"
        assert len(insights["key_findings"]) == 2
        assert len(insights["scenarios"]) == 1
        assert len(insights["strategic_implications"]) == 1

    def test_missing_files_returns_empty_lists(self, tmp_path):
        ld = tmp_path / "raw" / "empty-ind"
        ld.mkdir(parents=True)

        insights = extract_session_insights("empty-ind", str(ld), str(tmp_path))
        assert insights["indication"] == "empty-ind"
        assert insights["key_findings"] == []
        assert insights["scenarios"] == []

    def test_indication_name_from_slug_when_no_json(self, tmp_path):
        ld = tmp_path / "raw" / "non-small-cell-lung-cancer"
        ld.mkdir(parents=True)

        insights = extract_session_insights("non-small-cell-lung-cancer", str(ld), str(tmp_path))
        # slug.replace("-", " ").title() produces title-cased words
        assert insights["indication_name"] == "Non Small Cell Lung Cancer"


# ---------------------------------------------------------------------------
# TestWriteAndLoadInsights
# ---------------------------------------------------------------------------

class TestWriteAndLoadInsights:
    def test_write_then_load(self, tmp_path):
        insights = {
            "title": "Test Analysis",
            "type": "insight",
            "indication": "test",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_dir": "raw/test",
            "tags": ["test"],
            "key_findings": ["Finding 1"],
            "scenarios": [],
            "opportunities": [],
            "risk_zones": [],
            "changes": {},
            "strategic_implications": ["Action 1"],
        }
        path = write_session_insight(insights, str(tmp_path))
        assert os.path.exists(path)

        loaded = load_recent_insights(str(tmp_path))
        assert len(loaded) == 1
        assert "Finding 1" in loaded[0]["body"]

    def test_load_filters_by_indication(self, tmp_path):
        def _make(slug, title):
            return {
                "title": title,
                "type": "insight",
                "indication": slug,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_dir": f"raw/{slug}",
                "tags": [slug],
                "key_findings": ["F1"],
                "scenarios": [],
                "opportunities": [],
                "risk_zones": [],
                "changes": {},
                "strategic_implications": [],
            }

        write_session_insight(_make("obesity", "Obesity Analysis"), str(tmp_path))
        write_session_insight(_make("asthma", "Asthma Analysis"), str(tmp_path))

        loaded = load_recent_insights(str(tmp_path), indication="obesity")
        assert len(loaded) == 1
        assert loaded[0]["meta"]["indication"] == "obesity"

    def test_empty_wiki_returns_empty_list(self, tmp_path):
        result = load_recent_insights(str(tmp_path))
        assert result == []


# ---------------------------------------------------------------------------
# TestFormatForPrompt
# ---------------------------------------------------------------------------

class TestFormatForPrompt:
    def test_formats_recent(self):
        insights = [
            {
                "meta": {
                    "title": "Test Analysis",
                    "timestamp": "2026-04-08T00:00:00Z",
                    "indication": "test",
                },
                "body": "## Key Findings\n\n- Insight A\n- Insight B\n",
            }
        ]
        result = format_insights_for_prompt(insights)
        assert "Previous Analysis Insights" in result
        assert "Insight A" in result
        assert "Insight B" in result

    def test_empty_returns_empty(self):
        assert format_insights_for_prompt([]) == ""

    def test_truncates_to_max_insights(self):
        insights = [
            {
                "meta": {"title": f"Analysis {i}", "timestamp": "2026-04-08T00:00:00Z", "indication": f"ind{i}"},
                "body": f"- Finding {i}\n",
            }
            for i in range(10)
        ]
        result = format_insights_for_prompt(insights, max_insights=3)
        assert "7 more insights" in result
