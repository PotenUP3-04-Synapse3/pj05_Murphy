"""Baggage Claim 챕터(CH0_04) 전체 라우팅 흐름 결정적 단위 테스트.

목적
----
합성 UnderstandingOutput과 ScenarioStateMachine.decide()를 사용해
4가지 시나리오 경로를 end-to-end로 검증한다. NPC 대사나 LLM 없이 순수
상태머신 라우팅만 테스트하므로 항상 결정적이고 CI 게이트로 동작한다.

경로
----
1. 정상 통관   : BAG_001 → 002 → 003 → 004 → 005 → 006 → 007 → BAG_999_COMPLETE
2. 지속 실패   : 연속 불충분 → END_BAGGAGE_REPORT_INCOMPLETE
3. Critical    : BAG_006 미신고 고가품 → bad_end
4. 욕설 bad end: risk_delta >= 20 → BAD_END (BAG_BAD_END_VERBAL_ABUSE 포함)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    HintPolicy,
    InputSource,
    NodeContext,
    PlayerProfile,
    RandomCustomsItemContext,
    ScenarioState,
    UnderstandingOutput,
)
from backend.app.services.service_b.scenario_state_machine import ScenarioStateMachine

SCENARIO_NODE_PATH = Path("backend/app/data/scenario_nodes.json")
CHAPTER_ID = "CH0_04_BAGGAGE_CLAIM"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_nodes() -> dict:
    return json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))["nodes"]


def _node_context(node_id: str) -> NodeContext:
    nodes = _load_nodes()
    node = nodes[node_id]
    scenario_id = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))["scenario_id"]
    return NodeContext(
        node_id=node["node_id"],
        scenario_id=scenario_id,
        chapter_id=node["chapter_id"],
        node_type=node["node_type"],
        transition=node.get("transition"),
        npc_question=node["npc_question"],
        npc_question_goal=node["npc_question_goal"],
        objective_kr=node["objective_kr"],
        required_intents=node["required_intents"],
        required_slots=node["required_slots"],
        optional_slots=node.get("optional_slots", []),
        critical_slots=node.get("critical_slots", []),
        allowed_slot_values=node.get("allowed_slot_values", {}),
        risk_keywords=node.get("risk_keywords", []),
        recommended_expression=node["recommended_expression"],
        base_hint_kr=node["base_hint_kr"],
        hint_policy=HintPolicy(**node["hint_policy"]),
        success_next_node=node["branch_candidates"]["success"],
        retry_next_node=node["branch_candidates"]["retry"],
        clarify_next_node=node["branch_candidates"]["clarify"],
        hint_next_node=node["branch_candidates"]["hint"],
        warning_next_node=node["branch_candidates"]["warning"],
        allowed_next_nodes=node["allowed_next_nodes"],
    )


def _make_understanding(
    intent_success: bool = True,
    missing_slots: list[str] | None = None,
    extracted_slots: dict | None = None,
    confidence: float = 0.95,
    risk_delta: int = 0,
    risk_tags: list[str] | None = None,
    needs_clarification: bool = False,
    intent: str = "test_intent",
) -> UnderstandingOutput:
    return UnderstandingOutput(
        intent=intent,
        intent_success=intent_success,
        confidence=confidence,
        meaning_summary_kr="테스트용 합성 이해",
        emotion="Normal",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=risk_delta,
        risk_reason="",
        risk_tags=risk_tags or [],
        extracted_slots=extracted_slots or {},
        missing_slots=missing_slots or [],
        needs_clarification=needs_clarification,
    )


def _make_state(
    patience: int = 100,
    suspicion: int = 0,
    retry_count: int = 0,
    hint_count: int = 0,
    previous_fail_count: int = 0,
) -> ScenarioState:
    return ScenarioState(
        patience=patience,
        suspicion=suspicion,
        retry_count=retry_count,
        hint_count=hint_count,
        previous_fail_count=previous_fail_count,
        completed_intents=[],
    )


def _make_payload(
    node_id: str,
    understanding: UnderstandingOutput,
    state: ScenarioState | None = None,
    player_text: str = "test",
    random_customs_item: RandomCustomsItemContext | None = None,
) -> DevBPolicyInput:
    ctx = _node_context(node_id)
    return DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="flow_test",
        session_id="flow_test",
        player_id="flow_test",
        chapter_id=CHAPTER_ID,
        scene_id="JFK_BAGGAGE_CLAIM",
        current_node_id=node_id,
        turn_index=1,
        player_text=player_text,
        input_source=InputSource(
            input_type="voice",
            stt_confidence=1.0,
            language_detected="en-US",
            needs_repeat=False,
        ),
        player_profile=PlayerProfile(
            nickname="FlowTester",
            english_confidence="beginner",
            tier="Silver",
            travel_speaking_level="TSL_2_FUNCTIONAL",
        ),
        scenario_state=state or _make_state(),
        node_context=ctx,
        understanding=understanding,
        random_customs_item=random_customs_item,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_normal_clearance_full_flow() -> None:
    """정상 통관: BAG_001 → 002 → 003 → 004 → 005 → 006 → 007 → BAG_999_COMPLETE."""
    sm = ScenarioStateMachine()
    _ = _load_nodes()

    # BAG_001: 분실 신고
    d = sm.decide(_make_payload(
        "BAG_001_REPORT_MISSING_AT_DESK",
        _make_understanding(
            intent_success=True,
            extracted_slots={"missing_bag_statement": "my_bag_is_missing"},
        ),
    ))
    assert d.branch_type == "success", f"BAG_001 expected success, got {d.branch_type}"
    assert d.next_node_id == "BAG_002_PROVIDE_CLAIM_TAG"

    # BAG_002: 클레임태그 제공
    d = sm.decide(_make_payload(
        "BAG_002_PROVIDE_CLAIM_TAG",
        _make_understanding(
            intent_success=True,
            extracted_slots={"claim_tag_status": "tag_provided"},
        ),
    ))
    assert d.branch_type == "success", f"BAG_002 expected success, got {d.branch_type}"
    assert d.next_node_id == "BAG_003_CONFIRM_SEARCHED_CAROUSEL"

    # BAG_003: 캐러셀 확인
    d = sm.decide(_make_payload(
        "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
        _make_understanding(
            intent_success=True,
            extracted_slots={"carousel_search_confirmation": "searched_carefully"},
        ),
    ))
    assert d.branch_type == "success", f"BAG_003 expected success, got {d.branch_type}"
    assert d.next_node_id == "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD"

    # BAG_004: 리디렉트 수용
    d = sm.decide(_make_payload(
        "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_redirect_acknowledgement": "understood"},
        ),
    ))
    assert d.branch_type == "success", f"BAG_004 expected success, got {d.branch_type}"
    assert d.next_node_id == "BAG_005_CUSTOMS_HOLD_EXPLANATION"

    # BAG_005: 검사 동의
    d = sm.decide(_make_payload(
        "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_acknowledgement": "acknowledged"},
        ),
    ))
    assert d.branch_type == "success", f"BAG_005 expected success, got {d.branch_type}"
    assert d.next_node_id == "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"

    # BAG_006: 물품 설명 (저난이도 아이템, generic 통과)
    from backend.app.schemas.game_turn import CustomsItemJudgeContext
    ctx006 = _node_context("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM")
    ctx006.customs_item_context = CustomsItemJudgeContext(
        item_name="Mismatched Socks",
        item_category="clothing",
        difficulty=1,
        suspicion_reason="Unusual for customs",
        declared=False,
    )
    payload006 = _make_payload(
        "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
        _make_understanding(
            intent_success=True,
            extracted_slots={},
        ),
        random_customs_item=RandomCustomsItemContext(
            item_id="ITEM_MISMATCHED_SOCKS",
            item_name="Mismatched Socks",
            item_category="clothing",
            item_description="Unusual for customs",
            declared=False,
            difficulty=1,
            suspicion_reason="Unusual for customs",
        ),
    )
    payload006 = payload006.model_copy(update={"node_context": ctx006})
    d = sm.decide(payload006)
    assert d.branch_type == "success", f"BAG_006 (low diff) expected success, got {d.branch_type}"
    assert d.next_node_id == "BAG_007_CUSTOMS_CLEARANCE"

    # BAG_007: 통관 완료
    d = sm.decide(_make_payload(
        "BAG_007_CUSTOMS_CLEARANCE",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_clearance_acknowledgement": "acknowledged"},
        ),
    ))
    assert d.branch_type == "success", f"BAG_007 expected success, got {d.branch_type}"
    assert d.next_node_id == "BAG_999_COMPLETE"


def test_persistent_failure_ends_at_bad_end() -> None:
    """지속 불충분: retry_count>=5 AND hint_count>=1 (소진 상태 직접 주입) → END_BAGGAGE_REPORT_INCOMPLETE."""
    sm = ScenarioStateMachine()

    d = sm.decide(_make_payload(
        "BAG_001_REPORT_MISSING_AT_DESK",
        _make_understanding(
            intent_success=False,
            missing_slots=["missing_bag_statement"],
        ),
        state=_make_state(patience=0, retry_count=5, hint_count=1),
    ))
    assert d.branch_type == "bad_end", f"Expected bad_end on exhausted state, got {d.branch_type}"
    assert d.next_node_id == "END_BAGGAGE_REPORT_INCOMPLETE"


def test_persistent_failure_each_node_terminates() -> None:
    """각 노드에서 소진 상태 주입 시 bad_end로 종료 (종점 가드 검증)."""
    sm = ScenarioStateMachine()
    nodes_to_check = [
        "BAG_001_REPORT_MISSING_AT_DESK",
        "BAG_002_PROVIDE_CLAIM_TAG",
        "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
        "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
        "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        "BAG_007_CUSTOMS_CLEARANCE",
    ]
    for node_id in nodes_to_check:
        d = sm.decide(_make_payload(
            node_id,
            _make_understanding(
                intent_success=False,
                missing_slots=["dummy_slot"],
            ),
            state=_make_state(patience=0, retry_count=6, hint_count=1),
        ))
        assert d.branch_type == "bad_end", (
            f"Node {node_id}: expected bad_end on exhausted state, got {d.branch_type}"
        )
        assert "END_" in d.next_node_id or "BAD_END" in d.next_node_id, (
            f"Node {node_id}: expected ending node, got {d.next_node_id}"
        )


# ---------------------------------------------------------------------------
# bad_end 트리거 분리 테스트 — OR 조건 개별 검증
# 실제 조건: (retry_count >= MAX_HARD_FAIL_RETRIES OR patience <= 0) AND hint_count >= 1
# ---------------------------------------------------------------------------

def test_retry_limit_triggers_bad_end_without_patience_exhausted() -> None:
    """patience=100이어도 retry_count>=MAX_HARD_FAIL_RETRIES면 bad_end."""
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_001_REPORT_MISSING_AT_DESK",
        _make_understanding(intent_success=False, missing_slots=["missing_bag_statement"]),
        state=_make_state(patience=100, retry_count=5, hint_count=1),
    ))
    assert d.branch_type == "bad_end", (
        f"retry_count>=5 alone should trigger bad_end, got {d.branch_type}"
    )


def test_patience_floor_triggers_bad_end_without_retry_limit() -> None:
    """retry_count=0이어도 patience<=0이면 bad_end."""
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_001_REPORT_MISSING_AT_DESK",
        _make_understanding(intent_success=False, missing_slots=["missing_bag_statement"]),
        state=_make_state(patience=0, retry_count=0, hint_count=1),
    ))
    assert d.branch_type == "bad_end", (
        f"patience<=0 alone should trigger bad_end, got {d.branch_type}"
    )


def test_hint_given_before_bad_end_when_hint_count_zero() -> None:
    """retry 한계 도달 시 hint_count==0이면 bad_end 전에 GIVE_HINT를 먼저 반환."""
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_001_REPORT_MISSING_AT_DESK",
        _make_understanding(intent_success=False, missing_slots=["missing_bag_statement"]),
        state=_make_state(patience=0, retry_count=5, hint_count=0),
    ))
    assert d.branch_type == "hint", (
        f"When hint_count==0 at retry limit, should give hint first, got {d.branch_type}"
    )
    assert d.next_action == "GIVE_HINT"


# ---------------------------------------------------------------------------
# 실제 다회차 시뮬레이션 — 초기 상태에서 상태를 누적해 bad_end 도달 검증
# (Gap 3: 소진 상태 주입이 아닌 턴 진행으로 루프 없음 입증)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id,slot_name", [
    ("BAG_001_REPORT_MISSING_AT_DESK", "missing_bag_statement"),
    ("BAG_002_PROVIDE_CLAIM_TAG", "claim_tag_status"),
    ("BAG_003_CONFIRM_SEARCHED_CAROUSEL", "carousel_search_confirmation"),
    ("BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD", "customs_hold_redirect_acknowledgement"),
    ("BAG_005_CUSTOMS_HOLD_EXPLANATION", "customs_hold_acknowledgement"),
    ("BAG_007_CUSTOMS_CLEARANCE", "customs_clearance_acknowledgement"),
])
def test_node_persistent_failure_reaches_bad_end_from_fresh_state(
    node_id: str, slot_name: str
) -> None:
    """초기 상태(patience=100, retry=0)에서 연속 불충분 → 실제 상태 누적 → bad_end."""
    sm = ScenarioStateMachine()
    patience, _, retry_count, hint_count, previous_fail_count = 100, 0, 0, 0, 0

    reached_bad_end = False
    for turn in range(20):
        d = sm.decide(_make_payload(
            node_id,
            _make_understanding(intent_success=False, missing_slots=[slot_name]),
            state=_make_state(
                patience=patience,
                retry_count=retry_count,
                hint_count=hint_count,
                previous_fail_count=previous_fail_count,
            ),
        ))
        assert d.branch_type != "success", (
            f"{node_id} turn {turn}: insufficient answer should never yield success"
        )
        if d.branch_type == "bad_end":
            reached_bad_end = True
            break
        patience = max(0, patience + d.patience_delta)
        retry_count += d.retry_count_delta
        hint_count += d.hint_count_delta
        previous_fail_count += 1

    assert reached_bad_end, (
        f"{node_id}: 20회 내에 bad_end에 도달해야 함 (루프 없음 검증)"
    )


def test_critical_undeclared_valuable_in_bag006() -> None:
    """BAG_006 미신고 고가품(valuable) → 즉시 critical bad_end."""
    sm = ScenarioStateMachine()

    from backend.app.schemas.game_turn import CustomsItemJudgeContext
    ctx = _node_context("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM")
    ctx.customs_item_context = CustomsItemJudgeContext(
        item_name="1kg Gold Bar",
        item_category="valuable",
        difficulty=9,
        suspicion_reason="High value undeclared item",
        declared=False,
    )
    payload = _make_payload(
        "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
        _make_understanding(intent_success=True),
        random_customs_item=RandomCustomsItemContext(
            item_id="ITEM_GOLD_BAR",
            item_name="1kg Gold Bar",
            item_category="valuable",
            item_description="High value undeclared item",
            declared=False,
            difficulty=9,
            suspicion_reason="High value undeclared item",
        ),
    )
    payload = payload.model_copy(update={"node_context": ctx})
    d = sm.decide(payload)
    assert d.verdict == "CRITICAL_FAIL", f"Expected CRITICAL_FAIL, got {d.verdict}"
    assert d.branch_type == "bad_end", f"Expected bad_end, got {d.branch_type}"


def test_critical_undeclared_luxury_in_bag006() -> None:
    """BAG_006 미신고 luxury 아이템 → 즉시 critical bad_end."""
    sm = ScenarioStateMachine()

    from backend.app.schemas.game_turn import CustomsItemJudgeContext
    ctx = _node_context("BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM")
    ctx.customs_item_context = CustomsItemJudgeContext(
        item_name="Patek Philippe Watches",
        item_category="luxury",
        difficulty=12,
        suspicion_reason="Luxury item undeclared",
        declared=False,
    )
    payload = _make_payload(
        "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
        _make_understanding(intent_success=True),
        random_customs_item=RandomCustomsItemContext(
            item_id="ITEM_PATEK_WATCHES",
            item_name="Patek Philippe Watches",
            item_category="luxury",
            item_description="Luxury item undeclared",
            declared=False,
            difficulty=12,
            suspicion_reason="Luxury item undeclared",
        ),
    )
    payload = payload.model_copy(update={"node_context": ctx})
    d = sm.decide(payload)
    assert d.verdict == "CRITICAL_FAIL", f"Expected CRITICAL_FAIL, got {d.verdict}"
    assert d.branch_type == "bad_end", f"Expected bad_end, got {d.branch_type}"


def test_high_risk_expression_triggers_critical() -> None:
    """risk_delta >= 20 → critical 경로 (욕설/위험발언 유사 케이스)."""
    sm = ScenarioStateMachine()

    d = sm.decide(_make_payload(
        "BAG_001_REPORT_MISSING_AT_DESK",
        _make_understanding(
            intent_success=False,
            risk_delta=20,
            risk_tags=["illegal_work_intent"],
        ),
        state=_make_state(retry_count=0),
    ))
    assert d.verdict == "CRITICAL_FAIL", f"Expected CRITICAL_FAIL on high risk, got {d.verdict}"
    assert d.branch_type in {"bad_end", "warning"}, (
        f"Expected bad_end or warning, got {d.branch_type}"
    )


def test_no_premature_success_before_bag006() -> None:
    """BAG_001~005에서 조기 통과(success) 가 BAG_006를 건너뛰지 않는지 확인."""
    sm = ScenarioStateMachine()

    # BAG_004 success → 반드시 BAG_005로만 이동 (BAG_006 건너뜀 없음)
    d = sm.decide(_make_payload(
        "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_redirect_acknowledgement": "understood"},
        ),
    ))
    assert d.next_node_id == "BAG_005_CUSTOMS_HOLD_EXPLANATION", (
        f"BAG_004 success should go to BAG_005, not {d.next_node_id}"
    )
    # BAG_005 success → 반드시 BAG_006으로만 이동 (BAG_007 건너뜀 없음)
    d = sm.decide(_make_payload(
        "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_acknowledgement": "acknowledged"},
        ),
    ))
    assert d.next_node_id == "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM", (
        f"BAG_005 success should go to BAG_006, not {d.next_node_id}"
    )


# ---------------------------------------------------------------------------
# BAG_002 BUG #1 회귀: 물리 제출 표현 인식 (intent recognition fix)
# ---------------------------------------------------------------------------

def test_bag002_physical_handover_here_it_is() -> None:
    """'here it is' → claim_tag_status: has_claim_tag → BAG_003.

    BUG #1 회귀 테스트: 물리 제출 표현이 allowed_slot_value로 정규화되어야 함.
    LLM 없이 합성 UnderstandingOutput으로 상태머신 라우팅만 검증.
    """
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_002_PROVIDE_CLAIM_TAG",
        _make_understanding(
            intent_success=True,
            extracted_slots={"claim_tag_status": "has_claim_tag"},
        ),
        player_text="here it is",
    ))
    assert d.branch_type == "success", (
        f"BAG_002 'here it is' should succeed; got branch_type={d.branch_type}"
    )
    assert d.next_node_id == "BAG_003_CONFIRM_SEARCHED_CAROUSEL", (
        f"BAG_002 should advance to BAG_003; got {d.next_node_id}"
    )


def test_bag002_physical_handover_here_you_go() -> None:
    """'here you go' → claim_tag_status: has_claim_tag → BAG_003."""
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_002_PROVIDE_CLAIM_TAG",
        _make_understanding(
            intent_success=True,
            extracted_slots={"claim_tag_status": "has_claim_tag"},
        ),
        player_text="here you go",
    ))
    assert d.branch_type == "success"
    assert d.next_node_id == "BAG_003_CONFIRM_SEARCHED_CAROUSEL"


def test_bag002_explicit_claim_tag_regression() -> None:
    """'Yes, here is my baggage claim tag.' 명시 답변 회귀 — 기존 성공 경로 유지."""
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_002_PROVIDE_CLAIM_TAG",
        _make_understanding(
            intent_success=True,
            extracted_slots={"claim_tag_status": "has_claim_tag"},
        ),
        player_text="Yes, here is my baggage claim tag.",
    ))
    assert d.branch_type == "success"
    assert d.next_node_id == "BAG_003_CONFIRM_SEARCHED_CAROUSEL"


# ---------------------------------------------------------------------------
# BAG_005 BUG #2 회귀: 과거형 이행 확인 인식 (intent recognition fix)
# ---------------------------------------------------------------------------

def test_bag005_past_tense_yeah_i_checked_now() -> None:
    """'yeah I checked now' → customs_hold_acknowledgement: already_checked → BAG_006.

    BUG #2 회귀 테스트: 과거형 이행 확인 표현이 allowed_slot_value(already_checked)로
    정규화되어야 함. allowed_slot_values에 already_checked 추가 + LLM 규칙 추가로 수정.
    """
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_acknowledgement": "already_checked"},
        ),
        player_text="yeah I checked now",
    ))
    assert d.branch_type == "success", (
        f"BAG_005 'yeah I checked now' should succeed; got branch_type={d.branch_type}"
    )
    assert d.next_node_id == "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM", (
        f"BAG_005 should advance to BAG_006; got {d.next_node_id}"
    )


def test_bag005_past_tense_i_did() -> None:
    """'I did' → customs_hold_acknowledgement: already_checked → BAG_006."""
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_acknowledgement": "already_checked"},
        ),
        player_text="I did",
    ))
    assert d.branch_type == "success"
    assert d.next_node_id == "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"


def test_bag005_past_tense_yeah_i_did() -> None:
    """'yeah, I did.' → customs_hold_acknowledgement: already_checked → BAG_006."""
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_acknowledgement": "already_checked"},
        ),
        player_text="yeah, I did.",
    ))
    assert d.branch_type == "success"
    assert d.next_node_id == "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"


def test_bag005_future_tense_regression() -> None:
    """'Okay, I'll open it and check.' 미래형 동의 회귀 — 기존 성공 경로 유지."""
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_005_CUSTOMS_HOLD_EXPLANATION",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_acknowledgement": "will_unlock_and_check"},
        ),
        player_text="Okay, I'll open it and check.",
    ))
    assert d.branch_type == "success"
    assert d.next_node_id == "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"


def test_bag005_retry_node_already_checked() -> None:
    """BAG_005_RETRY 노드에서도 already_checked 슬롯 값이 success → BAG_006.

    RETRY 노드도 allowed_slot_values 수정 대상이었으므로 회귀 검증.
    """
    sm = ScenarioStateMachine()
    d = sm.decide(_make_payload(
        "BAG_005_RETRY_CUSTOMS_HOLD_EXPLANATION",
        _make_understanding(
            intent_success=True,
            extracted_slots={"customs_hold_acknowledgement": "already_checked"},
        ),
        player_text="I did",
    ))
    assert d.branch_type == "success", (
        f"BAG_005_RETRY 'I did' should succeed; got branch_type={d.branch_type}"
    )
