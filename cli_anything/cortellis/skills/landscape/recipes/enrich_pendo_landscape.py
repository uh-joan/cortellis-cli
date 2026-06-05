#!/usr/bin/env python3
"""
enrich_pendo_landscape.py — Enrich landscape with subscriber research attention.

Fetches a 7-day window of engagement signals for drugs in this indication:
  - Which drugs in the indication are getting the most subscriber attention?
  - Which organizations are most active researching THIS indication's drugs?
  - Week-over-week momentum for the indication as a whole.
  - Which accounts appeared this week for the first time?

Account-level data is indication-scoped: only views of drugs in this indication
are counted, so "Most Active Organizations" reflects obesity/MASLD/etc activity
specifically, not platform-wide browsing.

Writes:
  pendo_landscape.json   — raw data (includes IDs, for internal use only)
  pendo_landscape.md     — wiki-safe summary (no IDs, drug names + org names only)

Skips gracefully if PENDO_INTEGRATION_KEY is not set.

Usage: python3 enrich_pendo_landscape.py <landscape_dir> "<indication_name>"
"""

import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from dotenv import load_dotenv
# load_dotenv required: enrichment scripts run as standalone python3 commands.
load_dotenv()

from requests.exceptions import ConnectionError as ReqConnectionError, ReadTimeout

from cli_anything.cortellis.core.pendo import (
    PendoClient,
    drug_account_views_all,
    drug_views,
    new_accounts,
)

DAYS = 7
PHASE_FILES = [
    "launched.csv", "phase3.csv", "phase2.csv", "phase1.csv",
    "phase1_ci.csv", "phase1_merged.csv", "discovery.csv",
    "discovery_ci.csv", "preclinical_merged.csv", "other.csv",
]


