"""wiki_refresh.py — Tiered wiki refresh orchestrator.

Tier 1 — compile-only:   recompile all wiki articles from existing raw/ data.
Tier 2 — fetch+compile:  re-fetch structured/external data, then recompile (no LLM).
Tier 3 — full:           full refresh including LLM synthesis (Claude API, not yet impl).

Entry points:
    refresh_compile(base_dir, types, verbose)  → Tier 1
    refresh_data(base_dir, types, verbose)     → Tier 2
    refresh_full(base_dir, types, verbose)     → Tier 3
"""

import importlib.util
import json
import os
import subprocess
import sys
from typing import Optional

from cli_anything.cortellis.utils.data_helpers import read_json_safe
from cli_anything.cortellis.utils.wiki import (
    article_path,
    list_articles,
    load_index_entries,
    log_activity,
    update_index,
    wiki_root,
    write_article,
)
from cli_anything.cortellis.core.graph_utils import refresh_graph


ALL_TYPES = {"drug", "target", "company", "indication", "conference"}
_TIER2_TYPES = {"drug", "target", "company"}  # indication needs full landscape; conference has no structured fetch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_path(path: str, base_dir: str) -> str:
    if not path:
        return ""
    return path if os.path.isabs(path) else os.path.join(base_dir, path)


def _skill_recipe(skill_dir: str, recipe_name: str) -> str:
    return os.path.join(
        os.path.dirname(__file__), "..", "skills", skill_dir, "recipes", recipe_name
    )


def _load_compile_recipe(skill_dir: str, recipe_name: str):
    """Dynamically load a compile recipe — handles hyphenated skill dir names."""
    path = _skill_recipe(skill_dir, recipe_name)
    if not os.path.exists(path):
        raise ImportError(f"Recipe not found: {path}")
    mod_name = recipe_name.replace(".py", "").replace("-", "_")
    spec = importlib.util.spec_from_file_location(mod_name, os.path.abspath(path))
    mod = importlib.util.module_from_spec(spec)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    spec.loader.exec_module(mod)
    return mod


