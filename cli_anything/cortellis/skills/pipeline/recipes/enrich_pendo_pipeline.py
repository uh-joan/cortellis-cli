#!/usr/bin/env python3
"""
enrich_pendo_pipeline.py — Enrich pipeline with company drug watchlist.

Resolves the company's Pendo account, then fetches which drugs they've been
researching over the last 7 days. Cross-references against their own pipeline
to flag which watched drugs are external — the most strategically interesting signal.

Drug names resolved from local phase CSVs (raw/*/) — no additional API calls needed
for most watched drugs. Unknown IDs batch-resolved via Cortellis drugs.records API.

Three categories of watched drugs:
  - own_active:        in the company's active pipeline CSVs
  - own_originated:    originated by the company but not in active pipeline (deprioritized)
  - external:          originated by another company — primary competitive signal

Writes:
  pendo_watchlist.json     — raw data (includes IDs, for internal use only)
  pendo_watchlist.md       — wiki-safe summary (drug names, no IDs, no source attribution)
  pendo_account_id.txt     — cached account_id|ISO-date to avoid re-resolving on reruns

Skips gracefully if PENDO_INTEGRATION_KEY is not set or company account not found.

Usage: python3 enrich_pendo_pipeline.py <pipeline_dir> "<company_name>" [<raw_dir>]
"""

import csv
import difflib
import json
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from dotenv import load_dotenv
# load_dotenv required: enrichment scripts run as standalone python3 commands.
load_dotenv()

from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.core import drugs as _cortellis_drugs
from cli_anything.cortellis.core.pendo import (
    PendoClient,
    account_drugs,
    account_views,
)

DAYS = 7
WATCHLIST_LIMIT = 500
PHASE_FILES = [
    "launched.csv", "phase3.csv", "phase2.csv", "phase1.csv",
    "phase1_ci.csv", "phase1_merged.csv", "discovery.csv",
    "discovery_ci.csv", "preclinical_merged.csv", "phase1_si.csv",
    "preclinical_si.csv", "other.csv",
]


def _short_phase(phase: str) -> str:
    return re.sub(r"\s+Clinical$", "", phase).strip()


def _short_name(name: str) -> str:
    for sep in [" (", ","]:
        idx = name.find(sep)
        if idx > 0:
            return name[:idx].strip()
    return name


def _is_own_company(company_name: str, originator: str) -> bool:
    """True if originator is the same company as company_name (substring or fuzzy match)."""
    a = company_name.lower().strip()
    b = originator.lower().strip()
    return a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() > 0.8


def build_drug_cache(raw_dir: str) -> dict[str, dict]:
    """Scan all phase CSVs under raw_dir → {drug_id: {name, phase, company, mechanism}}."""
    drugs: dict[str, dict] = {}
    for root, _, files in os.walk(raw_dir):
        for fname in files:
            if fname not in set(PHASE_FILES):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        did = str(row.get("id", "")).strip()
                        name = row.get("name", "").strip()
                        if did and name and did not in drugs:
                            drugs[did] = {
                                "name": name,
                                "phase": row.get("phase", "").strip(),
                                "company": row.get("company", "").strip(),
                                "mechanism": row.get("mechanism", "").strip(),
                            }
            except Exception:
                pass
    return drugs


