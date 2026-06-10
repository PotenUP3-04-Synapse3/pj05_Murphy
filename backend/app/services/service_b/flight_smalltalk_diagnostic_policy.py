from __future__ import annotations

from dataclasses import dataclass


SCENE_ID = "FLIGHT_001_SEATMATE_SMALLTALK"
MINIMUM_PLAYER_TURNS = 3
SKIP_ELIGIBLE_PLAYER_TURNS = 5
FALLBACK_QUESTIONS = [
    "Is this your first time flying to New York?",
    "What are you most excited to do after you land?",
    "Are you traveling alone or with someone?",
    "How long will you stay in the United States?",
    "Do you usually like window seats or aisle seats?",
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
