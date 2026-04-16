"""
Detect if a question requires conversation context (--continue) or can start fresh.

Fresh: "/pipeline Pfizer", "show me obesity landscape", "what drugs does Novo have?"
Continue: "what about their deals?", "show me more", "expand on that", "same for Merck"
"""

import re

# ---------------------------------------------------------------------------
# Multi-entity parallel dispatch detection
# ---------------------------------------------------------------------------

_LIST_SEP = re.compile(r'\s*,\s*(?:and\s+)?|\s+and\s+')

_SKILL_KEYWORDS: dict[str, str] = {
    'landscape': 'landscape',
    'landscapes': 'landscape',
    'pipeline': 'pipeline',
    'pipelines': 'pipeline',
    'profile': 'drug-profile',
    'profiles': 'drug-profile',
}

_SKIP_WORDS = {'landscape', 'landscapes', 'pipeline', 'pipelines', 'profile',
               'profiles', 'compare', 'and', 'for', 'the', 'a', 'an'}

_STRIP_PREFIX = re.compile(
    r'^(?:landscape[s]?\s+for\s+|pipeline[s]?\s+for\s+|profile[s]?\s+for\s+|compare\s+)',
    re.IGNORECASE
)
_STRIP_SUFFIX = re.compile(
    r'\s+(?:landscape[s]?|pipeline[s]?|profile[s]?)$',
    re.IGNORECASE
)


def _clean_entity(e: str) -> str:
    e = _STRIP_PREFIX.sub('', e.strip())
    e = _STRIP_SUFFIX.sub('', e.strip())
    return e.strip()


def detect_multi_entity(question: str) -> dict | None:
    """Detect queries asking about 2+ entities that can be dispatched in parallel.

    Returns {'entities': [...], 'skill': '...'} when a comma-separated list of
    2+ named entities is found alongside a skill keyword, else None.

    Conservative — only fires when both a skill keyword AND a comma list are present.
    """
    q = question.strip()

    # Skip single explicit /skill invocations with one argument
    if q.startswith('/') and q.count(' ') <= 1:
        return None

    # Require a skill keyword
    skill = None
    for kw, sk in _SKILL_KEYWORDS.items():
        if re.search(rf'\b{kw}\b', q, re.IGNORECASE):
            skill = sk
            break
    if skill is None:
        return None

    # Require at least one comma (list signal)
    if ',' not in q:
        return None

    # Extract the first run of comma-separated named tokens
    list_match = re.search(
        r'(?:for\s+)?([A-Za-z][^,]+(?:,\s*(?:and\s+)?[A-Za-z][^,]+)+)', q
    )
    if not list_match:
        return None

    entities = [_clean_entity(e) for e in _LIST_SEP.split(list_match.group(1))]
    entities = [e for e in entities if e.lower() not in _SKIP_WORDS and len(e) > 2]

    if len(entities) < 2:
        return None

    return {'entities': entities, 'skill': skill}

# Patterns that indicate a follow-up needing previous context
_FOLLOWUP_PATTERNS = [
    # Pronouns referencing previous data
    re.compile(r"\b(their|its|them|those|these|that|the same)\b", re.IGNORECASE),
    # Follow-up phrases
    re.compile(r"^(what about|how about|and the|and their|also show|show me more|tell me more|more details?|expand|elaborate|go deeper|drill down)", re.IGNORECASE),
    # Backward references
    re.compile(r"\b(above|previous|last|earlier|same company|same drug|same indication|this company|this drug)\b", re.IGNORECASE),
    # Comparative/continuation
    re.compile(r"^(compare|versus|vs\.?|now show|now do|repeat|again)\b", re.IGNORECASE),
    # Very short follow-ups
    re.compile(r"^(why|how|when|really|details|deals|trials|patents)\??\s*$", re.IGNORECASE),
    # Cross-skill drill-down: user wants to go deeper on a drug/company from previous landscape
    re.compile(r"\b(drill\s+into|deep\s+dive\s+on|profile|details?\s+on)\b.{1,50}\b[A-Z][a-z]", re.IGNORECASE),
]

# Patterns that indicate a NEW topic (fresh start is fine)
_NEW_TOPIC_PATTERNS = [
    # Explicit skill invocation
    re.compile(r"^/\w+\s+\S+", re.IGNORECASE),
    # Named entity + question word
    re.compile(r"\b(pipeline|landscape|profile|drug-profile)\b.*\b[A-Z][a-z]+", re.IGNORECASE),
    re.compile(r"\b[A-Z][a-z]+.*\b(pipeline|landscape|profile)\b", re.IGNORECASE),
    # Direct questions with a named entity
    re.compile(r"\b(what|show|list|find|search|get)\b.{5,}", re.IGNORECASE),
]


def needs_context(question: str, turn_number: int) -> bool:
    """Return True if the question likely needs previous conversation context.

    Args:
        question: The user's question
        turn_number: Which turn this is (1 = first, 2+ = subsequent)

    Returns:
        True if --continue should be used
    """
    # First turn never needs context
    if turn_number <= 1:
        return False

    q = question.strip()

    # Explicit /skill invocations always start fresh
    if q.startswith("/"):
        return False

    # Very short queries (< 5 words, no proper nouns) are likely follow-ups
    words = q.split()
    if len(words) <= 3 and not any(w[0].isupper() and len(w) > 1 for w in words if w):
        return True

    # Check follow-up patterns
    for pattern in _FOLLOWUP_PATTERNS:
        if pattern.search(q):
            return True

    # If it matches a new topic pattern, start fresh
    for pattern in _NEW_TOPIC_PATTERNS:
        if pattern.search(q):
            return False

    # Default for turn 2+: use context (safer, avoids losing relevant state)
    return True
