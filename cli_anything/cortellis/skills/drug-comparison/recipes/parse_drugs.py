#!/usr/bin/env python3
"""Parse drug names from a comparison query and output a stable slug for the harness.

Usage:
  python3 parse_drugs.py "tirzepatide vs semaglutide"

Output (stdout): comparison,<slug>   e.g. comparison,tirzepatide-vs-semaglutide
The harness uses field 1 (slugified) to pin the output directory.
"""
import re
import sys


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def parse_drug_names(argument: str) -> list[str]:
    argument = re.sub(r"\b(?:vs\.?|versus|head[\s-]to[\s-]head)\b", ",", argument, flags=re.I)
    names = [n.strip() for n in argument.split(",") if n.strip()]
    return names[:5]


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    if not query:
        print("Usage: parse_drugs.py <query>", file=sys.stderr)
        sys.exit(1)

    names = parse_drug_names(query)
    if len(names) < 2:
        print(f"ERROR: need at least 2 drugs, got {names!r}", file=sys.stderr)
        sys.exit(1)

    slug = "-vs-".join(slugify(n) for n in names)
    print(f"comparison,{slug}")
