#!/usr/bin/env python3
"""
batch_compile_pipeline.py — Compile wiki articles for all obesity KB companies.

Reads company titles from pharma-kb obesity articles, runs compile_pipeline.py
for each company that has a raw/pipeline/<slug>/ directory.

Usage:
    python3 batch_compile_pipeline.py [--kb-dir PATH] [--workers N] [--dry-run]
"""

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT = Path(__file__).parent / "cli_anything/cortellis/skills/pipeline/recipes/compile_pipeline.py"
DEFAULT_KB_DIR = Path(__file__).parent.parent / "pharma-kb/datasets/obesity/companies"
RAW_PIPELINE_DIR = Path(__file__).parent / "raw/pipeline"
WIKI_DIR = Path(__file__).parent


def parse_frontmatter(path: Path) -> dict:
    """Extract title and slug from YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = parts[1]
    title_m = re.search(r'^title:\s*(.+)$', fm, re.MULTILINE)
    slug_m = re.search(r'^slug:\s*(.+)$', fm, re.MULTILINE)
    return {
        "title": title_m.group(1).strip().strip("'\"") if title_m else None,
        "slug": slug_m.group(1).strip().strip("'\"") if slug_m else None,
    }


def run_compile(slug: str, company_name: str, dry_run: bool) -> tuple[str, bool, str]:
    """Run compile_pipeline.py for one company. Returns (slug, success, message)."""
    pipeline_dir = str(RAW_PIPELINE_DIR / slug)

    if dry_run:
        return slug, True, f"[dry-run] would compile {company_name!r} → wiki/companies/{slug}.md"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), pipeline_dir, company_name, "--wiki-dir", str(WIKI_DIR)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode == 0:
        last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "ok"
        return slug, True, last
    else:
        err = (result.stderr or result.stdout or "unknown error").strip().splitlines()[-1]
        return slug, False, err


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch pipeline compile for obesity KB companies")
    parser.add_argument("--kb-dir", type=Path, default=DEFAULT_KB_DIR, help="Path to obesity KB companies dir")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers (default: 4)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would run without writing")
    args = parser.parse_args()

    if not args.kb_dir.exists():
        print(f"Error: KB dir not found: {args.kb_dir}", file=sys.stderr)
        sys.exit(1)

    articles = sorted(args.kb_dir.glob("*.md"))
    companies: list[tuple[str, str]] = []

    for path in articles:
        fm = parse_frontmatter(path)
        slug = fm.get("slug") or path.stem
        title = fm.get("title") or slug.replace("-", " ").title()
        if slug == "undisclosed" or not title:
            continue
        pipeline_dir = RAW_PIPELINE_DIR / slug
        if not pipeline_dir.exists():
            continue
        companies.append((slug, title))

    total = len(companies)
    print(f"Companies to compile: {total} (workers: {args.workers}{'  DRY RUN' if args.dry_run else ''})")

    succeeded, failed = 0, 0
    failures: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(run_compile, slug, title, args.dry_run): (slug, title)
            for slug, title in companies
        }
        done = 0
        for future in as_completed(futures):
            slug, title = futures[future]
            done += 1
            try:
                _, ok, msg = future.result()
            except Exception as e:
                ok, msg = False, str(e)

            status = "✓" if ok else "✗"
            print(f"  [{done:3d}/{total}] {status} {title[:40]:<40} {msg[:60]}")
            if ok:
                succeeded += 1
            else:
                failed += 1
                failures.append((slug, msg))

    print(f"\nDone: {succeeded} succeeded, {failed} failed")
    if failures:
        print("\nFailures:")
        for slug, msg in failures:
            print(f"  {slug}: {msg}")


if __name__ == "__main__":
    main()