def _run_script(cmd: list, verbose: bool = False) -> bool:
    """Run a command. Returns True on success, False on failure (non-fatal)."""
    if verbose:
        print(f"      $ {' '.join(str(c) for c in cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=not verbose, text=True)
    if result.returncode != 0 and verbose:
        print(f"      [warn] exit {result.returncode}", flush=True)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Tier 1 — compile-only
# ---------------------------------------------------------------------------

def refresh_compile(
    base_dir: str,
    types: Optional[set] = None,
    verbose: bool = True,
    dry_run: bool = False,
) -> dict:
    """Tier 1: recompile all wiki articles from existing raw/ data. No API calls."""
    w_dir = wiki_root(base_dir)
    articles = list_articles(w_dir)
    types = types or ALL_TYPES
    results: dict = {"ok": [], "skipped": [], "error": []}

    for art in articles:
        meta = art.get("meta") or {}
        atype = meta.get("type", "")
        slug = meta.get("slug", "")
        title = meta.get("title", slug)

        if not slug or atype not in types:
            continue

        if verbose:
            print(f"  [{atype:12}] {slug} ...", end=" ", flush=True)

        if dry_run:
            print("(dry-run)")
            results["ok"].append(slug)
            continue

        try:
            _compile_one(atype, meta, slug, title, base_dir)
            results["ok"].append(slug)
            if verbose:
                print("ok")
        except _SkipError as exc:
            results["skipped"].append((slug, str(exc)))
            if verbose:
                print(f"skip — {exc}")
        except Exception as exc:
            results["error"].append((slug, str(exc)))
            if verbose:
                print(f"ERROR: {exc}")

    if not dry_run:
        _finalize(w_dir, base_dir, "compile-only", results)

    return results


def _compile_one(atype: str, meta: dict, slug: str, title: str, base_dir: str) -> None:
    if atype == "drug":
        source_dir = _resolve_path(meta.get("source_dir", ""), base_dir)
        if not source_dir or not os.path.isdir(source_dir):
            raise _SkipError(f"source_dir not found: {meta.get('source_dir')}")
        mod = _load_compile_recipe("drug-profile", "compile_drug.py")
        new_meta, body = mod.compile_drug_article(source_dir, title, slug, base_dir)
        write_article(article_path("drugs", slug, base_dir), new_meta, body)

    elif atype == "target":
        source_dir = _resolve_path(meta.get("source_dir", ""), base_dir)
        if not source_dir or not os.path.isdir(source_dir):
            raise _SkipError(f"source_dir not found: {meta.get('source_dir')}")
        mod = _load_compile_recipe("target-profile", "compile_target.py")
        new_meta, body = mod.compile_target_article(source_dir, title, slug, base_dir)
        write_article(article_path("targets", slug, base_dir), new_meta, body)

    elif atype == "company":
        pipeline_meta = meta.get("pipeline", {})
        pipeline_dir = pipeline_meta.get("pipeline_dir", "") if isinstance(pipeline_meta, dict) else ""
        if pipeline_dir and os.path.isdir(pipeline_dir):
            mod = _load_compile_recipe("pipeline", "compile_pipeline.py")
            new_meta, body = mod.compile_pipeline_article(pipeline_dir, title, slug, base_dir)
            write_article(article_path("companies", slug, base_dir), new_meta, body)
        else:
            raise _SkipError("landscape-only company — run landscape skill to refresh")

    elif atype == "indication":
        source_dir = _resolve_path(meta.get("source_dir", ""), base_dir)
        if not source_dir or not os.path.isdir(source_dir):
            raise _SkipError(f"source_dir not found: {meta.get('source_dir')}")
        mod = _load_compile_recipe("landscape", "compile_dossier.py")
        new_meta, body = mod.compile_indication_article(source_dir, title, slug, base_dir)
        write_article(article_path("indications", slug, base_dir), new_meta, body)

    elif atype == "conference":
        source_dir = _resolve_path(meta.get("source_dir", ""), base_dir)
        if not source_dir or not os.path.isdir(source_dir):
            raise _SkipError(f"source_dir not found: {meta.get('source_dir')}")
        mod = _load_compile_recipe("conference-intel", "compile_conference.py")
        new_meta, body = mod.compile_conference_article(source_dir, title, slug, base_dir)
        write_article(article_path("conferences", slug, base_dir), new_meta, body)

    else:
        raise _SkipError(f"unknown type: {atype}")


# ---------------------------------------------------------------------------
# Tier 2 — fetch + enrich + compile (no LLM)
# ---------------------------------------------------------------------------

def refresh_data(
    base_dir: str,
    types: Optional[set] = None,
    verbose: bool = True,
    dry_run: bool = False,
) -> dict:
    """Tier 2: re-fetch structured/external data from APIs, then recompile. No LLM.

    Coverage:
      drug     — re-fetch Cortellis record + re-run all external enrichers
      target   — re-run external enrichers (UniProt, OpenTargets, ChEMBL, CPIC)
      company  — re-run fetch_phase.sh pipeline CSVs + compile
      indication / conference — not supported (use landscape skill / Tier 3)
    """
    w_dir = wiki_root(base_dir)
    articles = list_articles(w_dir)
    types = (types or _TIER2_TYPES) & _TIER2_TYPES
    results: dict = {"ok": [], "skipped": [], "error": []}

    for art in articles:
        meta = art.get("meta") or {}
        atype = meta.get("type", "")
        slug = meta.get("slug", "")
        title = meta.get("title", slug)

        if not slug or atype not in types:
            continue

        if verbose:
            print(f"  [{atype:12}] {slug} ...", flush=True)

        if dry_run:
            print("    (dry-run)")
            results["ok"].append(slug)
            continue

        try:
            _fetch_one(atype, meta, slug, title, base_dir, verbose)
            _compile_one(atype, meta, slug, title, base_dir)
            results["ok"].append(slug)
            if verbose:
                print(f"    [{slug}] done")
        except _SkipError as exc:
            results["skipped"].append((slug, str(exc)))
            if verbose:
                print(f"    skip — {exc}")
        except Exception as exc:
            results["error"].append((slug, str(exc)))
            if verbose:
                print(f"    ERROR: {exc}")

    if not dry_run:
        _finalize(w_dir, base_dir, "data", results)

    return results


def _fetch_one(atype: str, meta: dict, slug: str, title: str, base_dir: str, verbose: bool) -> None:
    if atype == "drug":
        source_dir = _resolve_path(meta.get("source_dir", ""), base_dir)
        if not source_dir or not os.path.isdir(source_dir):
            raise _SkipError(f"source_dir not found: {meta.get('source_dir')}")
        _fetch_drug(source_dir, title, verbose)

    elif atype == "target":
        source_dir = _resolve_path(meta.get("source_dir", ""), base_dir)
        if not source_dir or not os.path.isdir(source_dir):
            raise _SkipError(f"source_dir not found: {meta.get('source_dir')}")
        gene_symbol = meta.get("gene_symbol", "")
        _fetch_target(source_dir, title, gene_symbol, verbose)

    elif atype == "company":
        pipeline_meta = meta.get("pipeline", {})
        pipeline_dir = pipeline_meta.get("pipeline_dir", "") if isinstance(pipeline_meta, dict) else ""
        if not pipeline_dir or not os.path.isdir(pipeline_dir):
            raise _SkipError("no pipeline_dir — run landscape skill to refresh")
        _fetch_pipeline(pipeline_dir, title, verbose)

    else:
        raise _SkipError(f"Tier 2 not supported for type: {atype}")


def _fetch_drug(source_dir: str, drug_name: str, verbose: bool) -> None:
    """Re-fetch Cortellis drug record + all external enrichers."""
    record = read_json_safe(os.path.join(source_dir, "record.json")) or {}
    rec = record.get("drugRecordOutput", record)
    drug_id = rec.get("@id", "")
    if not drug_id:
        raise ValueError(f"No drug ID in {source_dir}/record.json")

    if verbose:
        print(f"    fetching Cortellis record (id={drug_id})...", flush=True)

    # Re-fetch core record
    record_path = os.path.join(source_dir, "record.json")
    with open(record_path, "w", encoding="utf-8") as f:
        result = subprocess.run(
            ["cortellis", "--json", "drugs", "records", drug_id],
            stdout=f, stderr=subprocess.PIPE, text=True,
        )
    if result.returncode != 0:
        raise RuntimeError(f"cortellis drugs records failed: {result.stderr[:200]}")

    # Re-fetch trials (shell script)
    trials_sh = _skill_recipe("drug-profile", "fetch_trials.sh")
    if os.path.exists(trials_sh):
        _run_script(
            ["bash", trials_sh, drug_name, os.path.join(source_dir, "trials.json")],
            verbose=verbose,
        )

    # Re-run external enrichers
    python = sys.executable
    for script, extra_args in [
        ("enrich_ct_trials.py",    []),
        ("enrich_fda_approval.py", []),
        ("enrich_fda_patent.py",   []),
        ("enrich_ema.py",          []),
        ("enrich_chembl.py",       []),
        ("enrich_cpic.py",         []),
        ("enrich_biorxiv.py",      []),
    ]:
        path = _skill_recipe("drug-profile", script)
        if os.path.exists(path):
            _run_script([python, path, source_dir, drug_name] + extra_args, verbose=verbose)


def _fetch_target(source_dir: str, target_name: str, gene_symbol: str, verbose: bool) -> None:
    """Re-run external enrichers for a target (UniProt, OpenTargets, ChEMBL, CPIC).

    Note: re-fetching the Cortellis target record requires multi-step shell scripts
    from the target-profile skill. That is deferred to Tier 3 (full skill re-run).
    """
    python = sys.executable
    identifier = gene_symbol or target_name

    if verbose:
        print(f"    re-running external enrichers (gene={identifier})...", flush=True)

    for script, arg in [
        ("enrich_target_uniprot.py",     identifier),
        ("enrich_target_opentargets.py", identifier),
        ("enrich_target_chembl.py",      identifier),
        ("enrich_target_cpic.py",        identifier),
        ("enrich_target_patents.py",     target_name),
    ]:
        path = _skill_recipe("target-profile", script)
        if os.path.exists(path):
            _run_script([python, path, source_dir, arg], verbose=verbose)


def _fetch_pipeline(pipeline_dir: str, company_name: str, verbose: bool) -> None:
    """Re-resolve company ID and re-fetch pipeline CSVs from Cortellis."""
    resolve_script = _skill_recipe("pipeline", "resolve_company.py")
    if not os.path.exists(resolve_script):
        raise ValueError("resolve_company.py not found")

    if verbose:
        print(f"    resolving company ID for '{company_name}'...", flush=True)

    result = subprocess.run(
        [sys.executable, resolve_script, company_name],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"resolve_company failed: {result.stdout[:200]}")

    # resolve_company.py outputs JSON with id field, or plain text
    company_id = ""
    try:
        resolved = json.loads(result.stdout)
        company_id = str(resolved.get("id", ""))
    except (json.JSONDecodeError, AttributeError):
        company_id = result.stdout.strip()

    if not company_id:
        raise ValueError(f"Could not resolve company ID for '{company_name}'")

    if verbose:
        print(f"    fetching pipeline phases (company_id={company_id})...", flush=True)

    fetch_sh = _skill_recipe("pipeline", "fetch_phase.sh")
    recipes_dir = os.path.dirname(fetch_sh)
    if not os.path.exists(fetch_sh):
        raise ValueError("fetch_phase.sh not found")

    for phase_code, filename in [
        ("L",  "launched.csv"),
        ("C3", "phase3.csv"),
        ("C2", "phase2.csv"),
        ("C1", "phase1_ci.csv"),
        ("DR", "discovery_ci.csv"),
    ]:
        _run_script(
            ["bash", fetch_sh, company_id, phase_code,
             os.path.join(pipeline_dir, filename), recipes_dir],
            verbose=verbose,
        )

    # Re-run external enrichers
    python = sys.executable
    enrich_script = _skill_recipe("pipeline", "enrich_pipeline_external.py")
    if os.path.exists(enrich_script):
        _run_script([python, enrich_script, pipeline_dir, company_name], verbose=verbose)


# ---------------------------------------------------------------------------
# Tier 3 — full refresh with LLM synthesis
# ---------------------------------------------------------------------------

def refresh_full(
    base_dir: str,
    types: Optional[set] = None,
    verbose: bool = True,
    dry_run: bool = False,
) -> dict:
    """Tier 3: full refresh including LLM synthesis via Claude API.

    Not yet implemented. LLM synthesis (SWOT, narratives, reports) requires
    orchestrating Claude agent runs per entity — the full skill workflow.

    To refresh with LLM synthesis today, re-run each skill manually:
      /drug-profile <name>
      /target-profile <name>
      /pipeline <company>
      /landscape <indication>
    """
    raise NotImplementedError(
        "Tier 3 (full refresh with LLM synthesis) is not yet implemented.\n\n"
        "To refresh with LLM synthesis, re-run skills manually:\n"
        "  /drug-profile <name>\n"
        "  /target-profile <name>\n"
        "  /pipeline <company>\n"
        "  /landscape <indication>"
    )


# ---------------------------------------------------------------------------
# Shared finalization
# ---------------------------------------------------------------------------

def _finalize(w_dir: str, base_dir: str, tier_label: str, results: dict) -> None:
    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    refresh_graph(base_dir)
    ok = len(results["ok"])
    skipped = len(results["skipped"])
    errors = len(results["error"])
    log_activity(w_dir, "refresh", f"{tier_label}: {ok} ok, {skipped} skipped, {errors} errors")


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------

class _SkipError(Exception):
    """Non-fatal: article cannot be refreshed for a known reason (skip, not error)."""
