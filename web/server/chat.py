"""Run a chat turn via the claude CLI and yield SSE-formatted events."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from web.server.prompt import build_system_prompt
from web.server import db

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _build_wiki_context(question: str, workspace_path: str) -> str:
    try:
        from cli_anything.cortellis.core.skill_router import check_wiki_fast_path
        from cli_anything.cortellis.utils.wiki import read_article as _read_wiki

        wiki_article_path = check_wiki_fast_path(question)
        if wiki_article_path:
            art = _read_wiki(wiki_article_path)
            if art:
                return (
                    "\n\n--- COMPILED WIKI ARTICLE ---\n"
                    "A compiled article is available. Use it to answer the question. "
                    "Only call the API if the user explicitly requests fresh data.\n\n"
                    f"Title: {art['meta'].get('title', 'Unknown')}\n"
                    f"Compiled: {art['meta'].get('compiled_at', 'Unknown')}\n\n"
                    f"{art['body']}\n"
                    "--- END COMPILED ARTICLE ---\n"
                )

        wiki_dir = os.path.join(workspace_path, "wiki")
        question_lower = question.lower()
        matched_articles = []
        for article_type in ("drugs", "companies"):
            type_dir = os.path.join(wiki_dir, article_type)
            if not os.path.isdir(type_dir):
                continue
            for fname in os.listdir(type_dir):
                if not fname.endswith(".md"):
                    continue
                slug = fname[:-3]
                slug_words = slug.replace("-", " ")
                if any(w in question_lower for w in slug_words.split() if len(w) > 3):
                    art = _read_wiki(os.path.join(type_dir, fname))
                    if art and art["meta"]:
                        matched_articles.append(art)
                if len(matched_articles) >= 3:
                    break
            if len(matched_articles) >= 3:
                break

        if matched_articles:
            parts = ["\n\n--- COMPILED WIKI ARTICLES ---\n"
                     "These wiki articles match your question. Use them to answer.\n\n"]
            for art in matched_articles:
                parts.append(f"### {art['meta'].get('title', 'Unknown')} "
                              f"(compiled: {art['meta'].get('compiled_at', '?')[:10]})\n\n")
                body = art["body"]
                if len(body) > 5000:
                    body = body[:5000] + "\n\n_[Article truncated]_\n"
                parts.append(f"{body}\n\n")
            parts.append("--- END COMPILED ARTICLES ---\n")
            return "".join(parts)
    except Exception:
        pass
    return ""


def _route_question(question: str) -> str:
    try:
        from cli_anything.cortellis.core.skill_router import detect_skill
        from cli_anything.cortellis.core.context_detector import detect_multi_entity

        CORTELLIS_SKILLS = {
            "pipeline", "landscape", "drug-profile", "drug-comparison",
            "conference-intel", "target-profile", "signals",
        }
        if question.startswith("/"):
            skill_name = question.split()[0][1:].lower()
            if skill_name in CORTELLIS_SKILLS:
                args = question[len(skill_name) + 1:].strip()
                return f"[SKILL: Use the /{skill_name} skill workflow] {args}"

        skill_directive = detect_skill(question)
        routed = f"{skill_directive}{question}" if skill_directive else question

        multi = detect_multi_entity(question)
        if multi and len(multi["entities"]) >= 2:
            entity_list = ", ".join(f'"{e}"' for e in multi["entities"])
            routed = (
                f"[PARALLEL DISPATCH: This query covers {len(multi['entities'])} entities "
                f"({entity_list}) for the /{multi['skill']} skill. "
                f"Run each as a separate Agent invocation with run_in_background=true "
                f"so they execute concurrently. Synthesize results after all complete.]\n"
                + routed
            )
        return routed
    except Exception:
        return question


def stream_chat_turn(conv_id: str, question: str, workspace_path: str):
    """Generator that yields SSE-formatted strings for a single chat turn."""
    ai_bin = shutil.which("claude")
    if not ai_bin:
        yield f"data: {json.dumps({'type': 'error', 'text': 'claude CLI not found. Install Claude Code first.'})}\n\n"
        return

    system_prompt = build_system_prompt(workspace_path)
    wiki_context = _build_wiki_context(question, workspace_path)
    history = db.get_history(conv_id)

    history_block = ""
    if history:
        lines = ["\n\n## Recent Conversation\n\n"]
        for t in history:
            a = t["a"][:400] + ("..." if len(t["a"]) > 400 else "")
            lines.append(f"**User:** {t['q']}\n\n**Assistant:** {a}\n\n---\n\n")
        history_block = "".join(lines)

    effective_prompt = system_prompt + wiki_context + history_block
    routed_question = _route_question(question)

    cmd = [
        ai_bin, "--print", "-p", routed_question,
        "--append-system-prompt", effective_prompt,
        "--allowedTools", "Bash",
        "--output-format", "stream-json", "--verbose",
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=workspace_path,
        )
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        return

    try:
        from cli_anything.cortellis.core.status_translator import translate_command
    except Exception:
        def translate_command(x):
            return None

    text = ""
    for line in iter(proc.stdout.readline, b""):
        decoded = line.decode("utf-8", errors="replace").strip()
        if not decoded:
            continue
        try:
            event = json.loads(decoded)
        except json.JSONDecodeError:
            continue

        etype = event.get("type", "")

        if etype == "assistant" and "message" in event:
            content = event["message"].get("content", [])
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_use" and block.get("name") == "Bash":
                        cmd_str = block.get("input", {}).get("command", "")
                        status = translate_command(cmd_str) or "Running query…"
                        yield f"data: {json.dumps({'type': 'tool_call', 'status': status, 'command': cmd_str})}\n\n"

        elif etype == "result":
            text = event.get("result", "")
            yield f"data: {json.dumps({'type': 'result', 'text': text})}\n\n"

    proc.wait()
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

    if text:
        db.add_message(conv_id, "assistant", text)
