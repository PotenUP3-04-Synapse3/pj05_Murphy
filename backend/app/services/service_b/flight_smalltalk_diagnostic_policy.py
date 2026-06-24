from __future__ import annotations
import json
import random
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
MAX_TURNS = 30
CONFIDENCE_THRESHOLD = 0.7
STEERING = 0.4
BLOCKED_FLIGHT_SEATMATE_PROBE_IDS = {
    "ADDRESS_HELP",
    "FORM_HELP_REQUEST",
    "HOTEL_HOSTEL_REPAIR",
    "STAY_PLACE",
}
BLOCKED_FLIGHT_SEATMATE_TOPICS = {"arrival_form"}
BLOCKED_FLIGHT_SEATMATE_COMPETENCIES = {"address_guidance", "stay_location"}


def is_probe_allowed_for_flight_seatmate(probe: dict[str, Any]) -> bool:
    """Keep Flight seatmate diagnostics in natural smalltalk territory."""

    if probe.get("probe_id") in BLOCKED_FLIGHT_SEATMATE_PROBE_IDS:
        return False
    if probe.get("topic_tag") in BLOCKED_FLIGHT_SEATMATE_TOPICS:
        return False
    if probe.get("target_competency") in BLOCKED_FLIGHT_SEATMATE_COMPETENCIES:
        return False
    return True

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

        # 2. 부적절 언행 제재 (tier >= 2 즉시 bad_end, tier == 1 경고 후 bad_end)
        incivility = getattr(payload.understanding, "incivility", None)
        if incivility is not None:
            if incivility.tier >= 2:
                return ScenarioDecision(
                    verdict="CRITICAL_FAIL",
                    branch_type="bad_end",
                    next_action="COMPLETE_CHAPTER",
                    next_node_id="FLIGHT_BAD_END_VERBAL_ABUSE",
                    branch_reason=f"verbal_abuse_t{incivility.tier}",
                    patience_delta=-20,
                    suspicion_delta=0,
                    retry_count_delta=0,
                    hint_count_delta=0,
                )
            elif incivility.tier == 1:
                reader = OpenKBFinalResultRecordReader(runtime_root=self.runtime_root)
                records = reader.read_session_records(payload.session_id)
                flight_records = [r for r in records if str(r.get("node_id", "")).startswith("FLIGHT_")]
                
                past_rudeness = 0
                for r in flight_records:
                    under = r.get("understanding") or {}
                    inciv_record = under.get("incivility") or {}
                    if inciv_record.get("tier", 0) >= 1:
                        past_rudeness += 1
                        
                if past_rudeness >= 1:
                    return ScenarioDecision(
                        verdict="CRITICAL_FAIL",
                        branch_type="bad_end",
                        next_action="COMPLETE_CHAPTER",
                        next_node_id="FLIGHT_BAD_END_VERBAL_ABUSE",
                        branch_reason="verbal_abuse_t1_repeated",
                        patience_delta=-20,
                        suspicion_delta=0,
                        retry_count_delta=0,
                        hint_count_delta=0,
                    )
                else:
                    return ScenarioDecision(
                        verdict="FAIL",
                        branch_type="warning",
                        next_action="WARNING",
                        next_node_id=SCENE_ID,
                        branch_reason="verbal_abuse_t1_warning",
                        patience_delta=-10,
                        suspicion_delta=0,
                        retry_count_delta=0,
                        hint_count_delta=0,
                    )

        # 3. Load session history from OpenKB
        reader = OpenKBFinalResultRecordReader(runtime_root=self.runtime_root)
        records = reader.read_session_records(payload.session_id)
        flight_records = [r for r in records if str(r.get("node_id", "")).startswith("FLIGHT_")]

        turns = len(flight_records) + 1

        social_repair = _social_repair_decision(payload, flight_records)
        if social_repair is not None:
            return social_repair

        # Identify covered competencies from history early
        covered_competencies = set()
        for r in flight_records:
            dseed = r.get("dialogue_seed")
            if dseed and isinstance(dseed, dict):
                goal = dseed.get("surface_goal", "")
                for p in self.probes:
                    if p["probe_id"] == goal or f"{p['target_competency']}_{p['topic_tag']}" == goal:
                        covered_competencies.add(p["target_competency"])

        # 4. 스킵(Skip) 신호 처리
        if getattr(payload, "skip_requested", False):
            # 조기 스킵 폴백: MIN_TURNS 미만인 경우 신뢰도 0.1 부여
            final_conf = 0.1 if turns < MIN_TURNS else min(1.0, len(covered_competencies) / 5.0)
            return ScenarioDecision(
                verdict="SUCCESS",
                branch_type="success",
                next_action="COMPLETE_CHAPTER",
                next_node_id="FLIGHT_999_COMPLETE",
                branch_reason="flight_smalltalk_skip_requested",
                patience_delta=0,
                suspicion_delta=0,
                retry_count_delta=0,
                hint_count_delta=0,
                cumulative_confidence=final_conf,
            )

        # 4.5 클라이언트 측 허용 노드 제한으로 인한 강제 완료 처리
        if payload.client_allowed_next_nodes and SCENE_ID not in payload.client_allowed_next_nodes and "FLIGHT_999_COMPLETE" in payload.client_allowed_next_nodes:
            final_conf = 0.1 if turns < MIN_TURNS else min(1.0, len(covered_competencies) / 5.0)
            return ScenarioDecision(
                verdict="SUCCESS",
                branch_type="success",
                next_action="COMPLETE_CHAPTER",
                next_node_id="FLIGHT_999_COMPLETE",
                branch_reason="flight_smalltalk_forced_complete_by_client",
                patience_delta=0,
                suspicion_delta=0,
                retry_count_delta=0,
                hint_count_delta=0,
                cumulative_confidence=final_conf,
            )

        # 5. 되묻기 최소화: needs_repeat이거나 confidence < 0.3인 경우 가벼운 clarify
        if payload.input_source.needs_repeat or payload.understanding.confidence < 0.3:
            next_node_id = state_machine._checked_next_node(payload.node_context.clarify_next_node, payload)
            
            # 대화 흐름의 일관성을 위해 직전 turn의 selected_probe를 찾아서 유지합니다.
            last_probe = None
            if flight_records:
                for r in reversed(flight_records):
                    dseed = r.get("dialogue_seed")
                    if dseed and isinstance(dseed, dict):
                        goal = dseed.get("surface_goal", "")
                        for p in self.probes:
                            if not is_probe_allowed_for_flight_seatmate(p):
                                continue
                            if p["probe_id"] == goal or f"{p['target_competency']}_{p['topic_tag']}" == goal:
                                last_probe = p
                                break
                    if last_probe:
                        break
            safe_probes = [
                p for p in self.probes
                if is_probe_allowed_for_flight_seatmate(p)
            ]
            if not last_probe and safe_probes:
                last_probe = safe_probes[0]
                
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
                selected_probe=last_probe,
                cumulative_confidence=0.1,
            )

        # 6. Identify used probes and current topic from history
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

        # 민감주제 차단 필터
        def is_probe_sensitive(probe: dict) -> bool:
            text = (probe.get("seed_text", "") + " " + probe.get("probe_id", "") + " " + probe.get("target_competency", "")).lower()
            sensitive_keywords = {
                "politics", "election", "president", "religion", "church", "god", "bible", "jesus", "buddha", "sex", "sexual", "gender", "health", "disease", "illness", "hospital", "cancer", "medical", "money", "salary", "wage", "income", "marriage", "divorce", "politics", "policymaker",
                "정치", "선거", "대통령", "종교", "교회", "성경", "하느님", "하나님", "예수", "불교", "부처", "섹스", "성별", "건강", "질병", "병원", "암", "의료", "돈", "월급", "소득", "결혼", "이혼", "정치인", "예배", "절"
            }
            for kw in sensitive_keywords:
                if kw in text:
                    return True
            return False

        # 7. 숨은-목표 기반 확률적 토픽 스티어링 (가중 랜덤 선택)
        selectable_probes = [
            p for p in self.probes
            if is_probe_allowed_for_flight_seatmate(p) and not is_probe_sensitive(p)
        ]
        unused_probes = [p for p in selectable_probes if p["probe_id"] not in used_probes]
        candidates = unused_probes if unused_probes else selectable_probes

        selected_probe = None
        if candidates:
            use_coherence = random.random() < STEERING
            if use_coherence:
                coherent_candidates = [
                    p for p in candidates
                    if p["topic_tag"] == current_topic or current_topic in p["coherent_topics"]
                ]
                chosen_pool = coherent_candidates if coherent_candidates else candidates
            else:
                unmeasured_candidates = [
                    p for p in candidates
                    if p["target_competency"] not in covered_competencies
                ]
                chosen_pool = unmeasured_candidates if unmeasured_candidates else candidates

            # 가중치 산출 (미커버 competency 우선권 부여)
            weights = []
            for p in chosen_pool:
                w = 1.0
                if p["target_competency"] not in covered_competencies:
                    w *= 5.0
                if p["topic_tag"] == current_topic or current_topic in p["coherent_topics"]:
                    w *= 2.0
                weights.append(w)

            selected_probe = random.choices(chosen_pool, weights=weights, k=1)[0]

        if not selected_probe and selectable_probes:
            selected_probe = selectable_probes[0]

        self.current_selected_probe = selected_probe

        # 8. 실시간 신뢰도(Confidence) 산출: 턴 수 누적이 아닌 커버된 competency 다양성으로 계산
        all_covered_competencies = set(covered_competencies)
        if selected_probe:
            all_covered_competencies.add(selected_probe["target_competency"])
        
        cumulative_confidence = min(1.0, len(all_covered_competencies) / 5.0)

        # 9. 종료 판정 조건 (turns >= 30 상한선 또는 (turns >= 3 & 핵심 competency 2개 이상 커버 & confidence >= 0.7))
        core_competencies = {"travel_purpose", "stay_duration", "stay_location"}
        covered_cores = all_covered_competencies.intersection(core_competencies)

        should_terminate = False
        if turns >= MAX_TURNS:
            should_terminate = True
        elif turns >= MIN_TURNS and len(covered_cores) >= 2 and cumulative_confidence >= CONFIDENCE_THRESHOLD:
            should_terminate = True

        next_action: NextAction
        if should_terminate:
            next_node_id = "FLIGHT_999_COMPLETE"
            next_action = "COMPLETE_CHAPTER"
        else:
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


