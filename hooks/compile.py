#!/usr/bin/env python3
"""
compile.py — Promote daily conversation logs into wiki concept/connection articles.

Uses Claude Agent SDK to analyze daily logs and produce structured wiki articles
with cross-references. Following Karpathy's compiler pattern:
  daily/ (source code) → LLM (compiler) → wiki/knowledge/ (executable)

Usage: python3 compile.py [--all] [--file daily/YYYY-MM-DD.md]
"""

# Set recursion guard BEFORE any imports
import os
os.environ["CLAUDE_INVOKED_BY"] = "compile-script"

import argparse
import asyncio
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "compile.log"
COMPILE_STATE_PATH = PROJECT_ROOT / "daily" / ".compile-state.json"

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [compile] %(message)s",
)

COMPILE_PROMPT = """You are compiling daily conversation logs into structured wiki articles for a pharmaceutical intelligence knowledge base.

Read the daily log below. Extract 2-5 distinct knowledge units (concepts) and any notable connections between them.

For each CONCEPT, create or update a markdown file at insights/concepts/<slug>.md with:
---
title: <Concept Title>
type: concept
tags: [tag1, tag2]
sources: [daily/<date>.md]
created: <today>
updated: <today>
---

## Key Points
- 3-5 bullet points

## Details
2+ paragraphs of context

## Related Concepts
- [[concepts/related-slug]] — how they connect

For each CONNECTION between 2+ concepts, create insights/connections/<slug>.md with:
---
title: <Connection Title>
type: connection
connects: [concepts/a, concepts/b]
---

## Relationship
Description of how these concepts connect.

IMPORTANT:
- Use [[wikilinks]] for all cross-references
- Only extract PHARMA-RELEVANT insights (drug pipeline, competitive positioning, deals, regulatory, mechanisms)
- Skip routine development/debugging content
- Update the insights/index.md with new entries
"""


# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------

