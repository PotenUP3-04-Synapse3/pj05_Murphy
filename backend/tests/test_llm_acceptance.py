from typing import Any

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.services.service_b.scenario_state_machine import ScenarioStateMachine
from backend.app.schemas.game_turn import (
    NodeContext,
    SlotEvidence,
    UnderstandingOutput,
    DevBPolicyInput,
    InputSource,
    PlayerProfile,
    ScenarioState,
    NpcContext,
)
from backend.app.services.service_c.settings_service import AppSettings
from backend.app.services.service_c.openkb_service import OpenKBService

class FakeUnderstandingLLMClient:
    model = "fake-understanding-model"

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.response

def _node_context(node_id: str) -> NodeContext:
    # Use OpenKBService to load real node context
    return OpenKBService().get_node_context("CH0_03_IMMIGRATION_CHECK", node_id)

def test_understanding_agent_accepts_open_slots() -> None:
    # Test that custom occupation "carpenter" is successfully extracted and accepted
    node_ctx = _node_context("IMM_009_OCCUPATION")
    llm_client = FakeUnderstandingLLMClient({
        "intent": "state_occupation",
        "intent_success": True,
        "confidence": 0.95,
        "meaning_summary_kr": "플레이어는 목수라고 대답했다.",
        "emotion": "calm",
        "answer_relevance": "on_topic",
        "ambiguity_type": "none",
        "risk_delta": 0,
        "risk_reason": "No risk.",
        "risk_tags": [],
        "slot_evidence": [
            {
                "slot": "occupation",
                "value": "carpenter",
                "confidence": 0.95,
                "evidence_text": "carpenter",
            }
        ],
        "missing_slots": [],
        "needs_clarification": False,
        "intent_satisfied": True,
        "judgment_reason": "Player answered a custom occupation.",
    })
    
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )
    output = agent.analyze_player_text("I am a carpenter.", node_ctx)
    
    assert output.intent_success is True
    assert output.intent_satisfied is True
    assert output.extracted_slots == {"occupation": "carpenter"}
    assert not output.missing_slots

def test_understanding_agent_rejects_open_slots_on_intent_mismatch() -> None:
    # Test that when intent_satisfied is False, intent_success is overridden to False
    node_ctx = _node_context("IMM_009_OCCUPATION")
    llm_client = FakeUnderstandingLLMClient({
        "intent": "state_occupation",
        "intent_success": True, # LLM tried to fill it, but intent_satisfied is False
        "confidence": 0.85,
        "meaning_summary_kr": "플레이어는 다른 말을 했다.",
        "emotion": "confused",
        "answer_relevance": "off_topic",
        "ambiguity_type": "off_topic_response",
        "risk_delta": 0,
        "risk_reason": "No risk.",
        "risk_tags": [],
        "slot_evidence": [
            {
                "slot": "occupation",
                "value": "something_else",
                "confidence": 0.6,
                "evidence_text": "something_else",
            }
        ],
        "missing_slots": ["occupation"],
        "needs_clarification": True,
        "intent_satisfied": False,
        "judgment_reason": "Player utterance did not satisfy occupation question.",
    })
    
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )
    output = agent.analyze_player_text("I want to eat pizza.", node_ctx)
    
    assert output.intent_success is False
    assert output.intent_satisfied is False

def test_scenario_state_machine_accepts_open_slots() -> None:
    # Test that the state machine accepts custom occupation "carpenter"
    node_ctx = _node_context("IMM_009_OCCUPATION")
    
    under_output = UnderstandingOutput(
        intent="state_occupation",
        intent_success=True,
        confidence=0.95,
        meaning_summary_kr="목수",
        emotion="calm",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=0,
        risk_reason="No risk.",
        risk_tags=[],
        slot_evidence=[
            SlotEvidence(
                slot="occupation",
                value="carpenter",
                confidence=0.95,
                evidence_text="carpenter",
            )
        ],
        extracted_slots={"occupation": "carpenter"},
        missing_slots=[],
        needs_clarification=False,
        intent_satisfied=True,
        judgment_reason="Custom occupation accepted.",
    )
    
    policy_input = DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_test",
        session_id="session_test",
        player_id="player_test",
        chapter_id="CH0_03_IMMIGRATION_CHECK",
        scene_id="JFK_IMMIGRATION_HALL",
        current_node_id="IMM_009_OCCUPATION",
        turn_index=3,
        player_text="I am a carpenter.",
        input_source=InputSource(input_type="voice", stt_confidence=0.9, language_detected="en-US", needs_repeat=False),
        player_profile=PlayerProfile(nickname="Sean", english_confidence="beginner", tier="Bronze", travel_speaking_level="TSL_1_SURVIVAL"),
        scenario_state=ScenarioState(patience=100, suspicion=0, retry_count=0, hint_count=0, previous_fail_count=0, completed_intents=[]),
        node_context=node_ctx,
        understanding=under_output,
        client_allowed_next_nodes=node_ctx.allowed_next_nodes,
    )
    
    sm = ScenarioStateMachine()
    decision = sm.decide(policy_input)
    assert decision.verdict == "SUCCESS"
    assert decision.branch_type == "success"
    assert decision.next_action == "ADVANCE"

