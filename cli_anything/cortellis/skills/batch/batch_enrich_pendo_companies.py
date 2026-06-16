#!/usr/bin/env python3
"""
batch_enrich_pendo_companies.py — Batch Pendo watchlist enrichment for all companies in a KB indication.

Reads wiki companies with the given indication, resolves Pendo account IDs via a single
account_views call, then fetches 7-day drug watchlists for all matched companies concurrently.

Companies without pipeline CSVs still work — all watched drugs appear as external
(in_own_pipeline=False) since there are no local CSVs to cross-reference.

Usage:
    python3 batch_enrich_pendo_companies.py [--indication obesity] [--wiki-dir .] [--workers 20] [--force]
"""

import difflib
import importlib.util
import json
import os
import sys
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from dotenv import load_dotenv
load_dotenv()

MAX_WORKERS = 20
SKILLS_DIR = Path(__file__).resolve().parent.parent


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_company_targets(wiki_dir: Path, indication: str) -> list[tuple[str, str, str]]:
    """Return [(slug, pipeline_dir, company_name), ...] for wiki companies in this indication."""
    targets = []
    for p in sorted((wiki_dir / "companies").glob("*.md")):
        text = p.read_text()
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        fm = yaml.safe_load(parts[1]) or {}
        if indication not in (fm.get("indications") or {}):
            continue
        slug = p.stem
        title = fm.get("title") or slug
        targets.append((slug, f"raw/pipeline/{slug}", title))
    return targets


def is_fresh(pipeline_dir: str) -> bool:
    p = Path(pipeline_dir) / "pendo_watchlist.md"
    if not p.exists():
        return False
    return datetime.fromtimestamp(p.stat().st_mtime).date() == date.today()


def resolve_all_accounts(
    mod, client, targets: list[tuple[str, str, str]]
) -> dict[str, tuple[str, str]]:
    """One account_views call → {slug: (account_id, matched_name)} for all matched companies."""
    print("  Fetching subscriber account list (1 API call)…")
    results = mod.account_views(client, days_ago=3, limit=5000).get("results", [])
    candidates = [
        (r.get("account_name", ""), r.get("accountId", ""))
        for r in results
        if r.get("account_name") and r.get("accountId")
    ]

    resolved: dict[str, tuple[str, str]] = {}
    for slug, _, company_name in targets:
        name_lower = company_name.lower()
        # Substring match (case-insensitive)
        for acct_name, aid in candidates:
            if name_lower in acct_name.lower() or acct_name.lower() in name_lower:
                resolved[slug] = (aid, acct_name)
                break
        else:
            # Fuzzy fallback
            names = [a for a, _ in candidates]
            matches = difflib.get_close_matches(company_name, names, n=1, cutoff=0.6)
            if matches:
                for acct_name, aid in candidates:
                    if acct_name == matches[0]:
                        resolved[slug] = (aid, acct_name)
                        break

    print(f"  Resolved {len(resolved)}/{len(targets)} companies in subscriber list")
    return resolved


def enrich_one(
    mod, client, slug: str, pipeline_dir: str, company_name: str, account_id: str,
    drug_cache: dict,
) -> tuple[str, str]:
    os.makedirs(pipeline_dir, exist_ok=True)
    Path(pipeline_dir, "pendo_account_id.txt").write_text(
        f"{account_id}|{date.today().isoformat()}"
    )

    try:
        raw_results = mod.account_drugs(
            client, account_id, days=mod.DAYS, limit=mod.WATCHLIST_LIMIT
        ).get("results", [])
        truncated = len(raw_results) == mod.WATCHLIST_LIMIT

        own_drug_ids = mod.load_own_drug_ids(pipeline_dir)

        unresolved_ids = [
            str(r.get("parameters", {}).get("parameter", ""))
            for r in raw_results
            if str(r.get("parameters", {}).get("parameter", "")) not in drug_cache
        ]
        local_cache = dict(drug_cache)
        if unresolved_ids:
            local_cache.update(mod.resolve_unknown_drugs(unresolved_ids))

        watched = []
        for r in raw_results:
            drug_id_str = str(r.get("parameters", {}).get("parameter", ""))
            views = r.get("numEvents", 0)
            if not drug_id_str:
                continue
            info = local_cache.get(drug_id_str, {})
            originator = info.get("company", "")
            in_own = drug_id_str in own_drug_ids
            own_originated = (
                not in_own
                and bool(originator)
                and mod._is_own_company(company_name, originator)
            )
            watched.append({
                "drug_id": drug_id_str,
                "name": info.get("name", ""),
                "phase": info.get("phase", ""),
                "company": originator,
                "mechanism": info.get("mechanism", ""),
                "views": views,
                "in_own_pipeline": in_own,
                "own_originated": own_originated,
            })

        payload = {
            "company_name": company_name,
            "account_id": account_id,
            "period_days": mod.DAYS,
            "truncated": truncated,
            "watched_drugs": watched,
        }

        Path(pipeline_dir, "pendo_watchlist.json").write_text(json.dumps(payload, indent=2))
        mod.write_summary(pipeline_dir, company_name, payload)
        return slug, "ok"
    except Exception as e:
        return slug, f"error: {e}"


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indication", default="obesity")
    parser.add_argument("--wiki-dir", default=".")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch even if pendo_watchlist.md is already fresh today")
    args = parser.parse_args()

    mod = _load_module(
        SKILLS_DIR / "pipeline/recipes/enrich_pendo_pipeline.py",
        "enrich_pendo_pipeline",
    )

    try:
        client = mod.PendoClient()
    except ValueError as e:
        print(f"Skipping: {e}", file=sys.stderr)
        sys.exit(0)

    wiki_dir = Path(args.wiki_dir) / "wiki"
    targets = get_company_targets(wiki_dir, args.indication)
    print(f"Found {len(targets)} {args.indication} companies in wiki")

    to_run = [(s, d, n) for s, d, n in targets if args.force or not is_fresh(d)]
    skipped = len(targets) - len(to_run)
    if skipped:
        print(f"  {skipped} already fresh today (use --force to re-fetch)")

    resolved = resolve_all_accounts(mod, client, to_run)

    runnable = [(s, d, n, resolved[s][0]) for s, d, n in to_run if s in resolved]
    unresolved_count = len(to_run) - len(runnable)
    if unresolved_count:
        print(f"  {unresolved_count} companies not in subscriber list — skipping")
    print(f"  Building drug name cache…")
    drug_cache = mod.build_drug_cache("raw")
    print(f"  Drug cache: {len(drug_cache):,} entries")
    print(f"  Enriching {len(runnable)} companies with {args.workers} workers\n")

    done, errors = 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(enrich_one, mod, client, s, d, n, aid, drug_cache): s
            for s, d, n, aid in runnable
        }
        for fut in as_completed(futs):
            slug, status = fut.result()
            if status == "ok":
                done += 1
                print(f"  ✓ {slug}")
            else:
                errors += 1
                print(f"  ✗ {slug}: {status}")

    print(
        f"\nDone: {done} enriched · {skipped} skipped · "
        f"{unresolved_count} unresolved · {errors} errors"
    )


if __name__ == "__main__":
    main()
