"""Baggage Claim 챕터(CH0_04) 7개 주요 노드별 판정 일관성 결정적 단위 테스트.

목적
----
각 노드에서 충분(sufficient) / 불충분(insufficient) / 무효(invalid) 답변을
합성 UnderstandingOutput으로 주입했을 때 상태머신이 올바른 branch_type과
next_node_id를 반환하는지 검증한다.

특히 BAG_003 캐러셀 회귀:
- allowed_slot_values에 등록된 확인 값 → success
- 모호 답변 → retry/clarify
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.schemas.game_turn import (
    CustomsItemJudgeContext,
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
from backend.app.services.service_c.settings_service import AppSettings

SCENARIO_NODE_PATH = Path("backend/app/data/scenario_nodes.json")
CHAPTER_ID = "CH0_04_BAGGAGE_CLAIM"


# ---------------------------------------------------------------------------
# Helpers (local copies to keep this file self-contained)
# ---------------------------------------------------------------------------

def _load_nodes() -> dict:
    return json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))["nodes"]


def _node_context(node_id: str) -> NodeContext:
    raw = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))
    node = raw["nodes"][node_id]
    return NodeContext(
        node_id=node["node_id"],
        scenario_id=raw["scenario_id"],
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


def _understanding(
    intent_success: bool = True,
    extracted_slots: dict | None = None,
    missing_slots: list[str] | None = None,
    needs_clarification: bool = False,
    risk_delta: int = 0,
    risk_tags: list[str] | None = None,
) -> UnderstandingOutput:
    return UnderstandingOutput(
        intent="test_intent",
        intent_success=intent_success,
        confidence=0.9,
        meaning_summary_kr="테스트",
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


def _state(patience: int = 100, retry_count: int = 0, hint_count: int = 0) -> ScenarioState:
    return ScenarioState(
        patience=patience,
        suspicion=0,
        retry_count=retry_count,
        hint_count=hint_count,
        previous_fail_count=0,
        completed_intents=[],
    )


def _payload(
    node_id: str,
    u: UnderstandingOutput,
    state: ScenarioState | None = None,
    player_text: str = "test",
    random_customs_item: RandomCustomsItemContext | None = None,
) -> DevBPolicyInput:
    ctx = _node_context(node_id)
    return DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="node_test",
        session_id="node_test",
        player_id="node_test",
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
            nickname="NodeTester",
            english_confidence="beginner",
            tier="Silver",
            travel_speaking_level="TSL_2_FUNCTIONAL",
        ),
        scenario_state=state or _state(),
        node_context=ctx,
        understanding=u,
        random_customs_item=random_customs_item,
    )


# ---------------------------------------------------------------------------
# BAG_001: 분실 신고
# ---------------------------------------------------------------------------

class TestBag001ReportMissing:
    """BAG_001_REPORT_MISSING_AT_DESK 판정 일관성."""

    SM = ScenarioStateMachine()

    def test_sufficient_answer_succeeds(self) -> None:
        """충분한 분실 신고 → success, 다음 노드 BAG_002."""
        d = self.SM.decide(_payload(
            "BAG_001_REPORT_MISSING_AT_DESK",
            _understanding(
                intent_success=True,
                extracted_slots={"missing_bag_statement": "my_bag_is_missing"},
            ),
        ))
        assert d.branch_type == "success"
        assert d.next_node_id == "BAG_002_PROVIDE_CLAIM_TAG"

    def test_insufficient_triggers_retry(self) -> None:
        """필수 슬롯 누락 → retry/clarify."""
        d = self.SM.decide(_payload(
            "BAG_001_REPORT_MISSING_AT_DESK",
            _understanding(
                intent_success=False,
                missing_slots=["missing_bag_statement"],
            ),
            state=_state(patience=80, retry_count=0),
        ))
        assert d.branch_type in {"retry", "clarify", "hint"}, (
            f"Expected retry/clarify/hint, got {d.branch_type}"
        )

    def test_patience_exhausted_bad_end(self) -> None:
        """(patience<=0 OR retry_count>=5) AND hint_count>=1 → bad_end."""
        d = self.SM.decide(_payload(
            "BAG_001_REPORT_MISSING_AT_DESK",
            _understanding(intent_success=False, missing_slots=["missing_bag_statement"]),
            state=_state(patience=0, retry_count=5, hint_count=1),
        ))
        assert d.branch_type == "bad_end"
        assert d.next_node_id == "END_BAGGAGE_REPORT_INCOMPLETE"


# ---------------------------------------------------------------------------
# BAG_002: 클레임태그 제공
# ---------------------------------------------------------------------------

class TestBag002ClaimTag:
    """BAG_002_PROVIDE_CLAIM_TAG 판정 일관성."""

    SM = ScenarioStateMachine()

    def test_tag_provided_succeeds(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_002_PROVIDE_CLAIM_TAG",
            _understanding(
                intent_success=True,
                extracted_slots={"claim_tag_status": "tag_provided"},
            ),
        ))
        assert d.branch_type == "success"
        assert d.next_node_id == "BAG_003_CONFIRM_SEARCHED_CAROUSEL"

    def test_tag_not_provided_retries(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_002_PROVIDE_CLAIM_TAG",
            _understanding(
                intent_success=False,
                missing_slots=["claim_tag_status"],
            ),
            state=_state(patience=60, retry_count=1),
        ))
        assert d.branch_type in {"retry", "clarify", "hint"}

    def test_retry_limit_ends_flow(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_002_PROVIDE_CLAIM_TAG",
            _understanding(intent_success=False, missing_slots=["claim_tag_status"]),
            state=_state(patience=0, retry_count=5, hint_count=1),
        ))
        assert d.branch_type == "bad_end"
        assert "END_" in d.next_node_id or "BAD_END" in d.next_node_id


# ---------------------------------------------------------------------------
# BAG_003: 캐러셀 확인 (회귀 핵심)
# ---------------------------------------------------------------------------

class TestBag003Carousel:
    """BAG_003_CONFIRM_SEARCHED_CAROUSEL 판정 + 캐러셀 회귀."""

    SM = ScenarioStateMachine()

    @pytest.mark.parametrize("slot_value", [
        "searched_carefully",
        "waited_until_stopped",
        "checked_twice",
    ])
    def test_allowed_slot_value_succeeds(self, slot_value: str) -> None:
        """allowed_slot_values 내 정상 확인 값 → success."""
        d = self.SM.decide(_payload(
            "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
            _understanding(
                intent_success=True,
                extracted_slots={"carousel_search_confirmation": slot_value},
            ),
        ))
        assert d.branch_type == "success", (
            f"slot_value={slot_value!r}: expected success, got {d.branch_type}"
        )
        assert d.next_node_id == "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD"

    def test_ambiguous_answer_triggers_clarify(self) -> None:
        """'maybe it was there' 같은 모호 답변 → retry/clarify (회귀)."""
        d = self.SM.decide(_payload(
            "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
            _understanding(
                intent_success=False,
                extracted_slots={},
                missing_slots=["carousel_search_confirmation"],
                needs_clarification=True,
            ),
            player_text="Maybe it was there, I'm not sure.",
        ))
        assert d.branch_type in {"retry", "clarify", "hint"}, (
            f"Ambiguous answer should not succeed; got {d.branch_type}"
        )

    def test_early_departure_triggers_bad(self) -> None:
        """'I just left' (risk keyword) + patience=0 + hint_count>=1 → bad_end."""
        d = self.SM.decide(_payload(
            "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
            _understanding(
                intent_success=False,
                missing_slots=["carousel_search_confirmation"],
            ),
            state=_state(patience=0, retry_count=5, hint_count=1),
            player_text="I just left the carousel area.",
        ))
        assert d.branch_type == "bad_end"

    def test_success_never_skips_bag004(self) -> None:
        """BAG_003 success가 BAG_004를 건너뛰지 않음 (조기통과 방지)."""
        d = self.SM.decide(_payload(
            "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
            _understanding(
                intent_success=True,
                extracted_slots={"carousel_search_confirmation": "searched_carefully"},
            ),
        ))
        assert d.next_node_id == "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD", (
            f"BAG_003 must not skip BAG_004; got {d.next_node_id}"
        )


# ---------------------------------------------------------------------------
# BAG_004: 리디렉트 수용
# ---------------------------------------------------------------------------

class TestBag004Redirect:
    """BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD 판정 일관성."""

    SM = ScenarioStateMachine()

    def test_acknowledged_succeeds(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
            _understanding(
                intent_success=True,
                extracted_slots={"customs_hold_redirect_acknowledgement": "understood"},
            ),
        ))
        assert d.branch_type == "success"
        assert d.next_node_id == "BAG_005_CUSTOMS_HOLD_EXPLANATION"

    def test_ignored_retries(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
            _understanding(
                intent_success=False,
                missing_slots=["customs_hold_redirect_acknowledgement"],
            ),
            state=_state(patience=70, retry_count=0),
        ))
        assert d.branch_type in {"retry", "clarify", "hint"}


# ---------------------------------------------------------------------------
# BAG_005: 검사 동의
# ---------------------------------------------------------------------------

class TestBag005CustomsHold:
    """BAG_005_CUSTOMS_HOLD_EXPLANATION 판정 일관성."""

    SM = ScenarioStateMachine()

    def test_acknowledged_succeeds(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_005_CUSTOMS_HOLD_EXPLANATION",
            _understanding(
                intent_success=True,
                extracted_slots={"customs_hold_acknowledgement": "acknowledged"},
            ),
        ))
        assert d.branch_type == "success"
        assert d.next_node_id == "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"

    def test_denial_retries(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_005_CUSTOMS_HOLD_EXPLANATION",
            _understanding(
                intent_success=False,
                missing_slots=["customs_hold_acknowledgement"],
            ),
            state=_state(patience=50, retry_count=1),
        ))
        assert d.branch_type in {"retry", "clarify", "hint"}


# ---------------------------------------------------------------------------
# BAG_007: 통관
# ---------------------------------------------------------------------------

class TestBag007Clearance:
    """BAG_007_CUSTOMS_CLEARANCE 판정 일관성."""

    SM = ScenarioStateMachine()

    def test_acknowledged_succeeds(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_007_CUSTOMS_CLEARANCE",
            _understanding(
                intent_success=True,
                extracted_slots={"customs_clearance_acknowledgement": "acknowledged"},
            ),
        ))
        assert d.branch_type == "success"
        assert d.next_node_id == "BAG_999_COMPLETE"

    def test_insufficient_retries(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_007_CUSTOMS_CLEARANCE",
            _understanding(
                intent_success=False,
                missing_slots=["customs_clearance_acknowledgement"],
            ),
            state=_state(patience=60, retry_count=1),
        ))
        assert d.branch_type in {"retry", "clarify", "hint"}

    def test_retry_limit_bad_end(self) -> None:
        d = self.SM.decide(_payload(
            "BAG_007_CUSTOMS_CLEARANCE",
            _understanding(intent_success=False, missing_slots=["customs_clearance_acknowledgement"]),
            state=_state(patience=0, retry_count=5, hint_count=1),
        ))
        assert d.branch_type == "bad_end"


# ---------------------------------------------------------------------------
# 공통 불변식: allowed_next_nodes 준수
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id,intent_success,slots,expected_next_candidates", [
    (
        "BAG_001_REPORT_MISSING_AT_DESK", True,
        {"missing_bag_statement": "my_bag_is_missing"},
        ["BAG_002_PROVIDE_CLAIM_TAG"],
    ),
    (
        "BAG_002_PROVIDE_CLAIM_TAG", True,
        {"claim_tag_status": "tag_provided"},
        ["BAG_003_CONFIRM_SEARCHED_CAROUSEL"],
    ),
    (
        "BAG_003_CONFIRM_SEARCHED_CAROUSEL", True,
        {"carousel_search_confirmation": "searched_carefully"},
        ["BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD"],
    ),
    (
        "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD", True,
        {"customs_hold_redirect_acknowledgement": "understood"},
        ["BAG_005_CUSTOMS_HOLD_EXPLANATION"],
    ),
    (
        "BAG_005_CUSTOMS_HOLD_EXPLANATION", True,
        {"customs_hold_acknowledgement": "acknowledged"},
        ["BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM"],
    ),
    (
        "BAG_007_CUSTOMS_CLEARANCE", True,
        {"customs_clearance_acknowledgement": "acknowledged"},
        ["BAG_999_COMPLETE"],
    ),
])
def test_next_node_within_allowed(
    node_id: str,
    intent_success: bool,
    slots: dict,
    expected_next_candidates: list[str],
) -> None:
    """success branch의 next_node_id가 allowed_next_nodes 내에 있는지 검증."""
    raw = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))
    allowed = raw["nodes"][node_id]["allowed_next_nodes"]

    sm = ScenarioStateMachine()
    d = sm.decide(_payload(
        node_id,
        _understanding(intent_success=intent_success, extracted_slots=slots),
    ))
    assert d.next_node_id in allowed, (
        f"{node_id}: next_node_id={d.next_node_id!r} not in allowed_next_nodes={allowed}"
    )
    if intent_success:
        assert d.next_node_id in expected_next_candidates, (
            f"{node_id}: expected one of {expected_next_candidates}, got {d.next_node_id}"
        )


# ---------------------------------------------------------------------------
# BAG_003 B-1 회귀: 실제 UnderstandingAgent(rule 모드)를 거치는 판정 검증
#
# 기존 TestBag003Carousel은 추출된 슬롯을 직접 주입해 상태머신만 테스트.
# 이 클래스는 실제 understanding agent를 통과해 슬롯이 제대로 추출되는지 검증.
# (B-1 수정 = LLM 프롬프트만 변경했으므로, rule 모드 확인 범위는 canonical 표현에 한정)
# ---------------------------------------------------------------------------

class TestBag003CarouselAgentLevel:
    """BAG_003 B-1 회귀: rule-mode agent가 carousel 확인 표현을 올바르게 추출하는지."""

    AGENT = UnderstandingAgent(settings=AppSettings(murphy_understanding_mode="rule"))
    SM = ScenarioStateMachine()
    NODE_ID = "BAG_003_CONFIRM_SEARCHED_CAROUSEL"

    @pytest.mark.parametrize("phrase,expected_slot_value", [
        ("I checked carefully", "searched_carefully"),
        ("I searched carefully", "searched_carefully"),
        ("I looked carefully", "searched_carefully"),
        ("I waited until it stopped", "waited_until_stopped"),
        ("I waited for the carousel to stop", "waited_until_stopped"),
        ("I checked twice", "checked_twice"),
        ("I looked twice", "checked_twice"),
    ])
    def test_canonical_phrase_extracts_slot(self, phrase: str, expected_slot_value: str) -> None:
        """Rule-mode: canonical 확인 표현 → carousel_search_confirmation 슬롯 추출."""
        ctx = _node_context(self.NODE_ID)
        result = self.AGENT.analyze_player_text(phrase, ctx)
        extracted = (result.extracted_slots or {}).get("carousel_search_confirmation")
        assert extracted == expected_slot_value, (
            f"'{phrase}': expected slot={expected_slot_value!r}, got {extracted!r}"
        )

    @pytest.mark.parametrize("phrase,expected_slot_value", [
        ("I checked carefully", "searched_carefully"),
        ("I checked twice", "checked_twice"),
    ])
    def test_canonical_phrase_full_pipeline_succeeds(self, phrase: str, expected_slot_value: str) -> None:
        """Rule-mode agent + state machine: canonical 표현 → 전체 파이프라인 success."""
        ctx = _node_context(self.NODE_ID)
        understanding = self.AGENT.analyze_player_text(phrase, ctx)
        d = self.SM.decide(_payload(
            self.NODE_ID,
            understanding,
            player_text=phrase,
        ))
        assert d.branch_type == "success", (
            f"'{phrase}': full pipeline should succeed, got branch_type={d.branch_type!r}, "
            f"extracted_slots={understanding.extracted_slots!r}"
        )
        assert d.next_node_id == "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD"

    def test_vague_phrase_does_not_succeed(self) -> None:
        """Rule-mode: 모호한 확인 답변 → 슬롯 미추출 → success 아님 (B-1 회귀 방지)."""
        ctx = _node_context(self.NODE_ID)
        phrase = "I don't know, maybe it was there."
        understanding = self.AGENT.analyze_player_text(phrase, ctx)
        d = self.SM.decide(_payload(self.NODE_ID, understanding, player_text=phrase))
        assert d.branch_type != "success", (
            f"Vague answer should not succeed; got {d.branch_type!r}"
        )

    def test_yes_alone_requires_llm_mode(self) -> None:
        """Rule-mode: 'yes' 단독 답변은 슬롯 미매핑 → success 아님.
        B-1 수정은 LLM 프롬프트 전용이므로 rule 모드에서 'yes'는 여전히 통과 안 됨.
        """
        ctx = _node_context(self.NODE_ID)
        understanding = self.AGENT.analyze_player_text("yes", ctx)
        extracted = (understanding.extracted_slots or {}).get("carousel_search_confirmation")
        assert extracted is None, (
            f"Rule-mode 'yes' should not extract carousel slot (LLM-only fix); got {extracted!r}"
        )
