"""Regression tests for ABSTAIN gate robustness on thin-pipeline / tie-degenerate inputs.

Each test exercises one invariant from the council's Contrarian finding on ALS-style
tie degeneracy (docs/fragmented_indication_stress_test.md, section 2d).

Run with: pytest cli_anything/cortellis/tests/test_abstain_robustness.py -v
"""
import os
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
_NARRATIVE = os.path.join(_REPO, "cli_anything/cortellis/skills/landscape/recipes/strategic_narrative.py")
_SCENARIO = os.path.join(_REPO, "cli_anything/cortellis/skills/landscape/recipes/scenario_library.py")


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
_DH = "company,name,phase,mechanism\n"


def _write_csvs(tmpdir, launched="", phase3="", phase2="", phase1="", discovery="",
                scores=None, companies=None):
    for fname, content in [
        ("launched.csv",   _DH + launched),
        ("phase3.csv",     _DH + phase3),
        ("phase2.csv",     _DH + phase2),
        ("phase1.csv",     _DH + phase1),
        ("discovery.csv",  _DH + discovery),
    ]:
        with open(os.path.join(tmpdir, fname), "w") as f:
            f.write(content)

    if scores is None:
        scores = [("CompanyA", 80), ("CompanyB", 20), ("CompanyC", 20),
                  ("CompanyD", 20), ("CompanyE", 20), ("CompanyF", 20)]
    with open(os.path.join(tmpdir, "strategic_scores.csv"), "w") as f:
        f.write("company,cpi_score\n")
        for co, cpi in scores:
            f.write(f"{co},{cpi}\n")

    if companies is None:
        companies = [s[0] for s in scores]
    with open(os.path.join(tmpdir, "companies.csv"), "w") as f:
        f.write("company,size\n")
        for co in companies:
            f.write(f"{co},mid\n")


def _run(script, tmpdir, extra_args=()):
    return subprocess.run(
        [sys.executable, script, tmpdir, "TestIndication"] + list(extra_args),
        capture_output=True, text=True, check=False
    )


def _confidence_narrative(out):
    """Extract confidence label from strategic_narrative.py output."""
    for line in out.splitlines():
        if "Primary beneficiar" in line and "confidence:" in line:
            return line.split("confidence:")[-1].strip()
        if "Insufficient signal" in line:
            return "ABSTAIN"
    return None


def _confidence_top_exit(out):
    """Extract confidence label from scenario_library top_exit output."""
    for line in out.splitlines():
        if line.startswith("## Scenario 1:") and "confidence:" in line:
            return line.split("confidence:")[-1].strip()
    return None


# ---------------------------------------------------------------------------
# Invariant 1 — ALS-style 4-way tie at ~1.0 → strategic_narrative emits ABSTAIN
# ---------------------------------------------------------------------------
def test_narrative_als_4way_tie_abstain():
    """4 beneficiaries with mechanism_overlap=1, phase3plus=0 must produce ABSTAIN.

    Protects against ALS-style tie degeneracy per docs/fragmented_indication_stress_test.md.
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3="CompanyA,DrugA1,phase3,mechX\nCompanyA,DrugA2,phase3,mechY\n",
            phase2=(
                "CompanyA,DrugA3,phase2,mechX\n"
                "CompanyB,DrugB1,phase2,mechX\n"
                "CompanyC,DrugC1,phase2,mechY\n"
                "CompanyD,DrugD1,phase2,mechX\n"
                "CompanyE,DrugE1,phase2,mechY\n"
            ),
        )
        r = _run(_NARRATIVE, d)
        assert r.returncode == 0, f"script crashed: {r.stderr}"
        label = _confidence_narrative(r.stdout)
        assert label == "ABSTAIN", f"expected ABSTAIN, got {label!r}"
        assert "ranking" not in r.stdout.lower() or "no confident" in r.stdout.lower(), \
            "ranking table must not appear under ABSTAIN"


# ---------------------------------------------------------------------------
# Invariant 2 — ALS-style 4-way tie → scenario_library top_exit emits ABSTAIN
# ---------------------------------------------------------------------------
def test_top_exit_als_4way_tie_abstain():
    """4 beneficiaries all tied must suppress the ranking table via ABSTAIN.

    Protects against ALS-style tie degeneracy per docs/fragmented_indication_stress_test.md.
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3="CompanyA,DrugA1,phase3,mechX\nCompanyA,DrugA2,phase3,mechY\n",
            phase2=(
                "CompanyA,DrugA3,phase2,mechX\n"
                "CompanyB,DrugB1,phase2,mechX\n"
                "CompanyC,DrugC1,phase2,mechY\n"
                "CompanyD,DrugD1,phase2,mechX\n"
                "CompanyE,DrugE1,phase2,mechY\n"
            ),
        )
        r = _run(_SCENARIO, d, ["--scenarios", "top_exit"])
        assert r.returncode == 0, f"script crashed: {r.stderr}"
        label = _confidence_top_exit(r.stdout)
        assert label == "ABSTAIN", f"expected ABSTAIN, got {label!r}"
        assert "Insufficient signal" in r.stdout, "ABSTAIN message missing"
        assert "| Rank |" not in r.stdout, "ranking table must not appear under ABSTAIN"


