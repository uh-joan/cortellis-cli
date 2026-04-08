#!/usr/bin/env python3
"""SessionEnd hook — capture conversation transcript and spawn flush.

Reads the JSONL transcript from Claude Code, extracts user/assistant turns,
and spawns flush.py as a background process to extract pharma insights.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Recursion guard: if we're invoked by the Agent SDK, exit immediately
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "flush.log"

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [session-end] %(message)s",
)

MAX_TURNS = 30
MAX_CONTEXT_CHARS = 15000
MIN_TURNS_TO_FLUSH = 1


def extract_conversation_context(transcript_path: str) -> tuple[str, int]:
    """Extract user/assistant turns from JSONL transcript.

    Returns (context_text, turn_count).
    """
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

                # Claude Code JSONL has nested format:
                # {"type": "user", "message": {"role": "user", "content": "..."}}
                entry_type = entry.get("type", "")
                message = entry.get("message", {})
                role = message.get("role", "") if isinstance(message, dict) else ""

                # Accept both nested and flat formats
                if not role:
                    role = entry.get("role", "")
                if role not in ("user", "assistant"):
                    continue

                content = message.get("content", "") if isinstance(message, dict) and role else entry.get("content", "")
                if isinstance(content, list):
                    # Handle structured content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif block.get("type") == "tool_result":
                                text_parts.append(f"[tool result: {str(block.get('content', ''))[:200]}]")
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

    # Take the most recent turns, limited by count and chars
    if len(turns) > MAX_TURNS:
        turns = turns[-MAX_TURNS:]

    context = "\n\n".join(turns)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[-MAX_CONTEXT_CHARS:]

    turn_count = len(turns)
    return context, turn_count


def main():
    """Read hook input, extract transcript, spawn flush."""
    try:
        raw_input = sys.stdin.read()
        # Handle Windows-style unescaped backslashes
        raw_input = raw_input.replace("\\", "\\\\") if "\\" in raw_input and "\\\\" not in raw_input else raw_input
        hook_data = json.loads(raw_input) if raw_input.strip() else {}
    except (json.JSONDecodeError, IOError):
        hook_data = {}

    session_id = hook_data.get("session_id", "unknown")
    transcript_path = hook_data.get("transcript_path", "")

    # Debug: log raw hook data to understand the format
    logging.info(f"Session end: {session_id}")
    logging.info(f"Hook data keys: {list(hook_data.keys())}")
    logging.info(f"Transcript path: '{transcript_path}' exists={os.path.exists(transcript_path) if transcript_path else 'N/A'}")

    if not transcript_path or not os.path.exists(transcript_path):
        logging.info(f"No transcript at provided path: '{transcript_path}'")
        # Claude Code stores transcripts as <session_id>.jsonl in the project dir
        # Discover the project slug from the cwd
        cwd_slug = str(PROJECT_ROOT).replace("/", "-").lstrip("-")
        possible_paths = [
            os.path.expanduser(f"~/.claude/projects/{cwd_slug}/{session_id}.jsonl"),
            os.path.expanduser(f"~/.claude/projects/-{cwd_slug}/{session_id}.jsonl"),
        ]
        # Also try glob for any matching jsonl
        import glob
        possible_paths += glob.glob(os.path.expanduser(f"~/.claude/projects/*/{session_id}.jsonl"))

        for pp in possible_paths:
            if os.path.exists(pp):
                logging.info(f"Found transcript at: {pp}")
                transcript_path = pp
                break
        else:
            logging.info(f"No transcript found for session {session_id}")
            return

    context, turn_count = extract_conversation_context(transcript_path)
    logging.info(f"Extracted context: {turn_count} turns, {len(context)} chars")

    if turn_count < MIN_TURNS_TO_FLUSH:
        logging.info(f"Only {turn_count} turns, skipping flush (min: {MIN_TURNS_TO_FLUSH})")
        return

    if not context.strip():
        logging.info("Empty context, skipping flush")
        return

    logging.info(f"Extracted {turn_count} turns ({len(context)} chars)")

    # Write context to a temp file for flush.py
    context_file = PROJECT_ROOT / "daily" / f".flush-{session_id}.md"
    os.makedirs(context_file.parent, exist_ok=True)
    context_file.write_text(context, encoding="utf-8")

    # Spawn flush.py as background process
    flush_script = PROJECT_ROOT / "hooks" / "flush.py"
    if not flush_script.exists():
        logging.error(f"flush.py not found at {flush_script}")
        return

    try:
        env = os.environ.copy()
        env["CLAUDE_INVOKED_BY"] = "session-end-hook"

        cmd = [
            str(PROJECT_ROOT / ".venv" / "bin" / "python3"),
            str(flush_script),
            str(context_file),
            session_id,
        ]

        kwargs = {"env": env, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        # Windows: suppress console window
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        subprocess.Popen(cmd, **kwargs)
        logging.info(f"Spawned flush.py for session {session_id}")

    except Exception as e:
        logging.error(f"Failed to spawn flush.py: {e}")


if __name__ == "__main__":
    main()
