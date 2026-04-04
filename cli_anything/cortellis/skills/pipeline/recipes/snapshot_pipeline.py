#!/usr/bin/env python3
"""Save a pipeline run snapshot for future comparison.

Usage: python3 snapshot_pipeline.py <pipeline_dir> <company_id>
Copies CSVs + manifest.json to ~/.cortellis/pipeline_snapshots/<company_id>/<date>/
"""
import os, shutil, sys
from datetime import date

if len(sys.argv) < 3:
    print("Usage: python3 snapshot_pipeline.py <pipeline_dir> <company_id>", file=sys.stderr)
    sys.exit(1)

pipeline_dir = sys.argv[1]
company_id = sys.argv[2]
today = date.today().isoformat()

snapshot_dir = os.path.expanduser(f"~/.cortellis/pipeline_snapshots/{company_id}/{today}")
os.makedirs(snapshot_dir, exist_ok=True)

copied = 0
for f in os.listdir(pipeline_dir):
    if f.endswith(".csv") or f == "manifest.json":
        shutil.copy2(os.path.join(pipeline_dir, f), os.path.join(snapshot_dir, f))
        copied += 1

print(f"Snapshot saved: {snapshot_dir} ({copied} files)", file=sys.stderr)
