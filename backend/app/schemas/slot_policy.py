"""Slot policy registry that determines slot classification types.

This file acts as a single source of truth for categorizing game slots as:
1. "numeric": Governed by strict rule-based parser logic (e.g., stay_duration).
2. "closed": Governed by strict enum candidate value validation (e.g., cash_amount).
3. "system": Produced or computed by the system, not directly from player text.
4. "open": Evaluated by agent-driven LLM semantic intent matching rather than
   strict enum matching.

By default, any slot not explicitly mapped to 'numeric', 'closed', or 'system' is
classified as 'open'.
"""

from typing import Literal

# The central registry of slot policy classifications
SLOT_POLICY: dict[str, Literal["open", "numeric", "closed", "system"]] = {
    "stay_duration": "numeric",
    "cash_amount": "closed",
    "final_recommendation": "system",
}

def get_slot_policy(slot_name: str) -> Literal["open", "numeric", "closed", "system"]:
    """Return the policy classification for a given slot name.
    
    If the slot is not explicitly registered in SLOT_POLICY, it defaults to 'open'.
    """
    return SLOT_POLICY.get(slot_name, "open")
