"""
Detect which skill workflow should handle a user question.

Returns a directive string to prepend to the question, or None if no skill applies.
High-precision patterns only — avoids false positives on simple factual queries.
"""

import re

# Each skill has trigger patterns and an extraction function for the subject.
# Patterns are tested in order; first match wins.

_SKILLS = [
    {
        "name": "pipeline",
        "triggers": [
            re.compile(r"\bpipeline\b", re.IGNORECASE),
            re.compile(r"\bdrug\s+portfolio\b", re.IGNORECASE),
            re.compile(r"\b(?:what(?:'s|s)?|show|list)\b.{0,30}\b(?:developing|pipeline|portfolio)\b", re.IGNORECASE),
        ],
        "directive": "/pipeline",
        "description": "company pipeline analysis",
    },
    {
        "name": "landscape",
        "triggers": [
            re.compile(r"\blandscape\b", re.IGNORECASE),
            re.compile(r"\bcompetitive\s+(?:landscape|analysis|overview)\b", re.IGNORECASE),
            re.compile(r"\bmarket\s+(?:overview|landscape|map)\b", re.IGNORECASE),
        ],
        "directive": "/landscape",
        "description": "competitive landscape for an indication",
    },
    {
        "name": "drug-profile",
        "triggers": [
            re.compile(r"\bdrug\s*profile\b", re.IGNORECASE),
            re.compile(r"\bdrug\s+dossier\b", re.IGNORECASE),
            re.compile(r"\bfull\s+(?:report|analysis)\b.{0,20}\bdrug\b", re.IGNORECASE),
            # "deep dive" only when NOT followed by deal/company/pipeline/landscape keywords
            re.compile(r"\bdeep\s*dive\b(?!.{0,15}\b(?:deal|company|pipeline|landscape|partner|competitor))", re.IGNORECASE),
        ],
        "directive": "/drug-profile",
        "description": "deep drug profile with SWOT, financials, competitive context",
    },
    {
        "name": "deal-scout",
        "triggers": [
            re.compile(r"\bdeal\s*scout\b", re.IGNORECASE),
            re.compile(r"\bdeal\s+landscape\b", re.IGNORECASE),
            re.compile(r"\bpartnership\s+(?:analysis|landscape|overview)\b", re.IGNORECASE),
        ],
        "directive": "/deal-scout",
        "description": "deal intelligence and partnership analysis",
    },
    {
        "name": "target-map",
        "triggers": [
            re.compile(r"\btarget\s*map\b", re.IGNORECASE),
            re.compile(r"\btarget[- ]drug[- ]indication\b", re.IGNORECASE),
        ],
        "directive": "/target-map",
        "description": "target-drug-indication mapping",
    },
    {
        "name": "regulatory-watch",
        "triggers": [
            re.compile(r"\bregulatory\s*watch\b", re.IGNORECASE),
            re.compile(r"\bregulatory\s+(?:timeline|tracker|overview)\b", re.IGNORECASE),
        ],
        "directive": "/regulatory-watch",
        "description": "regulatory event tracking",
    },
    {
        "name": "patent-cliff",
        "triggers": [
            re.compile(r"\bpatent\s*cliff\b", re.IGNORECASE),
            re.compile(r"\bpatent\s+expir", re.IGNORECASE),
            re.compile(r"\bgeneric\s+entry\b", re.IGNORECASE),
        ],
        "directive": "/patent-cliff",
        "description": "patent expiry and generic entry analysis",
    },
]


def detect_skill(question: str) -> str | None:
    """Detect if a question should be routed to a skill workflow.

    Returns a directive string like "[SKILL: /pipeline] " to prepend,
    or None if no skill applies.
    """
    # Don't re-route if user already used explicit /command
    if question.strip().startswith("/"):
        return None

    for skill in _SKILLS:
        for pattern in skill["triggers"]:
            if pattern.search(question):
                return f'[SKILL: Use the {skill["directive"]} skill workflow for this question] '

    return None
