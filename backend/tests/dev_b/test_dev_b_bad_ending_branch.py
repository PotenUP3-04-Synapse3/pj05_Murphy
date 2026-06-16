from __future__ import annotations

import json
from pathlib import Path

from backend.app.agents.agent_b.english_level_hint_agent import EnglishLevelHintAgent
from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    HintPolicy,
    InputSource,
    NodeContext,
    PlayerProfile,
    PreviousNodeResult,
    ScenarioState,
    UnderstandingOutput,
)
from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter
from backend.app.services.service_b.final_result_score_policy import FinalResultScorePolicy

from pydantic import BaseModel, Field

class IncivilityClassification(BaseModel):
    tier: int = Field(0, ge=0, le=3)
    detected_terms: list[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    category: str = "none"
    source: str = "none"

class MockUnderstandingOutput(UnderstandingOutput):
    incivility: IncivilityClassification | None = None

class MockDevBPolicyInput(DevBPolicyInput):
    understanding: MockUnderstandingOutput

SCENARIO_NODE_PATH = Path("backend/app/data/scenario_nodes.json")

def _node_context(node_id: str = "IMM_002_PURPOSE") -> NodeContext:
    node_data = json.loads(SCENARIO_NODE_PATH.read_text(encoding="utf-8"))
    node = node_data["nodes"][node_id]
    return NodeContext(
        node_id=node["node_id"],
        scenario_id=node_data["scenario_id"],
        chapter_id=node["chapter_id"],
        node_type=node["node_type"],
        transition=node.get("transition"),
        npc_question=node["npc_question"],
        npc_question_goal=node["npc_question_goal"],
        objective_kr=node["objective_kr"],
        required_intents=node["required_intents"],
        required_slots=node["required_slots"],
        optional_slots=node["optional_slots"],
        critical_slots=node["critical_slots"],
        allowed_slot_values=node["allowed_slot_values"],
        risk_keywords=node["risk_keywords"],
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

def _policy_input_with_incivility(
    *,
    incivility_tier: int | None = None,
    player_text: str = "I'm here for tourism.",
    node_id: str = "IMM_002_PURPOSE",
) -> DevBPolicyInput:
    context = _node_context(node_id)
    
    incivility = None
    if incivility_tier is not None:
        incivility = IncivilityClassification(
            tier=incivility_tier,
            detected_terms=["test_term"] if incivility_tier > 0 else [],
            confidence=0.9,
            category="profanity" if incivility_tier >= 3 else "rudeness",
            source="rule"
        )
        
    under = MockUnderstandingOutput(
        intent=context.required_intents[0] if context.required_intents else "state_travel_purpose",
        intent_success=True,
        confidence=0.92,
        meaning_summary_kr="Player answered description.",
        emotion="neutral",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=0,
        risk_reason="No risk.",
        risk_tags=[],
        extracted_slots={"visit_purpose": "tourism"},
        missing_slots=[],
        needs_clarification=False,
        incivility=incivility,
    )

    return MockDevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_dev_b_test",
        session_id="session_dev_b_test",
        player_id="player_dev_b_test",
        chapter_id=context.chapter_id,
        scene_id="JFK_IMMIGRATION_HALL",
        current_node_id=context.node_id,
        turn_index=2,
        player_text=player_text,
        input_source=InputSource(
            input_type="voice",
            stt_confidence=0.9,
            language_detected="en-US",
            needs_repeat=False,
        ),
        player_profile=PlayerProfile(
            nickname="Sean",
            english_confidence="beginner",
            tier="Bronze",
            travel_speaking_level="TSL_1_SURVIVAL",
        ),
        scenario_state=ScenarioState(
            patience=100,
            suspicion=0,
            retry_count=0,
            hint_count=0,
            previous_fail_count=0,
            completed_intents=["submit_passport"],
        ),
        node_context=context,
        understanding=under,
        previous_node_results=[
            PreviousNodeResult(
                node_id="IMM_001_PASSPORT",
                verdict="SUCCESS",
                next_action="ADVANCE",
                feedback_tags=["passport_submitted"],
            )
        ],
        client_allowed_next_nodes=context.allowed_next_nodes,
    )

def test_incivility_t3_triggers_immediate_bad_ending(tmp_path: Path) -> None:
    agent = EnglishLevelHintAgent(openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"))
    payload = _policy_input_with_incivility(incivility_tier=3)
    
    result = agent.evaluate_turn(payload)
    
    assert result.branch.branch_type == "bad_end"
    assert result.branch.next_action == "COMPLETE_CHAPTER"
    assert result.branch.next_node_id == "IMM_BAD_END_VERBAL_ABUSE"
    assert result.evaluation.verdict == "FAIL"
    assert "verbal_abuse" in result.evaluation.feedback_tags
    assert result.npc_emotion == "Anger"
    assert result.out_game_feedback_seed.include_in_final_report is True
    assert "verbal_conduct_card" in result.out_game_feedback_seed.focus_on_form_targets

def test_incivility_t2_once_does_not_trigger_bad_ending(tmp_path: Path) -> None:
    agent = EnglishLevelHintAgent(openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"))
    payload = _policy_input_with_incivility(incivility_tier=2)
    
    result = agent.evaluate_turn(payload)
    
    # T2 once should just progress normally using the normal policy graph
    assert result.branch.branch_type != "bad_end"
    assert agent._get_incivility_t2_streak(payload) == 1

def test_incivility_t2_twice_consecutively_triggers_bad_ending(tmp_path: Path) -> None:
    agent = EnglishLevelHintAgent(openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"))
    payload1 = _policy_input_with_incivility(incivility_tier=2)
    payload2 = _policy_input_with_incivility(incivility_tier=2)
    
    # Turn 1: T2 (streak becomes 1)
    result1 = agent.evaluate_turn(payload1)
    assert result1.branch.branch_type != "bad_end"
    
    # Turn 2: T2 (streak becomes 2 -> triggers Bad Ending)
    result2 = agent.evaluate_turn(payload2)
    assert result2.branch.branch_type == "bad_end"
    assert result2.branch.next_node_id == "IMM_BAD_END_VERBAL_ABUSE"

def test_incivility_t2_then_normal_resets_streak(tmp_path: Path) -> None:
    agent = EnglishLevelHintAgent(openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"))
    payload1 = _policy_input_with_incivility(incivility_tier=2)
    payload2 = _policy_input_with_incivility(incivility_tier=0)
    payload3 = _policy_input_with_incivility(incivility_tier=2)
    
    # Turn 1: T2
    agent.evaluate_turn(payload1)
    assert agent._get_incivility_t2_streak(payload1) == 1
    
    # Turn 2: T0 (resets streak)
    agent.evaluate_turn(payload2)
    assert agent._get_incivility_t2_streak(payload2) == 0
    
    # Turn 3: T2 (streak becomes 1, no bad ending)
    result3 = agent.evaluate_turn(payload3)
    assert result3.branch.branch_type != "bad_end"

def test_incivility_none_behaves_normally(tmp_path: Path) -> None:
    agent = EnglishLevelHintAgent(openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"))
    payload = _policy_input_with_incivility(incivility_tier=None)
    
    result = agent.evaluate_turn(payload)
    assert result.branch.branch_type == "success"

def test_verbal_abuse_causes_comic_fail_recommendation(tmp_path: Path) -> None:
    agent = EnglishLevelHintAgent(openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"))
    payload = _policy_input_with_incivility(incivility_tier=3)
    
    result = agent.evaluate_turn(payload)
    assert result.openkb_write is not None
    assert result.openkb_write.succeeded is True
    
    # Read the records and run the score policy
    writer = agent.openkb_writer
    assert isinstance(writer, OpenKBFeedbackWriter)
    from backend.app.services.service_b.final_result_score_policy import OpenKBFinalResultRecordReader
    reader = OpenKBFinalResultRecordReader(runtime_root=writer.runtime_root)
    records = reader.read_session_records(payload.session_id)
    
    score_policy = FinalResultScorePolicy()
    final_result = score_policy.build_result(records)
    
    assert final_result.final_recommendation == "COMIC_FAIL"
    assert "verbal_abuse" in final_result.reason_tags
