"""Tests for the strategic intelligence signal extraction module."""

import os
from datetime import datetime, timezone, timedelta

import pytest

from cli_anything.cortellis.utils.intelligence import (
    extract_signals,
    format_signals_for_prompt,
    generate_signals_report,
)
from cli_anything.cortellis.utils.wiki import write_article, wiki_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wiki(tmp_path):
    """Return the wiki/indications path, creating it."""
    ind_dir = tmp_path / "wiki" / "indications"
    ind_dir.mkdir(parents=True, exist_ok=True)
    return ind_dir


def _now_str(offset_days=0):
    dt = datetime.now(timezone.utc) - timedelta(days=offset_days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_indication(ind_dir, slug, meta, body="Test body."):
    path = str(ind_dir / f"{slug}.md")
    write_article(path, meta, body)
    return path


# ---------------------------------------------------------------------------
# TestExtractSignals
# ---------------------------------------------------------------------------

class TestExtractSignals:
    def test_detects_phase3_entrant(self, tmp_path):
        """Article with previous_snapshot showing +1 Phase 3 → high severity signal."""
        ind_dir = _make_wiki(tmp_path)
        _write_indication(
            ind_dir,
            "oncology",
            {
                "title": "Oncology",
                "slug": "oncology",
                "compiled_at": _now_str(0),
                "total_drugs": 501,
                "total_deals": 100,
                "phase_counts": {"launched": 10, "phase3": 51, "phase2": 80, "phase1": 100, "discovery": 260},
                "previous_snapshot": {
                    "compiled_at": _now_str(7),
                    "total_drugs": 500,
                    "total_deals": 100,
                    "phase_counts": {"launched": 10, "phase3": 50, "phase2": 80, "phase1": 100, "discovery": 260},
                },
            },
        )

        signals = extract_signals(str(tmp_path))
        phase3_signals = [s for s in signals if s["signal_type"] == "phase3_entrant"]
        assert len(phase3_signals) == 1
        assert phase3_signals[0]["severity"] == "high"
        assert "Oncology" in phase3_signals[0]["summary"]

    def test_detects_top_company_change(self, tmp_path):
        """Different top company in top_company field vs previous_snapshot → high signal."""
        ind_dir = _make_wiki(tmp_path)
        _write_indication(
            ind_dir,
            "diabetes",
            {
                "title": "Diabetes",
                "slug": "diabetes",
                "compiled_at": _now_str(0),
                "total_drugs": 500,
                "total_deals": 100,
                "top_company": "Novo Nordisk",
                "company_rankings": [
                    {"company": "Novo Nordisk", "cpi_score": 95.0, "tier": "A"},
                    {"company": "Eli Lilly", "cpi_score": 70.0, "tier": "A"},
                ],
                "previous_snapshot": {
                    "compiled_at": _now_str(7),
                    "total_drugs": 498,
                    "total_deals": 100,
                    "top_company": "Eli Lilly",
                    "company_rankings": [
                        {"company": "Eli Lilly", "cpi_score": 90.0, "tier": "A"},
                        {"company": "Novo Nordisk", "cpi_score": 70.0, "tier": "A"},
                    ],
                },
            },
        )

        signals = extract_signals(str(tmp_path))
        top_changed = [s for s in signals if s["signal_type"] == "top_company_changed"]
        assert len(top_changed) == 1
        assert top_changed[0]["severity"] == "high"
        assert "Novo Nordisk" in top_changed[0]["summary"]

    def test_detects_deal_acceleration(self, tmp_path):
        """20%+ deal increase → medium signal."""
        ind_dir = _make_wiki(tmp_path)
        _write_indication(
            ind_dir,
            "immunology",
            {
                "title": "Immunology",
                "slug": "immunology",
                "compiled_at": _now_str(0),
                "total_drugs": 300,
                "total_deals": 120,
                "previous_snapshot": {
                    "compiled_at": _now_str(7),
                    "total_drugs": 298,
                    "total_deals": 100,
                },
            },
        )

        signals = extract_signals(str(tmp_path))
        deal_sigs = [s for s in signals if s["signal_type"] == "deal_acceleration"]
        assert len(deal_sigs) == 1
        assert deal_sigs[0]["severity"] == "medium"
        assert "20%" in deal_sigs[0]["summary"]

    def test_skips_old_articles(self, tmp_path):
        """Articles older than max_age_days are ignored."""
        ind_dir = _make_wiki(tmp_path)
        _write_indication(
            ind_dir,
            "cardiology",
            {
                "title": "Cardiology",
                "slug": "cardiology",
                "compiled_at": _now_str(35),  # 35 days old
                "total_drugs": 400,
                "total_deals": 80,
                "previous_snapshot": {
                    "compiled_at": _now_str(42),
                    "total_drugs": 350,
                    "total_deals": 60,
                },
            },
        )

        signals = extract_signals(str(tmp_path), max_age_days=30)
        assert all(s["indication"] != "Cardiology" for s in signals)

    def test_no_previous_snapshot_no_signals(self, tmp_path):
        """Article without previous_snapshot → no signals (except staleness)."""
        ind_dir = _make_wiki(tmp_path)
        _write_indication(
            ind_dir,
            "neurology",
            {
                "title": "Neurology",
                "slug": "neurology",
                "compiled_at": _now_str(0),
                "total_drugs": 250,
                "total_deals": 50,
                # No previous_snapshot
            },
        )

        signals = extract_signals(str(tmp_path))
        # No change-based signals should be present
        change_types = {"phase3_entrant", "top_company_changed", "deal_acceleration",
                        "deal_deceleration", "significant_drug_change", "new_top10_entrant", "top10_dropout"}
        assert not any(s["signal_type"] in change_types for s in signals)

    def test_stale_data_warning(self, tmp_path):
        """Article 25+ days old → low severity data_stale signal."""
        ind_dir = _make_wiki(tmp_path)
        _write_indication(
            ind_dir,
            "respiratory",
            {
                "title": "Respiratory",
                "slug": "respiratory",
                "compiled_at": _now_str(26),  # 26 days old — within max_age but stale warning
                "total_drugs": 200,
                "total_deals": 40,
            },
        )

        signals = extract_signals(str(tmp_path), max_age_days=30)
        stale_sigs = [s for s in signals if s["signal_type"] == "data_stale"]
        assert len(stale_sigs) == 1
        assert stale_sigs[0]["severity"] == "low"
        assert "Respiratory" in stale_sigs[0]["summary"]


# ---------------------------------------------------------------------------
# TestFormatSignalsForPrompt
# ---------------------------------------------------------------------------

class TestFormatSignalsForPrompt:
    def test_groups_by_severity(self):
        # Signals are pre-sorted by severity (as extract_signals does) — high first
        signals = [
            {"severity": "high", "summary": "High signal", "signal_type": "phase3_entrant",
             "indication": "Y", "action": "Act", "data": {}},
            {"severity": "medium", "summary": "Med signal", "signal_type": "deal_acceleration",
             "indication": "X", "action": "Act", "data": {}},
        ]
        result = format_signals_for_prompt(signals)
        high_pos = result.find("HIGH")
        med_pos = result.find("MEDIUM")
        assert high_pos != -1
        assert med_pos != -1
        assert high_pos < med_pos

    def test_empty_signals_returns_empty(self):
        assert format_signals_for_prompt([]) == ""

    def test_limits_to_max(self):
        signals = [
            {"severity": "low", "summary": f"Signal {i}", "signal_type": "data_stale",
             "indication": "X", "action": "Act", "data": {}}
            for i in range(20)
        ]
        result = format_signals_for_prompt(signals, max_signals=5)
        assert "omitted" in result


# ---------------------------------------------------------------------------
# TestGenerateSignalsReport
# ---------------------------------------------------------------------------

class TestGenerateSignalsReport:
    def test_produces_full_report(self, tmp_path):
        """Create 2 indications with signals, verify report has all sections."""
        ind_dir = _make_wiki(tmp_path)

        for slug, title in [("obesity", "Obesity"), ("asthma", "Asthma")]:
            _write_indication(
                ind_dir,
                slug,
                {
                    "title": title,
                    "slug": slug,
                    "compiled_at": _now_str(0),
                    "total_drugs": 501,
                    "total_deals": 120,
                    "phase_counts": {"launched": 10, "phase3": 51, "phase2": 80, "phase1": 100, "discovery": 260},
                    "previous_snapshot": {
                        "compiled_at": _now_str(7),
                        "total_drugs": 500,
                        "total_deals": 100,
                        "phase_counts": {"launched": 10, "phase3": 50, "phase2": 80, "phase1": 100, "discovery": 260},
                    },
                },
            )

        report = generate_signals_report(str(tmp_path))
        assert "Strategic Intelligence Report" in report
        assert "Cross-Portfolio Summary" in report
        assert "High Priority Signals" in report
        # Both indications should appear
        assert "Obesity" in report
        assert "Asthma" in report

    def test_empty_wiki(self, tmp_path):
        """No articles → 'No strategic signals detected'"""
        _make_wiki(tmp_path)
        report = generate_signals_report(str(tmp_path))
        assert "No strategic signals detected" in report


# ---------------------------------------------------------------------------
# TestSkillRouterSignals
# ---------------------------------------------------------------------------

class TestSkillRouterSignals:
    def test_signals_trigger(self):
        from cli_anything.cortellis.core.skill_router import detect_skill
        result = detect_skill("what's happening across my landscapes?")
        assert result is not None and "signals" in result.lower()

    def test_strategic_update_trigger(self):
        from cli_anything.cortellis.core.skill_router import detect_skill
        result = detect_skill("give me a strategic intelligence report")
        assert result is not None and "signals" in result.lower()

    def test_signal_transduction_not_triggered(self):
        """'signal transduction' should NOT route to signals skill."""
        from cli_anything.cortellis.core.skill_router import detect_skill
        result = detect_skill("explain signal transduction pathways")
        # Should not match signals skill
        if result is not None:
            assert "signals_report" not in result

    def test_strategic_report_trigger(self):
        from cli_anything.cortellis.core.skill_router import detect_skill
        result = detect_skill("give me a strategic report on the portfolio")
        assert result is not None and "signals" in result.lower()
