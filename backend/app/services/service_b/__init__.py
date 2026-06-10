"""Developer B owned state machine and level adaptation services."""

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
