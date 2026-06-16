#!/usr/bin/env python3
"""
batch_enrich_pendo_drugs.py — Batch Pendo enrichment for all drugs in an indication KB.

Reads wiki drugs with the given indication, resolves drug IDs from raw/drugs/*/record.json,
and runs Pendo enrichment for each. Skips drugs whose pendo_summary.md is already fresh today.

Usage:
    python3 batch_enrich_pendo_drugs.py [--indication obesity] [--wiki-dir .] [--workers 8] [--force]
"""

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

MAX_WORKERS = 8
SKILLS_DIR = Path(__file__).resolve().parent.parent


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_drug_targets(wiki_dir: Path, indication: str) -> list[tuple[str, str, str]]:
    """Return [(slug, drug_dir, drug_id), ...] for wiki drugs with this indication."""
    targets = []
    for p in sorted((wiki_dir / "drugs").glob("*.md")):
        text = p.read_text()
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        fm = yaml.safe_load(parts[1]) or {}
        if indication not in (fm.get("indications") or []):
            continue
        slug = p.stem
        drug_dir = fm.get("source_dir") or f"raw/drugs/{slug}"
        record_path = Path(drug_dir) / "record.json"
        if not record_path.exists():
            continue
        try:
            rec = json.loads(record_path.read_text())
            drug_id = str(rec["drugRecordOutput"]["@id"])
            targets.append((slug, drug_dir, drug_id))
        except Exception:
            continue
    return targets


def is_fresh(drug_dir: str) -> bool:
    p = Path(drug_dir) / "pendo_summary.md"
    if not p.exists():
        return False
    return datetime.fromtimestamp(p.stat().st_mtime).date() == date.today()


def enrich_one(
    mod, client, slug: str, drug_dir: str, drug_id: str
) -> tuple[str, str]:
    os.makedirs(drug_dir, exist_ok=True)
    try:
        with ThreadPoolExecutor(max_workers=3) as ex:
            fut_trend    = ex.submit(mod.drug_trend, client, drug_id, 14)
            fut_rank     = ex.submit(mod.fetch_weekly_rank, client, drug_id)
            fut_visitors = ex.submit(mod.fetch_weekly_visitors, client, drug_id)
            trend_14          = fut_trend.result()
            rank, total_drugs = fut_rank.result()
            weekly_visitors   = fut_visitors.result()

        prior_7      = trend_14[:7]
        current_7    = trend_14[7:]
        weekly_total = sum(d["views"] for d in current_7)
        prior_total  = sum(d["views"] for d in prior_7)
        daily_avg    = weekly_total / max(len(current_7), 1)
        peak         = (max(current_7, key=lambda d: d["views"])
                        if current_7 else {"views": 0, "date": 0})
        peak_date    = mod._ms_to_date(peak["date"]) if peak["date"] else "n/a"

        unique_visitor_count = len(weekly_visitors)
        unique_account_count = len(
            {v["account_name"] for v in weekly_visitors if v["account_name"]}
        )
        top_accounts = mod.accounts_from_visitors(weekly_visitors)

        payload = {
            "drug_id": drug_id,
            "drug_name": slug,
            "period_days": mod.DAYS,
            "weekly_trend": current_7,
            "prior_7d_trend": prior_7,
            "weekly_total": weekly_total,
            "prior_7d_total": prior_total,
            "daily_avg": round(daily_avg, 1),
            "peak_views": peak["views"],
            "peak_date": peak_date,
            "rank_weekly": rank,
            "rank_total_drugs": total_drugs,
            "top_accounts": top_accounts,
            "unique_visitor_count": unique_visitor_count,
            "unique_account_count": unique_account_count,
            "weekly_visitors": weekly_visitors,
        }

        Path(drug_dir, "pendo_attention.json").write_text(json.dumps(payload, indent=2))
        mod.write_summary(drug_dir, slug, payload)
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
                        help="Re-fetch even if pendo_summary.md is already fresh today")
    args = parser.parse_args()

    mod = _load_module(SKILLS_DIR / "drug-profile/recipes/enrich_pendo.py", "enrich_pendo")

    try:
        client = mod.PendoClient()
    except ValueError as e:
        print(f"Skipping: {e}", file=sys.stderr)
        sys.exit(0)

    wiki_dir = Path(args.wiki_dir) / "wiki"
    targets = get_drug_targets(wiki_dir, args.indication)
    print(f"Found {len(targets)} {args.indication} drugs in wiki")

    to_run = [(s, d, did) for s, d, did in targets if args.force or not is_fresh(d)]
    skipped = len(targets) - len(to_run)
    if skipped:
        print(f"  {skipped} already fresh today — skipping (use --force to re-fetch)")
    print(f"  Enriching {len(to_run)} drugs with {args.workers} workers\n")

    done, errors = 0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(enrich_one, mod, client, s, d, did): s
            for s, d, did in to_run
        }
        for fut in as_completed(futs):
            slug, status = fut.result()
            if status == "ok":
                done += 1
                print(f"  ✓ {slug}")
            else:
                errors += 1
                print(f"  ✗ {slug}: {status}")

    print(f"\nDone: {done} enriched · {skipped} skipped · {errors} errors")


if __name__ == "__main__":
    main()
