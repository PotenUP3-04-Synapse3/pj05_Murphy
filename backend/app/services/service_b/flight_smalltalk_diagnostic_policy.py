from __future__ import annotations

from dataclasses import dataclass


SCENE_ID = "FLIGHT_001_SEATMATE_SMALLTALK"
MINIMUM_PLAYER_TURNS = 5
SKIP_ELIGIBLE_PLAYER_TURNS = 5
FALLBACK_QUESTIONS = [
    "Could I borrow your pen for this form?",
    "Are you visiting New York for a trip?",
    "How long will you stay there?",
    "Sorry, did you say this is your first time in America?",
    "Looks like we're landing soon. Are you ready for immigration?",
]


@dataclass(frozen=True)
class FlightSmallTalkDiagnosticDecision:
    scene_id: str
    diagnostic_only: bool
    minimum_turns_met: bool
    required_more_turns: int
    skip_eligible: bool
    should_emit_out_game_feedback_seed: bool
    should_show_out_game_feedback_now: bool


class FlightSmallTalkDiagnosticPolicy:
    def evaluate(self, *, player_turn_count: int) -> FlightSmallTalkDiagnosticDecision:
        safe_turn_count = max(0, player_turn_count)
        required_more_turns = max(0, MINIMUM_PLAYER_TURNS - safe_turn_count)
        return FlightSmallTalkDiagnosticDecision(
            scene_id=SCENE_ID,
            diagnostic_only=True,
            minimum_turns_met=required_more_turns == 0,
            required_more_turns=required_more_turns,
            skip_eligible=safe_turn_count >= SKIP_ELIGIBLE_PLAYER_TURNS,
            should_emit_out_game_feedback_seed=True,
            should_show_out_game_feedback_now=False,
        )

    def fallback_question(self, player_turn_count: int) -> str:
        safe_turn_count = max(0, player_turn_count)
        index = min(safe_turn_count, len(FALLBACK_QUESTIONS) - 1)
        return FALLBACK_QUESTIONS[index]
