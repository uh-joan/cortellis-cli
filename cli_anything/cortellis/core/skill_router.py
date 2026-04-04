"""
Detect which skill workflow should handle a user question.

Returns a directive string to prepend to the question, or None if no skill applies.
High-precision patterns only — avoids false positives on simple factual queries.
"""

import re

# Each skill has trigger patterns and an extraction function for the subject.
# Patterns are tested in order; first match wins.
# ORDERING RULE: specific skills MUST come before general ones to avoid false matches.
# e.g. clinical-landscape before landscape, head-to-head before drug-comparison.

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
    # --- specific landscape variants before generic landscape ---
    {
        "name": "clinical-landscape",
        "triggers": [
            re.compile(r"\bclinical\s*(?:trial)?\s*landscape\b", re.IGNORECASE),
            re.compile(r"\btrial\s+landscape\b", re.IGNORECASE),
            re.compile(r"\ball\s+(?:clinical\s+)?trials\s+(?:in|for)\b", re.IGNORECASE),
            re.compile(r"\btrial\s+(?:overview|distribution|analysis)\b.{0,20}\b(?:indication|disease)", re.IGNORECASE),
        ],
        "directive": "/clinical-landscape",
        "description": "clinical trial landscape for an indication (phases, sponsors, enrollment)",
    },
    {
        "name": "combination-landscape",
        "triggers": [
            re.compile(r"\bcombination\s*(?:landscape|therapy|therapies|analysis)\b", re.IGNORECASE),
            re.compile(r"\bcombo\s+(?:therapy|landscape|drugs)\b", re.IGNORECASE),
            re.compile(r"\bwhat.{0,15}combined\s+with\b", re.IGNORECASE),
        ],
        "directive": "/combination-landscape",
        "description": "combination therapy landscape for an indication",
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
    # --- indication-deep-dive before drug-profile (both match "deep dive") ---
    {
        "name": "indication-deep-dive",
        "triggers": [
            re.compile(r"\bindication\s*(?:deep\s*dive|analysis|dossier|overview)\b", re.IGNORECASE),
            re.compile(r"\bdisease\s*(?:deep\s*dive|analysis|overview)\b", re.IGNORECASE),
            re.compile(r"\beverything\s+(?:about|on)\s+(?:a\s+)?(?:disease|indication)\b", re.IGNORECASE),
            re.compile(r"\bcomplete\s+(?:indication|disease)\s+analysis\b", re.IGNORECASE),
        ],
        "directive": "/indication-deep-dive",
        "description": "complete indication analysis (drugs, trials, deals, regulatory, literature)",
    },
    {
        "name": "drug-profile",
        "triggers": [
            re.compile(r"\bdrug\s*profile\b", re.IGNORECASE),
            re.compile(r"\bdrug\s+dossier\b", re.IGNORECASE),
            re.compile(r"\bfull\s+(?:report|analysis)\b.{0,20}\bdrug\b", re.IGNORECASE),
            # "deep dive" only when NOT preceded/followed by deal/company/pipeline/landscape keywords
            re.compile(r"(?<!\bdeal\s)\bdeep\s*dive\b(?!.{0,15}\b(?:deal|company|pipeline|landscape|partner|competitor))", re.IGNORECASE),
        ],
        "directive": "/drug-profile",
        "description": "deep drug profile with SWOT, financials, competitive context",
    },
    # --- head-to-head before drug-comparison (both match "head to head") ---
    {
        "name": "head-to-head",
        "triggers": [
            re.compile(r"(?=.*\bhead[\s-]*to[\s-]*head\b)(?=.*\bcompan)", re.IGNORECASE),
            re.compile(r"\bcompany\s*(?:vs\.?|versus)\b", re.IGNORECASE),
            re.compile(r"\bcompar(?:e|ison)\b.{0,20}\bcompan", re.IGNORECASE),
            re.compile(r"\bcompan.{0,20}\bcompar(?:e|ison)\b", re.IGNORECASE),
        ],
        "directive": "/head-to-head",
        "description": "company vs company comparison (pipeline, deals, KPIs, overlap)",
    },
    {
        "name": "drug-comparison",
        "triggers": [
            re.compile(r"\bcompar(?:e|ison)\b.{0,30}\bdrug", re.IGNORECASE),
            re.compile(r"\bdrug.{0,30}\bcompar(?:e|ison)\b", re.IGNORECASE),
            re.compile(r"\bhead[\s-]*to[\s-]*head\b", re.IGNORECASE),
            re.compile(r"\bvs\.?\b.{0,20}\b(?:drug|tirzepatide|semaglutide|ozempic|wegovy)", re.IGNORECASE),
            re.compile(r"\bside\s*by\s*side\b", re.IGNORECASE),
        ],
        "directive": "/drug-comparison",
        "description": "side-by-side drug comparison (phase, mechanism, trials, financials)",
    },
    {
        "name": "company-peers",
        "triggers": [
            re.compile(r"\bpeer\s*(?:benchmark|comparison|analysis|finder)\b", re.IGNORECASE),
            re.compile(r"\bcompetitor\s*benchmark\b", re.IGNORECASE),
            re.compile(r"\bwho\s+competes\s+with\b", re.IGNORECASE),
            re.compile(r"\bsimilar\s+compan(?:y|ies)\b", re.IGNORECASE),
            re.compile(r"\bcompany\s+peers?\b", re.IGNORECASE),
        ],
        "directive": "/company-peers",
        "description": "company peer benchmarking with KPIs and indication overlap",
    },
    {
        "name": "deal-deep-dive",
        "triggers": [
            re.compile(r"\bdeal\s*(?:deep\s*dive|analysis|dossier|profile)\b", re.IGNORECASE),
            re.compile(r"\bexpanded\s+deal\b", re.IGNORECASE),
            re.compile(r"\bdeal\s+(?:terms|financials|structure)\b", re.IGNORECASE),
            re.compile(r"\banalyze\s+(?:the\s+)?deal\b", re.IGNORECASE),
        ],
        "directive": "/deal-deep-dive",
        "description": "expanded deal analysis with financials, territories, and comparables",
    },
    {
        "name": "regulatory-pathway",
        "triggers": [
            re.compile(r"\bregulatory\s*(?:pathway|intelligence|analysis|status|history)\b", re.IGNORECASE),
            re.compile(r"\bapproval\s*(?:timeline|history|status|pathway)\b", re.IGNORECASE),
            re.compile(r"\bNDA\s+(?:status|history|approval)\b", re.IGNORECASE),
            re.compile(r"\bregulatory\s+documents?\b", re.IGNORECASE),
        ],
        "directive": "/regulatory-pathway",
        "description": "regulatory intelligence report with approval timeline and citation graph",
    },
    {
        "name": "sales-forecast",
        "triggers": [
            re.compile(r"\bsales\s*(?:forecast|data|actual|revenue)\b", re.IGNORECASE),
            re.compile(r"\bforecast\s+(?:data|sales|revenue)\b", re.IGNORECASE),
            re.compile(r"\bcommercial\s+(?:data|performance|sales)\b", re.IGNORECASE),
            re.compile(r"\bhow\s+much\s+(?:does|did|is)\b.{0,20}\b(?:sell|revenue|sales)\b", re.IGNORECASE),
        ],
        "directive": "/sales-forecast",
        "description": "drug sales actuals and forecast with competitive context",
    },
    {
        "name": "pharmacology-dossier",
        "triggers": [
            re.compile(r"\bpharmacolog(?:y|ical)\s*(?:dossier|data|profile|report)\b", re.IGNORECASE),
            re.compile(r"\bpharmacokinetic\b", re.IGNORECASE),
            re.compile(r"\bpreclinical\s+(?:data|profile|dossier)\b", re.IGNORECASE),
            re.compile(r"\bdrug\s+design\s+(?:data|profile|dossier)\b", re.IGNORECASE),
        ],
        "directive": "/pharmacology-dossier",
        "description": "pharmacology and drug design dossier with PK/PD data",
    },
    {
        "name": "literature-review",
        "triggers": [
            re.compile(r"\bliterature\s*(?:review|search|analysis)\b", re.IGNORECASE),
            re.compile(r"\bpublication\s*(?:review|search|analysis|landscape)\b", re.IGNORECASE),
            re.compile(r"\bsystematic\s+(?:review|literature)\b", re.IGNORECASE),
            re.compile(r"\bwhat.{0,10}published\b.{0,20}\b(?:about|on|for)\b", re.IGNORECASE),
        ],
        "directive": "/literature-review",
        "description": "systematic literature review with publication analysis",
    },
    {
        "name": "partnership-network",
        "triggers": [
            re.compile(r"\bpartnership\s*(?:network|map|graph|analysis)\b", re.IGNORECASE),
            re.compile(r"\bwho\s+partners\s+with\b", re.IGNORECASE),
            re.compile(r"\bdeal\s+(?:network|partners|graph)\b", re.IGNORECASE),
            re.compile(r"\bpartner(?:s|ship)?\s+(?:overview|landscape)\b", re.IGNORECASE),
        ],
        "directive": "/partnership-network",
        "description": "partnership network analysis (deal graph for company or indication)",
    },
    {
        "name": "patent-watch",
        "triggers": [
            re.compile(r"\bpatent\s*(?:watch|expiry|cliff|timeline|landscape)\b", re.IGNORECASE),
            re.compile(r"\bpatent\s+expir(?:y|ation)\b", re.IGNORECASE),
            re.compile(r"\bgeneric\s+(?:threat|entry|competition)\b", re.IGNORECASE),
            re.compile(r"\bbiosimilar\s+(?:threat|competition|pipeline)\b", re.IGNORECASE),
        ],
        "directive": "/patent-watch",
        "description": "patent expiry timeline with generic/biosimilar threat assessment",
    },
    {
        "name": "disease-briefing",
        "triggers": [
            re.compile(r"\bdisease\s*briefing\b", re.IGNORECASE),
            re.compile(r"\bdisease\s+overview\s+briefing\b", re.IGNORECASE),
        ],
        "directive": "/disease-briefing",
        "description": "disease briefing from Drug Design (requires premium access)",
    },
    {
        "name": "mechanism-explorer",
        "triggers": [
            re.compile(r"\bmechanism\s*(?:explorer|analysis|overview|landscape)\b", re.IGNORECASE),
            re.compile(r"\ball\s+drugs\s+(?:for|with|targeting)\b.{0,20}\b(?:mechanism|target|action)\b", re.IGNORECASE),
            re.compile(r"\b(?:PD-1|PD-L1|EGFR|CDK4|GLP-1|JAK|BRAF|KRAS)\s+(?:inhibitor|agonist|antagonist)\s+(?:drugs|pipeline|landscape)\b", re.IGNORECASE),
        ],
        "directive": "/mechanism-explorer",
        "description": "mechanism of action explorer (all drugs, pharmacology, deals)",
    },
    {
        "name": "conference-intel",
        "triggers": [
            re.compile(r"\bconference\s*(?:intel|intelligence|overview|search)\b", re.IGNORECASE),
            re.compile(r"\b(?:ASCO|ESMO|AACR|ADA|EASD|ASH)\b.{0,20}\b(?:conference|meeting|congress|abstract)\b", re.IGNORECASE),
            re.compile(r"\bconference\s+(?:abstract|presentation|poster)\b", re.IGNORECASE),
        ],
        "directive": "/conference-intel",
        "description": "conference-based competitive intelligence",
    },
    {
        "name": "drug-swot",
        "triggers": [
            re.compile(r"\bswot\b", re.IGNORECASE),
            re.compile(r"\bstrategic\s+(?:analysis|assessment|position)\b.{0,20}\bdrug\b", re.IGNORECASE),
            re.compile(r"\bdrug\b.{0,20}\bstrategic\s+(?:analysis|assessment|position)\b", re.IGNORECASE),
            re.compile(r"\bstrengths?\s+(?:and\s+)?weakness", re.IGNORECASE),
        ],
        "directive": "/drug-swot",
        "description": "AI-generated strategic SWOT analysis from live data (8 domains)",
    },
    {
        "name": "target-profile",
        "triggers": [
            re.compile(r"\btarget\s*(?:profile|dossier|analysis|report)\b", re.IGNORECASE),
            re.compile(r"\bbiological\s+target\b.{0,20}\b(?:profile|analysis|report)\b", re.IGNORECASE),
            re.compile(r"\beverything\s+(?:about|on)\s+(?:a\s+)?target\b", re.IGNORECASE),
            re.compile(r"\btarget\s+(?:biology|validation|assessment)\b", re.IGNORECASE),
        ],
        "directive": "/target-profile",
        "description": "deep biological target profile (biology, drugs, pharmacology, interactions)",
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
