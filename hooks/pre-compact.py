#!/usr/bin/env python3
"""PreCompact hook — capture transcript before context window compression.

Nearly identical to session-end.py but fires before context compaction.
Higher turn threshold since compaction happens mid-session.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Recursion guard
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "flush.log"

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [pre-compact] %(message)s",
)

MAX_TURNS = 30
MAX_CONTEXT_CHARS = 15000
MIN_TURNS_TO_FLUSH = 5  # Higher threshold — compaction means substantial conversation


def extract_conversation_context(transcript_path: str) -> tuple[str, int]:
    """Extract user/assistant turns from JSONL transcript."""
    turns = []
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                role = entry.get("role", "")
                if role not in ("user", "assistant"):
                    continue

                content = entry.get("content", "")
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = "\n".join(text_parts)
                elif not isinstance(content, str):
                    content = str(content)

                if content.strip():
                    turns.append(f"**{role.title()}:** {content.strip()}")

    except (OSError, IOError) as e:
        logging.error(f"Failed to read transcript: {e}")
        return "", 0

    if len(turns) > MAX_TURNS:
        turns = turns[-MAX_TURNS:]

    context = "\n\n".join(turns)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[-MAX_CONTEXT_CHARS:]

    return context, len(turns)


def main():
    try:
        raw_input = sys.stdin.read()
        raw_input = raw_input.replace("\\", "\\\\") if "\\" in raw_input and "\\\\" not in raw_input else raw_input
        hook_data = json.loads(raw_input) if raw_input.strip() else {}
    except (json.JSONDecodeError, IOError):
        hook_data = {}

    session_id = hook_data.get("session_id", "unknown")
    transcript_path = hook_data.get("transcript_path", "")

    logging.info(f"Pre-compact: {session_id}")

    if not transcript_path or not os.path.exists(transcript_path):
        logging.info(f"No transcript at: {transcript_path}")
        return

    context, turn_count = extract_conversation_context(transcript_path)

    if turn_count < MIN_TURNS_TO_FLUSH:
        logging.info(f"Only {turn_count} turns, skipping (min: {MIN_TURNS_TO_FLUSH})")
        return

    if not context.strip():
        logging.info("Empty context, skipping")
        return

    logging.info(f"Extracted {turn_count} turns ({len(context)} chars) before compaction")

    context_file = PROJECT_ROOT / "daily" / f".flush-compact-{session_id}.md"
    os.makedirs(context_file.parent, exist_ok=True)
    context_file.write_text(context, encoding="utf-8")

    flush_script = PROJECT_ROOT / "hooks" / "flush.py"
    if not flush_script.exists():
        logging.error(f"flush.py not found")
        return

    try:
        env = os.environ.copy()
        env["CLAUDE_INVOKED_BY"] = "pre-compact-hook"

        cmd = [
            str(PROJECT_ROOT / ".venv" / "bin" / "python3"),
            str(flush_script),
            str(context_file),
            session_id,
        ]

        kwargs = {"env": env, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        subprocess.Popen(cmd, **kwargs)
        logging.info(f"Spawned flush.py for compaction {session_id}")

    except Exception as e:
        logging.error(f"Failed to spawn flush.py: {e}")


if __name__ == "__main__":
    main()
