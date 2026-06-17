from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import DevBPolicyInput
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision, ScenarioStateMachine, NextAction
from backend.app.services.service_b.final_result_score_policy import OpenKBFinalResultRecordReader

SCENE_ID = "FLIGHT_A_001_SEATMATE_SMALLTALK"
MINIMUM_PLAYER_TURNS = 3
SKIP_ELIGIBLE_PLAYER_TURNS = 3

MIN_TURNS = 3
MAX_TURNS = 7
CONFIDENCE_THRESHOLD = 0.7
STEERING = 0.4


@dataclass(frozen=True)
class FlightSmallTalkDiagnosticDecision:
    """
    비행기 내 스몰토크 단계에서 내려진 진단 평가 결과 데이터 클래스입니다.
    """
    scene_id: str
    diagnostic_only: bool
    minimum_turns_met: bool
    required_more_turns: int
    skip_eligible: bool
    should_emit_out_game_feedback_seed: bool
    should_show_out_game_feedback_now: bool
    cumulative_confidence: float = 0.0


class FlightSmallTalkDiagnosticPolicy:
    """
    비행기 안에서 진행되는 영어 회화 진단(스몰토크)의 진행 및 스킵 조건을 결정하는 정책 클래스입니다.
    """
    def __init__(
        self,
        runtime_root: Path | None = None,
        data_path: Path | None = None,
    ) -> None:
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")
        self.data_path = data_path or Path("backend/app/data/flight_smalltalk_probes.json")
        self._load_probes()
        self.current_selected_probe: dict[str, Any] | None = None

    def _load_probes(self) -> None:
        if self.data_path.exists():
            try:
                self.probes = json.loads(self.data_path.read_text(encoding="utf-8"))
            except Exception:
                self.probes = []
        else:
            self.probes = []

    def evaluate(self, *, player_turn_count: int) -> FlightSmallTalkDiagnosticDecision:
        """
        플레이어가 진행한 대화 횟수를 바탕으로 스몰토크 진단 결과를 평가합니다.
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
            cumulative_confidence=0.0,
        )



    def decide_conversational(self, payload: DevBPolicyInput) -> ScenarioDecision:
        """
        기내 스몰토크용 대화형 분기를 결정합니다. (패널티 미적립, 중립 진행)
        """
        state_machine = ScenarioStateMachine()

        # 1. 중대 위험(Critical Risk) 감지 시 기존 입국 심사 안전선 위임
        risk_total = payload.scenario_state.suspicion + payload.understanding.risk_delta
        if state_machine._is_critical_risk(payload, risk_total):
            return state_machine._critical_fail(payload, risk_total)

        # 2. 되묻기 최소화: needs_repeat이거나 confidence < 0.3인 경우 가벼운 clarify
        if payload.input_source.needs_repeat or payload.understanding.confidence < 0.3:
            next_node_id = state_machine._checked_next_node(payload.node_context.clarify_next_node, payload)
            return ScenarioDecision(
                verdict="UNCLEAR",
                branch_type="clarify",
                next_action="REASK",
                next_node_id=next_node_id,
                branch_reason="flight_smalltalk_clarify",
                patience_delta=0,
                suspicion_delta=0,
                retry_count_delta=0,
                hint_count_delta=0,
            )

        # Load session history from OpenKB
        reader = OpenKBFinalResultRecordReader(runtime_root=self.runtime_root)
        records = reader.read_session_records(payload.session_id)
        flight_records = [r for r in records if str(r.get("node_id", "")).startswith("FLIGHT_")]

        turns = len(flight_records) + 1

        # Calculate cumulative confidence (and standard error equivalents)
        base_conf = 0.1
        if payload.player_profile.english_confidence == "intermediate":
            base_conf = 0.2
        elif payload.player_profile.english_confidence == "advanced":
            base_conf = 0.3

        incr_conf = 0.0
        for r in flight_records:
            under = r.get("understanding") or {}
            conf = under.get("confidence", 0.8)
            verdict = r.get("evaluation", {}).get("verdict", "")
            if verdict == "SUCCESS":
                incr_conf += 0.15 * conf + 0.05
            elif verdict in {"UNCLEAR", "PARTIAL"}:
                incr_conf += 0.10 * conf
            else:
                incr_conf += 0.05 * conf

        # Include current turn information
        current_conf = payload.understanding.confidence
        current_incr = 0.15 * current_conf + 0.05
        cumulative_confidence = min(1.0, base_conf + incr_conf + current_incr)

        # Identify used probes and current topic from history
        used_probes = set()
        current_topic = "travel"
        for r in flight_records:
            dseed = r.get("dialogue_seed")
            if dseed and isinstance(dseed, dict):
                goal = dseed.get("surface_goal", "")
                for p in self.probes:
                    if p["probe_id"] == goal or f"{p['target_competency']}_{p['topic_tag']}" == goal:
                        used_probes.add(p["probe_id"])
                        current_topic = p["topic_tag"]

        # Opportunistic probe selection based on steering knob
        selected_probe = None

        unused_probes = [p for p in self.probes if p["probe_id"] not in used_probes]

        if STEERING > 0.0 and unused_probes:
            # Pick a probe matching current topic/coherent topics first
            coherent_probes = [
                p for p in unused_probes
                if p["topic_tag"] == current_topic or current_topic in p["coherent_topics"]
            ]
            if coherent_probes:
                selected_probe = coherent_probes[0]
            else:
                selected_probe = unused_probes[0]
        else:
            # pure follow or no unused probes left
            if self.probes:
                selected_probe = self.probes[0]

        if not selected_probe and self.probes:
            selected_probe = self.probes[0]

        self.current_selected_probe = selected_probe

        # Determine next node and action
        # Bounded termination conditions
        should_terminate = False
        if turns >= MIN_TURNS and cumulative_confidence >= CONFIDENCE_THRESHOLD:
            should_terminate = True
        elif turns >= MAX_TURNS:
            should_terminate = True

        if should_terminate:
            next_node_id = "FLIGHT_999_COMPLETE"
            next_action: NextAction = "COMPLETE_CHAPTER"
        else:
            # Self loop
            next_node_id = SCENE_ID
            next_action = "ADVANCE"

        return ScenarioDecision(
            verdict="SUCCESS",
            branch_type="success",
            next_action=next_action,
            next_node_id=next_node_id,
            branch_reason="flight_smalltalk_continue",
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
            selected_probe=selected_probe,
            cumulative_confidence=cumulative_confidence,
        )
