"""
Translate raw Bash commands into user-friendly status messages for the chat spinner.

Returns None for commands that should be silently skipped.
"""

import re

# Phase code to human-readable label
_PHASE_LABELS = {
    "L": "Launched",
    "C3": "Phase 3",
    "C2": "Phase 2",
    "C1": "Phase 1",
    "DR": "Discovery",
    "DX": "Discontinued",
}

# Utility commands that should be silently skipped
_SKIP_RE = re.compile(
    r"^\s*(echo|cat|wc|head|tail|sleep|printf|mkdir|rm|cp|mv|ls)\b",
    re.IGNORECASE,
)

# Python script basename → (friendly label, show_first_arg)
_PYTHON_SCRIPTS = {
    "resolve_indication": ("Resolving indication", True),
    "ci_drugs_to_csv": ("Processing drug data", False),
    "landscape_report_generator": ("Generating landscape report", False),
    "company_landscape": ("Analyzing company landscape", False),
    "enrich_mechanisms": ("Enriching mechanism data", False),
    "group_biosimilars": ("Grouping biosimilar drugs", False),
    "resolve_company": ("Resolving company ID", False),
    "report_generator": ("Generating pipeline report", False),
}


def translate_command(cmd: str) -> "str | None":
    """Translate a raw Bash command to a user-friendly status message.

    Returns None if the command should be silently skipped.
    """
    # Strip venv activation prefix
    cmd = re.sub(r"^source\s+\S+/activate\s*&&\s*", "", cmd.strip())

    # Skip utility commands
    if _SKIP_RE.match(cmd):
        return None

    # Python script handling
    py_m = re.match(r"python3?\s+\S*?([a-zA-Z_]+)\.py\b(.*)", cmd)
    if py_m:
        script_key = py_m.group(1).lower()
        rest = py_m.group(2).strip()
        for key, (label, show_arg) in _PYTHON_SCRIPTS.items():
            if key in script_key:
                if show_arg:
                    arg_m = re.search(r'["\']([^"\']+)["\']|(\S+)', rest)
                    if arg_m:
                        arg = arg_m.group(1) or arg_m.group(2)
                        return f"{label}: {arg}"
                return label
        return f"Running script: {script_key}"

    # Cortellis commands
    cortellis_m = re.match(r"cortellis(?:\s+--json)?\s+(.*)", cmd, re.IGNORECASE)
    if not cortellis_m:
        return None

    sub = cortellis_m.group(1).strip()

    # ontology search
    if re.match(r"ontology\s+search\b", sub, re.IGNORECASE):
        term_m = (
            re.search(r'--term\s+"([^"]+)"', sub) or
            re.search(r"--term\s+'([^']+)'", sub) or
            re.search(r'--term\s+(\S+)', sub)
        )
        if term_m:
            return f"Looking up indication: {term_m.group(1).strip()}"
        return "Searching ontology"

    # ner match
    ner_m = re.match(r"ner\s+match\b(.*)", sub, re.IGNORECASE)
    if ner_m:
        arg_m = re.search(r'"([^"]+)"|\'([^\']+)\'|(\S+)', ner_m.group(1).strip())
        if arg_m:
            term = arg_m.group(1) or arg_m.group(2) or arg_m.group(3)
            return f"Resolving entity: {term}"
        return "Resolving entity"

    # drugs search
    drugs_m = re.match(r"drugs\s+search\b(.*)", sub, re.IGNORECASE)
    if drugs_m:
        args = drugs_m.group(1)
        phase_m = re.search(r"--phase\s+(\S+)", args, re.IGNORECASE)
        hits_m = re.search(r"--hits\s+(\d+)", args, re.IGNORECASE)
        phase = _PHASE_LABELS.get(phase_m.group(1).upper(), phase_m.group(1)) if phase_m else None
        hits = hits_m.group(1) if hits_m else None
        if phase and hits:
            return f"Fetching {phase} drugs (up to {hits})"
        if phase:
            return f"Fetching {phase} drugs"
        if hits:
            return f"Searching drugs (up to {hits})"
        return "Searching drugs"

    # drugs get
    if re.match(r"drugs\s+get\b", sub, re.IGNORECASE):
        return "Fetching drug details"

    # companies search
    companies_m = re.match(r"companies\s+search\b(.*)", sub, re.IGNORECASE)
    if companies_m:
        q_m = (
            re.search(r'--(?:query|name)\s+"([^"]+)"', companies_m.group(1)) or
            re.search(r"--(?:query|name)\s+'([^']+)'", companies_m.group(1)) or
            re.search(r'--(?:query|name)\s+(\S+)', companies_m.group(1))
        )
        if q_m:
            return f"Looking up company: {q_m.group(1).strip()}"
        return "Searching companies"

    # companies get
    if re.match(r"companies\s+get\b", sub, re.IGNORECASE):
        return "Fetching company details"

    # deals search
    if re.match(r"deals\s+search\b", sub, re.IGNORECASE):
        return "Searching recent deals"

    # trials search
    if re.match(r"trials\s+search\b", sub, re.IGNORECASE):
        return "Searching clinical trials"

    # regulatory
    if re.match(r"regulatory\s+search\b", sub, re.IGNORECASE):
        return "Searching regulatory events"

    # literature
    if re.match(r"literature\s+search\b", sub, re.IGNORECASE):
        return "Searching literature"

    # press-releases / press_releases
    if re.match(r"press[_-]releases?\s+search\b", sub, re.IGNORECASE):
        return "Searching press releases"

    # analytics
    analytics_m = re.match(r"analytics\s+(\S+)", sub, re.IGNORECASE)
    if analytics_m:
        return f"Running analytics: {analytics_m.group(1)}"

    # targets
    if re.match(r"targets\s+search\b", sub, re.IGNORECASE):
        return "Searching targets"

    # conferences
    if re.match(r"conferences\s+search\b", sub, re.IGNORECASE):
        return "Searching conferences"

    # Generic cortellis fallback
    tokens = sub.split()
    if tokens:
        return "Running: cortellis {}".format(" ".join(tokens[:2]))

    return "Querying Cortellis"
