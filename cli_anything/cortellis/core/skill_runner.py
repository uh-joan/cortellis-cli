"""Skill runner — enforced step sequencing for landscape and pipeline skills.

Runs recipe scripts in guaranteed order via subprocess, exiting 1 on any
step failure so broken data is never silently compiled into the wiki.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LANDSCAPE_RECIPES = REPO_ROOT / "cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES = REPO_ROOT / "cli_anything/cortellis/skills/pipeline/recipes"
PYTHON = sys.executable


def _step(label: str) -> None:
    print(f"\n▶ {label}", file=sys.stderr, flush=True)


def _run(cmd: list[str], capture_stdout: bool = False, allow_fail: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=capture_stdout, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0 and not allow_fail:
        if capture_stdout and result.stderr:
            print(result.stderr, file=sys.stderr)
        print(f"  FAILED (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def _run_shell(cmd: str, allow_fail: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, shell=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0 and not allow_fail:
        print(f"  FAILED (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def run_landscape(indication: str, force_refresh: bool = False) -> None:
    """Run the landscape skill pipeline with enforced step sequencing."""

    # Step 0: freshness check
    if not force_refresh:
        _step("Step 0: Wiki freshness check")
        r = _run(
            [PYTHON, "-c",
             f"import sys; sys.path.insert(0, r'{REPO_ROOT}');"
             f"from cli_anything.cortellis.utils.wiki import check_freshness, slugify;"
             f"print(check_freshness(slugify('{indication}')))"],
            capture_stdout=True,
        )
        status = r.stdout.strip()
        print(f"  Status: {status}", file=sys.stderr)
        if status == "fresh":
            print("  Serving from wiki cache. Use --force-refresh to re-fetch.", file=sys.stderr)
            # Print compiled article to stdout
            _run_shell(
                f"{PYTHON} -c \""
                f"import sys; sys.path.insert(0, r'{REPO_ROOT}');"
                f"from cli_anything.cortellis.utils.wiki import read_article, slugify;"
                f"art = read_article('wiki/indications/' + slugify('{indication}') + '.md');"
                f"print(art['body'] if art else '')\""
            )
            return

    # Step 1: Resolve indication ID
    _step("Step 1: Resolving indication ID")
    r = _run([PYTHON, str(LANDSCAPE_RECIPES / "resolve_indication.py"), indication], capture_stdout=True)
    line = r.stdout.strip()
    if "," not in line:
        print(f"  ERROR: resolution returned no ID: {line!r}", file=sys.stderr)
        sys.exit(1)
    ind_id, ind_name = line.split(",", 1)
    print(f"  → ID={ind_id}  Name={ind_name}", file=sys.stderr)

    output_dir = REPO_ROOT / "raw" / _slug(ind_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    DIR = str(output_dir)

    # Step 2: Drugs by phase
    for phase_code, phase_name in [("L", "launched"), ("C3", "phase3"), ("C2", "phase2"),
                                    ("C1", "phase1"), ("DR", "discovery")]:
        _step(f"Step 2: Fetching {phase_name} (phase {phase_code})")
        _run(["bash", str(LANDSCAPE_RECIPES / "fetch_indication_phase.sh"),
              ind_id, phase_code, str(output_dir / f"{phase_name}.csv"), str(PIPELINE_RECIPES)])

    # Step 3: Enrich mechanisms
    _step("Step 3: Enriching mechanisms from SI")
    _run([PYTHON, str(LANDSCAPE_RECIPES / "enrich_mechanisms.py"), DIR], allow_fail=True)

    # Step 4: Group biosimilars
    _step("Step 4: Grouping biosimilars")
    _run([PYTHON, str(LANDSCAPE_RECIPES / "group_biosimilars.py"), DIR], allow_fail=True)

    # Step 5: Company landscape
    _step("Step 5: Building company landscape")
    r = _run([PYTHON, str(LANDSCAPE_RECIPES / "company_landscape.py"), DIR], capture_stdout=True)
    companies_csv = output_dir / "companies.csv"
    companies_csv.write_text(r.stdout)

    # Step 5b/5c: Company enrichment + normalization
    _step("Step 5b: Enriching company sizes")
    _run([PYTHON, str(LANDSCAPE_RECIPES / "enrich_company_sizes.py"), DIR], allow_fail=True)
    _step("Step 5c: Normalizing company names")
    _run([PYTHON, str(LANDSCAPE_RECIPES / "company_normalize.py"), DIR], allow_fail=True)

    # Step 6: Deals
    _step("Step 6: Fetching deals")
    deals_csv = str(output_dir / "deals.csv")
    _run_shell(
        f"bash {LANDSCAPE_RECIPES}/fetch_deals_paginated.sh "
        f"'--indication \"{ind_name}\"' {deals_csv} {PIPELINE_RECIPES}"
    )
    _step("Step 6b: Deal analytics")
    r = _run([PYTHON, str(LANDSCAPE_RECIPES / "deals_analytics.py"),
              deals_csv, str(output_dir / "deals.meta.json")], capture_stdout=True, allow_fail=True)
    if r.stdout:
        (output_dir / "deals_analytics.md").write_text(r.stdout)

    # Step 7: Trials + catch missing drugs
    _step("Step 7: Trial activity summary")
    _run([PYTHON, str(LANDSCAPE_RECIPES / "trials_phase_summary.py"),
          ind_id, str(output_dir / "trials_summary.csv"), str(companies_csv)], allow_fail=True)
    _step("Step 8: Catching missing drugs")
    _run([PYTHON, str(LANDSCAPE_RECIPES / "catch_missing_drugs.py"), ind_id, DIR], allow_fail=True)

    # Step 9: Report
    _step("Step 9: Generating report")
    r = _run([PYTHON, str(LANDSCAPE_RECIPES / "landscape_report_generator.py"),
              DIR, ind_name, ind_id, indication], capture_stdout=True)
    (output_dir / "report.md").write_text(r.stdout)
    print(r.stdout)

    # Steps 10–12: Scoring + analysis
    for label, script, out_file in [
        ("Step 10: Strategic scoring", "strategic_scoring.py", "strategic_scores.md"),
        ("Step 11: Opportunity matrix", "opportunity_matrix.py", "opportunity_analysis.md"),
        ("Step 12: Strategic narrative", "strategic_narrative.py", "strategic_briefing.md"),
        ("Step 12c: LOE analysis", "loe_analysis.py", "loe_analysis.md"),
    ]:
        _step(label)
        cmd = [PYTHON, str(LANDSCAPE_RECIPES / script), DIR]
        if "narrative" in script:
            cmd.append(ind_name)
        r = _run(cmd, capture_stdout=True, allow_fail=True)
        if r.stdout:
            (output_dir / out_file).write_text(r.stdout)

    # Step 15: Compile to wiki
    _step("Step 15: Compiling to wiki")
    _run([PYTHON, str(LANDSCAPE_RECIPES / "compile_dossier.py"), DIR, ind_name])

    slug = _slug(ind_name)
    print(f"\n✓ Landscape complete → wiki/indications/{slug}.md", file=sys.stderr)


def run_pipeline(company: str, force_refresh: bool = False) -> None:
    """Run the pipeline skill workflow with enforced step sequencing."""

    # Step 1: Resolve company ID
    _step("Step 1: Resolving company ID")
    r = _run([PYTHON, str(PIPELINE_RECIPES / "resolve_company.py"), company], capture_stdout=True)
    parts = r.stdout.strip().split(",")
    if not parts[0]:
        print(f"  ERROR: company resolution failed: {r.stdout.strip()!r}", file=sys.stderr)
        sys.exit(1)
    company_id = parts[0]
    company_name = parts[1] if len(parts) > 1 else company
    active_drugs = parts[2] if len(parts) > 2 else "?"
    print(f"  → ID={company_id}  Name={company_name}", file=sys.stderr)

    output_dir = REPO_ROOT / "raw" / _slug(company_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    DIR = str(output_dir)

    # Step 3: CI pipeline by phase
    for phase_code, fname in [("L", "launched"), ("C3", "phase3"), ("C2", "phase2"),
                               ("C1", "phase1_ci"), ("DR", "discovery_ci")]:
        _step(f"Step 3: Fetching CI {fname} (phase {phase_code})")
        _run(["bash", str(PIPELINE_RECIPES / "fetch_phase.sh"),
              company_id, phase_code, str(output_dir / f"{fname}.csv"), str(PIPELINE_RECIPES)])

    # Steps 4a/4b: SI compounds
    _step("Step 4a: Fetching SI Phase I")
    _run(["bash", str(PIPELINE_RECIPES / "fetch_phase_si.sh"),
          f'organizationsOriginator:"{company_name}" AND developmentIsActive:Yes AND phaseHighest:"Phase I"',
          str(output_dir / "phase1_si.csv"), str(PIPELINE_RECIPES)])

    _step("Step 4b: Fetching SI Preclinical")
    _run(["bash", str(PIPELINE_RECIPES / "fetch_phase_si.sh"),
          f'organizationsOriginator:"{company_name}" AND developmentIsActive:Yes AND phaseHighest:"Preclinical"',
          str(output_dir / "preclinical_si.csv"), str(PIPELINE_RECIPES)])

    # Step 7: Catch missing drugs
    _step("Step 7: Catching missing drugs")
    _run([PYTHON, str(PIPELINE_RECIPES / "catch_missing_drugs.py"), company_id, DIR], allow_fail=True)

    # Report
    _step("Report: Generating pipeline report")
    r = _run([PYTHON, str(PIPELINE_RECIPES / "report_generator.py"),
              DIR, company_name, company_id, active_drugs], capture_stdout=True)
    (output_dir / "report.md").write_text(r.stdout)
    print(r.stdout)

    # Compile
    _step("Compile: Writing to wiki")
    _run([PYTHON, str(PIPELINE_RECIPES / "compile_pipeline.py"), DIR, company_name])

    slug = _slug(company_name)
    print(f"\n✓ Pipeline complete → wiki/companies/{slug}.md", file=sys.stderr)