# ---------------------------------------------------------------------------
# Invariant 3 — 2-beneficiary tie → BOTH scripts emit ABSTAIN (the subtle case)
# ---------------------------------------------------------------------------
def test_narrative_2way_tie_abstain():
    """2 beneficiaries both with overlap=1 (tie within 0.1) must produce ABSTAIN.

    This was the pre-fix failure mode: the len>=3 guard was bypassed and LOW was
    emitted instead. Regression guard per T7 investigation.
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3="CompanyA,DrugA1,phase3,mechX\nCompanyA,DrugA2,phase3,mechY\n",
            phase2="CompanyB,DrugB1,phase2,mechX\nCompanyC,DrugC1,phase2,mechY\n",
        )
        r = _run(_NARRATIVE, d)
        assert r.returncode == 0, f"script crashed: {r.stderr}"
        label = _confidence_narrative(r.stdout)
        assert label == "ABSTAIN", f"expected ABSTAIN, got {label!r}"


def test_top_exit_2way_tie_abstain():
    """scenario_library top_exit: 2-way tie must emit ABSTAIN, not LOW.

    Pre-fix behavior: len(top5)==2 branch fell through to MEDIUM/LOW without
    checking if s1 ≈ s2. Regression guard per T7 investigation.
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3="CompanyA,DrugA1,phase3,mechX\nCompanyA,DrugA2,phase3,mechY\n",
            phase2="CompanyB,DrugB1,phase2,mechX\nCompanyC,DrugC1,phase2,mechY\n",
        )
        r = _run(_SCENARIO, d, ["--scenarios", "top_exit"])
        assert r.returncode == 0, f"script crashed: {r.stderr}"
        label = _confidence_top_exit(r.stdout)
        assert label == "ABSTAIN", f"expected ABSTAIN, got {label!r}"


# ---------------------------------------------------------------------------
# Invariant 4 — 1-beneficiary-only → LOW (one real signal, no comparison point)
# ---------------------------------------------------------------------------
def test_narrative_1beneficiary_low():
    """Single beneficiary → LOW (conservative; no comparison point for ranking).

    LOW is chosen over ABSTAIN because there is one real overlap signal; ABSTAIN
    would suppress even that weak directional hint which is unhelpful when only
    one candidate exists.
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3="CompanyA,DrugA1,phase3,mechX\n",
            phase2="CompanyB,DrugB1,phase2,mechX\n",
        )
        r = _run(_NARRATIVE, d)
        assert r.returncode == 0, f"script crashed: {r.stderr}"
        label = _confidence_narrative(r.stdout)
        assert label == "LOW", f"expected LOW, got {label!r}"


def test_top_exit_1beneficiary_low():
    """Single beneficiary → LOW in scenario_library top_exit.

    Pre-fix behavior was HIGH (no comparison point yet confident = bad signal).
    Now returns LOW.
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3="CompanyA,DrugA1,phase3,mechX\n",
            phase2="CompanyB,DrugB1,phase2,mechX\n",
        )
        r = _run(_SCENARIO, d, ["--scenarios", "top_exit"])
        assert r.returncode == 0, f"script crashed: {r.stderr}"
        label = _confidence_top_exit(r.stdout)
        assert label == "LOW", f"expected LOW, got {label!r}"


