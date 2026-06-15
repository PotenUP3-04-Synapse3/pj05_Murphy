"""Developer C adapter for calling Developer B policy logic.

Beginner guide:
Developer B owns level, hint, score, and branch policy.  Developer C calls B
through this adapter so the orchestrator can stay stable even if B changes its
internal implementation.  The adapter also attaches the final Alpha scoreboard
result when the current node is the approved final-result trigger.
"""

from pathlib import Path
from typing import Any

from backend.app.agents.agent_b import EnglishLevelHintAgent
from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput, FinalResult, FinalScoreState
from backend.app.services.service_b.final_result_score_policy import (
    FinalResultScorePolicy,
    OpenKBFinalResultRecordReader,
)
from backend.app.services.service_b.focus_on_form_report_policy import FocusOnFormReportPolicy

ALPHA_FINAL_SCOREBOARD_NODE_ID = "ALPHA_999_FINAL_SCOREBOARD"


class DevBPolicyClient:
    def __init__(
        self,
        agent: EnglishLevelHintAgent | None = None,
        *,
        agent_run_root: Path | None = None,
        final_result_policy: FinalResultScorePolicy | None = None,
        final_record_reader: OpenKBFinalResultRecordReader | None = None,
        focus_on_form_report_policy: FocusOnFormReportPolicy | None = None,
    ) -> None:
        self.agent = agent or EnglishLevelHintAgent(agent_run_root=agent_run_root)
        self.final_result_policy = final_result_policy or FinalResultScorePolicy()
        self.final_record_reader = final_record_reader or OpenKBFinalResultRecordReader()
        self.focus_on_form_report_policy = focus_on_form_report_policy or FocusOnFormReportPolicy()

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        output = self.agent.evaluate_turn(payload)
        if output.branch.branch_type != "final" or payload.current_node_id != ALPHA_FINAL_SCOREBOARD_NODE_ID:
            return output

        final_result = self.final_result_policy.build_result(
            self.final_record_reader.read_session_records(payload.session_id),
            final_state=FinalScoreState(
                patience=payload.scenario_state.patience + output.state_delta.patience_delta,
                suspicion=payload.scenario_state.suspicion + output.state_delta.suspicion_delta,
                retry_count=payload.scenario_state.retry_count + output.state_delta.retry_count_delta,
                hint_count=payload.scenario_state.hint_count + output.state_delta.hint_count_delta,
            ),
        )
        return output.model_copy(update={"final_result": final_result})

    def final_result_for_session(self, session_id: str) -> FinalResult:
        return self.final_result_policy.build_result(
            self.final_record_reader.read_session_records(session_id),
        )

    def out_game_feedback_for_session(self, session_id: str) -> dict[str, Any]:
        """Build the B-owned out-game learning card report for a session.

        Beginner guide:
        Developer B owns the Focus-on-Form report content.  Developer C only
        asks B's policy object for the already-shaped report and then exposes it
        on the final result endpoint as learning metadata.  This method must not
        change branch, score, verdict, next-node, or state-delta authority.
        """

        return self.focus_on_form_report_policy.build_session_report(session_id)