def load_indication_drugs(landscape_dir: str) -> dict[str, dict]:
    """Read all phase CSVs → {drug_id: {name, phase, company}}."""
    drugs: dict[str, dict] = {}
    for fname in PHASE_FILES:
        fpath = os.path.join(landscape_dir, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                did = str(row.get("id", "")).strip()
                name = row.get("name", "").strip()
                if did and name:
                    drugs[did] = {
                        "name": name,
                        "phase": row.get("phase", "").strip(),
                        "company": row.get("company", "").strip(),
                    }
    return drugs


def _short_phase(phase: str) -> str:
    """'Phase 3 Clinical' → 'Phase 3', 'Launched' stays."""
    return re.sub(r"\s+Clinical$", "", phase).strip()


def _short_name(name: str) -> str:
    """Truncate drug name at first ' (' or ',' to drop formulation/biosimilar cruft."""
    for sep in [" (", ","]:
        idx = name.find(sep)
        if idx > 0:
            return name[:idx].strip()
    return name


def fetch_drug_views_range(client: PendoClient, start: int, end: int) -> dict[str, int]:
    """Sum drug page views for days [start, end) ago. Returns {drug_id: total_views}."""
    def _fetch(d: int) -> list:
        return drug_views(client, days_ago=d, limit=5000).get("results", [])

    totals: dict[str, int] = defaultdict(int)
    with ThreadPoolExecutor(max_workers=end - start) as ex:
        for rows in as_completed([ex.submit(_fetch, d) for d in range(start, end)]):
            for r in rows.result():
                did = str(r.get("parameters", {}).get("parameter", ""))
                totals[did] += r.get("numEvents", 0)
    return dict(totals)


def fetch_weekly_indication_account_views(
    client: PendoClient, indication_drug_ids: set[str]
) -> list[dict]:
    """Sum account views for THIS indication's drugs over 7 days.

    Uses drug_account_views_all to get (drug_id, accountId, views) tuples,
    filters to indication drug IDs, then aggregates by account.
    Returns [{accountId, account_name, total_views}] sorted descending.
    """
    def _fetch(d: int) -> list:
        return drug_account_views_all(client, days_ago=d, limit=5000).get("results", [])

    totals: dict[str, dict] = defaultdict(lambda: {"account_name": "", "total_views": 0})
    with ThreadPoolExecutor(max_workers=DAYS) as ex:
        for rows in as_completed([ex.submit(_fetch, d) for d in range(1, DAYS + 1)]):
            for r in rows.result():
                if str(r.get("drug_id", "")) not in indication_drug_ids:
                    continue
                aid = r.get("accountId", "")
                if not aid:
                    continue
                totals[aid]["account_name"] = r.get("account_name", "") or aid
                totals[aid]["total_views"] += r.get("views", 0)

    return sorted(
        [{"accountId": k, "account_name": v["account_name"], "total_views": v["total_views"]}
         for k, v in totals.items()],
        key=lambda x: -x["total_views"],
    )


def write_summary(landscape_dir: str, indication_name: str, data: dict) -> None:
    top_drugs = data["top_indication_drugs"]
    top_accts = data["top_indication_accounts"]
    new_accts = data["new_accounts"]
    total_ind_views = data["indication_weekly_views"]
    prior_ind_views = data["indication_prior_views"]
    total_platform_views = data["platform_weekly_views"]

    if prior_ind_views > 0 and total_ind_views > 0:
        pct = ((total_ind_views - prior_ind_views) / prior_ind_views) * 100
        mom = f"{'↑' if pct >= 0 else '↓'} {abs(pct):.0f}% vs prior 7 days"
    elif total_ind_views == 0:
        mom = "no activity recorded"
    else:
        mom = "no prior period data"

    _end = date.today() - timedelta(days=1)
    _start = date.today() - timedelta(days=DAYS)
    date_range = (
        f"{_start.strftime('%b')} {_start.day} – "
        f"{_end.strftime('%b')} {_end.day}, {_end.year}"
    )

    lines = [
        f"## Industry Research Activity — {indication_name} ({date_range})\n\n",
        f"*{total_ind_views:,} views across {len(top_drugs)} tracked drugs in this indication · {mom}*\n\n",
    ]

    if top_drugs:
        lines.append("### Most-Researched Drugs\n\n")
        lines.append("| Drug | Phase | Organization | Views (7d) | Industry Rank |\n")
        lines.append("|---|---|---|---|---|\n")
        for d in top_drugs[:15]:
            lines.append(
                f"| {_short_name(d['name'])} | {_short_phase(d['phase'])} | {d['company']} "
                f"| {d['views']:,} | #{d['platform_rank']:,} |\n"
            )
        lines.append("\n")

    if top_accts:
        named = [a for a in top_accts if a.get("account_name")][:10]
        if named:
            lines.append(f"### Most Active Organizations — {indication_name}\n\n")
            lines.append("| Organization | Views (7d) |\n")
            lines.append("|---|---|\n")
            for a in named:
                lines.append(f"| {a['account_name']} | {a['total_views']:,} |\n")
            lines.append("\n")

    if new_accts:
        lines.append(f"### New Organizations This Week ({len(new_accts)} vs prior 7 days)\n\n")
        named_new = [a for a in new_accts if a.get("account_name")][:10]
        for a in named_new:
            lines.append(f"- {a['account_name']} ({a.get('total_views', 0):,} views)\n")
        lines.append("\n")

    out_path = os.path.join(landscape_dir, "pendo_landscape.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: enrich_pendo_landscape.py <landscape_dir> <indication_name>",
              file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    indication_name = sys.argv[2]

    try:
        client = PendoClient()
    except ValueError as e:
        print(f"  Skipping Pendo enrichment: {e}", file=sys.stderr)
        sys.exit(0)

    print(f"Fetching subscriber research activity for: {indication_name}")

    indication_drugs = load_indication_drugs(landscape_dir)
    if not indication_drugs:
        print("  No drug CSVs found — skipping.", file=sys.stderr)
        sys.exit(0)
    indication_drug_ids = set(indication_drugs.keys())
    print(f"  Indication drugs loaded: {len(indication_drugs)}")

    # 4 concurrent outer fetches — each internally parallelizes its day calls
    with ThreadPoolExecutor(max_workers=4) as ex:
        fut_current = ex.submit(fetch_drug_views_range, client, 1, DAYS + 1)
        fut_prior = ex.submit(fetch_drug_views_range, client, DAYS + 1, DAYS * 2 + 1)
        fut_accts = ex.submit(fetch_weekly_indication_account_views, client, indication_drug_ids)
        fut_new = ex.submit(new_accounts, client, DAYS, 5000)

        current_drug_views = fut_current.result()
        prior_drug_views = fut_prior.result()
        indication_acct_views = fut_accts.result()
        try:
            new_accts_raw = fut_new.result()
        except (ReadTimeout, ReqConnectionError) as e:
            print(f"  new_accounts timed out — skipping ({e})", file=sys.stderr)
            new_accts_raw = []

    platform_total = sum(current_drug_views.values())

    # Platform rank from current week
    ranked = sorted(current_drug_views.items(), key=lambda x: -x[1])
    platform_rank = {did: i + 1 for i, (did, _) in enumerate(ranked)}

    # Join against indication drugs
    indication_hits = []
    for did, info in indication_drugs.items():
        views = current_drug_views.get(did, 0)
        if views > 0:
            indication_hits.append({
                "drug_id": did,
                "name": info["name"],
                "phase": info["phase"],
                "company": info["company"],
                "views": views,
                "platform_rank": platform_rank.get(did, len(ranked) + 1),
            })
    indication_hits.sort(key=lambda x: -x["views"])

    indication_total = sum(h["views"] for h in indication_hits)
    prior_indication_total = sum(
        prior_drug_views.get(did, 0) for did in indication_drug_ids
    )

    print(f"  Platform drug views: {platform_total:,} across {len(current_drug_views):,} drugs")
    print(f"  Indication hits: {len(indication_hits)} drugs with views "
          f"({indication_total:,} current / {prior_indication_total:,} prior week)")
    print(f"  Indication accounts: {len(indication_acct_views)}")
    print(f"  New accounts: {len(new_accts_raw)}")

    payload = {
        "indication_name": indication_name,
        "period_days": DAYS,
        "indication_weekly_views": indication_total,
        "indication_prior_views": prior_indication_total,
        "platform_weekly_views": platform_total,
        "top_indication_drugs": indication_hits,
        "top_indication_accounts": indication_acct_views,
        "new_accounts": new_accts_raw,
    }

    json_path = os.path.join(landscape_dir, "pendo_landscape.json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  Written: {json_path}")

    write_summary(landscape_dir, indication_name, payload)
    print(f"Subscriber activity enrichment complete for {indication_name}.")


if __name__ == "__main__":
    main()
