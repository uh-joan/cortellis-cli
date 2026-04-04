#!/usr/bin/env python3
"""Verify Cortellis API credentials are valid before running the pipeline.

Usage: python3 check_api.py
Exit 0 if API is reachable and credentials are valid, exit 1 otherwise.
"""
import json, subprocess, sys

r = subprocess.run(
    ["cortellis", "--json", "companies", "get", "18614"],
    capture_output=True, text=True, timeout=30,
)
try:
    d = json.loads(r.stdout)
    if "companyRecordOutput" in d:
        print("API check passed", file=sys.stderr)
        sys.exit(0)
    if "error" in d:
        print(f"API error: {d['error']}", file=sys.stderr)
        sys.exit(1)
except (json.JSONDecodeError, Exception) as e:
    print(f"API check failed: {e}", file=sys.stderr)

sys.exit(1)
