"""
Developer B가 소유한 상태 머신 및 레벨 적응(Level Adaptation) 관련 핵심 서비스 패키지입니다.

초보자 가이드: 이 패키지는 시나리오의 진행 방향을 판단하는 상태 머신(ScenarioStateMachine), 
영어 피드백을 동적으로 생성하는 생성기(FeedbackHintGenerator), 
그리고 사용자의 발화 난이도 및 평가를 수행하는 다양한 비즈니스 로직 서비스를 제공합니다.
의존성 복잡도를 피하기 위해 지연 임포트(Lazy Import) 방식을 채택하고 있습니다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.app.services.service_b.developer_b_agent_run_logger import DeveloperBAgentRunLogger
    from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGenerator
    from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import FlightSmallTalkDiagnosticPolicy
    from backend.app.services.service_b.focus_on_form_report_policy import FocusOnFormReportPolicy
    from backend.app.services.service_b.level_adaptation_controller import LevelAdaptationController
    from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter
    from backend.app.services.service_b.scenario_state_machine import ScenarioStateMachine
    from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyController


__all__ = [
    "DeveloperBAgentRunLogger",
    "FeedbackHintGenerator",
    "FlightSmallTalkDiagnosticPolicy",
    "FocusOnFormReportPolicy",
    "LevelAdaptationController",
    "OpenKBFeedbackWriter",
    "ScenarioStateMachine",
    "TierDifficultyController",
]


def __getattr__(name: str) -> Any:
    if name == "DeveloperBAgentRunLogger":
        from backend.app.services.service_b.developer_b_agent_run_logger import DeveloperBAgentRunLogger

        return DeveloperBAgentRunLogger
    if name == "FeedbackHintGenerator":
        from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGenerator

        return FeedbackHintGenerator
    if name == "FlightSmallTalkDiagnosticPolicy":
        from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import FlightSmallTalkDiagnosticPolicy

        return FlightSmallTalkDiagnosticPolicy
    if name == "FocusOnFormReportPolicy":
        from backend.app.services.service_b.focus_on_form_report_policy import FocusOnFormReportPolicy

        return FocusOnFormReportPolicy
    if name == "LevelAdaptationController":
        from backend.app.services.service_b.level_adaptation_controller import LevelAdaptationController

        return LevelAdaptationController
    if name == "OpenKBFeedbackWriter":
        from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter

        return OpenKBFeedbackWriter
    if name == "ScenarioStateMachine":
        from backend.app.services.service_b.scenario_state_machine import ScenarioStateMachine

        return ScenarioStateMachine
    if name == "TierDifficultyController":
        from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyController

        return TierDifficultyController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
