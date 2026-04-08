"""Tests for audience-specific landscape briefing recipes."""

import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)


def _create_mock_landscape(tmp_path):
    """Create a minimal but valid landscape directory for audience testing."""
    d = tmp_path / "raw" / "test-indication"
    d.mkdir(parents=True)
    sd = str(d)

    # Phase CSVs
    phase_header = ["name", "id", "phase", "indication", "mechanism", "company", "source"]
    _write_csv(os.path.join(sd, "launched.csv"), phase_header, [
        ["Drug A", "101", "Launched", "Test", "Mechanism X", "Company A", "src"],
        ["Drug B", "102", "Launched", "Test", "Mechanism Y", "Company B", "src"],
    ])
    _write_csv(os.path.join(sd, "phase3.csv"), phase_header, [
        ["Drug C", "103", "Phase 3", "Test", "Mechanism X", "Company C", "src"],
    ])
    _write_csv(os.path.join(sd, "phase2.csv"), phase_header, [
        ["Drug D", "104", "Phase 2", "Test", "Mechanism Z", "Company D", "src"],
        ["Drug E", "105", "Phase 2", "Test", "Mechanism X", "Company E", "src"],
    ])
    _write_csv(os.path.join(sd, "phase1.csv"), phase_header, [])
    _write_csv(os.path.join(sd, "discovery.csv"), phase_header, [])
    _write_csv(os.path.join(sd, "other.csv"), phase_header, [])

    # Strategic scores
    _write_csv(
        os.path.join(sd, "strategic_scores.csv"),
        ["company", "cpi_tier", "cpi_score", "pipeline_breadth", "phase_score",
         "mechanism_diversity", "deal_activity", "trial_intensity", "position"],
        [
            ["Company A", "A", "85.0", "5", "40.0", "3", "4", "6", "Leader"],
            ["Company B", "B", "55.0", "3", "25.0", "2", "2", "3", "Challenger"],
            ["Company C", "C", "30.0", "2", "15.0", "1", "1", "1", "Emerging"],
        ],
    )

    # Mechanism scores
    _write_csv(
        os.path.join(sd, "mechanism_scores.csv"),
        ["mechanism", "active_count", "launched", "phase3", "phase2", "phase1",
         "discovery", "company_count", "crowding_index"],
        [
            ["Mechanism X", "4", "1", "1", "1", "0", "0", "3", "12"],
            ["Mechanism Y", "1", "1", "0", "0", "0", "0", "1", "1"],
        ],
    )

    # Opportunity matrix
    _write_csv(
        os.path.join(sd, "opportunity_matrix.csv"),
        ["mechanism", "launched", "phase3", "phase2", "phase1", "discovery",
         "total", "companies", "status", "opportunity_score"],
        [
            ["Mechanism X", "1", "1", "1", "0", "0", "3", "3", "Active", "0.5"],
            ["Mechanism Z", "0", "0", "1", "0", "0", "1", "1", "Emerging", "0.8"],
        ],
    )

    # Deals
    _write_csv(
        os.path.join(sd, "deals.csv"),
        ["title", "id", "principal", "partner", "type", "date"],
        [
            ["Deal 1", "D001", "Company A", "Company B", "Licensing", "2026-03-01"],
            ["Deal 2", "D002", "Company C", "Company A", "Co-development", "2026-02-15"],
        ],
    )

    return sd


# ---------------------------------------------------------------------------
# BD Brief tests
# ---------------------------------------------------------------------------