def test_scenario_state_machine_rejects_open_slots_if_intent_unsatisfied() -> None:
    node_ctx = _node_context("IMM_009_OCCUPATION")
    
    under_output = UnderstandingOutput(
        intent="state_occupation",
        intent_success=True,
        confidence=0.55,
        meaning_summary_kr="불명확",
        emotion="confused",
        answer_relevance="partially_related",
        ambiguity_type="unclear_required_slot",
        risk_delta=0,
        risk_reason="No risk.",
        risk_tags=[],
        slot_evidence=[],
        extracted_slots={},
        missing_slots=["occupation"],
        needs_clarification=True,
        intent_satisfied=False,
        judgment_reason="Utterance did not answer occupation.",
    )
    
    policy_input = DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_test",
        session_id="session_test",
        player_id="player_test",
        chapter_id="CH0_03_IMMIGRATION_CHECK",
        scene_id="JFK_IMMIGRATION_HALL",
        current_node_id="IMM_009_OCCUPATION",
        turn_index=3,
        player_text="I don't know.",
        input_source=InputSource(input_type="voice", stt_confidence=0.9, language_detected="en-US", needs_repeat=False),
        player_profile=PlayerProfile(nickname="Sean", english_confidence="beginner", tier="Bronze", travel_speaking_level="TSL_1_SURVIVAL"),
        scenario_state=ScenarioState(patience=100, suspicion=0, retry_count=0, hint_count=0, previous_fail_count=0, completed_intents=[]),
        node_context=node_ctx,
        understanding=under_output,
        client_allowed_next_nodes=node_ctx.allowed_next_nodes,
    )
    
    sm = ScenarioStateMachine()
    decision = sm.decide(policy_input)
    assert decision.verdict == "UNCLEAR"
    assert decision.branch_type == "clarify"
    assert decision.next_action == "REASK"

def test_critical_risk_is_preserved() -> None:
    # Test that risk check (illegal_work_intent) still fails even if open slot logic is in play
    node_ctx = _node_context("IMM_009_OCCUPATION")
    
    under_output = UnderstandingOutput(
        intent="state_occupation",
        intent_success=True,
        confidence=0.95,
        meaning_summary_kr="일하러 왔다",
        emotion="nervous",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=30,
        risk_reason="Illegal work intent.",
        risk_tags=["illegal_work_intent"],
        slot_evidence=[],
        extracted_slots={"occupation": "illegal_work"},
        missing_slots=[],
        needs_clarification=False,
        intent_satisfied=True,
        judgment_reason="Declared illegal work intention.",
    )
    
    policy_input = DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_test",
        session_id="session_test",
        player_id="player_test",
        chapter_id="CH0_03_IMMIGRATION_CHECK",
        scene_id="JFK_IMMIGRATION_HALL",
        current_node_id="IMM_009_OCCUPATION",
        turn_index=3,
        player_text="I want to work illegally here.",
        input_source=InputSource(input_type="voice", stt_confidence=0.9, language_detected="en-US", needs_repeat=False),
        player_profile=PlayerProfile(nickname="Sean", english_confidence="beginner", tier="Bronze", travel_speaking_level="TSL_1_SURVIVAL"),
        scenario_state=ScenarioState(patience=100, suspicion=0, retry_count=0, hint_count=0, previous_fail_count=0, completed_intents=[]),
        node_context=node_ctx,
        understanding=under_output,
        client_allowed_next_nodes=node_ctx.allowed_next_nodes,
    )
    
    sm = ScenarioStateMachine()
    decision = sm.decide(policy_input)
    assert decision.verdict == "CRITICAL_FAIL"
    assert decision.branch_type in {"warning", "bad_end"}

