from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Any

from backend.app.schemas.game_turn import DevBPolicyInput


BranchType = Literal["success", "retry", "clarify", "hint", "warning", "bad_end", "final"]
NextAction = Literal["ADVANCE", "REASK", "GIVE_HINT", "WARNING", "FAIL_END", "FINAL_DECISION", "COMPLETE_CHAPTER"]
Verdict = Literal["SUCCESS", "PARTIAL", "UNCLEAR", "FAIL", "CRITICAL_FAIL"]

GOLD_CHALLENGE_SOURCE_NODE_ID = "IMM_005_RETURN_TICKET"
GOLD_BAG_CONTENT_CHALLENGE_NODE_ID = "IMM_ALPHA_GOLD_BAG_CONTENT_CHECK"
ALPHA_FINAL_SCOREBOARD_NODE_ID = "ALPHA_999_FINAL_SCOREBOARD"
CHAPTER_COMPLETE_NODE_IDS = {"FLIGHT_999_COMPLETE", "IMM_999_CLEARED", "BAG_999_COMPLETE"}


@dataclass(frozen=True)
class ScenarioDecision:
    """
    상태 머신이 결정한 시나리오 분기 판단 및 수치 변경 정보를 포함하는 데이터 클래스입니다.
    
    초보자 가이드: 이 클래스는 플레이어의 발화 평가 결과(verdict), 다음 시나리오 분기 타입(branch_type), 
    수행할 액션(next_action), 이동할 다음 노드 ID(next_node_id), 분기 결정 근거(branch_reason), 
    그리고 인내심(patience) 및 의심도(suspicion) 수치 변화량 등을 한데 묶어서 보관합니다.
    """
    verdict: Verdict
    branch_type: BranchType
    next_action: NextAction
    next_node_id: str
    branch_reason: str
    patience_delta: int
    suspicion_delta: int
    retry_count_delta: int
    hint_count_delta: int
    selected_probe: dict[str, Any] | None = None
    cumulative_confidence: float | None = None