class TestBdBrief:
    def test_generates_bd_sections(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_bd_brief

        result = generate_bd_brief(sd, "Test Indication")

        assert "Opportunity Overview" in result
        assert "Deal Landscape" in result
        assert "White Space" in result
        assert "Recommended Next Steps" in result

    def test_competitive_positioning_section(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_bd_brief

        result = generate_bd_brief(sd, "Test Indication")
        assert "Competitive Positioning" in result

    def test_key_assets_section(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_bd_brief

        result = generate_bd_brief(sd, "Test Indication")
        assert "Key Assets" in result

    def test_deal_velocity_section(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_bd_brief

        result = generate_bd_brief(sd, "Test Indication")
        assert "Deal Velocity" in result

    def test_empty_deals_handled(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        # Remove deals.csv to simulate no deals
        deals_path = os.path.join(sd, "deals.csv")
        if os.path.exists(deals_path):
            os.remove(deals_path)

        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_bd_brief

        result = generate_bd_brief(sd, "Test Indication")
        # Should not raise; section should show fallback text
        assert "No recent deals" in result or "Deal Velocity" in result

    def test_empty_opportunity_matrix_handled(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        om_path = os.path.join(sd, "opportunity_matrix.csv")
        if os.path.exists(om_path):
            os.remove(om_path)

        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_bd_brief

        result = generate_bd_brief(sd, "Test Indication")
        assert "White Space" in result  # Section still present
        assert "No white space" in result or "not identified" in result or "Not identified" in result


# ---------------------------------------------------------------------------
# Executive Brief tests
# ---------------------------------------------------------------------------

class TestExecBrief:
    def test_generates_five_bullets(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_exec_brief

        result = generate_exec_brief(sd, "Test Indication")

        # Extract the Strategic Summary section
        lines = result.split("\n")
        in_summary = False
        bullet_count = 0
        for line in lines:
            if "## Strategic Summary" in line:
                in_summary = True
                continue
            if in_summary and line.startswith("## "):
                break
            if in_summary and line.startswith("- "):
                bullet_count += 1

        assert bullet_count == 5, f"Expected 5 bullets in Strategic Summary, got {bullet_count}"

    def test_no_raw_cpi_numbers(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_exec_brief

        result = generate_exec_brief(sd, "Test Indication")

        # Should not contain "CPI" as a raw label or bare float scores like "85.0"
        assert "CPI" not in result, "Exec brief should not contain raw CPI label"
        # Should not contain bare CPI values (85.0, 55.0, 30.0 from mock data)
        assert "85.0" not in result
        assert "55.0" not in result
        assert "30.0" not in result

    def test_company_matrix_present(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_exec_brief

        result = generate_exec_brief(sd, "Test Indication")
        assert "Company Matrix" in result

    def test_key_numbers_section(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_exec_brief

        result = generate_exec_brief(sd, "Test Indication")
        assert "Key Numbers" in result

    def test_key_numbers_has_six_metrics(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_exec_brief

        result = generate_exec_brief(sd, "Test Indication")

        # Count data rows in Key Numbers table (skip header and separator)
        lines = result.split("\n")
        in_numbers = False
        data_rows = 0
        for line in lines:
            if "## Key Numbers" in line:
                in_numbers = True
                continue
            if in_numbers and line.startswith("## "):
                break
            if in_numbers and line.startswith("| ") and "---" not in line and "Metric" not in line:
                data_rows += 1

        assert data_rows == 6, f"Expected 6 metric rows in Key Numbers, got {data_rows}"

    def test_one_page_view_section(self, tmp_path):
        sd = _create_mock_landscape(tmp_path)
        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_exec_brief

        result = generate_exec_brief(sd, "Test Indication")
        assert "One-Page View" in result

    def test_empty_landscape_handled(self, tmp_path):
        sd = str(tmp_path / "raw" / "empty")
        os.makedirs(sd)

        from cli_anything.cortellis.skills.landscape.recipes.format_audience import generate_exec_brief

        result = generate_exec_brief(sd, "Empty Test")
        assert "Strategic Summary" in result
        assert "Key Numbers" in result


# ---------------------------------------------------------------------------
# CLI / main() tests
# ---------------------------------------------------------------------------

class TestMainCli:
    def test_bd_flag(self, tmp_path, monkeypatch, capsys):
        sd = _create_mock_landscape(tmp_path)
        monkeypatch.setattr(
            sys, "argv",
            ["format_audience.py", sd, "Test Indication", "--audience", "bd"],
        )

        from cli_anything.cortellis.skills.landscape.recipes import format_audience
        import importlib
        importlib.reload(format_audience)

        format_audience.main()

        # Output file should be created
        out_file = os.path.join(sd, "test-indication-bd-brief.md")
        assert os.path.exists(out_file), f"Expected {out_file} to be created"
        content = open(out_file).read()
        assert "Opportunity Overview" in content

    def test_exec_flag(self, tmp_path, monkeypatch, capsys):
        sd = _create_mock_landscape(tmp_path)
        monkeypatch.setattr(
            sys, "argv",
            ["format_audience.py", sd, "Test Indication", "--audience", "exec"],
        )

        from cli_anything.cortellis.skills.landscape.recipes import format_audience
        import importlib
        importlib.reload(format_audience)

        format_audience.main()

        out_file = os.path.join(sd, "test-indication-exec-brief.md")
        assert os.path.exists(out_file), f"Expected {out_file} to be created"
        content = open(out_file).read()
        assert "Strategic Summary" in content

    def test_no_audience_exits_zero(self, tmp_path, monkeypatch):
        sd = _create_mock_landscape(tmp_path)
        monkeypatch.setattr(
            sys, "argv",
            ["format_audience.py", sd, "Test Indication"],
        )

        from cli_anything.cortellis.skills.landscape.recipes import format_audience
        import importlib
        importlib.reload(format_audience)

        # Should exit 0 (informational, not error)
        with pytest.raises(SystemExit) as exc_info:
            format_audience.main()
        assert exc_info.value.code == 0

    def test_missing_dir_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys, "argv",
            ["format_audience.py", "/nonexistent/path", "--audience", "bd"],
        )

        from cli_anything.cortellis.skills.landscape.recipes import format_audience
        import importlib
        importlib.reload(format_audience)

        with pytest.raises(SystemExit) as exc_info:
            format_audience.main()
        assert exc_info.value.code != 0