def _social_repair_decision(
    payload: DevBPolicyInput,
    flight_records: list[dict[str, Any]],
) -> ScenarioDecision | None:
    social_context = _social_context_dict(payload.understanding)
    obligation_status = str(social_context.get("obligation_status") or "")
    pending_obligation = str(social_context.get("pending_social_obligation") or "")
    if pending_obligation != "seatmate_pen_request":
        return None
    if obligation_status not in {"open", "ignored", "unclear"}:
        return None
    if not _is_social_stall_move(payload.player_text, social_context):
        return None

    lifecycle = _social_obligation_lifecycle(flight_records)
    if lifecycle == "paused_or_closed":
        return ScenarioDecision(
            verdict="SUCCESS",
            branch_type="success",
            next_action="COMPLETE_CHAPTER",
            next_node_id="FLIGHT_999_COMPLETE",
            branch_reason="flight_smalltalk_social_pause_closed",
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
            selected_probe=None,
            cumulative_confidence=0.0,
        )
    if lifecycle == "engagement_checked":
        return ScenarioDecision(
            verdict="SUCCESS",
            branch_type="success",
            next_action="COMPLETE_CHAPTER",
            next_node_id="FLIGHT_999_COMPLETE",
            branch_reason="flight_smalltalk_engagement_give_space",
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
            selected_probe=None,
            cumulative_confidence=0.0,
        )
    if lifecycle == "dropped":
        return ScenarioDecision(
            verdict="UNCLEAR",
            branch_type="clarify",
            next_action="REASK",
            next_node_id=SCENE_ID,
            branch_reason="flight_smalltalk_engagement_check",
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
            selected_probe=None,
            cumulative_confidence=0.0,
        )

    social_stall_streak = _social_stall_streak(payload, flight_records)
    if social_stall_streak >= 5:
        return ScenarioDecision(
            verdict="SUCCESS",
            branch_type="success",
            next_action="COMPLETE_CHAPTER",
            next_node_id="FLIGHT_999_COMPLETE",
            branch_reason="flight_smalltalk_engagement_give_space",
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
            selected_probe=None,
            cumulative_confidence=0.0,
        )
    if social_stall_streak >= 4:
        return ScenarioDecision(
            verdict="UNCLEAR",
            branch_type="clarify",
            next_action="REASK",
            next_node_id=SCENE_ID,
            branch_reason="flight_smalltalk_engagement_check",
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
            selected_probe=None,
            cumulative_confidence=0.0,
        )
    if social_stall_streak >= 3:
        return ScenarioDecision(
            verdict="SUCCESS",
            branch_type="success",
            next_action="ADVANCE",
            next_node_id=SCENE_ID,
            branch_reason="flight_smalltalk_social_obligation_dropped",
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
            selected_probe=None,
            cumulative_confidence=0.1,
        )

    branch_reason = (
        "flight_smalltalk_repeated_social_repair"
        if social_stall_streak >= 2
        else "flight_smalltalk_social_obligation_open"
    )
    return ScenarioDecision(
        verdict="UNCLEAR",
        branch_type="clarify",
        next_action="REASK",
        next_node_id=SCENE_ID,
        branch_reason=branch_reason,
        patience_delta=0,
        suspicion_delta=0,
        retry_count_delta=0,
        hint_count_delta=0,
        selected_probe=None,
        cumulative_confidence=0.0,
    )


