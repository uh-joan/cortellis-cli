#!/usr/bin/env python3
"""
enrich_pendo.py — Enrich drug profile with subscriber research attention data.

Fetches a 7-day window: daily view trend, rank among all drugs, and top
organizations researching this drug. Compares current week vs prior week
to surface momentum.

Writes:
  pendo_attention.json   — raw engagement data (includes IDs, for internal use only)
  pendo_summary.md       — sanitized summary safe for wiki (no IDs, no source names)

Skips gracefully if PENDO_INTEGRATION_KEY is not set.

Usage: python3 enrich_pendo.py <drug_dir> <drug_id> [<drug_name>]
"""

import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from dotenv import load_dotenv
# load_dotenv required here: enrichment scripts run as standalone python3 commands,
# not through the CLI which handles env loading centrally.
load_dotenv()

from cli_anything.cortellis.core.pendo import (
    PendoClient,
    drug_trend,
    drug_views,
    visitors,
)

DAYS = 7


def _ms_to_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_weekly_rank(client: PendoClient, drug_id: str) -> tuple[int, int]:
    """Return (rank, total_drugs) by summing views across the last 7 days."""
    def _fetch(d: int) -> list:
        return drug_views(client, days_ago=d, limit=5000).get("results", [])

    totals: dict[str, int] = defaultdict(int)
    with ThreadPoolExecutor(max_workers=DAYS) as ex:
        for rows in as_completed([ex.submit(_fetch, d) for d in range(1, DAYS + 1)]):
            for r in rows.result():
                did = str(r.get("parameters", {}).get("parameter", ""))
                totals[did] += r.get("numEvents", 0)

    ranked = sorted(totals.items(), key=lambda x: -x[1])
    total = len(ranked)
    for i, (did, _) in enumerate(ranked):
        if did == str(drug_id):
            return i + 1, total
    return total + 1, total


def fetch_weekly_visitors(client: PendoClient, drug_id: str) -> list:
    """Fetch unique visitors across the 7-day window, deduped by visitorId."""
    def _fetch(d: int) -> list:
        return visitors(client, drug_id=drug_id, days_ago=d).get("results", [])

    seen: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=DAYS) as ex:
        for rows in as_completed([ex.submit(_fetch, d) for d in range(1, DAYS + 1)]):
            for v in rows.result():
                vid = v.get("visitorId", "")
                if not vid:
                    continue
                if vid not in seen:
                    seen[vid] = {
                        "visitorId": vid,
                        "account_name": v.get("account_name", ""),
                        "visitor_email": v.get("visitor_email", ""),
                        "total_views": 0,
                        "days_active": 0,
                    }
                seen[vid]["total_views"] += v.get("page_views", 0)
                seen[vid]["days_active"] += 1

    return sorted(seen.values(), key=lambda x: -x["total_views"])


def accounts_from_visitors(visitor_list: list) -> list:
    """Derive account-level aggregation from visitor list (single source of truth)."""
    totals: dict[str, int] = defaultdict(int)
    for v in visitor_list:
        name = v.get("account_name", "")
        if name:
            totals[name] += v.get("total_views", 0)
    return sorted(
        [{"account_name": k, "total_views": v} for k, v in totals.items()],
        key=lambda x: -x["total_views"],
    )


def write_summary(drug_dir: str, drug_name: str, data: dict) -> None:
    weekly_total = data["weekly_total"]
    daily_avg = data["daily_avg"]
    peak_views = data["peak_views"]
    peak_date = data["peak_date"]
    rank = data["rank_weekly"]
    total_drugs = data["rank_total_drugs"]
    accounts = data["top_accounts"]
    unique_visitors = data.get("unique_visitor_count", 0)
    unique_accounts = data.get("unique_account_count", 0)

    prior_total = data.get("prior_7d_total", 0)
    if prior_total > 0 and weekly_total > 0:
        pct = ((weekly_total - prior_total) / prior_total) * 100
        trend_line = f"{'↑' if pct >= 0 else '↓'} {abs(pct):.0f}% vs prior 7 days"
    elif weekly_total == 0:
        trend_line = "no activity recorded"
    else:
        trend_line = "no prior period data"

    _end = date.today() - timedelta(days=1)
    _start = date.today() - timedelta(days=DAYS)
    date_range = (
        f"{_start.strftime('%b')} {_start.day} – "
        f"{_end.strftime('%b')} {_end.day}, {_end.year}"
    )

    lines = [
        f"## Industry Research Attention — {date_range}\n\n",
        f"- **Weekly views:** {weekly_total:,} | **Unique researchers:** {unique_visitors}"
        f" ({unique_accounts} organizations)\n",
        f"- **Daily avg:** {daily_avg:.0f} | **Peak:** {peak_views:,} ({peak_date})\n",
        f"- **Rank:** #{rank:,} of {total_drugs:,} drugs researched (7-day total)\n",
        f"- **Trend:** {trend_line}\n",
    ]

    named_accounts = [a for a in accounts if a.get("account_name")][:10]
    if named_accounts:
        lines.append("\n**Top organizations researching this drug:**\n\n")
        lines.append("| Organization | Views (7d) |\n")
        lines.append("|---|---|\n")
        for a in named_accounts:
            lines.append(f"| {a['account_name']} | {a['total_views']:,} |\n")
        lines.append("\n")

    out_path = os.path.join(drug_dir, "pendo_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: enrich_pendo.py <drug_dir> <drug_id> [<drug_name>]", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_id = sys.argv[2]
    drug_name = sys.argv[3] if len(sys.argv) > 3 else drug_id

    os.makedirs(drug_dir, exist_ok=True)

    try:
        client = PendoClient()
    except ValueError as e:
        print(f"  Skipping Pendo enrichment: {e}", file=sys.stderr)
        sys.exit(0)

    print(f"Fetching research engagement data for: {drug_name}")

    # Run all 3 fetches concurrently — each internally parallelizes its own day calls
    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_trend = ex.submit(drug_trend, client, drug_id, 14)
        fut_rank = ex.submit(fetch_weekly_rank, client, drug_id)
        fut_visitors = ex.submit(fetch_weekly_visitors, client, drug_id)
        trend_14 = fut_trend.result()
        rank, total_drugs = fut_rank.result()
        weekly_visitors = fut_visitors.result()

    # 14-day trend — first 7 = prior week, last 7 = current week (sorted ascending)
    prior_7 = trend_14[:7]
    current_7 = trend_14[7:]

    weekly_total = sum(d["views"] for d in current_7)
    prior_total = sum(d["views"] for d in prior_7)
    daily_avg = weekly_total / max(len(current_7), 1)

    peak = max(current_7, key=lambda d: d["views"]) if current_7 else {"views": 0, "date": 0}
    peak_date = _ms_to_date(peak["date"]) if peak["date"] else "n/a"

    unique_visitor_count = len(weekly_visitors)
    unique_account_count = len({v["account_name"] for v in weekly_visitors if v["account_name"]})
    top_accounts = accounts_from_visitors(weekly_visitors)

    print(f"  Weekly total: {weekly_total:,} views | Peak: {peak['views']:,} on {peak_date}")
    print(f"  Weekly rank: #{rank} of {total_drugs}")
    print(f"  Unique visitors: {unique_visitor_count} ({unique_account_count} accounts)")

    payload = {
        "drug_id": drug_id,
        "drug_name": drug_name,
        "period_days": DAYS,
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

    json_path = os.path.join(drug_dir, "pendo_attention.json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  Written: {json_path}")

    write_summary(drug_dir, drug_name, payload)
    print(f"Research engagement enrichment complete for {drug_name}.")


if __name__ == "__main__":
    main()
