#!/usr/bin/env python3
"""Flush — extract pharma intelligence insights from conversation transcript.

Uses the Claude Agent SDK to analyze conversation context and extract
key decisions, lessons, strategic insights for the daily log.

Usage: python3 flush.py <context_file> <session_id>

Runs as a background process spawned by session-end.py or pre-compact.py.
"""

# Set recursion guard BEFORE any imports
import os
os.environ["CLAUDE_INVOKED_BY"] = "flush-script"

import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "flush.log"
STATE_PATH = PROJECT_ROOT / "daily" / ".flush-state.json"

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [flush] %(message)s",
)

EXTRACTION_PROMPT = """You are analyzing a conversation transcript from a pharmaceutical intelligence CLI (cortellis-cli).

Extract ONLY the valuable, non-obvious insights. Skip routine operations, tool outputs, and trivial exchanges.

Structure your response EXACTLY as follows:

## Session Summary
One paragraph describing what was accomplished.

## Key Decisions
- Decision 1 (with rationale)
- Decision 2

## Lessons Learned
- Lesson 1 (what worked or didn't)
- Lesson 2

## Strategic Insights
- Any pharmaceutical competitive intelligence findings
- Drug pipeline observations
- Deal or regulatory signals
- Market dynamics or trends noted

## Action Items
- Pending tasks or follow-ups

If the conversation was routine with no notable insights, respond with:
## Session Summary
Routine session with no notable insights to capture.

IMPORTANT: Be selective. Only extract things that would be valuable to recall in a future session. Skip boilerplate, debugging, and routine API calls."""


def check_dedup(session_id: str) -> bool:
    """Check if this session was already flushed recently (within 60s)."""
    if not STATE_PATH.exists():
        return False
    try:
        state = json.loads(STATE_PATH.read_text())
        if state.get("last_session_id") == session_id:
            last_ts = state.get("last_flush_ts", 0)
            if (datetime.now(timezone.utc).timestamp() - last_ts) < 60:
                return True
    except (json.JSONDecodeError, OSError):
        pass
    return False


def update_dedup(session_id: str):
    """Record that this session was flushed."""
    os.makedirs(STATE_PATH.parent, exist_ok=True)
    state = {
        "last_session_id": session_id,
        "last_flush_ts": datetime.now(timezone.utc).timestamp(),
    }
    STATE_PATH.write_text(json.dumps(state))


def append_to_daily_log(content: str):
    """Append extracted content to today's daily log."""
    daily_dir = PROJECT_ROOT / "daily"
    daily_dir.mkdir(exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = daily_dir / f"{date_str}.md"

    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    entry = f"\n\n---\n\n### Session ({timestamp})\n\n{content}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        if not log_path.exists() or log_path.stat().st_size == 0:
            f.write(f"# Daily Log — {date_str}\n")
        f.write(entry)

    logging.info(f"Appended to {log_path}")
    return log_path


async def extract_with_agent_sdk(context: str) -> str:
    """Use claude CLI to extract insights from conversation context.

    Shells out to the claude CLI with --print flag for reliable extraction.
    Falls back to basic extraction if claude is not available.
    """
    import subprocess as sp
    import shutil

    claude_bin = shutil.which("claude")
    if not claude_bin:
        logging.warning("claude CLI not found, falling back to basic extraction")
        return extract_basic(context)

    # Truncate context to stay within token limits
    truncated = context[:12000] if len(context) > 12000 else context
    prompt = f"{EXTRACTION_PROMPT}\n\n---\n\nCONVERSATION TRANSCRIPT:\n\n{truncated}"

    try:
        result = sp.run(
            [claude_bin, "--print", "-p", prompt, "--max-turns", "1",
             "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "CLAUDE_INVOKED_BY": "flush-script"},
        )
        if result.returncode == 0 and result.stdout.strip():
            logging.info(f"Claude CLI extraction: {len(result.stdout)} chars")
            return result.stdout.strip()
        else:
            logging.warning(f"Claude CLI returned code {result.returncode}, falling back")
            return extract_basic(context)

    except sp.TimeoutExpired:
        logging.warning("Claude CLI timed out after 120s, falling back")
        return extract_basic(context)
    except Exception as e:
        logging.error(f"Claude CLI failed: {e}, falling back to basic extraction")
        return extract_basic(context)


def extract_basic(context: str) -> str:
    """Fallback extraction without Agent SDK — just capture the conversation summary."""
    lines = context.strip().split("\n")
    user_messages = [l for l in lines if l.startswith("**User:**")]
    assistant_messages = [l for l in lines if l.startswith("**Assistant:**")]

    summary_parts = ["## Session Summary\n"]
    summary_parts.append(f"Session with {len(user_messages)} user messages and {len(assistant_messages)} assistant responses.\n")

    # Extract user questions as key topics
    if user_messages:
        summary_parts.append("\n## Key Topics\n")
        for msg in user_messages[:10]:
            topic = msg.replace("**User:**", "").strip()[:150]
            if topic:
                summary_parts.append(f"- {topic}\n")

    return "".join(summary_parts)


def should_trigger_compile() -> bool:
    """Check if we should trigger compilation (after 6 PM, log changed since last compile)."""
    now = datetime.now(timezone.utc)
    if now.hour < 18:
        return False

    date_str = now.strftime("%Y-%m-%d")
    log_path = PROJECT_ROOT / "daily" / f"{date_str}.md"
    if not log_path.exists():
        return False

    # Check if log changed since last compile via hash
    current_hash = hashlib.sha256(log_path.read_bytes()).hexdigest()
    compile_state = STATE_PATH.parent / ".compile-state.json"
    if compile_state.exists():
        try:
            state = json.loads(compile_state.read_text())
            if state.get("last_hash") == current_hash:
                return False
        except (json.JSONDecodeError, OSError):
            pass

    return True


def trigger_compile():
    """Spawn compile process for today's log."""
    try:
        from cli_anything.cortellis.utils.session_memory import flush_session_memory
        flush_session_memory()
        logging.info("Triggered session memory flush (compile)")
    except Exception as e:
        logging.error(f"Compile trigger failed: {e}")


async def main_async():
    if len(sys.argv) < 3:
        logging.error("Usage: flush.py <context_file> <session_id>")
        sys.exit(1)

    context_file = Path(sys.argv[1])
    session_id = sys.argv[2]

    logging.info(f"Flush starting for session {session_id}")

    # Dedup check
    if check_dedup(session_id):
        logging.info(f"Session {session_id} already flushed recently, skipping")
        return

    # Read context
    if not context_file.exists():
        logging.error(f"Context file not found: {context_file}")
        return

    context = context_file.read_text(encoding="utf-8")
    if not context.strip():
        logging.info("Empty context, skipping")
        return

    logging.info(f"Processing {len(context)} chars from {context_file.name}")

    # Extract insights
    extracted = await extract_with_agent_sdk(context)

    if not extracted.strip():
        logging.info("No insights extracted")
        return

    # Append to daily log
    log_path = append_to_daily_log(extracted)
    logging.info(f"Insights written to {log_path}")

    # Update dedup state
    update_dedup(session_id)

    # Clean up temp context file
    try:
        context_file.unlink()
    except OSError:
        pass

    # Check if we should trigger compilation
    if should_trigger_compile():
        trigger_compile()

    logging.info(f"Flush complete for session {session_id}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
