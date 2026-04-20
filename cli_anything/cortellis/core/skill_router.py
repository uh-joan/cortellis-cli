"""
Detect which skill workflow should handle a user question.

Returns a directive string to prepend to the question, or None if no skill applies.
High-precision patterns only — avoids false positives on simple factual queries.
"""

import os
import re
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]

from cli_anything.cortellis.utils.wiki import article_path, check_freshness, slugify

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
            re.compile(r"--target\b", re.IGNORECASE),
            re.compile(r"--technology\b", re.IGNORECASE),
            re.compile(r"\b(ADC|mRNA|CAR-T|gene\s+therapy|cell\s+therapy|bispecific)\s+landscape\b", re.IGNORECASE),
        ],
        "directive": "/landscape",
        "description": "competitive landscape for an indication, target, or technology/modality",
    },
    {
        "name": "drug-comparison",
        "triggers": [
            re.compile(r"\bcompare\s+(?:drug|drugs)\b", re.IGNORECASE),
            re.compile(r"\bdrug\s+comparison\b", re.IGNORECASE),
            re.compile(r"\bhead\s+to\s+head\b", re.IGNORECASE),
            re.compile(r"\bversus\b", re.IGNORECASE),
            re.compile(r"\bvs\.?\s+", re.IGNORECASE),
        ],
        "directive": "/drug-comparison",
        "description": "side-by-side comparison of 2-5 drugs",
    },
    {
        "name": "conference-intel",
        "triggers": [
            re.compile(r"\bconferences?\b", re.IGNORECASE),
            re.compile(r"\bcongress\b", re.IGNORECASE),
            re.compile(r"\b(?:ASCO|ESMO|ASH|AAN|AACR|EHA|EASL)\b", re.IGNORECASE),
            re.compile(r"\babstracts?\b", re.IGNORECASE),
        ],
        "directive": "/conference-intel",
        "description": "conference intelligence briefing with What's New / So What / What's Next",
    },
    {
        "name": "signals",
        "triggers": [
            re.compile(r"\bsignals?\b(?!.{0,30}\b(?:transduction|pathway|receptor|cascade|kinase|protein)\b)", re.IGNORECASE),
            re.compile(r"\bstrategic\s+(?:update|report|intelligence)\b", re.IGNORECASE),
            re.compile(r"\bwhat.s\s+happening\b", re.IGNORECASE),
            re.compile(r"\bintelligence\s+report\b", re.IGNORECASE),
        ],
        "directive": "[SKILL: Use the /signals workflow — run python3 $RECIPES/signals_report.py to generate a strategic intelligence report from compiled wiki data] ",
        "description": "strategic intelligence report from compiled wiki signals",
    },
    {
        "name": "insights",
        "triggers": [
            re.compile(r"\binsights?\s+(?:report|summary|accumulated|previous)\b", re.IGNORECASE),
            re.compile(r"\bprevious\s+(?:analysis|analyses|insights)\b", re.IGNORECASE),
            re.compile(r"\bwhat\s+have\s+we\s+learned\b", re.IGNORECASE),
            re.compile(r"\baccumulated\s+(?:intelligence|insights?|analysis)\b", re.IGNORECASE),
        ],
        "directive": "[SKILL: Run python3 $RECIPES/insights_report.py to show accumulated analysis insights from the wiki] ",
        "description": "accumulated analysis insights from previous landscape analyses",
    },
    {
        "name": "lint-wiki",
        "triggers": [
            re.compile(r"\blint\b", re.IGNORECASE),
            re.compile(r"\bhealth.check\b", re.IGNORECASE),
            re.compile(r"\bbroken.links?\b", re.IGNORECASE),
        ],
        "directive": "[SKILL: Run python3 $RECIPES/lint_wiki.py to health-check the wiki knowledge base] ",
        "description": "wiki health check: broken links, orphans, stale articles, missing refs, empty sections, index consistency, freshness gaps",
    },
    {
        "name": "wiki-manage",
        "triggers": [
            re.compile(r"\breset\s+(?:the\s+)?(?:wiki|knowledge\s+base|kb)\b", re.IGNORECASE),
            re.compile(r"\bremove\s+.+\s+from\s+(?:the\s+)?(?:wiki|kb|knowledge)\b", re.IGNORECASE),
            re.compile(r"\bprune\s+(?:the\s+)?wiki\b", re.IGNORECASE),
            re.compile(r"\bwiki\s+status\b", re.IGNORECASE),
            re.compile(r"\bclean\s+(?:up\s+)?(?:the\s+)?(?:wiki|kb|knowledge)\b", re.IGNORECASE),
        ],
        "directive": "[SKILL: Run python3 $RECIPES/wiki_manage.py with the appropriate command (reset, remove <slug>, prune, or status)] ",
        "description": "wiki management: reset, remove indication, prune orphans, status",
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
]


def detect_skill_name(question: str) -> str | None:
    """Return just the skill name for harness routing, or None if no skill matches."""
    if question.strip().startswith("/"):
        return None
    for skill in _SKILLS:
        for pattern in skill["triggers"]:
            if pattern.search(question):
                return skill["name"]
    return None


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
                directive = skill["directive"]
                # Skills with a pre-formatted directive (already contains [SKILL:) are returned as-is
                if directive.startswith("[SKILL:"):
                    return directive
                return f'[SKILL: Use the {directive} skill workflow for this question] '

    return None


# Patterns for extracting indication names from landscape questions.
_INDICATION_PATTERNS = [
    re.compile(r"\blandscape\s+for\s+(.+?)(?:\s*\?|$)", re.IGNORECASE),
    re.compile(r"\bcompetitive\s+(?:landscape|analysis|overview)\s+(?:for\s+|in\s+)?(.+?)(?:\s*\?|$)", re.IGNORECASE),
    re.compile(r"\bmarket\s+(?:overview|landscape|map)\s+(?:for\s+|in\s+)?(.+?)(?:\s*\?|$)", re.IGNORECASE),
    # Match "the <indication> landscape" — more specific than the greedy fallback below
    re.compile(r"\bthe\s+(.+?)\s+landscape\b", re.IGNORECASE),
    re.compile(r"^(.+?)\s+landscape\b", re.IGNORECASE),
]


def check_wiki_fast_path(question: str) -> Optional[str]:
    """Check if a landscape question can be answered from compiled wiki.

    Returns path to the fresh wiki article if one exists, or None.
    Extracts the indication name from the question and checks wiki freshness.
    """
    # Only applies to landscape-routed questions
    if not detect_skill(question):
        return None
    is_landscape = False
    for skill in _SKILLS:
        if skill["name"] == "landscape":
            for pattern in skill["triggers"]:
                if pattern.search(question):
                    is_landscape = True
                    break
            break
    if not is_landscape:
        return None

    # Try to extract an indication name via regex heuristics
    indication: Optional[str] = None
    for pat in _INDICATION_PATTERNS:
        m = pat.search(question)
        if m:
            indication = m.group(1).strip()
            break

    candidates = [indication] if indication else []

    # Also scan wiki/indications/ for known slugs that appear in the question
    indications_dir = os.path.join(os.getcwd(), "wiki", "indications")
    if os.path.isdir(indications_dir):
        for fname in os.listdir(indications_dir):
            if fname.endswith(".md"):
                slug = fname[:-3]
                if slug in question.lower().replace(" ", "-") or slug.replace("-", " ") in question.lower():
                    candidates.insert(0, slug)

    for candidate in candidates:
        if not candidate:
            continue
        slug = slugify(candidate)
        if check_freshness(slug) == "fresh":
            return article_path("indications", slug)

    return None
