"""Service for picking Eokkka locations and customs items based on TSL.

This module provides the logic to dynamically assign a travel location or a
customs item based on the player's Travel Speaking Level (TSL) and associated
difficulty ranges. It contains robust fallback logic for empty ranges.
"""

from __future__ import annotations

import random

from backend.app.data.challenge_tables import (
    CUSTOMS_ITEMS,
    LOCATIONS,
    CustomsItemEntry,
    LocationEntry,
)
from backend.app.schemas.game_turn import RandomCustomsItemContext

# Mapping TSL level to target difficulty ranges (1-12)
TSL_TO_DIFFICULTY_RANGE: dict[str, tuple[int, int]] = {
    "TSL_1_SURVIVAL": (1, 3),
    "TSL_2_FUNCTIONAL": (4, 6),
    "TSL_3_INDEPENDENT": (7, 9),
    "TSL_4_STRATEGIC": (10, 12),
}


def pick_location(tsl: str, *, rng: random.Random | None = None) -> LocationEntry:
    """Select a random location from the difficulty pool corresponding to the TSL.

    If the difficulty range has no locations (e.g. difficulty 3), it falls back
    to the closest available difficulties.
    """
    if rng is None:
        rng = random.Random()

    target_range = TSL_TO_DIFFICULTY_RANGE.get(tsl, (1, 12))
    min_diff, max_diff = target_range

    # Find candidates matching the range
    candidates = [loc for loc in LOCATIONS if min_diff <= loc.difficulty <= max_diff]

    # Fallback logic if pool is empty: find entries with minimum distance to range
    if not candidates:
        min_dist = float("inf")
        for loc in LOCATIONS:
            dist = 0
            if loc.difficulty < min_diff:
                dist = min_diff - loc.difficulty
            elif loc.difficulty > max_diff:
                dist = loc.difficulty - max_diff
            if dist < min_dist:
                min_dist = dist
                candidates = [loc]
            elif dist == min_dist:
                candidates.append(loc)

    return rng.choice(candidates)


def pick_customs_item(tsl: str, *, rng: random.Random | None = None) -> CustomsItemEntry:
    """Select a random customs item from the difficulty pool corresponding to the TSL.

    If the difficulty range has no items, it falls back to the closest available
    difficulties.
    """
    if rng is None:
        rng = random.Random()

    target_range = TSL_TO_DIFFICULTY_RANGE.get(tsl, (1, 12))
    min_diff, max_diff = target_range

    # Find candidates matching the range
    candidates = [item for item in CUSTOMS_ITEMS if min_diff <= item.difficulty <= max_diff]

    # Fallback logic if pool is empty
    if not candidates:
        min_dist = float("inf")
        for item in CUSTOMS_ITEMS:
            dist = 0
            if item.difficulty < min_diff:
                dist = min_diff - item.difficulty
            elif item.difficulty > max_diff:
                dist = item.difficulty - max_diff
            if dist < min_dist:
                min_dist = dist
                candidates = [item]
            elif dist == min_dist:
                candidates.append(item)

    return rng.choice(candidates)


def to_random_customs_item_context(entry: CustomsItemEntry) -> RandomCustomsItemContext:
    """Map a CustomsItemEntry to a RandomCustomsItemContext Pydantic schema."""
    return RandomCustomsItemContext(
        item_id=entry.item_id,
        item_name=entry.name_en,
        item_category=entry.item_category,
        item_description=entry.suspicion_reason,
        visit_location=None,
        declared=False,
        source="rule",
        difficulty=entry.difficulty,
        suspicion_reason=entry.suspicion_reason,
    )