# ---------------------------------------------------------------------------
# Invariant 5 — 5-way distinct ranking must NOT produce ABSTAIN (regression guardrail)
# ---------------------------------------------------------------------------
def test_distinct_ranking_not_abstain():
    """Overlaps of 4/2/1/1/1 across 5 companies must produce HIGH, not ABSTAIN.

    Ensures the tie-detection fix does not over-trigger on genuinely differentiated
    pipelines (regression guardrail).
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3=(
                "CompanyA,D1,phase3,m1\nCompanyA,D2,phase3,m2\n"
                "CompanyA,D3,phase3,m3\nCompanyA,D4,phase3,m4\n"
            ),
            phase2=(
                "CompanyB,D5,phase2,m1\nCompanyB,D6,phase2,m2\n"
                "CompanyB,D7,phase2,m3\nCompanyB,D8,phase2,m4\n"
                "CompanyC,D9,phase2,m1\nCompanyC,D10,phase2,m2\n"
                "CompanyD,D11,phase2,m1\n"
                "CompanyE,D12,phase2,m2\n"
                "CompanyF,D13,phase2,m3\n"
            ),
        )
        r_n = _run(_NARRATIVE, d)
        r_s = _run(_SCENARIO, d, ["--scenarios", "top_exit"])
        assert r_n.returncode == 0
        assert r_s.returncode == 0
        label_n = _confidence_narrative(r_n.stdout)
        label_s = _confidence_top_exit(r_s.stdout)
        assert label_n != "ABSTAIN", f"narrative: distinct ranking must not ABSTAIN, got {label_n!r}"
        assert label_s != "ABSTAIN", f"top_exit: distinct ranking must not ABSTAIN, got {label_s!r}"
        assert label_n in ("HIGH", "MEDIUM"), f"narrative: expected HIGH/MEDIUM, got {label_n!r}"
        assert label_s in ("HIGH", "MEDIUM"), f"top_exit: expected HIGH/MEDIUM, got {label_s!r}"


# ---------------------------------------------------------------------------
# Invariant 6 — crowded_consolidation on single dominant mechanism → HIGH/MEDIUM, no crash
# ---------------------------------------------------------------------------
def test_crowded_consolidation_no_crash():
    """crowded_consolidation with one clearly dominant mechanism must not crash.

    Uses mechanism_scores.csv (required by that scenario).
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3=(
                "CompanyA,D1,phase3,m1\nCompanyB,D2,phase3,m1\n"
                "CompanyC,D3,phase3,m1\nCompanyD,D4,phase3,m1\n"
            ),
            phase2="CompanyE,D5,phase2,m2\n",
        )
        # Write mechanism_scores.csv (required by crowded_consolidation)
        with open(os.path.join(d, "mechanism_scores.csv"), "w") as f:
            f.write("mechanism,active_count,company_count\n")
            f.write("m1,4,4\n")
            f.write("m2,1,1\n")
        r = _run(_SCENARIO, d, ["--scenarios", "crowded_consolidation"])
        assert r.returncode == 0, f"script crashed: {r.stderr}"
        assert "Scenario 2" in r.stdout, "expected crowded_consolidation output"
        # Must not ABSTAIN — single dominant mechanism is legitimate signal
        for line in r.stdout.splitlines():
            if "Scenario 2" in line and "confidence:" in line:
                label = line.split("confidence:")[-1].strip()
                assert label in ("HIGH", "MEDIUM", "LOW"), f"unexpected label: {label!r}"
                break


# ---------------------------------------------------------------------------
# Invariant 7 — loe_wave on zero launched drugs → ABSTAIN (existing guarantee)
# ---------------------------------------------------------------------------
def test_loe_wave_zero_launched_abstain():
    """loe_wave with no companies having launched drugs must emit ABSTAIN.

    Documents the already-correct behavior as a regression guardrail.
    Per docs/fragmented_indication_stress_test.md section 3 (LOE wave findings).
    """
    with tempfile.TemporaryDirectory() as d:
        _write_csvs(d,
            phase3="CompanyA,D1,phase3,m1\nCompanyB,D2,phase3,m2\n",
        )
        # Write loe_metrics.csv with no launched drugs
        with open(os.path.join(d, "loe_metrics.csv"), "w") as f:
            f.write("company,launched,phase3,refill_gap,loe_exposure_pct,risk_flag\n")
            f.write("CompanyA,0,1,-1,0.0,low\n")
            f.write("CompanyB,0,1,-1,0.0,low\n")
        r = _run(_SCENARIO, d, ["--scenarios", "loe_wave"])
        assert r.returncode == 0, f"script crashed: {r.stderr}"
        for line in r.stdout.splitlines():
            if "Scenario 3" in line and "confidence:" in line:
                label = line.split("confidence:")[-1].strip()
                assert label == "ABSTAIN", f"expected ABSTAIN on zero-launched, got {label!r}"
                break
        else:
            assert False, "Scenario 3 confidence line not found in output"