def _social_obligation_lifecycle(flight_records: list[dict[str, Any]]) -> str:
    """Read the latest seatmate social-obligation stage from B's record trail."""

    for record in reversed(flight_records):
        branch = record.get("branch") if isinstance(record, dict) else {}
        branch_reason = str(branch.get("branch_reason") or "") if isinstance(branch, dict) else ""
        if "social_pause_closed" in branch_reason or "engagement_give_space" in branch_reason:
            return "paused_or_closed"
        if "engagement_check" in branch_reason:
            return "engagement_checked"
        if "social_obligation_dropped" in branch_reason:
            return "dropped"
        if "repeated_social_repair" in branch_reason:
            return "repaired_once"
        if "social_obligation_open" in branch_reason:
            return "open"
    return "none"


def _social_context_dict(understanding: Any) -> dict[str, Any]:
    social_context = getattr(understanding, "social_context", None)
    if isinstance(social_context, dict):
        return social_context
    if social_context is not None and hasattr(social_context, "model_dump"):
        return social_context.model_dump()
    return {}


def _social_stall_streak(
    payload: DevBPolicyInput,
    flight_records: list[dict[str, Any]],
) -> int:
    count = 1 if _is_social_stall_move(payload.player_text, _social_context_dict(payload.understanding)) else 0
    for record in reversed(flight_records):
        understanding = record.get("understanding") if isinstance(record, dict) else {}
        social_context = understanding.get("social_context") if isinstance(understanding, dict) else {}
        player_text = str(record.get("player_text") or "") if isinstance(record, dict) else ""
        if _is_social_stall_move(player_text, social_context if isinstance(social_context, dict) else {}):
            count += 1
            continue
        break
    return count


