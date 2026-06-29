"""Unit tests for Eokkka location and customs item challenge assignment.

This test suite verifies that the challenge assignment service maps player
TSLs to appropriate difficulty pools, handles pool gaps gracefully with adjacent
fallbacks, responds deterministically to seeded random number generators, and
correctly converts entry models to Pydantic context schemas.
"""

from __future__ import annotations

import random

from backend.app.data.challenge_tables import (
    CUSTOMS_ITEMS,
    LOCATIONS,
    CustomsItemEntry,
    LocationEntry,
)
from backend.app.services.service_b.challenge_assignment_service import (
    TSL_TO_DIFFICULTY_RANGE,
    pick_customs_item,
    pick_location,
    to_random_customs_item_context,
)
from backend.app.schemas.game_turn import RandomCustomsItemContext


def test_pick_location_respects_tsl_range() -> None:
    """Verify that picking locations for each TSL maps to appropriate difficulties.

    The LOCATIONS table now covers every difficulty 1-12 with two entries each,
    so each TSL must always pick a location strictly within its range.
    """
    for tsl, (min_diff, max_diff) in TSL_TO_DIFFICULTY_RANGE.items():
        # Run multiple times to cover random choices
        for _ in range(30):
            loc = pick_location(tsl)
            assert isinstance(loc, LocationEntry)
            assert min_diff <= loc.difficulty <= max_diff
            assert isinstance(loc.location_id, str)
            assert loc.location_id.startswith("LOC_")


def test_pick_customs_item_respects_tsl_range() -> None:
    """Verify that picking customs items for each TSL maps strictly to their ranges."""
    for tsl, (min_diff, max_diff) in TSL_TO_DIFFICULTY_RANGE.items():
        for _ in range(30):
            item = pick_customs_item(tsl)
            assert isinstance(item, CustomsItemEntry)
            assert min_diff <= item.difficulty <= max_diff


def test_higher_level_gets_harder_challenge() -> None:
    """Ensure that strategic (TSL_4) challenges are more difficult than survival (TSL_1) ones."""
    for _ in range(30):
        loc_survival = pick_location("TSL_1_SURVIVAL")
        loc_strategic = pick_location("TSL_4_STRATEGIC")
        assert loc_survival.difficulty < loc_strategic.difficulty

        item_survival = pick_customs_item("TSL_1_SURVIVAL")
        item_strategic = pick_customs_item("TSL_4_STRATEGIC")
        assert item_survival.difficulty < item_strategic.difficulty


def test_pick_is_deterministic_with_seeded_rng() -> None:
    """Verify that injecting a seeded random generator produces identical results."""
    rng1 = random.Random(42)
    rng2 = random.Random(42)

    for _ in range(20):
        loc1 = pick_location("TSL_2_FUNCTIONAL", rng=rng1)
        loc2 = pick_location("TSL_2_FUNCTIONAL", rng=rng2)
        assert loc1.location_id == loc2.location_id

        item1 = pick_customs_item("TSL_2_FUNCTIONAL", rng=rng1)
        item2 = pick_customs_item("TSL_2_FUNCTIONAL", rng=rng2)
        assert item1.item_id == item2.item_id


def test_empty_pool_falls_back_to_adjacent() -> None:
    """Explicitly verify the distance-based fallback behavior.

    If a custom locations list is temporarily set to have a gap, the picker
    must choose the entry with the minimum distance to the target range.
    """
    # Create custom location list with a gap and run pick logic
    # Mocking LOCATIONS temporarily for this unit test
    fake_locations = [
        LocationEntry("LOC_EASY", "Easy Place", "쉬운 곳", 1, "Easy"),
        LocationEntry("LOC_HARD", "Hard Place", "어려운 곳", 10, "Hard"),
    ]

    import backend.app.services.service_b.challenge_assignment_service as cas
    original_locations = cas.LOCATIONS
    try:
        cas.LOCATIONS = fake_locations
        # TSL_2_FUNCTIONAL is range 4-6. Neither LOC_EASY (diff 1) nor LOC_HARD (diff 10) matches.
        # Distance from 4-6 to 1 is 3 (4 - 1 = 3).
        # Distance from 4-6 to 10 is 4 (10 - 6 = 4).
        # Thus, LOC_EASY is closer (distance 3 vs 4) and should be picked.
        picked = pick_location("TSL_2_FUNCTIONAL")
        assert picked.location_id == "LOC_EASY"
    finally:
        cas.LOCATIONS = original_locations


def test_table_covers_all_tiers() -> None:
    """Ensure that the static LOCATIONS and CUSTOMS_ITEMS tables cover all TSL levels."""
    for tsl in TSL_TO_DIFFICULTY_RANGE:
        locs_pool = [loc for loc in LOCATIONS if TSL_TO_DIFFICULTY_RANGE[tsl][0] <= loc.difficulty <= TSL_TO_DIFFICULTY_RANGE[tsl][1]]
        items_pool = [item for item in CUSTOMS_ITEMS if TSL_TO_DIFFICULTY_RANGE[tsl][0] <= item.difficulty <= TSL_TO_DIFFICULTY_RANGE[tsl][1]]

        # Each TSL spans 3 difficulties with two entries each = 6 per tier.
        assert len(locs_pool) == 6
        assert len(items_pool) == 6


def test_to_context_helper_maps_fields() -> None:
    """Verify that to_random_customs_item_context maps all entry attributes properly."""
    entry = CustomsItemEntry(
        item_id="ITEM_TEST",
        name_en="Test Item",
        name_ko="테스트 아이템",
        item_category="electronics",
        difficulty=5,
        suspicion_reason="This looks like a test payload.",
    )
    context = to_random_customs_item_context(entry)
    assert isinstance(context, RandomCustomsItemContext)
    assert context.item_id == "ITEM_TEST"
    assert context.item_name == "Test Item"
    assert context.item_category == "electronics"
    assert context.item_description == "This looks like a test payload."
    assert context.difficulty == 5
    assert context.suspicion_reason == "This looks like a test payload."
    assert context.declared is False
    assert context.source == "rule"