class ScenarioStateMachine:
    """
    학습자와 NPC 간의 대화 진행 상황에 따라 다음 시나리오 노드와 수치 변화량을 결정하는 규칙 기반 상태 머신 클래스입니다.
    
    초보자 가이드: 플레이어가 올바른 대답을 했는지(Success), 답변이 모호한지(Unclear), 힌트가 필요한 상황인지(Hint) 
    혹은 불법 취업 의심 등 중대한 입국 위험을 발생시켰는지(Critical Risk)를 분석하여 게임의 다음 진행 방향(예: 합격, 재요청, 경고, 탈락 등)을 판정합니다.
    """
    def decide(self, payload: DevBPolicyInput) -> ScenarioDecision:
        """
        학습자의 발화 이해 결과(payload)를 종합 분석하여 시나리오 상의 분기 결정을 내립니다.
        
        Args:
            payload: 학습자 발화 분석 및 현재 시나리오 상태 데이터
            
        Returns:
            결정된 분기 방향과 수치 증감 데이터가 포함된 ScenarioDecision 객체
            
        Raises:
            ValueError: 허용된 다음 노드 목록이 유효하지 않을 때 발생
        """
        self._validate_allowed_nodes(payload)

        # 1. Check if the user successfully completed the turn
        is_success = self._is_success(payload)

        # 2. Enforce retry limit (3) and patience floor (<= 0) to transition to bad endings or force ADVANCE
        if not is_success:
            if payload.scenario_state.retry_count >= 3 or payload.scenario_state.patience <= 0:
                # If they are out of retries or patience, force bad ending
                return self._force_bad_end(
                    payload,
                    f"Patience exhausted ({payload.scenario_state.patience}) or retry limit exceeded ({payload.scenario_state.retry_count}) on failure."
                )

        # 3. Check critical risks
        risk_total = payload.scenario_state.suspicion + payload.understanding.risk_delta
        if self._is_critical_risk(payload, risk_total):
            return self._critical_fail(payload, risk_total)

        # 4. Handle success branch
        if is_success:
            if payload.current_node_id == ALPHA_FINAL_SCOREBOARD_NODE_ID:
                return self._success(payload, branch_type="final", next_action="FINAL_DECISION")
            return self._success(payload, branch_type="success", next_action="ADVANCE")

        # 5. Handle clarify/hint/retry with patience/retry checks
        # evaluate _should_give_hint before _is_unclear when retry_count >= 2
        if payload.scenario_state.retry_count >= 2:
            if self._should_give_hint(payload):
                return self._hint(payload)
            if self._is_unclear(payload):
                return self._clarify(payload)
        else:
            if self._is_unclear(payload):
                return self._clarify(payload)
            if self._should_give_hint(payload):
                return self._hint(payload)

        return self._retry(payload)

    def _validate_allowed_nodes(self, payload: DevBPolicyInput) -> None:
        """
        이동 가능한 노드 목록(allowed_next_nodes)이 존재하고 비어있지 않은지 유효성을 검사합니다.
        """
        if not payload.node_context.allowed_next_nodes:
            raise ValueError("node_context.allowed_next_nodes must not be empty")

    def _has_invalid_required_slot_value(self, payload: DevBPolicyInput) -> bool:
        """
        요구되는 슬롯(required_slots) 중 허용 가능한 값 목록(allowed_slot_values)이 정의된 슬롯이 있을 때,
        실제로 추출된 슬롯 값(extracted_slots)이 존재하지만 그 값이 허용 후보군에 실재하지 않는 경우 True를 반환합니다.
        추출되지 않은(누락된) 슬롯은 여기서 검증하지 않고 missing_slots 및 retry/hint 로직에서 처리되도록 합니다.
        """
        allowed = payload.node_context.allowed_slot_values or {}
        extracted = payload.understanding.extracted_slots or {}
        for slot in payload.node_context.required_slots:
            candidates = allowed.get(slot)
            if not candidates:
                # 허용값 목록(후보군)이 정의되지 않은 자유 서술형 슬롯은 검증 생략
                continue
            if slot in extracted:
                value = extracted[slot]
                if value is None:
                    return True
                
                # stay_duration의 경우 추출값이 "five days", "one week" 등 구체적인 문자열일 수 있으므로
                # allowed_slot_values 범주인 ("days", "weeks", "months", "until_date")와의 매핑 검사를 별도로 지원합니다.
                if slot == "stay_duration":
                    matched = False
                    for candidate in candidates:
                        if candidate == "days" and ("day" in value or "days" in value):
                            matched = True
                            break
                        elif candidate == "weeks" and ("week" in value or "weeks" in value):
                            matched = True
                            break
                        elif candidate == "months" and ("month" in value or "months" in value):
                            matched = True
                            break
                        elif candidate == "until_date" and "until" in value:
                            matched = True
                            break
                    if not matched:
                        return True
                else:
                    if value not in candidates:
                        # 추출된 값이 후보군에 매핑되지 않는 유효하지 않은 값임
                        return True
        return False

    def _is_success(self, payload: DevBPolicyInput) -> bool:
        """
        플레이어의 발화 결과가 성공 의도(Intent Success)를 충족하고, 요구되는 중요 슬롯 정보가 누락되지 않았으며,
        추출된 슬롯 값들이 유효한 후보군에 포함되는지 검사합니다.
        
        이미 완료된 의도(completed_intents)인 경우 누락 슬롯(missing_slots)이 있더라도 정답 처리(Success)로 우회합니다.
        """
        req_intents = payload.node_context.required_intents or []
        completed = set(payload.scenario_state.completed_intents or [])
        has_already_completed = any(intent in completed for intent in req_intents)

        if has_already_completed:
            return (
                payload.understanding.intent_success
                and not self._has_invalid_required_slot_value(payload)
            )
        else:
            return (
                payload.understanding.intent_success
                and not payload.understanding.missing_slots
                and not self._has_invalid_required_slot_value(payload)
            )

    def _is_unclear(self, payload: DevBPolicyInput) -> bool:
        """
        사용자의 답변이 모호한지(Confidence 부족, 질문과 무관 등) 또는 다시 말해달라는 요청(needs_repeat)이거나,
        추출된 필수 슬롯의 값이 유효하지 않은 경우 검사합니다.
        """
        return (
            payload.input_source.needs_repeat
            or payload.understanding.needs_clarification
            or payload.understanding.confidence < 0.5
            or payload.understanding.answer_relevance == "partially_related"
            or self._has_invalid_required_slot_value(payload)
        )

    def _should_give_hint(self, payload: DevBPolicyInput) -> bool:
        """
        플레이어의 등급(Bronze 등)이나 대화 실패 횟수(retry_count)를 분석하여 힌트를 필수로 제공해야 하는 상황인지 판단합니다.
        """
        if payload.scenario_state.retry_count >= 2:
            return True
        if payload.player_profile.tier == "Bronze" and payload.understanding.missing_slots:
            return True
        return payload.scenario_state.previous_fail_count >= 2

    def _is_critical_risk(self, payload: DevBPolicyInput, risk_total: int) -> bool:
        """
        불법 체류, 취업 목적, 알 수 없는 가방 내용물 등 중대한 입국 거부 유발 키워드가 감지되거나 누적 의심도 수치가 기준을 넘었는지 확인합니다.
        """
        critical_tags = {
            "illegal_work_intent",
            "overstay_intent",
            "unknown_contents",
            "received_from_stranger",
            "dangerous_use",
            "commercial_resale",
            "refuse_submission",
        }
        return (
            payload.understanding.risk_delta >= 20
            or risk_total >= 50
            or bool(critical_tags.intersection(payload.understanding.risk_tags))
        )

    def _success(
        self,
        payload: DevBPolicyInput,
        *,
        branch_type: BranchType,
        next_action: NextAction,
    ) -> ScenarioDecision:
        """
        성공 판정 시, 다음 진행할 시나리오 노드를 찾고 점수/수치(Patience, Suspicion 등)를 보정해 ScenarioDecision 결과로 빌드합니다.
        """
        next_node_id = self._checked_next_node(self._preferred_success_node(payload), payload)
        if next_node_id in CHAPTER_COMPLETE_NODE_IDS:
            next_action = "COMPLETE_CHAPTER"
        return ScenarioDecision(
            verdict="SUCCESS",
            branch_type=branch_type,
            next_action=next_action,
            next_node_id=next_node_id,
            branch_reason="Required intent and required slots were satisfied.",
            patience_delta=0,
            suspicion_delta=max(payload.understanding.risk_delta, 0),
            retry_count_delta=0,
            hint_count_delta=0,
        )

    def _preferred_success_node(self, payload: DevBPolicyInput) -> str:
        """
        정답 처리가 되었을 때 시나리오의 흐름 상 가장 알맞은 타겟 노드 ID를 결정합니다.
        """
        if self._should_route_gold_bag_content_challenge(payload):
            return GOLD_BAG_CONTENT_CHALLENGE_NODE_ID
        return payload.node_context.success_next_node

    def _should_route_gold_bag_content_challenge(self, payload: DevBPolicyInput) -> bool:
        """
        골드 티어 플레이어에게 수하물 상세 검사 시나리오(Gold Bag Content Challenge)를 유도할 수 있는 특수 조건인지 검사합니다.
        """
        return (
            payload.current_node_id == GOLD_CHALLENGE_SOURCE_NODE_ID
            and payload.player_profile.tier == "Gold"
            and payload.understanding.confidence >= 0.85
            and not payload.understanding.missing_slots
            and GOLD_BAG_CONTENT_CHALLENGE_NODE_ID in payload.node_context.allowed_next_nodes
        )

    def _clarify(self, payload: DevBPolicyInput) -> ScenarioDecision:
        """
        모호한 응답으로 판단되어 되묻기(Clarification) 처리가 필요할 때의 분기 정보와 수치 변화량을 결정합니다.
        """
        next_node_id = self._checked_next_node(payload.node_context.clarify_next_node, payload)
        return ScenarioDecision(
            verdict="UNCLEAR",
            branch_type="clarify",
            next_action="REASK",
            next_node_id=next_node_id,
            branch_reason="Meaning is unclear or needs clarification.",
            patience_delta=-5,
            suspicion_delta=max(payload.understanding.risk_delta, 0),
            retry_count_delta=1,
            hint_count_delta=0,
        )

    def _hint(self, payload: DevBPolicyInput) -> ScenarioDecision:
        """
        플레이어에게 힌트(GIVE_HINT)를 직접적으로 노출해야 하는 시나리오 분기 정보와 수치 변화량을 결정합니다.
        """
        next_node_id = self._checked_next_node(payload.node_context.hint_next_node, payload)
        return ScenarioDecision(
            verdict="FAIL",
            branch_type="hint",
            next_action="GIVE_HINT",
            next_node_id=next_node_id,
            branch_reason="Repeated failure or beginner support policy requires a hint.",
            patience_delta=-10,
            suspicion_delta=max(payload.understanding.risk_delta, 0),
            retry_count_delta=1,
            hint_count_delta=1,
        )

    def _retry(self, payload: DevBPolicyInput) -> ScenarioDecision:
        """
        답변 오류로 인해 다시 답변을 요구(REASK)해야 하는 분기 정보와 수치 변화량을 결정합니다.
        """
        next_node_id = self._checked_next_node(payload.node_context.retry_next_node, payload)
        return ScenarioDecision(
            verdict="FAIL",
            branch_type="retry",
            next_action="REASK",
            next_node_id=next_node_id,
            branch_reason="Required intent or slot was not satisfied.",
            patience_delta=-8,
            suspicion_delta=max(payload.understanding.risk_delta, 0),
            retry_count_delta=1,
            hint_count_delta=0,
        )

    def _critical_fail(self, payload: DevBPolicyInput, risk_total: int) -> ScenarioDecision:
        """
        중대 입국 위험이 감지되었을 때, 경고 단계를 발생시키거나 즉시 탈락(Bad End)으로 이끄는 시나리오 분기 정보를 결정합니다.
        """
        branch_type: BranchType = "bad_end" if risk_total >= 70 or payload.scenario_state.retry_count >= 2 else "warning"
        next_action: NextAction = "FAIL_END" if branch_type == "bad_end" else "WARNING"
        preferred = self._preferred_bad_end_node(payload) if branch_type == "bad_end" else payload.node_context.warning_next_node
        next_node_id = self._checked_next_node(preferred, payload)
        return ScenarioDecision(
            verdict="CRITICAL_FAIL",
            branch_type=branch_type,
            next_action=next_action,
            next_node_id=next_node_id,
            branch_reason="Risk expression increased immigration suspicion.",
            patience_delta=-20,
            suspicion_delta=max(payload.understanding.risk_delta, 20),
            retry_count_delta=1,
            hint_count_delta=0,
        )

    def _preferred_bad_end_node(self, payload: DevBPolicyInput) -> str:
        """
        강제 퇴거(Bad End) 시 플레이어가 도달할 노드 ID(예: 2차 심사대실 이동 등)를 선택합니다.
        """
        if "END_SECONDARY_INSPECTION" in payload.node_context.allowed_next_nodes:
            return "END_SECONDARY_INSPECTION"
        if "END_BAGGAGE_REPORT_INCOMPLETE" in payload.node_context.allowed_next_nodes:
            return "END_BAGGAGE_REPORT_INCOMPLETE"
        return payload.node_context.warning_next_node

    def _force_bad_end(self, payload: DevBPolicyInput, reason: str) -> ScenarioDecision:
        """
        인내심 고갈 또는 최대 재시도 횟수 도달 시 즉시 강제 종료 분기(bad_end)로 이끄는 결정을 내립니다.
        """
        preferred = self._preferred_bad_end_node(payload)
        next_node_id = self._checked_next_node(preferred, payload)
        return ScenarioDecision(
            verdict="FAIL",
            branch_type="bad_end",
            next_action="FAIL_END",
            next_node_id=next_node_id,
            branch_reason=reason,
            patience_delta=0,
            suspicion_delta=0,
            retry_count_delta=0,
            hint_count_delta=0,
        )

    def _checked_next_node(self, preferred_next_node: str, payload: DevBPolicyInput) -> str:
        """
        이동 대상으로 추천된 노드가 허용된 다음 노드 목록(allowed_next_nodes)에 부합하는지 검증합니다.
        """
        allowed_next_nodes = payload.node_context.allowed_next_nodes
        if preferred_next_node in allowed_next_nodes and self._client_allows(preferred_next_node, payload):
            return preferred_next_node

        for candidate in allowed_next_nodes:
            if self._client_allows(candidate, payload):
                return candidate

        raise ValueError("No next_node_id is allowed by both node_context and client_allowed_next_nodes")

    def _client_allows(self, next_node_id: str, payload: DevBPolicyInput) -> bool:
        """
        클라이언트 측에서 명시적으로 허용한 다음 노드 제약 조건에 어긋나지 않는지 최종 확인합니다.
        """
        return not payload.client_allowed_next_nodes or next_node_id in payload.client_allowed_next_nodes
