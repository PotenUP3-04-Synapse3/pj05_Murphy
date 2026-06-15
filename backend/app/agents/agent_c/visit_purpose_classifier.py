"""Classify simple visit-purpose answers without calling an LLM.

Beginner guide:
The Understanding Agent sometimes needs a deterministic fallback.  This file
maps common English words such as "tourism", "business", or "uncle" to the
slot values Developer B expects.  It is deliberately small and rule-based so
tests can pass without API keys.
"""

from __future__ import annotations

VISIT_PURPOSE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "family_visit": ("uncle", "aunt", "cousin", "parents", "family", "relative"),
    "friend_visit": ("friend",),
    "business": ("business", "meeting", "conference"),
    "study": ("study", "school"),
    "transit": ("transit", "layover"),
    "tourism": ("tourism", "travel", "vacation", "sightseeing"),
}

VISIT_PURPOSE_VALUES = tuple(VISIT_PURPOSE_KEYWORDS)


def classify_visit_purpose(
    player_text: str,
    allowed_values: list[str] | None = None,
) -> str | None:
    normalized = player_text.lower()
    allowed = set(allowed_values or VISIT_PURPOSE_VALUES)
    for purpose, keywords in VISIT_PURPOSE_KEYWORDS.items():
        if purpose not in allowed:
            continue
        if any(keyword in normalized for keyword in keywords):
            return purpose
    return None
