"""Tests for compile.py — daily log → wiki concept/connection compiler."""

import sys
from pathlib import Path


# Ensure project root is on sys.path so hooks.compile is importable
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hooks.compile import (
    compile_basic,
    file_sha256,
    save_compile_state,
    logs_to_process,
    _is_routine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PHARMA_LOG = """\
# Daily Log — 2026-04-01

---

### Session (10:00:00 UTC)

## Session Summary
Analyzed GLP-1 competitive landscape for obesity indication.

## Key Decisions
- Prioritize Novo Nordisk semaglutide tracking over Eli Lilly tirzepatide for Q2
- Use CPI scores above 0.7 as threshold for deal monitoring

## Lessons Learned
- Fetching all pipeline phases in one call reduces API round-trips by 60%
- Phase III density is the strongest predictor of near-term competitive pressure

## Strategic Insights
- Novo Nordisk holds 34% pipeline share in GLP-1 obesity space
- Tirzepatide dual-agonist mechanism creates differentiated positioning vs monoagonists
- Regulatory fast-track designation accelerates competitive timeline by 6-12 months

## Action Items
- Set up weekly freshness check for obesity indication
"""

ROUTINE_LOG = """\
# Daily Log — 2026-04-02

---

### Session (09:00:00 UTC)

## Session Summary
Routine session with no notable insights to capture.
"""


# ---------------------------------------------------------------------------
# TestIsRoutine
# ---------------------------------------------------------------------------

class TestIsRoutine:
    def test_pharma_log_not_routine(self):
        assert _is_routine(PHARMA_LOG) is False

    def test_routine_log_detected(self):
        assert _is_routine(ROUTINE_LOG) is True

    def test_routine_with_bullets_not_routine(self):
        log = ROUTINE_LOG + "\n## Strategic Insights\n\n- Important finding\n"
        assert _is_routine(log) is False


# ---------------------------------------------------------------------------
# TestCompileBasic
# ---------------------------------------------------------------------------

class TestCompileBasic:
    def test_extracts_concepts_from_log(self, tmp_path):
        """Create a daily log with Key Decisions + Lessons, verify concept articles created."""
        written = compile_basic(PHARMA_LOG, "2026-04-01", str(tmp_path))

        assert len(written) >= 2, f"Expected at least 2 articles, got {len(written)}: {written}"

        # All written files must exist
        for p in written:
            assert Path(p).exists(), f"Article not found: {p}"

        # At least one must be under insights/concepts/
        concept_paths = [p for p in written if "/concepts/" in p]
        assert len(concept_paths) >= 1

        # Verify frontmatter of a concept article
        from cli_anything.cortellis.utils.wiki import read_article
        art = read_article(concept_paths[0])
        assert art is not None
        assert art["meta"]["type"] == "concept"
        assert "daily/2026-04-01.md" in art["meta"]["sources"]
        assert "## Key Points" in art["body"]

    def test_creates_connections(self, tmp_path):
        """Log mentioning multiple related topics → connection article created."""
        written = compile_basic(PHARMA_LOG, "2026-04-01", str(tmp_path))

        connection_paths = [p for p in written if "/connections/" in p]
        assert len(connection_paths) >= 1, "Expected at least one connection article"

        from cli_anything.cortellis.utils.wiki import read_article
        art = read_article(connection_paths[0])
        assert art is not None
        assert art["meta"]["type"] == "connection"
        assert len(art["meta"]["connects"]) >= 2

    def test_incremental_skips_unchanged(self, tmp_path):
        """Same log compiled twice → second compile uses cached hash, no reprocessing."""
        daily_dir = tmp_path / "daily"
        daily_dir.mkdir()
        log_file = daily_dir / "2026-04-01.md"
        log_file.write_text(PHARMA_LOG, encoding="utf-8")

        # Override state path to use tmp_path
        import hooks.compile as compile_mod
        original_state_path = compile_mod.COMPILE_STATE_PATH
        compile_mod.COMPILE_STATE_PATH = daily_dir / ".compile-state.json"

        try:
            # First compile — should process
            first = logs_to_process(daily_dir, force_all=False)
            assert log_file in first

            # Simulate state save after first compile
            state = {str(log_file): file_sha256(log_file)}
            save_compile_state(state)

            # Second check — file unchanged, should be empty
            second = logs_to_process(daily_dir, force_all=False)
            assert log_file not in second, "Unchanged log should be skipped on second pass"

            # --all flag forces recompile
            third = logs_to_process(daily_dir, force_all=True)
            assert log_file in third
        finally:
            compile_mod.COMPILE_STATE_PATH = original_state_path

    def test_empty_log_produces_nothing(self, tmp_path):
        """Log with only 'Routine session' → no articles written."""
        written = compile_basic(ROUTINE_LOG, "2026-04-02", str(tmp_path))
        assert written == [], f"Expected no articles for routine log, got: {written}"

    def test_concepts_dir_created(self, tmp_path):
        """compile_basic creates wiki/insights/concepts/ and connections/ dirs."""
        compile_basic(PHARMA_LOG, "2026-04-01", str(tmp_path))
        assert (tmp_path / "wiki" / "insights" / "concepts").is_dir()
        assert (tmp_path / "wiki" / "insights" / "connections").is_dir()

    def test_insights_index_updated(self, tmp_path):
        """compile_basic writes or updates wiki/insights/index.md."""
        compile_basic(PHARMA_LOG, "2026-04-01", str(tmp_path))
        index = tmp_path / "wiki" / "insights" / "index.md"
        assert index.exists(), "insights/index.md should be created"
        content = index.read_text(encoding="utf-8")
        assert "## Concepts" in content

    def test_partial_sections(self, tmp_path):
        """Log with only Strategic Insights section → one concept article."""
        partial_log = """\
# Daily Log — 2026-04-03

---

### Session (14:00:00 UTC)

## Session Summary
Quick strategic review.

## Strategic Insights
- FDA accelerated approval pathway reduces time-to-market by 18 months
- Orphan drug designation confers 7-year market exclusivity in the US
"""
        written = compile_basic(partial_log, "2026-04-03", str(tmp_path))
        # Only Strategic Insights section populated → 1 concept, no connection
        concept_paths = [p for p in written if "/concepts/" in p]
        conn_paths = [p for p in written if "/connections/" in p]
        assert len(concept_paths) == 1
        assert len(conn_paths) == 0