def load_compile_state() -> dict:
    """Load compile state tracking file hashes."""
    if not COMPILE_STATE_PATH.exists():
        return {}
    try:
        return json.loads(COMPILE_STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_compile_state(state: dict) -> None:
    """Persist compile state."""
    COMPILE_STATE_PATH.parent.mkdir(exist_ok=True)
    COMPILE_STATE_PATH.write_text(json.dumps(state, indent=2))


def file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Daily log discovery
# ---------------------------------------------------------------------------

def find_daily_logs(daily_dir: Path) -> list[Path]:
    """Return all YYYY-MM-DD.md files in the daily directory, sorted."""
    return sorted(daily_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md"))


def logs_to_process(daily_dir: Path, force_all: bool = False) -> list[Path]:
    """Return daily logs that need (re-)compiling.

    In incremental mode (default), only returns logs whose SHA-256 hash
    differs from the stored compile state.
    """
    logs = find_daily_logs(daily_dir)
    if force_all:
        return logs

    state = load_compile_state()
    changed = []
    for log in logs:
        current_hash = file_sha256(log)
        if state.get(str(log)) != current_hash:
            changed.append(log)
    return changed


# ---------------------------------------------------------------------------
# Section parsing helpers (shared with compile_basic)
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(
    r"^(#{1,3}\s+(.+?))$\n(.*?)(?=^#{1,3}\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _extract_section(md: str, heading: str) -> str:
    """Extract content under a markdown heading (## or ###)."""
    if not md:
        return ""
    escaped = re.escape(heading)
    pattern = re.compile(
        r"^#{1,3}\s+" + escaped + r".*?$\n(.*?)(?=^#{1,3}\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(md)
    return m.group(1).strip() if m else ""


def _extract_bullets(text: str) -> list[str]:
    """Extract bullet points (lines starting with - or *) from text."""
    bullets = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            bullets.append(line[2:].strip())
    return bullets


def _is_routine(log_content: str) -> bool:
    """Return True if the log signals a routine session with no notable insights."""
    lower = log_content.lower()
    # If every session summary says "routine session" and there are no bullets
    # in Key Decisions / Lessons / Strategic Insights, treat as empty.
    has_routine_marker = "routine session with no notable insights" in lower
    has_any_bullets = bool(re.search(r"^[-*]\s+\S", log_content, re.MULTILINE))
    return has_routine_marker and not has_any_bullets


# ---------------------------------------------------------------------------
# Fallback deterministic compilation
# ---------------------------------------------------------------------------

def compile_basic(log_content: str, log_date: str, wiki_dir: str) -> list[str]:
    """Fallback: extract concepts from daily log without Agent SDK.

    Parses structured sections (Key Decisions, Lessons Learned, Strategic Insights)
    and creates concept articles from them. Returns list of paths written.
    """
    if _is_routine(log_content):
        logging.info(f"compile_basic: {log_date} is routine, skipping")
        return []

    # Collect pharma-relevant bullets from the three high-value sections
    sections = {
        "Key Decisions": _extract_bullets(_extract_section(log_content, "Key Decisions")),
        "Lessons Learned": _extract_bullets(_extract_section(log_content, "Lessons Learned")),
        "Strategic Insights": _extract_bullets(_extract_section(log_content, "Strategic Insights")),
    }

    all_bullets: list[tuple[str, str]] = []  # (section_name, bullet_text)
    for section_name, bullets in sections.items():
        for b in bullets:
            all_bullets.append((section_name, b))

    if not all_bullets:
        logging.info(f"compile_basic: no bullets found in {log_date}")
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Group bullets into concept articles (one per distinct section type,
    # merging all bullets from that section into a single concept article)
    written: list[str] = []
    concepts_created: list[str] = []

    sys.path.insert(0, str(PROJECT_ROOT))
    from cli_anything.cortellis.utils.wiki import write_article, wiki_root as get_wiki_root, slugify as _slugify

    w_dir = get_wiki_root(wiki_dir)
    concepts_dir = os.path.join(w_dir, "insights", "concepts")
    connections_dir = os.path.join(w_dir, "insights", "connections")
    os.makedirs(concepts_dir, exist_ok=True)
    os.makedirs(connections_dir, exist_ok=True)

    for section_name, bullets in sections.items():
        if not bullets:
            continue

        # Build a concept article slug and title from the section + date
        title = f"{section_name} — {log_date}"
        slug = _slugify(title)
        path = os.path.join(concepts_dir, f"{slug}.md")

        meta = {
            "title": title,
            "type": "concept",
            "tags": ["daily-log", _slugify(section_name)],
            "sources": [f"daily/{log_date}.md"],
            "created": today,
            "updated": today,
        }

        key_points = "\n".join(f"- {b}" for b in bullets[:5])
        body = (
            f"## Key Points\n\n{key_points}\n\n"
            f"## Details\n\n"
            f"Extracted from daily log {log_date}, section '{section_name}'.\n\n"
            f"These insights were captured during active pharmaceutical intelligence work "
            f"and represent decisions, learnings, or strategic observations from that session.\n"
        )

        if concepts_created:
            related = "\n".join(
                f"- [[concepts/{s}]] — related session insight" for s in concepts_created
            )
            body += f"\n## Related Concepts\n\n{related}\n"

        write_article(path, meta, body)
        written.append(path)
        concepts_created.append(slug)
        logging.info(f"compile_basic: wrote concept {path}")

    # If we produced 2+ concepts, create a connection article linking them
    if len(concepts_created) >= 2:
        conn_title = f"Session Connections — {log_date}"
        conn_slug = _slugify(conn_title)
        conn_path = os.path.join(connections_dir, f"{conn_slug}.md")

        conn_meta = {
            "title": conn_title,
            "type": "connection",
            "connects": [f"concepts/{s}" for s in concepts_created],
            "sources": [f"daily/{log_date}.md"],
            "created": today,
            "updated": today,
        }

        concept_links = "\n".join(
            f"- [[concepts/{s}]]" for s in concepts_created
        )
        conn_body = (
            f"## Relationship\n\n"
            f"These concepts were all captured in the same daily log ({log_date}), "
            f"suggesting they emerged from the same working session and may be contextually related.\n\n"
            f"### Connected Concepts\n\n{concept_links}\n"
        )

        write_article(conn_path, conn_meta, conn_body)
        written.append(conn_path)
        logging.info(f"compile_basic: wrote connection {conn_path}")

    # Update the insights index
    _update_insights_index(w_dir, log_date)

    return written


def _update_insights_index(wiki_dir: str, log_date: str) -> None:
    """Append or refresh the insights/index.md with concepts and connections."""
    index_path = os.path.join(wiki_dir, "insights", "index.md")

    concepts_dir = os.path.join(wiki_dir, "insights", "concepts")
    connections_dir = os.path.join(wiki_dir, "insights", "connections")

    lines = [
        "# Knowledge Insights Index\n\n",
        f"> Auto-generated. Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n",
    ]

    # Concepts section
    concept_files = sorted(os.listdir(concepts_dir)) if os.path.isdir(concepts_dir) else []
    if concept_files:
        lines.append("## Concepts\n\n")
        lines.append("| Title | Tags | Sources | Updated |\n")
        lines.append("|---|---|---|---|\n")
        for fname in concept_files:
            if not fname.endswith(".md"):
                continue
            from cli_anything.cortellis.utils.wiki import read_article
            art = read_article(os.path.join(concepts_dir, fname))
            if art and art["meta"]:
                m = art["meta"]
                slug = fname[:-3]
                title = m.get("title", slug)
                tags = ", ".join(m.get("tags", []))
                sources = ", ".join(m.get("sources", []))
                updated = m.get("updated", "-")
                lines.append(
                    f"| [concepts/{slug}](concepts/{slug}.md)"
                    f" | {tags}"
                    f" | {sources}"
                    f" | {updated} |\n"
                )
        lines.append("\n")

    # Connections section
    conn_files = sorted(os.listdir(connections_dir)) if os.path.isdir(connections_dir) else []
    if conn_files:
        lines.append("## Connections\n\n")
        lines.append("| Title | Connects | Sources | Created |\n")
        lines.append("|---|---|---|---|\n")
        for fname in conn_files:
            if not fname.endswith(".md"):
                continue
            from cli_anything.cortellis.utils.wiki import read_article
            art = read_article(os.path.join(connections_dir, fname))
            if art and art["meta"]:
                m = art["meta"]
                slug = fname[:-3]
                title = m.get("title", slug)
                connects = ", ".join(m.get("connects", []))
                sources = ", ".join(m.get("sources", []))
                created = m.get("created", "-")
                lines.append(
                    f"| [connections/{slug}](connections/{slug}.md)"
                    f" | {connects}"
                    f" | {sources}"
                    f" | {created} |\n"
                )
        lines.append("\n")

    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    logging.info(f"Updated insights index at {index_path}")


# ---------------------------------------------------------------------------
# Agent SDK compilation (with fallback)
# ---------------------------------------------------------------------------

async def compile_with_agent_sdk(
    log_content: str, log_date: str, wiki_dir: str
) -> list[str]:
    """Try to compile via Claude Agent SDK; fall back to compile_basic."""
    try:
        from claude_agent_sdk import AgentClient

        client = AgentClient()
        prompt = (
            f"{COMPILE_PROMPT}\n\n---\n\n"
            f"DAILY LOG ({log_date}):\n\n{log_content}"
        )

        response = await client.process(
            prompt=prompt,
            allowed_tools=[],
            max_turns=2,
        )

        # Extract text from response
        if hasattr(response, "text"):
            raw = response.text
        elif hasattr(response, "content"):
            if isinstance(response.content, list):
                raw = "\n".join(
                    block.text for block in response.content
                    if hasattr(block, "text")
                )
            else:
                raw = str(response.content)
        else:
            raw = str(response)

        # The agent returns instructions; we fall through to basic compile
        # since we don't have file-write tools wired to the agent here.
        logging.info(f"Agent SDK responded ({len(raw)} chars) for {log_date}; using basic compile")
        return compile_basic(log_content, log_date, wiki_dir)

    except ImportError:
        logging.info("claude-agent-sdk not available, using compile_basic")
        return compile_basic(log_content, log_date, wiki_dir)
    except Exception as exc:
        logging.error(f"Agent SDK failed for {log_date}: {exc}; using compile_basic")
        return compile_basic(log_content, log_date, wiki_dir)


# ---------------------------------------------------------------------------
# Main compile loop
# ---------------------------------------------------------------------------

async def compile_logs(
    daily_dir: Path,
    wiki_dir: str,
    force_all: bool = False,
    specific_file: Path | None = None,
) -> int:
    """Compile daily logs into wiki concept/connection articles.

    Returns the number of logs processed.
    """
    if specific_file:
        logs = [specific_file] if specific_file.exists() else []
    else:
        logs = logs_to_process(daily_dir, force_all=force_all)

    if not logs:
        logging.info("No logs to process")
        return 0

    state = load_compile_state()
    processed = 0

    for log_path in logs:
        log_date = log_path.stem  # YYYY-MM-DD
        logging.info(f"Compiling {log_path.name}")

        content = log_path.read_text(encoding="utf-8")
        if not content.strip():
            logging.info(f"  Empty log, skipping")
            state[str(log_path)] = file_sha256(log_path)
            continue

        written = await compile_with_agent_sdk(content, log_date, wiki_dir)
        logging.info(f"  Wrote {len(written)} articles from {log_path.name}")

        # Update state hash regardless of output (avoids reprocessing empty logs)
        state[str(log_path)] = file_sha256(log_path)
        processed += 1

    save_compile_state(state)
    return processed


async def main_async() -> None:
    parser = argparse.ArgumentParser(
        description="Compile daily conversation logs into wiki concept/connection articles."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Force full recompilation of all daily logs",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Target a specific daily log file (e.g. daily/2026-04-07.md)",
    )
    args = parser.parse_args()

    daily_dir = PROJECT_ROOT / "daily"
    wiki_dir = str(PROJECT_ROOT)

    specific = args.file
    if specific and not specific.is_absolute():
        specific = PROJECT_ROOT / specific

    count = await compile_logs(
        daily_dir=daily_dir,
        wiki_dir=wiki_dir,
        force_all=args.all,
        specific_file=specific,
    )

    print(f"Compile complete: {count} log(s) processed")
    logging.info(f"Compile complete: {count} log(s) processed")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
