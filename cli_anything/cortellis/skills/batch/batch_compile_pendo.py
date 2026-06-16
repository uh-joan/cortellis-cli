#!/usr/bin/env python3
"""
batch_compile_pendo.py — Recompile wiki articles that have Pendo data, then re-export to pharma-kb.

Finds all raw/drugs/<slug>/pendo_summary.md and raw/pipeline/<slug>/pendo_watchlist.md,
runs compile_drug.py / compile_pipeline.py for each, recompiles the indication dossier,
then runs export.py.

Usage:
    python3 batch_compile_pendo.py [--indication obesity] [--wiki-dir .] [--export-dir ../pharma-kb] [--no-export]
"""

import json
import subprocess
import sys
import yaml
from pathlib import Path

RECIPES_DRUG      = Path("cli_anything/cortellis/skills/drug-profile/recipes")
RECIPES_PIPELINE  = Path("cli_anything/cortellis/skills/pipeline/recipes")
RECIPES_LANDSCAPE = Path("cli_anything/cortellis/skills/landscape/recipes")


def get_title(wiki_subdir: Path, slug: str, fallback: str) -> str:
    p = wiki_subdir / f"{slug}.md"
    if not p.exists():
        return fallback
    parts = p.read_text().split("---", 2)
    if len(parts) < 3:
        return fallback
    fm = yaml.safe_load(parts[1]) or {}
    return fm.get("title") or fallback


def run(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    FAILED: {result.stderr.strip()[:300]}")
        return False
    return True


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indication", default="obesity")
    parser.add_argument("--wiki-dir", default=".")
    parser.add_argument("--export-dir", default="../pharma-kb")
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args()

    wiki_dir = Path(args.wiki_dir) / "wiki"

    # --- Landscape indication ---
    indication_dir = f"raw/{args.indication}"
    if Path(indication_dir, "pendo_landscape.md").exists():
        print(f"Compiling indication: {args.indication}")
        ok = run([
            "python3", str(RECIPES_LANDSCAPE / "compile_dossier.py"),
            indication_dir, args.indication.capitalize(),
            "--wiki-dir", args.wiki_dir,
        ])
        print(f"  {'✓' if ok else '✗'} {args.indication}")

    # --- Drugs ---
    drug_md_paths = sorted(Path("raw/drugs").glob("*/pendo_summary.md"))
    print(f"\nCompiling {len(drug_md_paths)} drugs…")
    compiled_drugs, failed_drugs = 0, 0
    for md_path in drug_md_paths:
        slug = md_path.parent.name
        name = get_title(wiki_dir / "drugs", slug, slug)
        ok = run([
            "python3", str(RECIPES_DRUG / "compile_drug.py"),
            str(md_path.parent), name, "--wiki-dir", args.wiki_dir,
        ])
        if ok:
            compiled_drugs += 1
            print(f"  ✓ {slug}")
        else:
            failed_drugs += 1
            print(f"  ✗ {slug}")

    # --- Pipeline companies ---
    company_md_paths = sorted(Path("raw/pipeline").glob("*/pendo_watchlist.md"))
    print(f"\nCompiling {len(company_md_paths)} companies…")
    compiled_cos, failed_cos = 0, 0
    for md_path in company_md_paths:
        slug = md_path.parent.name
        json_path = md_path.parent / "pendo_watchlist.json"
        name = json.loads(json_path.read_text())["company_name"]
        ok = run([
            "python3", str(RECIPES_PIPELINE / "compile_pipeline.py"),
            str(md_path.parent), name, "--wiki-dir", args.wiki_dir,
        ])
        if ok:
            compiled_cos += 1
            print(f"  ✓ {slug}")
        else:
            failed_cos += 1
            print(f"  ✗ {slug}")

    total_failures = failed_drugs + failed_cos
    print(
        f"\nCompile: {compiled_drugs} drugs · {compiled_cos} companies"
        + (f" · {total_failures} failures" if total_failures else "")
    )

    # --- Export ---
    if not args.no_export:
        export_script = Path(args.export_dir) / "scripts/export.py"
        if not export_script.exists():
            print(f"\nExport script not found at {export_script} — skipping")
            return
        print(f"\nExporting {args.indication} → {args.export_dir}…")
        ok = run(["python3", str(export_script), "--indication", args.indication])
        print(f"  {'✓ Export complete' if ok else '✗ Export failed'}")


if __name__ == "__main__":
    main()
