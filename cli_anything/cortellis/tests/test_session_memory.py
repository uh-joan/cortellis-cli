"""Tests for session memory: stale-detection and wiki flush."""

import csv
import os
import time
from datetime import datetime, timezone, timedelta

import pytest

from cli_anything.cortellis.utils.session_memory import (
    _MARKER_FILE,
    get_raw_dirs,
    get_newest_mtime,
    get_stale_indications,
    flush_session_memory,
)
from cli_anything.cortellis.utils.wiki import article_path, write_article, read_article


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_csv(path: str, rows=None):
    """Write a minimal CSV file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "cpi_score"])
        writer.writeheader()
        for row in (rows or [{"company": "Acme", "cpi_score": "80"}]):
            writer.writerow(row)


def make_landscape_dir(dir_path):
    """Create a minimal landscape directory that compile_dossier will accept."""
    os.makedirs(dir_path, exist_ok=True)
    make_csv(os.path.join(dir_path, "strategic_scores.csv"))
    # compile_dossier requires at least one phase CSV
    phase_path = os.path.join(dir_path, "launched.csv")
    with open(phase_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "id", "phase", "indication", "mechanism", "company", "source"])
        writer.writeheader()
        writer.writerow({"name": "TestDrug", "id": "1", "phase": "Launched", "indication": "Test", "mechanism": "Mech", "company": "Acme", "source": "src"})
    # compile_dossier checks for landscape_dir key in freshness.json to distinguish
    # indication landscape dirs from company pipeline dirs
    import json as _json
    with open(os.path.join(dir_path, "freshness.json"), "w") as _f:
        _json.dump({"landscape_dir": dir_path, "staleness_level": "ok"}, _f)


def make_marker(raw_dir, compiled_at_iso: str):
    """Write a .wiki_compiled_at marker file into a raw dir."""
    marker_path = os.path.join(str(raw_dir), _MARKER_FILE)
    with open(marker_path, "w") as f:
        f.write(compiled_at_iso)


def make_wiki_article(base_dir, slug, compiled_at_iso):
    """Write a minimal wiki indication article with a given compiled_at."""
    path = article_path("indications", slug, str(base_dir))
    meta = {
        "title": slug.replace("-", " ").title(),
        "type": "indication",
        "slug": slug,
        "compiled_at": compiled_at_iso,
    }
    write_article(path, meta, "## Body\n\nSome content.\n")
    return path


# ---------------------------------------------------------------------------
# TestGetRawDirs
# ---------------------------------------------------------------------------

class TestGetRawDirs:
    def test_finds_dirs_with_csvs(self, tmp_path):
        # Create raw/obesity/ with a .csv
        obesity_dir = tmp_path / "raw" / "obesity"
        obesity_dir.mkdir(parents=True)
        make_csv(str(obesity_dir / "strategic_scores.csv"))

        # Create raw/empty/ without any .csv
        empty_dir = tmp_path / "raw" / "empty"
        empty_dir.mkdir(parents=True)
        (empty_dir / "notes.txt").write_text("no csv here")

        result = get_raw_dirs(str(tmp_path))
        assert len(result) == 1
        assert result[0] == str(obesity_dir)

    def test_empty_raw(self, tmp_path):
        # No raw/ dir at all
        result = get_raw_dirs(str(tmp_path))
        assert result == []

    def test_only_csv_dirs_returned(self, tmp_path):
        # Multiple dirs, only those with .csv files
        for name in ("alpha", "beta", "gamma"):
            d = tmp_path / "raw" / name
            d.mkdir(parents=True)
            if name != "beta":
                make_csv(str(d / "data.csv"))

        result = get_raw_dirs(str(tmp_path))
        names = {os.path.basename(p) for p in result}
        assert names == {"alpha", "gamma"}


# ---------------------------------------------------------------------------
# TestGetNewestMtime
# ---------------------------------------------------------------------------

class TestGetNewestMtime:
    def test_returns_newest(self, tmp_path):
        f1 = tmp_path / "old.csv"
        f1.write_text("old")
        time.sleep(0.05)
        f2 = tmp_path / "new.csv"
        f2.write_text("new")

        result = get_newest_mtime(str(tmp_path))
        assert result is not None
        assert result.tzinfo is not None  # must be tz-aware UTC
        # The newest file mtime should match f2
        f2_mtime = datetime.fromtimestamp(f2.stat().st_mtime, tz=timezone.utc)
        assert abs((result - f2_mtime).total_seconds()) < 1.0

    def test_empty_dir(self, tmp_path):
        result = get_newest_mtime(str(tmp_path))
        assert result is None

    def test_single_file(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("x")
        result = get_newest_mtime(str(tmp_path))
        assert result is not None
        expected = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        assert abs((result - expected).total_seconds()) < 1.0


# ---------------------------------------------------------------------------
# TestGetStaleIndications
# ---------------------------------------------------------------------------

class TestGetStaleIndications:
    def test_missing_wiki_is_stale(self, tmp_path):
        # raw/obesity/ exists, no wiki article
        obesity_dir = tmp_path / "raw" / "obesity"
        obesity_dir.mkdir(parents=True)
        make_csv(str(obesity_dir / "strategic_scores.csv"))

        result = get_stale_indications(str(tmp_path))
        assert len(result) == 1
        assert result[0]["slug"] == "obesity"
        assert result[0]["wiki_status"] == "missing"
        assert result[0]["wiki_compiled_at"] is None
        assert result[0]["raw_mtime"] is not None

    def test_fresh_wiki_not_in_results(self, tmp_path):
        # raw/obesity/ exists, marker written recently (after the raw files)
        obesity_dir = tmp_path / "raw" / "obesity"
        obesity_dir.mkdir(parents=True)
        make_csv(str(obesity_dir / "strategic_scores.csv"))

        # Marker compiled one hour in the future relative to now
        future_iso = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        make_marker(obesity_dir, future_iso)

        result = get_stale_indications(str(tmp_path))
        assert result == []

    def test_old_wiki_is_stale(self, tmp_path):
        # raw/obesity/ exists, marker written before the raw files were modified
        obesity_dir = tmp_path / "raw" / "obesity"
        obesity_dir.mkdir(parents=True)

        # Write marker with an old timestamp
        past_iso = "2020-01-01T00:00:00Z"
        make_marker(obesity_dir, past_iso)

        # Then write the csv (newer than the marker)
        make_csv(str(obesity_dir / "strategic_scores.csv"))

        result = get_stale_indications(str(tmp_path))
        assert len(result) == 1
        assert result[0]["slug"] == "obesity"
        assert result[0]["wiki_status"] == "stale"
        assert result[0]["wiki_compiled_at"] == past_iso

    def test_multiple_indications_mixed(self, tmp_path):
        # obesity: stale (no marker), diabetes: fresh (future marker)
        for slug in ("obesity", "diabetes"):
            d = tmp_path / "raw" / slug
            d.mkdir(parents=True)
            make_csv(str(d / "strategic_scores.csv"))

        # diabetes has a future marker
        future_iso = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        make_marker(tmp_path / "raw" / "diabetes", future_iso)

        result = get_stale_indications(str(tmp_path))
        slugs = {r["slug"] for r in result}
        assert slugs == {"obesity"}


# ---------------------------------------------------------------------------
# TestFlushSessionMemory
# ---------------------------------------------------------------------------

class TestFlushSessionMemory:
    def test_compiles_stale(self, tmp_path):
        # Create raw/test-indication/ with landscape CSVs, no wiki article
        raw_dir = tmp_path / "raw" / "test-indication"
        make_landscape_dir(str(raw_dir))

        recompiled = flush_session_memory(str(tmp_path))

        assert "test-indication" in recompiled
        # Wiki article should now exist
        path = article_path("indications", "test-indication", str(tmp_path))
        assert os.path.exists(path)
        art = read_article(path)
        assert art is not None
        assert art["meta"].get("compiled_at") is not None

    def test_skips_fresh(self, tmp_path):
        # Create raw/obesity/ + marker that's fresh (future timestamp)
        obesity_dir = tmp_path / "raw" / "obesity"
        obesity_dir.mkdir(parents=True)
        make_csv(str(obesity_dir / "strategic_scores.csv"))

        future_iso = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        make_marker(obesity_dir, future_iso)

        recompiled = flush_session_memory(str(tmp_path))
        assert recompiled == []

    def test_handles_compile_error(self, tmp_path):
        # Create raw/bad-data/ with landscape CSVs but empty strategic_scores
        bad_dir = tmp_path / "raw" / "bad-data"
        make_landscape_dir(str(bad_dir))
        # Overwrite strategic_scores with empty data to trigger edge case
        make_csv(str(bad_dir / "strategic_scores.csv"), rows=[])

        # Should not raise, even if compile encounters an issue
        try:
            recompiled = flush_session_memory(str(tmp_path))
            # Either compiled (with empty data) or failed gracefully — no crash
            assert isinstance(recompiled, list)
        except Exception as exc:
            pytest.fail(f"flush_session_memory raised unexpectedly: {exc}")

    def test_returns_only_recompiled_slugs(self, tmp_path):
        # Two stale indications
        for slug in ("alpha", "beta"):
            d = tmp_path / "raw" / slug
            make_landscape_dir(str(d))

        recompiled = flush_session_memory(str(tmp_path))
        assert set(recompiled) == {"alpha", "beta"}
