#!/usr/bin/env python3
"""SessionStart hook — inject wiki knowledge + recent insights at conversation start.

Loads wiki/INDEX.md, recent strategic signals, and accumulated session insights
so Claude starts every session with full pharmaceutical intelligence context.
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_wiki_index() -> str:
    """Load wiki INDEX.md content."""
    index_path = PROJECT_ROOT / "wiki" / "INDEX.md"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return ""


def get_recent_log() -> str:
    """Get the most recent daily log (today or yesterday)."""
    from datetime import datetime, timedelta, timezone

    daily_dir = PROJECT_ROOT / "daily"
    if not daily_dir.is_dir():
        return ""

    now = datetime.now(timezone.utc)
    for offset in range(3):  # today, yesterday, day before
        date_str = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        log_path = daily_dir / f"{date_str}.md"
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8")
            # Limit to last 30 lines to manage token budget
            lines = content.strip().split("\n")
            if len(lines) > 30:
                content = "\n".join(lines[-30:])
            return f"## Recent Session Log ({date_str})\n\n{content}"

    return ""


def get_recent_insights() -> str:
    """Load recent session insights summaries."""
    try:
        from cli_anything.cortellis.utils.insights_extractor import (
            load_recent_insights,
            format_insights_for_prompt,
        )
        wiki_path = str(PROJECT_ROOT / "wiki")
        if os.path.isdir(wiki_path):
            recent = load_recent_insights(wiki_path, max_age_days=14)
            return format_insights_for_prompt(recent, max_insights=3)
    except Exception:
        pass
    return ""


def get_signals() -> str:
    """Load strategic signals."""
    try:
        from cli_anything.cortellis.utils.intelligence import (
            extract_signals,
            format_signals_for_prompt,
        )
        wiki_path = str(PROJECT_ROOT / "wiki")
        if os.path.isdir(wiki_path):
            signals = extract_signals(wiki_path)
            return format_signals_for_prompt(signals) if signals else ""
    except Exception:
        pass
    return ""


def build_context() -> str:
    """Assemble all context sections."""
    from datetime import datetime, timezone

    parts = []
    parts.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")

    # Wiki index
    wiki_index = get_wiki_index()
    if wiki_index:
        parts.append(
            "\n## Available Compiled Knowledge\n\n"
            "CRITICAL: ALWAYS check the wiki BEFORE making API calls. "
            "If the answer exists in a compiled article, use it. "
            "Only call the Cortellis API when the wiki lacks the information "
            "or the user explicitly asks for a fresh analysis.\n\n"
            "Before fetching drug lists, company data, or landscape info, "
            "first read the relevant wiki article or raw CSV.\n\n"
            "Read articles: `cat wiki/indications/<slug>.md`\n"
            "Read raw data: `cat raw/<slug>/launched.csv`\n"
            "Compare: `python3 $RECIPES/portfolio_report.py`\n"
            "Changes: `python3 $RECIPES/diff_landscape.py <slug>`\n\n"
            f"{wiki_index}"
        )
    else:
        parts.append("\n_No compiled wiki articles yet. Run /landscape to build the knowledge base._")

    # Strategic signals
    signals = get_signals()
    if signals:
        parts.append(signals)

    # Recent insights
    insights = get_recent_insights()
    if insights:
        parts.append(insights)

    # Recent daily log
    daily_log = get_recent_log()
    if daily_log:
        parts.append(f"\n{daily_log}")

    context = "\n".join(parts)

    # Cap at 20K chars to stay within token budget
    if len(context) > 20000:
        context = context[:20000] + "\n\n_[Context truncated to 20K chars]_"

    return context


def main():
    """Output context as JSON for Claude Code hook system."""
    context = build_context()
    output = {
        "hookSpecificOutput": {
            "additionalContext": context
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
