#!/usr/bin/env python3
"""Enrich launched.csv with regulatory approval regions per drug.

The landscape skill's `fetch_indication_phase.sh` searches Cortellis with
`--indication <ID> --phase L`, which returns drugs that are (a) linked to
the target indication AND (b) launched *somewhere*. It does NOT guarantee
the launched status is FOR that indication in a given region.

This recipe resolves the ambiguity by walking
`IDdbDevelopmentStatus.DevelopmentStatusCurrent[]` on each launched drug and
keeping only the (country, status, date) rows whose indication matches the
target. It then aggregates:
  - countries where the drug is Launched or Registered for this indication
  - earliest launch date in any region
  - has_us / has_eu / has_jp flags
  - has_major_western flag (any of US/EU/JP)

Outputs (written to <DIR>):
  - approval_regions.json : per-drug detail
  - approval_regions.md   : headline metric + per-drug table

Usage:
    python3 enrich_approval_regions.py <DIR> <IND_ID> [IND_NAME]

Example:
    python3 enrich_approval_regions.py raw/psoriasis 281 Psoriasis

Stdlib only. Relies on the `cortellis` CLI being on PATH.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

try:
    from _audit_trail import (
        build_audit_trail,
        render_audit_trail_markdown,
        write_audit_trail_json,
    )
    _HAVE_AUDIT = True
except Exception:
    _HAVE_AUDIT = False


BATCH_SIZE = 20
TIMEOUT_SEC = 60
LAUNCHED_STATUSES = {"L", "R"}  # Launched, Registered (approved)
MAJOR_WESTERN = {"US", "EU", "Japan", "JP"}


def _ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _read_launched_ids(data_dir: str):
    """Return list of (drug_id, drug_name, company) from launched.csv."""
    path = os.path.join(data_dir, "launched.csv")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            did = (row.get("id") or "").strip()
            if did:
                out.append((did, row.get("name", ""), row.get("company", "")))
    return out


def _batch_fetch(ids):
    """Return list of Drug dicts from `cortellis drugs records`."""
    if not ids:
        return []
    try:
        result = subprocess.run(
            ["cortellis", "--json", "drugs", "records", *ids],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
        )
        data = json.loads(result.stdout)
    except Exception as exc:
        print(f"[warn] batch fetch failed for {len(ids)} ids: {exc}", file=sys.stderr)
        return []
    out = data.get("drugRecordsOutput", {})
    drugs = _ensure_list(out.get("Drug"))
    return drugs


def _matches_indication(row_indication: dict, target_id: str, target_name: str) -> bool:
    """Return True if a DevelopmentStatusCurrent row targets our indication.

    Matches by exact indication id, OR by substring of the target name in the
    row's indication name. The substring check catches child indications (e.g.
    "Plaque psoriasis" when target is "Psoriasis") without needing the ontology.
    """
    if not row_indication:
        return False
    rid = str(row_indication.get("@id", "") or "")
    if target_id and rid == str(target_id):
        return True
    if target_name:
        rname = (row_indication.get("$", "") or "").strip().lower()
        tname = target_name.strip().lower()
        if tname and tname in rname:
            return True
    return False


def _analyze_drug(drug: dict, target_id: str, target_name: str) -> dict:
    """Extract approval regions for a drug, filtered to the target indication."""
    ds_block = drug.get("IDdbDevelopmentStatus") or {}
    rows = _ensure_list(ds_block.get("DevelopmentStatusCurrent"))

    countries = set()
    earliest = None  # (iso_date_str, country)
    row_details = []  # each: {country, status, date}

    for row in rows:
        status = (row.get("DevelopmentStatus") or {}).get("@id", "")
        if status not in LAUNCHED_STATUSES:
            continue
        if not _matches_indication(row.get("Indication") or {}, target_id, target_name):
            continue
        country = ((row.get("Country") or {}).get("$") or "").strip()
        status_label = ((row.get("DevelopmentStatus") or {}).get("$") or "").strip()
        date_raw = (row.get("StatusDate") or "")[:10]  # YYYY-MM-DD
        if country:
            countries.add(country)
        row_details.append({
            "country": country,
            "status": status_label,
            "date": date_raw,
        })
        if date_raw:
            if earliest is None or date_raw < earliest[0]:
                earliest = (date_raw, country)

    has_us = "US" in countries
    has_eu = "EU" in countries
    has_jp = ("Japan" in countries) or ("JP" in countries)
    has_major_western = has_us or has_eu or has_jp

    return {
        "drug_id": str(drug.get("@id", "")),
        "drug_name": drug.get("DrugName", "") or "",
        "countries": sorted(countries),
        "country_count": len(countries),
        "earliest_launch_date": earliest[0] if earliest else None,
        "earliest_launch_country": earliest[1] if earliest else None,
        "has_us": has_us,
        "has_eu": has_eu,
        "has_jp": has_jp,
        "has_major_western": has_major_western,
        "rows": row_details,
    }


def _render_markdown(indication_name: str,
                     indication_id: str,
                     analyses: list,
                     audit_md: str = "") -> str:
    total = len(analyses)
    matched = sum(1 for a in analyses if a["countries"])
    unmatched = total - matched
    with_us_eu_jp = sum(1 for a in analyses if a["has_major_western"])
    us = sum(1 for a in analyses if a["has_us"])
    eu = sum(1 for a in analyses if a["has_eu"])
    jp = sum(1 for a in analyses if a["has_jp"])
    china_only = sum(
        1 for a in analyses
        if a["countries"] and not a["has_major_western"] and set(a["countries"]) <= {"China"}
    )

    pct_western = f"{(with_us_eu_jp / total * 100):.0f}%" if total else "n/a"

    lines = [
        f"# Approval Regions: {indication_name}",
        "",
        f"_Per-drug regulatory approval scope for launched drugs, derived from "
        f"`IDdbDevelopmentStatus.DevelopmentStatusCurrent[]` filtered to "
        f"indication id={indication_id}._",
        "",
        "## Headline",
        "",
        f"- **Launched drugs analyzed:** {total}",
        f"- **Matched to target indication:** {matched} "
        f"({'no match — possible taxonomy mismatch' if matched == 0 else 'good'})",
        f"- **Unmatched (launched for other indications, linked via IndicationsPrimary only):** {unmatched}",
        f"- **With US or EU or JP approval for this indication:** **{with_us_eu_jp}** ({pct_western})",
        f"  - US: {us}  |  EU: {eu}  |  Japan: {jp}",
        f"- **China-only approvals:** {china_only}",
        "",
    ]

    if with_us_eu_jp == 0 and matched > 0:
        lines += [
            "> **FINDING: No US/EU/JP approved drug exists for this indication.** "
            f"All {matched} matched launches are outside the major Western regulated "
            "regions. Treat this as a pre-first-in-class market in the West.",
            "",
        ]
    elif unmatched > 0:
        lines += [
            f"> **NOTE:** {unmatched} launched drug(s) in `launched.csv` have no "
            f"`Launched`/`Registered` row for this specific indication. They were "
            "included by Cortellis via `IndicationsPrimary` linkage (e.g. a label "
            "covers a broader autoimmune category, or a trial was run without "
            "approval). Treat their 'Launched' status as indication-adjacent, not "
            "indication-specific.",
            "",
        ]

    lines += [
        "## Per-drug detail",
        "",
        "| Drug | Scope | Countries | Earliest | US | EU | JP |",
        "|------|-------|-----------|----------|:--:|:--:|:--:|",
    ]

    for a in sorted(analyses, key=lambda x: (
        not x["has_major_western"],  # western first
        -x["country_count"],
        x["drug_name"].lower(),
    )):
        name = (a["drug_name"] or "?")[:50]
        if not a["countries"]:
            scope = "no-match"
            countries_str = "(no launched row for this indication)"
        elif a["has_major_western"]:
            scope = "Western"
            countries_str = ", ".join(a["countries"])
        else:
            scope = "Non-Western"
            countries_str = ", ".join(a["countries"])
        earliest = a["earliest_launch_date"] or ""
        us_mark = "[Y]" if a["has_us"] else ""
        eu_mark = "[Y]" if a["has_eu"] else ""
        jp_mark = "[Y]" if a["has_jp"] else ""
        lines.append(
            f"| {name} | {scope} | {countries_str} | {earliest} | {us_mark} | {eu_mark} | {jp_mark} |"
        )

    if audit_md:
        lines += ["", audit_md]

    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) < 3:
        print("usage: enrich_approval_regions.py <DIR> <IND_ID> [IND_NAME]", file=sys.stderr)
        sys.exit(2)

    data_dir = sys.argv[1]
    indication_id = str(sys.argv[2])
    indication_name = sys.argv[3] if len(sys.argv) > 3 else ""

    if not os.path.isdir(data_dir):
        print(f"[error] not a directory: {data_dir}", file=sys.stderr)
        sys.exit(1)

    launched = _read_launched_ids(data_dir)
    if not launched:
        print(f"[info] no launched.csv rows in {data_dir}; nothing to do", file=sys.stderr)
        # Still write an empty artifact so downstream tools see a stable file
        out = {
            "indication_id": indication_id,
            "indication_name": indication_name,
            "run_timestamp_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_launched": 0,
            "analyses": [],
        }
        with open(os.path.join(data_dir, "approval_regions.json"), "w") as f:
            json.dump(out, f, indent=2)
        with open(os.path.join(data_dir, "approval_regions.md"), "w") as f:
            f.write(f"# Approval Regions: {indication_name or indication_id}\n\n"
                    f"_No launched drugs in this landscape._\n")
        return

    # Build id->metadata map from CSV (used to fall back if batch fetch misses)
    csv_meta = {did: {"drug_name_csv": nm, "company_csv": co} for (did, nm, co) in launched}
    all_ids = [did for (did, _, _) in launched]

    # Batch fetch all drug records
    drugs_by_id = {}
    for i in range(0, len(all_ids), BATCH_SIZE):
        chunk = all_ids[i:i + BATCH_SIZE]
        fetched = _batch_fetch(chunk)
        for d in fetched:
            drugs_by_id[str(d.get("@id", ""))] = d

    # Analyze each
    analyses = []
    for did in all_ids:
        drug = drugs_by_id.get(did)
        if not drug:
            # Couldn't fetch — emit a placeholder so counts stay consistent
            analyses.append({
                "drug_id": did,
                "drug_name": csv_meta[did]["drug_name_csv"],
                "countries": [],
                "country_count": 0,
                "earliest_launch_date": None,
                "earliest_launch_country": None,
                "has_us": False,
                "has_eu": False,
                "has_jp": False,
                "has_major_western": False,
                "rows": [],
                "fetch_error": True,
            })
            continue
        a = _analyze_drug(drug, indication_id, indication_name)
        # Prefer CSV name if API returned empty (rare)
        if not a["drug_name"]:
            a["drug_name"] = csv_meta[did]["drug_name_csv"]
        analyses.append(a)

    # Audit trail
    audit_md = ""
    if _HAVE_AUDIT:
        try:
            audit = build_audit_trail("enrich_approval_regions.py", data_dir)
            audit_md = render_audit_trail_markdown(audit)
            write_audit_trail_json(audit, data_dir, "enrich_approval_regions.py")
        except Exception:
            audit_md = ""

    # Write JSON
    out = {
        "indication_id": indication_id,
        "indication_name": indication_name,
        "run_timestamp_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_launched": len(analyses),
        "counts": {
            "matched_to_indication": sum(1 for a in analyses if a["countries"]),
            "has_major_western": sum(1 for a in analyses if a["has_major_western"]),
            "has_us": sum(1 for a in analyses if a["has_us"]),
            "has_eu": sum(1 for a in analyses if a["has_eu"]),
            "has_jp": sum(1 for a in analyses if a["has_jp"]),
        },
        "analyses": analyses,
    }
    json_path = os.path.join(data_dir, "approval_regions.json")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)

    md_path = os.path.join(data_dir, "approval_regions.md")
    with open(md_path, "w") as f:
        f.write(_render_markdown(
            indication_name or indication_id, indication_id, analyses, audit_md=audit_md
        ))

    # Stderr summary (one line so the test loop can grep it)
    counts = out["counts"]
    print(
        f"[approval_regions] {data_dir}: "
        f"launched={len(analyses)} matched={counts['matched_to_indication']} "
        f"western={counts['has_major_western']} "
        f"(US={counts['has_us']} EU={counts['has_eu']} JP={counts['has_jp']})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