def _is_social_stall_move(player_text: str, social_context: dict[str, Any]) -> bool:
    conversation_move = str(social_context.get("conversation_move") or "")
    if conversation_move in {"meaningful_answer", "refusal"}:
        return False
    if conversation_move in {
        "greeting_only",
        "repeated_greeting",
        "low_content_non_answer",
        "filler",
        "off_topic",
        "clarification_request",
        "unknown",
    }:
        return True
    engagement_quality = str(social_context.get("engagement_quality") or "")
    obligation_status = str(social_context.get("obligation_status") or "")
    if engagement_quality in {"thin", "stalled"} and obligation_status in {"open", "ignored", "unclear"}:
        return True
    normalized = " ".join(player_text.lower().replace("?", " ").replace(".", " ").split())
    if normalized in {"what", "what what", "what what what", "fine", "fine fine", "fine fine fine"}:
        return True
    return _is_greeting_move(player_text, social_context)


def _is_greeting_move(player_text: str, social_context: dict[str, Any]) -> bool:
    if str(social_context.get("conversation_move") or "") in {"greeting_only", "repeated_greeting"}:
        return True
    normalized = " ".join(player_text.lower().replace("?", " ").replace(".", " ").split())
    if not normalized:
        return False
    words = normalized.split()
    greeting_words = {"hello", "hi", "hey", "hiya"}
    soft_fillers = {"there", "again", "um", "uh", "uhm", "ah"}
    return any(word in greeting_words for word in words) and all(
        word in greeting_words or word in soft_fillers for word in words
    )
