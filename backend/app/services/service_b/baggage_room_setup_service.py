from __future__ import annotations

import random

from backend.app.schemas.game_turn import (
    BaggageSetupRequest,
    BaggageSetupResponse,
    SetupPlayerProfile,
)
from backend.app.services.service_b.challenge_assignment_service import (
    pick_customs_item,
    to_random_customs_item_context,
)
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyController

TSL_RANK = {
    "TSL_1_SURVIVAL": 1,
    "TSL_2_FUNCTIONAL": 2,
    "TSL_3_INDEPENDENT": 3,
    "TSL_4_STRATEGIC": 4,
}

TIER_DEFAULT_TSL = {
    "Bronze": "TSL_1_SURVIVAL",
    "Silver": "TSL_2_FUNCTIONAL",
    "Gold": "TSL_3_INDEPENDENT",
}


class BaggageRoomSetupService:
    """Service to setup 2P baggage claim chapter and assign a bag owner."""

    def resolve_setup(self, request: BaggageSetupRequest) -> BaggageSetupResponse:
        p1 = request.player1_profile
        p2 = request.player2_profile
        room_id = request.room_id

        # Determine TSL for each player
        tsl1 = self._resolve_tsl(p1)
        tsl2 = self._resolve_tsl(p2)

        rank1 = TSL_RANK.get(tsl1, 2)
        rank2 = TSL_RANK.get(tsl2, 2)

        # 1. Compare TSL (lower TSL = owner)
        if rank1 < rank2:
            owner = p1
            owner_tsl = tsl1
        elif rank2 < rank1:
            owner = p2
            owner_tsl = tsl2
        else:
            # TSL is equal. Compare total_score.
            score1 = p1.total_score if p1.total_score is not None else 0
            score2 = p2.total_score if p2.total_score is not None else 0
            
            if score1 < score2:
                owner = p1
                owner_tsl = tsl1
            elif score2 < score1:
                owner = p2
                owner_tsl = tsl2
            else:
                # Both TSL and total_score are equal. Deterministic choice using room_id seed.
                rng = random.Random(room_id)
                # Sort player IDs to ensure ordering is consistent before random selection
                sorted_players = sorted([p1, p2], key=lambda x: x.player_id)
                owner = rng.choice(sorted_players)
                owner_tsl = tsl1 if owner.player_id == p1.player_id else tsl2

        # 2. Pick a customs item using owner's TSL and deterministic seed from room_id
        rng_item = random.Random(room_id)
        item = pick_customs_item(owner_tsl, rng=rng_item)
        random_customs_item_context = to_random_customs_item_context(item)

        return BaggageSetupResponse(
            room_id=room_id,
            bag_owner_player_id=owner.player_id,
            random_customs_item=random_customs_item_context,
        )

    def _resolve_tsl(self, p: SetupPlayerProfile) -> str:
        """Resolve TSL for a player based on TSL, total_score, or tier (with fallback)."""
        if p.travel_speaking_level is not None:
            return p.travel_speaking_level

        # Fallback to total_score
        if p.total_score is not None:
            return TierDifficultyController().travel_speaking_level_for_total(p.total_score)

        # Fallback to tier
        if p.tier in TIER_DEFAULT_TSL:
            return TIER_DEFAULT_TSL[p.tier]

        # Default fallback
        return "TSL_2_FUNCTIONAL"
