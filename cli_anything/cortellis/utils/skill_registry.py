"""
skill_registry.py — Compact harness-first skill registry for system prompts.

Shared by web/server/prompt.py and cli chat_cmd in cortellis_cli.py.
"""

import re

# Skills that have a workflow.yaml and can be run via `cortellis run-skill`
HARNESS_SKILLS = {
    "landscape", "pipeline", "drug-profile", "drug-comparison",
    "conference-intel", "target-profile", "changelog", "ingest",
}

_REGISTRY = [
    {
        "name": "landscape",
        "triggers": "landscape, competitive analysis, who's competing, market overview",
        "syntax": 'cortellis run-skill landscape "<indication>"',
        "output": "wiki/indications/<slug>.md",
        "note": None,
    },
    {
        "name": "pipeline",
        "triggers": "pipeline, drug portfolio, what drugs does X make",
        "syntax": 'cortellis run-skill pipeline "<company>"',
        "output": "wiki/companies/<slug>.md",
        "note": None,
    },
    {
        "name": "drug-profile",
        "triggers": "drug profile, deep dive on drug, full drug report",
        "syntax": 'cortellis run-skill drug-profile "<drug>"',
        "output": "wiki/drugs/<slug>.md",
        "note": None,
    },
    {
        "name": "target-profile",
        "triggers": "target profile, mechanism landscape, target deep dive",
        "syntax": 'cortellis run-skill target-profile "<target>"',
        "output": "wiki/targets/<slug>.md",
        "note": None,
    },
    {
        "name": "drug-comparison",
        "triggers": "compare drugs, head to head, X vs Y",
        "syntax": 'cortellis run-skill drug-comparison "<drug1> vs <drug2>"',
        "output": "wiki/comparisons/<slug>.md",
        "note": None,
    },
    {
        "name": "conference-intel",
        "triggers": "conference, congress, ASCO, abstracts",
        "syntax": 'cortellis run-skill conference-intel "<query>"',
        "output": "wiki/conferences/<slug>.md",
        "note": None,
    },
    {
        "name": "changelog",
        "triggers": "changelog, what changed, pipeline history",
        "syntax": 'cortellis run-skill changelog "<indication>"',
        "output": "stdout narrative (no wiki file) — read the command output directly",
        "note": "Prerequisite: /landscape <indication> must have been run first",
    },
    {
        "name": "ingest",
        "triggers": "ingest, add document, import memo",
        "syntax": 'cortellis run-skill ingest "<file_path>"',
        "output": "wiki/internal/<slug>.md",
        "note": None,
    },
]


def wiki_output_hint(skill_name: str, args: str) -> str:
    """Return the 'then read ...' hint for a skill's output location."""
    slug = re.sub(r"[^a-z0-9]+", "-", args.lower()).strip("-")
    hints = {
        "landscape":        f"read `wiki/indications/{slug}.md`",
        "pipeline":         f"read `wiki/companies/{slug}.md`",
        "drug-profile":     f"read `wiki/drugs/{slug}.md`",
        "target-profile":   f"read `wiki/targets/{slug}.md`",
        "drug-comparison":  f"read `wiki/comparisons/{slug}.md`",
        "conference-intel": f"read `wiki/conferences/{slug}.md`",
        "changelog":        "read the stdout output directly (no wiki file written)",
        "ingest":           f"read `wiki/internal/{slug}.md`",
    }
    return hints.get(skill_name, "read the resulting wiki article")


def build_skill_registry_prompt(venv_activate: str) -> str:
    """Return the harness-first skill execution block for system prompts."""
    run_prefix = f"source {venv_activate} && cortellis run-skill"

    rows = []
    for s in _REGISTRY:
        note = f" _{s['note']}_" if s["note"] else ""
        rows.append(
            f"| `{s['name']}` | {s['triggers']} | `{s['syntax']}` | {s['output']}{note} |"
        )
    table = "\n".join([
        "| Skill | Triggers | Command | Output |",
        "|---|---|---|---|",
    ] + rows)

    return f"""
## Skill Execution — HARNESS MODE (CRITICAL)

NEVER manually execute skill steps by running individual recipe scripts.
NEVER follow SKILL.md steps one-by-one via Bash.
Instead, execute skills as a SINGLE Bash command:

  {run_prefix} <skill> "<args>"

The harness handles all steps internally (API calls, compilation, wiki updates).

### Harness-backed skills

{table}

### Post-skill workflow
1. Run: `{run_prefix} <skill> "<args>"`
2. Wait for completion — narrate each wave as it prints (e.g. "✓ Wave 0: resolve")
3. Read the output location shown above
4. Present a structured summary with key highlights
5. Offer 2-3 follow-up suggestions (/pipeline, /drug-profile, etc.)

### Routing rules
- `/landscape obesity` → `{run_prefix} landscape "obesity"`
- `/pipeline "Novo Nordisk"` → `{run_prefix} pipeline "Novo Nordisk"`
- Auto-detected queries (e.g. "obesity landscape") → same harness command
- `changelog` has no wiki output — summarize stdout directly
"""
