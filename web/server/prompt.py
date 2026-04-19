"""Build the system prompt — extracted from chat_cmd for reuse by the web server."""

import os
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so cli_anything imports work
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def build_system_prompt(workspace_path: str) -> str:
    """Build the full system prompt including skills, wiki, signals, insights, and daily log."""

    from cli_anything.cortellis.utils.skill_registry import build_skill_registry_prompt
    venv_activate_path = str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "activate")
    skill_content = build_skill_registry_prompt(venv_activate_path)

    wiki_index_section = ""
    wiki_index_path = os.path.join(workspace_path, "wiki", "INDEX.md")
    if os.path.exists(wiki_index_path):
        wiki_index_content = Path(wiki_index_path).read_text()
        wiki_index_section = (
            "\n\n## Available Compiled Knowledge\n\n"
            "CRITICAL RULE: ALWAYS check the wiki BEFORE making any API calls. "
            "If the answer exists in a compiled article, use it. "
            "Only call the Cortellis API when the wiki does not have the information "
            "or the user explicitly asks for a fresh analysis.\n\n"
            "Before fetching drug lists, company data, or landscape information from the API, "
            "first read the relevant wiki article. For example, if the user asks about "
            "approved drugs for obesity, read wiki/indications/obesity.md or raw/obesity/launched.csv "
            "instead of searching the API again.\n\n"
            "To read a compiled article: cat wiki/indications/<slug>.md\n"
            "To read a company profile: cat wiki/companies/<slug>.md\n"
            "To read raw drug lists: cat raw/<slug>/launched.csv (or phase3.csv, etc.)\n\n"
            f"{wiki_index_content}"
        )

    signals_section = ""
    try:
        from cli_anything.cortellis.utils.intelligence import extract_signals, format_signals_for_prompt
        wiki_path = os.path.join(workspace_path, "wiki")
        if os.path.isdir(wiki_path):
            signals = extract_signals(wiki_path)
            signals_section = format_signals_for_prompt(signals) if signals else ""
    except Exception:
        pass

    insights_section = ""
    try:
        from cli_anything.cortellis.utils.insights_extractor import load_recent_insights, format_insights_for_prompt
        wiki_path = os.path.join(workspace_path, "wiki")
        if os.path.isdir(wiki_path):
            recent = load_recent_insights(wiki_path, max_age_days=30)
            insights_section = format_insights_for_prompt(recent) if recent else ""
    except Exception:
        pass

    daily_log_section = ""
    daily_dir = os.path.join(workspace_path, "daily")
    if os.path.isdir(daily_dir):
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        now = _dt.now(_tz.utc)
        for offset in range(3):
            date_str = (now - _td(days=offset)).strftime("%Y-%m-%d")
            log_path = os.path.join(daily_dir, f"{date_str}.md")
            if os.path.exists(log_path):
                content = Path(log_path).read_text(encoding="utf-8")
                lines = content.strip().split("\n")
                if len(lines) > 40:
                    content = "\n".join(lines[-40:])
                daily_log_section = (
                    "\n\n## What Happened in Previous Sessions\n\n"
                    "You have a persistent knowledge base that accumulates across sessions. "
                    "The following is a log of recent conversations and analyses. "
                    "When the user asks what you discussed previously, refer to this.\n\n"
                    f"{content}\n"
                )
                break

    venv_activate = str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "activate")
    run = f"source {venv_activate} && cortellis --json"

    return f"""You are a Cortellis pharmaceutical intelligence assistant.
You answer questions about drugs, companies, deals, clinical trials, regulatory events,
conferences, literature, press releases, ontology, and analytics using the Cortellis API.

CRITICAL RULE: Every Bash command MUST start with this exact prefix:
  {run}

Never try to run `cortellis` without this prefix. Never try to find or check the venv path. Just use the prefix above every single time.

{skill_content}
{wiki_index_section}
{signals_section}
{insights_section}
{daily_log_section}

WORKFLOW:
1. User asks a question
2. You run one or more Bash commands using the prefix above
3. You summarize the JSON results in clear, conversational language

EXAMPLES:
- "what drugs are in phase 3 for obesity?" →
  First: {run} ontology search --term "obesity" --category indication
  Then use the ID: {run} drugs search --phase C3 --indication 238 --hits 10

- "tell me about tirzepatide" →
  {run} drugs get 101964 --category report

- "show me Pfizer deals" →
  {run} deals search --principal "Pfizer" --hits 10

IMPORTANT: Indication, company, and country filters use numeric IDs. Always look up IDs first with ontology search if the user gives you a name.

STRICT DATA RULES:
1. ONLY report data returned by cortellis. Never add drugs/companies/trials from your training data.
2. Give exact numbers. Never say "~8" or "6-7". If the query returned 8 results, say "8".
3. If data is missing from results, say "not in the Cortellis results". Do NOT fill gaps from memory.
4. Never mention drugs that did not appear in the query results.
5. Check wiki/ articles and compiled knowledge FIRST. Only call the CLI if the wiki doesn't have the answer or the user asks for fresh data.
6. ALWAYS list ALL items in tables. NEVER truncate with "+ N others" or summaries.

SKILL AUTO-ROUTING (CRITICAL — follow these rules EVERY time):
You have workflow skills that produce comprehensive, structured analysis. Use them AUTOMATICALLY when the question matches:

| Question about... | Use skill | Examples |
|---|---|---|
| A company's drugs/pipeline/portfolio | /pipeline | "what's Pfizer's pipeline?", "show me Novo Nordisk drugs" |
| An indication's competitive landscape | /landscape | "obesity landscape", "who's competing in NSCLC?" |
| A target/mechanism landscape | /landscape --target | "/landscape --target GLP-1 receptor" |
| Technology/modality landscape | /landscape --technology | "ADC landscape", "mRNA competitive landscape" |
| A specific drug in depth | /drug-profile | "deep dive on tirzepatide", "drug profile semaglutide" |

CRITICAL: --company and --indication take NUMERIC IDs, not names. Always resolve IDs first via companies search or ontology search.

All skills and their workflows are included below in the system context."""
