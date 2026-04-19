#!/usr/bin/env python3
"""
enrich_from_manifest.py — Run deep-profile sub-skills for entities in enrichment_manifest.json.

Reads the manifest written by compile_dossier.py and runs drug-profile, pipeline,
or target-profile for any entity that does not yet have a deep wiki article.
Idempotent: re-running skips entities already profiled.

Usage:
  python3 enrich_from_manifest.py <manifest_path> --type drugs|companies|targets [--dry-run]
"""

import json
import os
import subprocess
import sys


def run_skill(skill_name, argument, dry_run=False):
    cmd = ["cortellis", "run-skill", skill_name, argument]
    if dry_run:
        print(f"    [dry-run] {' '.join(cmd)}")
        return True
    print(f"    → {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    if len(sys.argv) < 2:
        print("Usage: enrich_from_manifest.py <manifest_path> --type drugs|companies|targets [--dry-run]", file=sys.stderr)
        sys.exit(1)

    manifest_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    type_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--type" and i + 1 < len(sys.argv):
            type_filter = sys.argv[i + 1]

    if not os.path.exists(manifest_path):
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        print("Run 'cortellis run-skill landscape <indication>' first.", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    indication = manifest.get("indication", "unknown")
    print(f"\nEnriching KB for: {indication}" + (" (dry-run)" if dry_run else ""))

    done = failed = skipped = 0

    if not type_filter or type_filter == "drugs":
        todo = [d for d in manifest.get("drugs", []) if not d.get("has_deep_profile")]
        already = len(manifest.get("drugs", [])) - len(todo)
        print(f"\n  Drugs: {len(todo)} to profile, {already} already done")
        for drug in todo:
            ok = run_skill("drug-profile", drug["name"], dry_run)
            if ok:
                done += 1
            else:
                failed += 1

    if not type_filter or type_filter == "companies":
        todo = [c for c in manifest.get("companies", []) if not c.get("has_pipeline")]
        already = len(manifest.get("companies", [])) - len(todo)
        print(f"\n  Companies: {len(todo)} to profile, {already} already done")
        for company in todo:
            ok = run_skill("pipeline", company["name"], dry_run)
            if ok:
                done += 1
            else:
                failed += 1

    if not type_filter or type_filter == "targets":
        todo = [t for t in manifest.get("targets", []) if not t.get("has_deep_profile")]
        already = len(manifest.get("targets", [])) - len(todo)
        print(f"\n  Targets: {len(todo)} to profile, {already} already done")
        for target in todo:
            ok = run_skill("target-profile", target.get("search_name") or target["mechanism"], dry_run)
            if ok:
                done += 1
            else:
                failed += 1

    print(f"\n  Done: {done} profiled" + (f", {failed} failed" if failed else "") + ".")


if __name__ == "__main__":
    main()
