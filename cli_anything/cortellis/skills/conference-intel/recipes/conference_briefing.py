#!/usr/bin/env python3
"""
conference_briefing.py — Generate conference intelligence briefing.

Cross-references conference data against compiled wiki knowledge.

Usage: python3 conference_briefing.py <output_dir> "<query>"
"""

import json
import os
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_conference_data(output_dir):
    """Read conference JSON files from output_dir.

    Looks for files named conference_*.json or *.json in the directory.
    Returns a list of conference dicts.
    """
    conferences = []
    if not os.path.isdir(output_dir):
        return conferences

    for fname in sorted(os.listdir(output_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(output_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            # Handle both single record and search result shapes
            if isinstance(data, dict):
                # Search result: look for hits list
                hits = (
                    data.get("conferenceList", {}).get("conference", [])
                    or data.get("hits", [])
                    or data.get("results", [])
                )
                if hits and isinstance(hits, list):
                    conferences.extend(hits)
                else:
                    # Single conference record
                    conferences.append(data)
            elif isinstance(data, list):
                conferences.extend(data)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[warn] Could not read {fpath}: {exc}", file=sys.stderr)

    return conferences


def _load_wiki_articles(wiki_dir):
    """Load all markdown articles from wiki_dir recursively.

    Returns list of (path, content) tuples.
    """
    articles = []
    if not os.path.isdir(wiki_dir):
        return articles

    for root, _dirs, files in os.walk(wiki_dir):
        for fname in files:
            if fname.endswith(".md") and fname != "INDEX.md":
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        content = f.read()
                    articles.append((fpath, content))
                except OSError:
                    pass

    return articles


# ---------------------------------------------------------------------------
# Cross-reference
# ---------------------------------------------------------------------------

def cross_reference_wiki(conferences, wiki_dir):
    """Check which presenters/drugs appear in wiki articles.

    Returns a dict mapping entity names to list of wiki article slugs/titles
    that mention them.
    """
    articles = _load_wiki_articles(wiki_dir)
    if not articles:
        return {}

    cross_refs = {}

    for conf in conferences:
        # Collect entity mentions from conference: drug names, company names, presenters
        entities = _extract_entities(conf)
        for entity in entities:
            if not entity or len(entity) < 3:
                continue
            entity_lower = entity.lower()
            matched_articles = []
            for fpath, content in articles:
                if entity_lower in content.lower():
                    # Extract article title from filename or frontmatter
                    slug = os.path.splitext(os.path.basename(fpath))[0]
                    matched_articles.append(slug)
            if matched_articles:
                cross_refs[entity] = matched_articles

    return cross_refs


def _extract_entities(conf):
    """Extract drug names, company names, and presenter names from a conference record."""
    entities = []
    if not isinstance(conf, dict):
        return entities

    # Common field names for drugs
    for field in ("drugs", "drug_list", "drugList", "relatedDrugs"):
        val = conf.get(field)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    entities.append(item)
                elif isinstance(item, dict):
                    entities.append(item.get("name") or item.get("drugName") or "")
        elif isinstance(val, str):
            entities.append(val)

    # Common field names for companies/sponsors
    for field in ("companies", "sponsor", "sponsors", "organizer"):
        val = conf.get(field)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    entities.append(item)
                elif isinstance(item, dict):
                    entities.append(item.get("name") or item.get("companyName") or "")
        elif isinstance(val, str):
            entities.append(val)

    # Presenters / authors
    for field in ("presenters", "speakers", "authors"):
        val = conf.get(field)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    entities.append(item)
                elif isinstance(item, dict):
                    entities.append(item.get("name") or "")

    # Also extract drugs and companies from nested presentations/abstracts/sessions
    for pres_field in ("presentations", "abstracts", "sessions"):
        pres_list = conf.get(pres_field)
        if not isinstance(pres_list, list):
            continue
        for pres in pres_list:
            if not isinstance(pres, dict):
                continue
            # Drug names from presentations
            for drug_field in ("drug", "drugName", "drug_name"):
                val = pres.get(drug_field)
                if val and isinstance(val, str):
                    entities.append(val)
            # Company names from presentations
            for comp_field in ("company", "sponsor", "companyName"):
                val = pres.get(comp_field)
                if val and isinstance(val, str):
                    entities.append(val)

    return [e.strip() for e in entities if e and e.strip()]


# ---------------------------------------------------------------------------
# Briefing generation
# ---------------------------------------------------------------------------

def _safe_str(val, default=""):
    if val is None:
        return default
    return str(val).strip()


def generate_briefing(conferences, cross_refs, query):
    """Produce markdown briefing with 'What's New / So What / What's Next'.

    Args:
        conferences: list of conference dicts.
        cross_refs: dict from cross_reference_wiki().
        query: original search query string.

    Returns:
        Markdown string.
    """
    lines = []

    lines.append(f"# Conference Intelligence Briefing: {query}")
    lines.append("")

    if not conferences:
        lines.append("_No conference data found for this query._")
        lines.append("")
        lines.append("## What's New")
        lines.append("_No recent conference activity identified._")
        lines.append("")
        lines.append("## So What")
        lines.append("_Insufficient data for strategic implications._")
        lines.append("")
        lines.append("## What's Next")
        lines.append("_No upcoming conferences identified._")
        lines.append("")
        return "\n".join(lines)

    # --- Conference Overviews ---
    lines.append(f"## Conferences Found ({len(conferences)})")
    lines.append("")

    for conf in conferences:
        name = _safe_str(
            conf.get("name") or conf.get("conferenceName") or conf.get("title"),
            "Unknown Conference",
        )
        dates = _safe_str(
            conf.get("dates") or conf.get("startDate") or conf.get("date")
        )
        location = _safe_str(
            conf.get("location") or conf.get("city") or conf.get("venue")
        )
        conf_id = _safe_str(conf.get("id") or conf.get("conferenceId"))

        lines.append(f"### {name}")
        if dates:
            lines.append(f"- **Dates:** {dates}")
        if location:
            lines.append(f"- **Location:** {location}")
        if conf_id:
            lines.append(f"- **ID:** {conf_id}")

        # Key presentations / abstracts
        presentations = (
            conf.get("presentations")
            or conf.get("abstracts")
            or conf.get("sessions")
            or []
        )
        if presentations and isinstance(presentations, list):
            lines.append(f"- **Key Presentations:** {len(presentations)}")
            for pres in presentations[:5]:
                if isinstance(pres, dict):
                    title = _safe_str(
                        pres.get("title") or pres.get("name"), "Untitled"
                    )
                    drug = _safe_str(
                        pres.get("drug") or pres.get("drugName") or pres.get("drug_name")
                    )
                    company = _safe_str(
                        pres.get("company") or pres.get("sponsor")
                    )
                    entry = f"  - {title}"
                    highlights = []
                    if drug:
                        highlights.append(f"Drug: **{drug}**")
                    if company:
                        highlights.append(f"Company: **{company}**")
                    if highlights:
                        entry += f" ({', '.join(highlights)})"
                    lines.append(entry)
                elif isinstance(pres, str):
                    lines.append(f"  - {pres}")
        lines.append("")

    # --- Cross-References ---
    if cross_refs:
        lines.append("## Cross-References with Compiled Knowledge")
        lines.append("")
        lines.append("The following entities from these conferences appear in compiled landscape articles:")
        lines.append("")
        for entity, slugs in sorted(cross_refs.items()):
            slug_list = ", ".join(f"`{s}`" for s in slugs[:3])
            lines.append(f"- **{entity}** — mentioned in: {slug_list}")
        lines.append("")

    # --- What's New ---
    lines.append("## What's New")
    lines.append("")
    if conferences:
        lines.append(
            f"- **{len(conferences)} conference(s)** identified for query: *{query}*"
        )
        # Highlight any cross-referenced entities
        if cross_refs:
            known_entities = [e for e in cross_refs if cross_refs[e]]
            if known_entities:
                entity_str = ", ".join(f"**{e}**" for e in known_entities[:5])
                lines.append(
                    f"- Entities with compiled landscape coverage: {entity_str}"
                )
    else:
        lines.append("_No new conference activity identified._")
    lines.append("")

    # --- So What ---
    lines.append("## So What")
    lines.append("")
    if cross_refs:
        lines.append(
            "Key strategic observation: entities presented at these conferences "
            "overlap with compiled competitive landscapes, suggesting active "
            "clinical/regulatory momentum is translating into scientific discourse."
        )
        lines.append("")
        for entity, slugs in list(cross_refs.items())[:3]:
            lines.append(
                f"- **{entity}** (appearing in {', '.join(slugs[:2])}) "
                f"has a presence in both conference activity and compiled market data."
            )
    else:
        lines.append(
            "No cross-references found with compiled knowledge base. "
            "Consider running `/landscape` for the relevant indication to build context."
        )
    lines.append("")

    # --- What's Next ---
    lines.append("## What's Next")
    lines.append("")
    lines.append("**Upcoming milestones to watch:**")
    lines.append("")

    # Extract future dates from conferences
    future_confs = []
    for conf in conferences:
        date_str = _safe_str(conf.get("startDate") or conf.get("date") or conf.get("dates"))
        name = _safe_str(
            conf.get("name") or conf.get("conferenceName") or conf.get("title"),
            "Unknown Conference",
        )
        if date_str and date_str >= datetime.now(timezone.utc).strftime("%Y"):
            future_confs.append((date_str, name))

    if future_confs:
        future_confs.sort()
        for date_str, name in future_confs[:5]:
            lines.append(f"- **{name}** ({date_str})")
    else:
        lines.append(
            "- Monitor upcoming abstracts and late-breaking sessions from identified conferences."
        )
        lines.append(
            "- Track regulatory submissions for drugs highlighted at these conferences."
        )
        lines.append(
            "- Watch for deal activity involving companies active at these meetings."
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(
            "Usage: conference_briefing.py <output_dir> \"<query>\"",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir = sys.argv[1]
    query = sys.argv[2]

    # Wiki directory: look relative to cwd
    wiki_dir = os.path.join(os.getcwd(), "wiki")

    conferences = load_conference_data(output_dir)
    print(f"Loaded {len(conferences)} conference record(s).", file=sys.stderr)

    cross_refs = cross_reference_wiki(conferences, wiki_dir)
    print(f"Cross-referenced {len(cross_refs)} entities against wiki.", file=sys.stderr)

    briefing = generate_briefing(conferences, cross_refs, query)

    # Write to file if output_dir exists, else print
    if os.path.isdir(output_dir):
        out_path = os.path.join(output_dir, "conference_briefing.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(briefing)
        print(f"Written: {out_path}", file=sys.stderr)

    print(briefing)


if __name__ == "__main__":
    main()