def load_own_drug_ids(pipeline_dir: str) -> set[str]:
    """Load all drug IDs from the company's active pipeline CSVs."""
    own: set[str] = set()
    for fname in PHASE_FILES:
        fpath = os.path.join(pipeline_dir, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                did = str(row.get("id", "")).strip()
                if did:
                    own.add(did)
    return own


def resolve_unknown_drugs(drug_ids: list[str]) -> dict[str, dict]:
    """Batch-resolve drug IDs via Cortellis API.

    Returns {drug_id: {name, phase, company, mechanism}} for resolved IDs.
    Silently skips on auth or network errors.
    """
    try:
        client = CortellisClient()
    except Exception:
        return {}

    resolved: dict[str, dict] = {}
    for i in range(0, len(drug_ids), 50):
        chunk = drug_ids[i : i + 50]
        try:
            resp = _cortellis_drugs.records(client, chunk)
            drugs_data = resp.get("drugRecordsOutput", {}).get("Drug", [])
            if isinstance(drugs_data, dict):
                drugs_data = [drugs_data]
            for d in drugs_data:
                did = str(d.get("@id", ""))
                name = d.get("DrugName", "")
                phase = (d.get("PhaseHighest") or {}).get("$", "")
                company = (d.get("CompanyOriginator") or {}).get("$", "")
                action_list = (d.get("ActionsPrimary") or {}).get("Action", [])
                if isinstance(action_list, dict):
                    action_list = [action_list]
                mechanism = "; ".join(
                    a.get("$", "") for a in action_list if a.get("$")
                )
                if did and name:
                    resolved[did] = {
                        "name": name,
                        "phase": phase,
                        "company": company,
                        "mechanism": mechanism,
                    }
        except Exception:
            pass
    return resolved


def resolve_account_id(
    client: PendoClient,
    company_name: str,
    cache_path: str,
) -> str | None:
    """Resolve Pendo accountId for company_name.

    Caches result as "<accountId>|<ISO-date>" to cache_path.
    Uses days_ago=3 for reliable resolution (avoids low-activity weekend days).
    """
    if os.path.exists(cache_path):
        cached = open(cache_path).read().strip()
        if "|" in cached:
            aid, cached_date = cached.split("|", 1)
        else:
            aid = cached
            cached_date = ""
        if aid:
            print(f"  Account ID loaded from cache: {aid} (cached {cached_date})")
            return aid

    print("  Fetching account list to resolve company name…")
    results = account_views(client, days_ago=3, limit=5000).get("results", [])

    name_lower = company_name.lower()
    candidates = [(r.get("account_name", ""), r.get("accountId", "")) for r in results
                  if r.get("account_name") and r.get("accountId")]

    def _write_cache(aid: str) -> None:
        with open(cache_path, "w") as f:
            f.write(f"{aid}|{date.today().isoformat()}")

    # Exact substring match first (case-insensitive)
    for acct_name, aid in candidates:
        if name_lower in acct_name.lower() or acct_name.lower() in name_lower:
            print(f"  Resolved '{company_name}' → '{acct_name}' (accountId: {aid})")
            _write_cache(aid)
            return aid

    # Fuzzy fallback
    names = [acct_name for acct_name, _ in candidates]
    matches = difflib.get_close_matches(company_name, names, n=1, cutoff=0.6)
    if matches:
        for acct_name, aid in candidates:
            if acct_name == matches[0]:
                print(f"  Resolved '{company_name}' → '{acct_name}' (fuzzy, accountId: {aid})")
                _write_cache(aid)
                return aid

    print(f"  Could not resolve account for '{company_name}' — not found in active subscriber list",
          file=sys.stderr)
    return None


def write_summary(pipeline_dir: str, company_name: str, data: dict) -> None:
    watched = data["watched_drugs"]
    named = [d for d in watched if d.get("name")]
    own_active = [d for d in named if d["in_own_pipeline"]]
    own_orig = [d for d in named if not d["in_own_pipeline"] and d.get("own_originated")]
    external = [d for d in named if not d["in_own_pipeline"] and not d.get("own_originated")]
    truncated = data.get("truncated", False)

    summary_parts = [f"{len(own_active)} active pipeline · {len(external)} external"]
    if own_orig:
        summary_parts.append(f"{len(own_orig)} deprioritized own")
    trunc_note = " *(list truncated — more drugs watched)*" if truncated else ""

    _end = date.today() - timedelta(days=1)
    _start = date.today() - timedelta(days=DAYS)
    date_range = (
        f"{_start.strftime('%b')} {_start.day} – "
        f"{_end.strftime('%b')} {_end.day}, {_end.year}"
    )

    lines = [
        f"## Competitive Drug Watchlist — {date_range}\n\n",
        f"*{len(named)} drugs researched ({', '.join(summary_parts)})*{trunc_note}\n\n",
    ]

    if external:
        lines.append("### External Drugs Being Researched\n\n")
        lines.append("| Drug | Phase | Originator | Mechanism | Views (7d) |\n")
        lines.append("|---|---|---|---|---|\n")
        for d in external:
            mech = d.get("mechanism") or "—"
            lines.append(
                f"| {_short_name(d['name'])} | {_short_phase(d.get('phase', ''))} "
                f"| {d.get('company', '—')} | {mech} | {d['views']:,} |\n"
            )
        lines.append("\n")

        # Split compound mechanism strings and count individual mechanisms
        mech_counts: dict[str, int] = {}
        for d in external:
            for m in (d.get("mechanism") or "").split("; "):
                m = m.strip()
                if m:
                    mech_counts[m] = mech_counts.get(m, 0) + 1
        top_mechs = sorted(mech_counts.items(), key=lambda x: -x[1])[:5]
        if top_mechs:
            lines.append("**Most-watched external mechanisms:**\n\n")
            for m, c in top_mechs:
                lines.append(f"- {m} ({c} drugs)\n")
            lines.append("\n")

    if own_orig:
        lines.append("### Deprioritized Own Drugs Being Revisited\n\n")
        lines.append("| Drug | Phase | Mechanism | Views (7d) |\n")
        lines.append("|---|---|---|---|\n")
        for d in own_orig:
            mech = d.get("mechanism") or "—"
            lines.append(
                f"| {_short_name(d['name'])} | {_short_phase(d.get('phase', ''))} "
                f"| {mech} | {d['views']:,} |\n"
            )
        lines.append("\n")

    if own_active:
        lines.append("### Active Pipeline Drugs Also Researched\n\n")
        lines.append("| Drug | Phase | Mechanism | Views (7d) |\n")
        lines.append("|---|---|---|---|\n")
        for d in own_active:
            mech = d.get("mechanism") or "—"
            lines.append(
                f"| {_short_name(d['name'])} | {_short_phase(d.get('phase', ''))} "
                f"| {mech} | {d['views']:,} |\n"
            )
        lines.append("\n")

    out_path = os.path.join(pipeline_dir, "pendo_watchlist.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: enrich_pendo_pipeline.py <pipeline_dir> <company_name> [<raw_dir>]",
              file=sys.stderr)
        sys.exit(1)

    pipeline_dir = sys.argv[1]
    company_name = sys.argv[2]
    raw_dir = sys.argv[3] if len(sys.argv) > 3 else "raw"

    try:
        client = PendoClient()
    except ValueError as e:
        print(f"  Skipping Pendo enrichment: {e}", file=sys.stderr)
        sys.exit(0)

    print(f"Fetching drug watchlist for: {company_name}")

    cache_path = os.path.join(pipeline_dir, "pendo_account_id.txt")
    account_id = resolve_account_id(client, company_name, cache_path)
    if not account_id:
        sys.exit(0)

    print(f"  Fetching {DAYS}-day drug watchlist for account {account_id}…")
    raw_results = account_drugs(client, account_id, days=DAYS, limit=WATCHLIST_LIMIT).get("results", [])
    truncated = len(raw_results) == WATCHLIST_LIMIT
    if truncated:
        print(f"  Warning: result count equals limit ({WATCHLIST_LIMIT}) — list may be truncated")
    print(f"  Drugs watched: {len(raw_results)}")

    print(f"  Building drug name cache from {raw_dir}/…")
    drug_cache = build_drug_cache(raw_dir)
    print(f"  Drug cache: {len(drug_cache):,} entries")

    own_drug_ids = load_own_drug_ids(pipeline_dir)
    print(f"  Own pipeline drugs: {len(own_drug_ids)}")

    # Batch-resolve drug IDs not in local cache via Cortellis API
    unresolved_ids = [
        str(r.get("parameters", {}).get("parameter", ""))
        for r in raw_results
        if str(r.get("parameters", {}).get("parameter", "")) not in drug_cache
    ]
    if unresolved_ids:
        print(f"  Resolving {len(unresolved_ids)} unknown drug IDs via Cortellis API…")
        resolved = resolve_unknown_drugs(unresolved_ids)
        drug_cache.update(resolved)
        print(f"  Resolved: {len(resolved)}/{len(unresolved_ids)}")

    watched = []
    for r in raw_results:
        drug_id = str(r.get("parameters", {}).get("parameter", ""))
        views = r.get("numEvents", 0)
        if not drug_id:
            continue
        info = drug_cache.get(drug_id, {})
        originator = info.get("company", "")
        in_own_pipeline = drug_id in own_drug_ids
        own_originated = (
            not in_own_pipeline
            and bool(originator)
            and _is_own_company(company_name, originator)
        )
        watched.append({
            "drug_id": drug_id,
            "name": info.get("name", ""),
            "phase": info.get("phase", ""),
            "company": originator,
            "mechanism": info.get("mechanism", ""),
            "views": views,
            "in_own_pipeline": in_own_pipeline,
            "own_originated": own_originated,
        })

    named_count = sum(1 for d in watched if d["name"])
    external_count = sum(1 for d in watched if d["name"] and not d["in_own_pipeline"] and not d.get("own_originated"))
    own_orig_count = sum(1 for d in watched if d.get("own_originated"))
    print(f"  Resolved names: {named_count}/{len(watched)} | "
          f"External: {external_count} | Deprioritized own: {own_orig_count}")

    payload = {
        "company_name": company_name,
        "account_id": account_id,
        "period_days": DAYS,
        "truncated": truncated,
        "watched_drugs": watched,
    }

    json_path = os.path.join(pipeline_dir, "pendo_watchlist.json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  Written: {json_path}")

    write_summary(pipeline_dir, company_name, payload)
    print(f"Drug watchlist enrichment complete for {company_name}.")


if __name__ == "__main__":
    main()
