"""
Detect if a question requires conversation context (--continue) or can start fresh.

Fresh: "/pipeline Pfizer", "show me obesity landscape", "what drugs does Novo have?"
Continue: "what about their deals?", "show me more", "expand on that", "same for Merck"
"""

import re

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
