from __future__ import annotations

from dataclasses import dataclass


SCENE_ID = "FLIGHT_A_001_SEATMATE_SMALLTALK"
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
    """
    비행기 내 스몰토크 단계에서 내려진 진단 평가 결과 데이터 클래스입니다.
    
    초보자 가이드: 이 클래스는 비행기 안에서의 가벼운 대화(스몰토크)를 분석하여 
    진단 모드 여부, 최소 턴 완료 여부, 추가로 필요한 대화 턴 수 등의 진단 메타데이터를 보관합니다.
    """
    scene_id: str
    diagnostic_only: bool
    minimum_turns_met: bool
    required_more_turns: int
    skip_eligible: bool
    should_emit_out_game_feedback_seed: bool
    should_show_out_game_feedback_now: bool


class FlightSmallTalkDiagnosticPolicy:
    """
    비행기 안에서 진행되는 영어 회화 진단(스몰토크)의 진행 및 스킵 조건을 결정하는 정책 클래스입니다.
    
    초보자 가이드: 플레이어가 비행기 시나리오에서 최소 대화 횟수(5번)를 채웠는지 판단하여, 
    다음 단계(입국 심사)로 스킵해도 되는지, 혹은 추가적인 영어 질문(폴백 질문)을 던져야 하는지 결정합니다.
    """
    def evaluate(self, *, player_turn_count: int) -> FlightSmallTalkDiagnosticDecision:
        """
        플레이어가 진행한 대화 횟수를 바탕으로 스몰토크 진단 결과를 평가합니다.
        
        Args:
            player_turn_count: 플레이어가 발화한 대화 턴 수
            
        Returns:
            진단 정보와 진행 지속 여부가 포함된 FlightSmallTalkDiagnosticDecision 객체
        """
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
        """
        진단 대화가 더 필요하지만 LLM 대사 생성이 지연되거나 불가능할 때 사용할 대체(Fallback) 영어 질문을 반환합니다.
        
        Args:
            player_turn_count: 현재까지 대화 턴 수
            
        Returns:
            옆자리 승객이 던질 수 있는 일상 대화용 영어 질문 텍스트
        """
        safe_turn_count = max(0, player_turn_count)
        index = min(safe_turn_count, len(FALLBACK_QUESTIONS) - 1)
        return FALLBACK_QUESTIONS[index]
