#!/usr/bin/env python3
"""
link_wiki_drugs.py — Reverse-index drug profiles onto target pages.

For each target wiki page, finds all drug profiles whose mechanism field
matches the target's known names, then:
  - Updates the target's frontmatter with wiki_drugs: [slug, ...]
  - Adds/updates a "## Drug Profiles in Wiki" section in the body

Matching strategy (tiered, most-specific first):
  1. Full title phrase match (e.g. "free fatty acid receptor 1")
  2. Gene symbol match (e.g. "ffar1", "lepr")
  3. Aliases from ALIASES table (for Cortellis mechanism name divergences)

Usage:
    python3 link_wiki_drugs.py [--wiki-dir wiki] [--dry-run]

Options:
    --wiki-dir   Path to the wiki directory (default: wiki)
    --dry-run    Print matches without writing files
    --target     Only update a specific target slug
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

# ── Known aliases: target slug → extra search terms ──────────────────────────
# Add entries here when a drug's mechanism name diverges from the target title/gene.
ALIASES: dict[str, list[str]] = {
    "npy2r":                         ["peptide yy", "neuropeptide y ligand", "pyy", "npy ligand"],
    "gdf-15":                         ["gdf-15 ligand", "gfral", "growth differentiation factor 15"],
    "acvr1c":                         ["alk7", "alk-7", "activin receptor-like kinase 7", "acvr1c gene"],
    "amp-activated-protein-kinase":   ["ampk", "amp activated protein kinase"],
    "fibroblast-growth-factor-21":    ["fgf21", "fgf-21 ligand", "klotho beta"],
    "gdf-8":                          ["myostatin", "gdf-8 antagonist", "gdf8", "mstn"],
    "activin-type-iib-receptor":      ["activin type-iib", "acvr2b", "actriib"],
    "leptin-receptor":                ["leptin receptor", "leptin sensitizer", "leptin mimetic"],
    "glucagon":                       ["glucagon ligand"],
    "inhbe":                          ["inhbe gene", "inhibin beta e", "inhbe"],
    "activin-type-iia-receptor":      ["activin type-iia receptor", "acvr2a", "actriia"],
    "crf-2-receptor":                 ["crf-2 receptor", "crhr2", "urocortin receptor 2"],
    "protein-tyrosine-phosphatase-1b":["protein tyrosine phosphatase-1b", "ptp-1b", "ptp1b inhibitor", "ptpn1"],
    "farnesoid-x-receptor":           ["farnesoid x receptor", "fxr agonist", "nr1h4"],
    "melanocortin-mc3-receptor":      ["melanocortin mc3 receptor", "mc3 receptor", "mc3r"],
    "glucagon-like-peptide-2-receptor":["glucagon-like peptide-2 receptor", "glp-2 receptor", "glp2r"],
    "insulin-receptor":               ["insulin receptor agonist", "insulin receptor modulator"],
    "androgen-receptor":              ["androgen receptor agonist", "androgen receptor modulator"],
    "fgf-receptor":                   ["fgf receptor agonist", "fgf1 receptor agonist", "fgfr1"],
    "proprotein-convertase-pc9":      ["proprotein convertase pc9", "pcsk9 inhibitor", "pcsk9 gene inhibitor"],
    "g-protein-coupled-receptor-120": ["g-protein coupled receptor 120", "gpr120", "ffar4"],
}

# Minimum term length to avoid overly broad single-word matches
MIN_TERM_LEN = 5

# Targets where the title is too generic — skip automatic title/subphrase matching,
# rely only on ALIASES. Map slug → True.
SUPPRESS_AUTO_MATCH: set[str] = {
    "glucagon",                    # "glucagon" appears in "glucagon-like peptide 1 receptor agonist"
    "npy2r",                       # "receptor type 2" subphrase is too generic; use ALIASES only
    "g-protein-coupled-receptor-120",  # "free fatty acid receptor" subphrase matches FFAR1 drugs; use ALIASES only
}

# For these targets, require the term to appear as a whole word (not as part of a longer word).
# Uses \b word boundary in regex matching.
REQUIRE_WORD_BOUNDARY: set[str] = {
    "npy2r",                # prevents "receptor type 2" matching unrelated drugs
    "glucagon-receptor",    # prevents "glucagon" matching GLP-1 drugs
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse(path: Path) -> tuple[dict, str]:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    return yaml.safe_load(parts[1]) or {}, parts[2]


def _write(path: Path, fm: dict, body: str) -> None:
    fm_yaml = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    path.write_text(f"---\n{fm_yaml}---{body}", encoding="utf-8")


def _search_terms(slug: str, title: str, gene: str) -> list[str]:
    """Build ordered list of search terms, most specific first."""
    terms = []

    if slug not in SUPPRESS_AUTO_MATCH:
        # 1. Full title (lowercased, stripped of common suffix words)
        clean_title = re.sub(r"\s*\(.*?\)", "", title.lower()).strip()
        if len(clean_title) >= MIN_TERM_LEN:
            terms.append(clean_title)

        # 2. Gene symbol variants (lowercased, with and without hyphens)
        if gene:
            g = gene.lower().strip()
            terms.append(g)
            terms.append(g.replace("-", ""))
            terms.append(g.replace("_", ""))

        # 3. Title subphrases (sliding window, 3+ words)
        words = clean_title.split()
        for size in range(len(words), 2, -1):
            for i in range(len(words) - size + 1):
                phrase = " ".join(words[i : i + size])
                if len(phrase) >= MIN_TERM_LEN and phrase not in terms:
                    terms.append(phrase)

    # 4. Aliases from the lookup table (always applied)
    for alias in ALIASES.get(slug, []):
        if alias not in terms:
            terms.append(alias.lower())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _mechanism_matches(mechanism: str, terms: list[str], slug: str = "") -> list[str]:
    """Return the terms that matched (for debug output)."""
    mech_lower = mechanism.lower()
    matched = []
    for t in terms:
        if slug in REQUIRE_WORD_BOUNDARY:
            if re.search(r"\b" + re.escape(t) + r"\b", mech_lower):
                matched.append(t)
        else:
            if t in mech_lower:
                matched.append(t)
    return matched


def _update_body(body: str, drug_slugs: list[str]) -> str:
    """Add or replace the '## Drug Profiles in Wiki' section."""
    section_header = "## Drug Profiles in Wiki"
    links = "\n".join(f"- [[{slug}]]" for slug in sorted(drug_slugs))
    new_section = f"\n{section_header}\n\n{links}\n"

    if section_header in body:
        # Replace existing section
        body = re.sub(
            rf"\n{re.escape(section_header)}\n[\s\S]*?(?=\n## |\Z)",
            new_section,
            body,
        )
    else:
        # Append before the last section or at end
        body = body.rstrip() + "\n" + new_section

    return body


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-dir", default="wiki", help="Path to wiki directory")
    parser.add_argument("--dry-run", action="store_true", help="Print matches, don't write")
    parser.add_argument("--target", help="Only process this target slug")
    args = parser.parse_args()

    wiki = Path(args.wiki_dir)
    if not wiki.exists():
        sys.exit(f"Wiki directory not found: {wiki}")

    # Load all drug profiles → {slug: mechanism}
    drug_index: dict[str, str] = {}
    for p in sorted((wiki / "drugs").glob("*.md")):
        fm, _ = _parse(p)
        mech = fm.get("mechanism") or ""
        if mech:
            drug_index[fm.get("slug") or p.stem] = mech

    print(f"Loaded {len(drug_index)} drug profiles with mechanism data")

    # Process each full target profile (skip aliases)
    target_dir = wiki / "targets"
    updated = 0
    for p in sorted(target_dir.glob("*.md")):
        fm, body = _parse(p)
        if fm.get("alias_for"):
            continue
        slug = fm.get("slug") or p.stem
        if args.target and slug != args.target:
            continue

        title = fm.get("title") or ""
        gene = fm.get("gene_symbol") or ""
        terms = _search_terms(slug, title, gene)

        matched: dict[str, list[str]] = {}
        for drug_slug, mechanism in drug_index.items():
            hits = _mechanism_matches(mechanism, terms, slug)
            if hits:
                matched[drug_slug] = hits

        if not matched:
            continue

        print(f"\n{slug} ({title})")
        for drug_slug, hits in sorted(matched.items()):
            print(f"  → {drug_slug}  [matched: {hits[0]}]")

        if not args.dry_run:
            fm["wiki_drugs"] = sorted(matched.keys())
            body = _update_body(body, list(matched.keys()))
            _write(p, fm, body)
            updated += 1

    if not args.dry_run:
        print(f"\n✓ Updated {updated} target pages")
    else:
        print("\n(dry run — no files written)")


if __name__ == "__main__":
    main()
