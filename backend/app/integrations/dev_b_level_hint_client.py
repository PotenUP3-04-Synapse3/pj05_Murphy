from pathlib import Path

from backend.app.agents.agent_b import EnglishLevelHintAgent
from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput, FinalResult, FinalScoreState
from backend.app.services.service_b.final_result_score_policy import (
    FinalResultScorePolicy,
    OpenKBFinalResultRecordReader,
)


class DevBPolicyClient:
    def __init__(
        self,
        agent: EnglishLevelHintAgent | None = None,
        *,
        agent_run_root: Path | None = None,
        final_result_policy: FinalResultScorePolicy | None = None,
        final_record_reader: OpenKBFinalResultRecordReader | None = None,
    ) -> None:
        self.agent = agent or EnglishLevelHintAgent(agent_run_root=agent_run_root)
        self.final_result_policy = final_result_policy or FinalResultScorePolicy()
        self.final_record_reader = final_record_reader or OpenKBFinalResultRecordReader()

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        output = self.agent.evaluate_turn(payload)
        if output.branch.branch_type != "final":
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
