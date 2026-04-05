"""Reproducibility tests for strategic_scoring.py and strategic_narrative.py.

Runs each script twice on the same input and asserts byte-identical output files.
Requires raw/asthma/ fixture directory — skipped automatically if absent.

Run with:
    pytest cli_anything/cortellis/tests/test_strategic_reproducibility.py -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_RECIPES_DIR = os.path.join(
    _REPO_ROOT,
    "cli_anything", "cortellis", "skills", "landscape", "recipes",
)
_SCORING_SCRIPT = os.path.join(_RECIPES_DIR, "strategic_scoring.py")
_NARRATIVE_SCRIPT = os.path.join(_RECIPES_DIR, "strategic_narrative.py")
_FIXTURE_DIR = os.path.join(_REPO_ROOT, "raw", "asthma")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_scoring(landscape_dir: str, preset: str | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, _SCORING_SCRIPT, landscape_dir]
    if preset:
        cmd.append(preset)
    return subprocess.run(cmd, capture_output=True, text=True)


def _run_narrative(landscape_dir: str, preset: str | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, _NARRATIVE_SCRIPT, landscape_dir]
    if preset:
        cmd.append(preset)
    return subprocess.run(cmd, capture_output=True, text=True)


def _copy_fixture(tmp_dir: str) -> str:
    """Copy fixture into a fresh temp subdir and return the path."""
    dest = os.path.join(tmp_dir, "asthma")
    shutil.copytree(_FIXTURE_DIR, dest)
    return dest


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------

_FIXTURE_MISSING = not os.path.isdir(_FIXTURE_DIR)
_SKIP_REASON = f"Fixture directory not found: {_FIXTURE_DIR}"


# ---------------------------------------------------------------------------
# Tests — strategic_scoring.py
# ---------------------------------------------------------------------------

class TestScoringReproducibility:
    @pytest.mark.skipif(_FIXTURE_MISSING, reason=_SKIP_REASON)
    def test_default_preset_is_deterministic(self):
        """Two runs with default preset produce byte-identical CSV outputs."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            dir1 = _copy_fixture(tmp1)
            dir2 = _copy_fixture(tmp2)

            r1 = _run_scoring(dir1)
            assert r1.returncode == 0, f"Run 1 failed:\n{r1.stderr}"

            r2 = _run_scoring(dir2)
            assert r2.returncode == 0, f"Run 2 failed:\n{r2.stderr}"

            for fname in ("strategic_scores.csv", "mechanism_scores.csv"):
                p1 = os.path.join(dir1, fname)
                p2 = os.path.join(dir2, fname)
                assert os.path.exists(p1), f"Missing output in run 1: {fname}"
                assert os.path.exists(p2), f"Missing output in run 2: {fname}"
                assert _read_bytes(p1) == _read_bytes(p2), (
                    f"{fname} differs between runs (non-deterministic output)"
                )

    @pytest.mark.skipif(_FIXTURE_MISSING, reason=_SKIP_REASON)
    def test_respiratory_preset_is_deterministic(self):
        """Two runs with respiratory preset produce byte-identical CSV outputs."""
        with tempfile.TemporaryDirectory() as tmp1:
            with tempfile.TemporaryDirectory() as tmp2:
                dir1 = _copy_fixture(tmp1)
                dir2 = _copy_fixture(tmp2)

                r1 = _run_scoring(dir1, preset="respiratory")
                assert r1.returncode == 0, f"Run 1 (respiratory) failed:\n{r1.stderr}"

                r2 = _run_scoring(dir2, preset="respiratory")
                assert r2.returncode == 0, f"Run 2 (respiratory) failed:\n{r2.stderr}"

                for fname in ("strategic_scores.csv", "mechanism_scores.csv"):
                    p1 = os.path.join(dir1, fname)
                    p2 = os.path.join(dir2, fname)
                    assert os.path.exists(p1), f"Missing output in run 1: {fname}"
                    assert os.path.exists(p2), f"Missing output in run 2: {fname}"
                    assert _read_bytes(p1) == _read_bytes(p2), (
                        f"{fname} differs between runs with respiratory preset"
                    )

    @pytest.mark.skipif(_FIXTURE_MISSING, reason=_SKIP_REASON)
    def test_preset_outputs_differ_from_default(self):
        """respiratory preset should produce different scores than default preset."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            dir_default = _copy_fixture(tmp1)
            dir_resp = _copy_fixture(tmp2)

            r_default = _run_scoring(dir_default)
            assert r_default.returncode == 0

            r_resp = _run_scoring(dir_resp, preset="respiratory")
            assert r_resp.returncode == 0

            p_default = os.path.join(dir_default, "strategic_scores.csv")
            p_resp = os.path.join(dir_resp, "strategic_scores.csv")

            assert os.path.exists(p_default)
            assert os.path.exists(p_resp)
            assert _read_bytes(p_default) != _read_bytes(p_resp), (
                "respiratory preset produced identical output to default — weights not applied"
            )


# ---------------------------------------------------------------------------
# Tests — strategic_narrative.py
# ---------------------------------------------------------------------------

class TestNarrativeReproducibility:
    @pytest.mark.skipif(_FIXTURE_MISSING, reason=_SKIP_REASON)
    def test_narrative_is_deterministic(self):
        """Two runs of strategic_narrative.py produce byte-identical briefing."""
        if not os.path.exists(_NARRATIVE_SCRIPT):
            pytest.skip(f"strategic_narrative.py not found: {_NARRATIVE_SCRIPT}")

        with tempfile.TemporaryDirectory() as tmp1:
            with tempfile.TemporaryDirectory() as tmp2:
                dir1 = _copy_fixture(tmp1)
                dir2 = _copy_fixture(tmp2)

                # Scoring must run first so narrative has inputs
                r1s = _run_scoring(dir1)
                r2s = _run_scoring(dir2)
                assert r1s.returncode == 0
                assert r2s.returncode == 0

                r1 = _run_narrative(dir1)
                assert r1.returncode == 0, f"Narrative run 1 failed:\n{r1.stderr}"

                r2 = _run_narrative(dir2)
                assert r2.returncode == 0, f"Narrative run 2 failed:\n{r2.stderr}"

                fname = "strategic_briefing.md"
                p1 = os.path.join(dir1, fname)
                p2 = os.path.join(dir2, fname)
                assert os.path.exists(p1), f"Missing {fname} after narrative run 1"
                assert os.path.exists(p2), f"Missing {fname} after narrative run 2"
                assert _read_bytes(p1) == _read_bytes(p2), (
                    f"{fname} differs between runs (non-deterministic narrative output)"
                )