def test_stay_duration_strict_rule_validation() -> None:
    # Test that numeric stay_duration still validates values against allowed/parsed categories
    node_ctx = _node_context("IMM_003_DURATION")
    
    # Value "invalid_value" is not standard numeric pattern
    under_output = UnderstandingOutput(
        intent="state_stay_duration",
        intent_success=True,
        confidence=0.9,
        meaning_summary_kr="기간 답변",
        emotion="calm",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=0,
        risk_reason="No risk.",
        risk_tags=[],
        slot_evidence=[],
        extracted_slots={"stay_duration": "invalid_value"},
        missing_slots=[],
        needs_clarification=False,
        intent_satisfied=True,
    )
    
    policy_input = DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_test",
        session_id="session_test",
        player_id="player_test",
        chapter_id="CH0_03_IMMIGRATION_CHECK",
        scene_id="JFK_IMMIGRATION_HALL",
        current_node_id="IMM_003_DURATION",
        turn_index=3,
        player_text="I stay for invalid.",
        input_source=InputSource(input_type="voice", stt_confidence=0.9, language_detected="en-US", needs_repeat=False),
        player_profile=PlayerProfile(nickname="Sean", english_confidence="beginner", tier="Bronze", travel_speaking_level="TSL_1_SURVIVAL"),
        scenario_state=ScenarioState(patience=100, suspicion=0, retry_count=0, hint_count=0, previous_fail_count=0, completed_intents=[]),
        node_context=node_ctx,
        understanding=under_output,
        client_allowed_next_nodes=node_ctx.allowed_next_nodes,
    )
    
    sm = ScenarioStateMachine()
    decision = sm.decide(policy_input)
    # Since stay_duration is numeric, it is validated. "invalid_value" fails check and triggers retry.
    assert decision.verdict == "UNCLEAR"
    assert decision.branch_type == "clarify"
    assert decision.next_action == "REASK"

def test_paraphrased_open_slots_accepted() -> None:
    # Test that a paraphrased answer where evidence_text is not a substring of player_text is accepted for open slots
    node_ctx = _node_context("IMM_009_OCCUPATION")
    llm_client = FakeUnderstandingLLMClient({
        "intent": "state_occupation",
        "intent_success": True,
        "confidence": 0.95,
        "meaning_summary_kr": "집을 짓는 일을 한다고 말했다.",
        "emotion": "calm",
        "answer_relevance": "on_topic",
        "ambiguity_type": "none",
        "risk_delta": 0,
        "risk_reason": "No risk.",
        "risk_tags": [],
        "slot_evidence": [
            {
                "slot": "occupation",
                "value": "carpenter",
                "confidence": 0.95,
                "evidence_text": "carpenter", # not in player_text
            }
        ],
        "missing_slots": [],
        "needs_clarification": False,
        "intent_satisfied": True,
        "judgment_reason": "Paraphrase of carpenter.",
    })
    
    agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=llm_client,
    )
    output = agent.analyze_player_text("I build houses for a living.", node_ctx)
    
    assert output.intent_success is True
    assert output.intent_satisfied is True
    assert output.extracted_slots == {"occupation": "carpenter"}
    assert not output.missing_slots

def test_cash_amount_closed_policy_validation() -> None:
    # Test that cash_amount slot policy is closed and strictly checked
    from backend.app.schemas.slot_policy import get_slot_policy
    assert get_slot_policy("cash_amount") == "closed"
    
    node_ctx = _node_context("IMM_010_CASH")
    # Value "invalid_cash" is not in allowed cash_amount enum candidates
    under_output = UnderstandingOutput(
        intent="state_cash_amount",
        intent_success=True,
        confidence=0.9,
        meaning_summary_kr="자금 답변",
        emotion="calm",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=0,
        risk_reason="No risk.",
        risk_tags=[],
        slot_evidence=[],
        extracted_slots={"cash_amount": "invalid_cash"},
        missing_slots=[],
        needs_clarification=False,
        intent_satisfied=True,
    )
    
    policy_input = DevBPolicyInput(
        contract_version="dev_b_policy.v1",
        request_id="req_test",
        session_id="session_test",
        player_id="player_test",
        chapter_id="CH0_03_IMMIGRATION_CHECK",
        scene_id="JFK_IMMIGRATION_HALL",
        current_node_id="IMM_010_CASH",
        turn_index=3,
        player_text="I have some money.",
        input_source=InputSource(input_type="voice", stt_confidence=0.9, language_detected="en-US", needs_repeat=False),
        player_profile=PlayerProfile(nickname="Sean", english_confidence="beginner", tier="Bronze", travel_speaking_level="TSL_1_SURVIVAL"),
        scenario_state=ScenarioState(patience=100, suspicion=0, retry_count=0, hint_count=0, previous_fail_count=0, completed_intents=[]),
        node_context=node_ctx,
        understanding=under_output,
        client_allowed_next_nodes=node_ctx.allowed_next_nodes,
    )
    
    sm = ScenarioStateMachine()
    decision = sm.decide(policy_input)
    # Since cash_amount is closed, value validation checks against candidates and rejects it.
    assert decision.verdict == "UNCLEAR"
    assert decision.branch_type == "clarify"
    assert decision.next_action == "REASK"

