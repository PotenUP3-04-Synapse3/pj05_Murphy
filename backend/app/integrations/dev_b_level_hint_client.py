"""Developer C adapter for calling Developer B policy logic.

Beginner guide:
Developer B owns level, hint, score, and branch policy.  Developer C calls B
through this adapter so the orchestrator can stay stable even if B changes its
internal implementation.  The adapter also attaches the final result when any
terminal node is reached (normal clear or bad ending).
"""

import logging
from pathlib import Path
from typing import Any

from backend.app.agents.agent_b import EnglishLevelHintAgent
from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput, FinalResult, FinalScoreState
from backend.app.services.service_b.final_result_score_policy import (
    FinalResultScorePolicy,
    OpenKBFinalResultRecordReader,
)
from backend.app.services.service_b.focus_on_form_report_policy import FocusOnFormReportPolicy
from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter

logger = logging.getLogger(__name__)

# 모든 터미널 노드 — 정상 클리어 + 챕터별 BAD END + 중간 종료
TERMINAL_NODE_IDS: frozenset[str] = frozenset({
    "ALPHA_999_FINAL_SCOREBOARD",       # 정상 클리어
    "FLIGHT_BAD_END_VERBAL_ABUSE",      # 기내 욕설
    "IMM_BAD_END_VERBAL_ABUSE",         # 입국심사 욕설/패배
    "BAG_BAD_END_VERBAL_ABUSE",         # 수화물 욕설
    "END_SECONDARY_INSPECTION",         # 2차 심사 강제 이동
    "END_BAGGAGE_REPORT_INCOMPLETE",    # 수화물 신고 미완료
})


class DevBPolicyClient:
    def __init__(
        self,
        agent: EnglishLevelHintAgent | None = None,
        *,
        agent_run_root: Path | None = None,
        final_result_policy: FinalResultScorePolicy | None = None,
        final_record_reader: OpenKBFinalResultRecordReader | None = None,
        focus_on_form_report_policy: FocusOnFormReportPolicy | None = None,
        final_result_writer: OpenKBFeedbackWriter | None = None,
    ) -> None:
        self.agent = agent or EnglishLevelHintAgent(agent_run_root=agent_run_root)
        self.final_result_policy = final_result_policy or FinalResultScorePolicy()
        self.final_record_reader = final_record_reader or OpenKBFinalResultRecordReader()
        self.focus_on_form_report_policy = focus_on_form_report_policy or FocusOnFormReportPolicy()
        self.final_result_writer = final_result_writer or OpenKBFeedbackWriter()

    def evaluate_turn(self, payload: DevBPolicyInput) -> DevBPolicyOutput:
        output = self.agent.evaluate_turn(payload)

        if payload.current_node_id not in TERMINAL_NODE_IDS:
            return output
        if output.branch.branch_type not in {"final", "bad_end"}:
            return output

        final_state = FinalScoreState(
            patience=payload.scenario_state.patience + output.state_delta.patience_delta,
            suspicion=payload.scenario_state.suspicion + output.state_delta.suspicion_delta,
            retry_count=payload.scenario_state.retry_count + output.state_delta.retry_count_delta,
            hint_count=payload.scenario_state.hint_count + output.state_delta.hint_count_delta,
        )
        records = self.final_record_reader.read_session_records(payload.session_id)
        # LLM 총평은 터미널 노드 도달 시 1회 생성
        final_result = self.final_result_policy.build_result(
            records,
            final_state=final_state,
            generate_llm_summary=True,
        )
        # OpenKB에 저장 — 이후 결과 조회는 여기서 읽음
        try:
            self.final_result_writer.save_final_result(payload.session_id, final_result)
        except Exception as exc:
            logger.warning("최종 결과 저장 실패 (session=%s): %s", payload.session_id, exc)

        return output.model_copy(update={"final_result": final_result})

    def final_result_for_session(self, session_id: str, *, player_id: str | None = None) -> FinalResult:
        # 저장된 결과 우선 반환 (LLM 총평 포함)
        if not player_id:
            cached = self.final_result_writer.load_final_result(session_id)
            if cached is not None:
                return cached

        records = self.final_record_reader.read_session_records(session_id)
        if player_id:
            player_records = [
                r for r in records
                if (r.get("speaker_player_id") or r.get("player_id")) == player_id
            ]
            room_state = self.final_result_policy.state_from_records(records)
            return self.final_result_policy.build_result(
                player_records,
                final_state=room_state,
            )
        # 저장본 없음 — LLM 없이 템플릿 폴백
        return self.final_result_policy.build_result(records)

    def out_game_feedback_for_session(self, session_id: str, *, player_id: str | None = None) -> dict[str, Any]:
        """Build the B-owned out-game learning card report for a session.

        Beginner guide:
        Developer B owns the Focus-on-Form report content.  Developer C only
        asks B's policy object for the already-shaped report and then exposes it
        on the final result endpoint as learning metadata.  This method must not
        change branch, score, verdict, next-node, or state-delta authority.
        """
        records = self.final_record_reader.read_session_records(session_id)
        if player_id:
            player_records = [
                r for r in records
                if (r.get("speaker_player_id") or r.get("player_id")) == player_id
            ]
            return self.focus_on_form_report_policy.build_report(player_records)

        return self.focus_on_form_report_policy.build_report(records)
