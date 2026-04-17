"""Import CLI session history (daily/*.md) into SQLite as conversations."""

import os
from pathlib import Path

from web.server import db


def import_cli_history(workspace_path: str) -> int:
    """Import CLI session history into SQLite. Returns number of new conversations created."""
    daily_dir = os.path.join(workspace_path, "daily")
    if not os.path.isdir(daily_dir):
        return 0

    existing = db.list_conversations(workspace_path)
    imported_titles = {c["title"] for c in existing if c["title"].startswith("CLI — ")}

    created = 0
    for fname in sorted(os.listdir(daily_dir)):
        if not fname.endswith(".md"):
            continue
        date = fname[:-3]
        conv_title = f"CLI — {date}"
        if conv_title in imported_titles:
            continue

        path = os.path.join(daily_dir, fname)
        try:
            content = Path(path).read_text(encoding="utf-8")
            if len(content.strip()) < 50:
                continue
            conv = db.create_conversation(workspace_path, conv_title)
            # Store the full session log as a single readable assistant message
            db.add_message(conv["id"], "assistant", content)
            created += 1
        except Exception:
            pass

    return created