def test_suspicion_data_cleared_on_non_relevant_nodes() -> None:
    from backend.app.integrations.dev_a_npc_dialogue_client import DevANpcDialogueClient
    from backend.app.schemas.game_turn import (
        DevADialogueInput,
        DevBPolicyOutput,
        Evaluation,
        Branch,
        StateDelta,
        ReportItem,
        Scores,
        DialogueSeed,
        RandomCustomsItemContext,
        GameState,
        LevelHint,
        InGameFeedback,
        ErrorCapture,
        OutGameFeedbackSeed,
    )
    
    node_ctx_passport = _node_context("IMM_001_PASSPORT")
    
    under_output = UnderstandingOutput(
        intent="submit_passport",
        intent_success=True,
        confidence=0.95,
        meaning_summary_kr="여권 제출",
        emotion="calm",
        answer_relevance="on_topic",
        ambiguity_type="none",
        risk_delta=0,
        risk_reason="No risk.",
        risk_tags=[],
        extracted_slots={},
        missing_slots=[],
        needs_clarification=False,
        intent_satisfied=True,
    )
    
    dialogue_seed = DialogueSeed(
        scene="JFK_IMMIGRATION_HALL",
        npc_role="immigration_officer",
        surface_goal="ask_passport",
        hidden_assessment_goal="check_passport",
        opening_intent="submit_passport",
        max_turns=6,
        difficulty_profile="beginner",
        tone_guidance="firm",
        stop_condition="",
        suspicion_scope="declaration", # non-relevant scope
        assigned_visit_location="Queens",
        item_name="apples",
        item_id="apples_id",
    )
    
    policy_output = DevBPolicyOutput(
        contract_version="dev_b_policy.v1",
        node_id="IMM_001_PASSPORT",
        evaluation=Evaluation(
            verdict="SUCCESS",
            detected_intents=["submit_passport"],
            required_intents_passed=True,
            filled_slots={},
            missing_slots=[],
            scores=Scores(task_success=100, clarity=100, grammar=100, vocabulary=100, problem_solving=100, politeness=100),
            feedback_tags=[],
        ),
        level_hint=LevelHint(
            english_level="beginner",
            travel_speaking_level="TSL_1_SURVIVAL",
            needs_hint=False,
            hint_level="none",
            hint_type=None,
            hint_kr=None,
            example_en="Here is my passport.",
            recommended_expression="Here is my passport.",
        ),
        in_game_feedback=InGameFeedback(
            show=False,
            feedback_strategy="none",
            timing="during_dialogue_turn",
            priority="low",
            purpose="none",
            focus="none",
            npc_recast_line_candidate=None,
            clarification_prompt_candidate=None,
            elicitation_cue_candidate=None,
            scaffolding_hint=None,
            blocks_progression=False,
        ),
        error_capture=ErrorCapture(should_record=False, storage_format="markdown", markdown_entry=None),
        out_game_feedback_seed=OutGameFeedbackSeed(include_in_final_report=False, openkb_query_tags=[], focus_on_form_targets=[], report_priority="low"),
        dialogue_seed=dialogue_seed,
        branch=Branch(branch_type="success", next_action="ADVANCE", next_node_id="IMM_002_PURPOSE", branch_reason="success", allowed_next_node_checked=True),
        state_delta=StateDelta(patience_delta=0, suspicion_delta=0, retry_count_delta=0, hint_count_delta=0),
        report_item=ReportItem(summary="good", improvement="good", example_answer="good", score_tags=[]),
    )
    
    dialogue_input = DevADialogueInput(
        contract_version="dev_a_dialogue.v1",
        request_id="req_test",
        session_id="session_test",
        current_node_id="IMM_001_PASSPORT",
        player_text="Here is my passport.",
        npc=NpcContext(npc_id="miller", npc_role="immigration_officer", last_npc_message="Passport please."),
        node_context=node_ctx_passport,
        understanding=under_output,
        developer_b_policy=policy_output,
        random_customs_item=RandomCustomsItemContext(item_name="apples", declared=False),
        game_state=GameState(current_objective="Submit passport", random_customs_item=RandomCustomsItemContext(item_name="apples", declared=False), assigned_visit_location="Queens"),
    )
    
    client = DevANpcDialogueClient(use_llm_dialogue=False)
    ld_payload = client._build_level_design_payload(dialogue_input, dialogue_input.npc)
    
    assert ld_payload["random_customs_item"] is None
    assert ld_payload["game_state"]["random_customs_item"] is None
    assert ld_payload["game_state"]["assigned_visit_location"] is None
    
    assert ld_payload["dialogue_seed"]["random_customs_item"] is None
    assert ld_payload["dialogue_seed"]["item_name"] is None
    assert ld_payload["dialogue_seed"]["assigned_visit_location"] is None
    assert ld_payload["dialogue_seed"]["suspicion_scope"] == "none"
