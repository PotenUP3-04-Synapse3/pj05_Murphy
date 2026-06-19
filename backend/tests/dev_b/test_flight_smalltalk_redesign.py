import json
from pathlib import Path

from backend.app.schemas.game_turn import IncivilityClassification
from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import FlightSmallTalkDiagnosticPolicy
from backend.app.services.service_b.level_adaptation_controller import LevelAdaptationController
from backend.tests.dev_b.test_developer_b_policy_engine import _policy_input, _node_context


def test_flight_smalltalk_skip_request(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="Skip this chapter.",
        confidence=0.8,
    )
    # Set skip_requested to True
    payload.skip_requested = True
    
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=tmp_path / "openkb" / "dev_b")
    decision = policy.decide_conversational(payload)
    
    assert decision.next_node_id == "FLIGHT_999_COMPLETE"
    assert decision.next_action == "COMPLETE_CHAPTER"
    assert decision.branch_type == "success"
    assert decision.cumulative_confidence == 0.1  # Low confidence because it's first turn (<3 MIN_TURNS)


def test_flight_smalltalk_early_skip_low_confidence(tmp_path: Path) -> None:
    # 1. 2 turns -> early skip -> confidence = 0.1
    runtime_root = tmp_path / "openkb" / "dev_b"
    runtime_root.mkdir(parents=True, exist_ok=True)
    jsonl_path = runtime_root / "session_dev_b_test.jsonl"
    
    history_record = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "dialogue_seed": {
            "scene": "FLIGHT_A_001_SEATMATE_SMALLTALK",
            "npc_role": "seatmate",
            "surface_goal": "TRAVEL_PURPOSE",
            "hidden_assessment_goal": "a",
            "opening_intent": "a",
            "difficulty_profile": "a",
            "tone_guidance": "a",
            "stop_condition": "a"
        },
        "evaluation": {"verdict": "SUCCESS"},
        "understanding": {"confidence": 0.9}
    }
    
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record) + "\n")
        
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="I want to skip",
        confidence=0.8,
    )
    payload.skip_requested = True
    
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=runtime_root)
    decision = policy.decide_conversational(payload)
    
    assert decision.next_node_id == "FLIGHT_999_COMPLETE"
    assert decision.cumulative_confidence == 0.1
    
    # 2. 3 turns -> skip -> normal confidence calculation (not 0.1)
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record) + "\n")
        f.write(json.dumps(history_record) + "\n")
        f.write(json.dumps(history_record) + "\n")
        
    decision2 = policy.decide_conversational(payload)
    assert decision2.next_node_id == "FLIGHT_999_COMPLETE"
    # unique competency covered is 1 (TRAVEL_PURPOSE), so confidence = 1/5 = 0.2
    assert decision2.cumulative_confidence == 0.2


def test_flight_smalltalk_30_turns_limit(tmp_path: Path) -> None:
    runtime_root = tmp_path / "openkb" / "dev_b"
    runtime_root.mkdir(parents=True, exist_ok=True)
    jsonl_path = runtime_root / "session_dev_b_test.jsonl"
    
    # Write 29 history entries
    history_record = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "dialogue_seed": {"scene": "FLIGHT_A_001_SEATMATE_SMALLTALK", "npc_role": "seatmate", "surface_goal": "TRAVEL_PURPOSE"},
        "evaluation": {"verdict": "SUCCESS"},
        "understanding": {"confidence": 0.9}
    }
    
    with jsonl_path.open("w", encoding="utf-8") as f:
        for _ in range(29):
            f.write(json.dumps(history_record) + "\n")
            
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="Wait",
        confidence=0.8,
    )
    
    # Current turn is the 30th turn
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=runtime_root)
    decision = policy.decide_conversational(payload)
    
    assert decision.next_node_id == "FLIGHT_999_COMPLETE"
    assert decision.next_action == "COMPLETE_CHAPTER"


def test_flight_smalltalk_random_steering(tmp_path: Path) -> None:
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="Yes",
    )
    
    # Repeatedly call probe selection and ensure it is not deterministic
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=tmp_path / "openkb" / "dev_b")
    
    probes_chosen = set()
    for _ in range(100):
        decision = policy.decide_conversational(payload)
        assert decision.selected_probe is not None
        probes_chosen.add(decision.selected_probe["probe_id"])
        
    # We should have chosen multiple different probes, not just the first one
    assert len(probes_chosen) > 1


def test_flight_smalltalk_sensitive_topic_filtering(tmp_path: Path) -> None:
    # Inject a sensitive probe into the policy's probes list
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=tmp_path / "openkb" / "dev_b")
    
    sensitive_probe = {
        "probe_id": "POLITICAL_TEST",
        "target_competency": "politics",
        "difficulty": 2,
        "topic_tag": "politics",
        "coherent_topics": ["politics"],
        "seed_text": "What do you think about the president?"
    }
    
    policy.probes.append(sensitive_probe)
    
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="I'm okay",
    )
    
    # Make 100 choices and ensure POLITICAL_TEST is never chosen
    for _ in range(100):
        decision = policy.decide_conversational(payload)
        assert decision.selected_probe is not None
        assert decision.selected_probe["probe_id"] != "POLITICAL_TEST"


def test_flight_smalltalk_incivility_tier_bad_ending(tmp_path: Path) -> None:
    # 1. Tier 2 immediate bad ending
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(
        node_context=context,
        player_text="Shut up and give me the pen.",
    )
    payload.understanding.incivility = IncivilityClassification(tier=2)
    
    policy = FlightSmallTalkDiagnosticPolicy(runtime_root=tmp_path / "openkb" / "dev_b")
    decision = policy.decide_conversational(payload)
    
    assert decision.verdict == "CRITICAL_FAIL"
    assert decision.branch_type == "bad_end"
    assert decision.next_node_id == "FLIGHT_BAD_END_VERBAL_ABUSE"
    assert decision.next_action == "COMPLETE_CHAPTER"
    
    # 2. Tier 1 first time -> warning
    payload_warn = _policy_input(
        node_context=context,
        player_text="Hey you.",
    )
    payload_warn.understanding.incivility = IncivilityClassification(tier=1)
    
    decision_warn = policy.decide_conversational(payload_warn)
    assert decision_warn.verdict == "FAIL"
    assert decision_warn.branch_type == "warning"
    assert decision_warn.next_node_id == "FLIGHT_A_001_SEATMATE_SMALLTALK"
    assert decision_warn.next_action == "WARNING"
    
    # 3. Tier 1 second time -> bad end
    runtime_root = tmp_path / "openkb" / "dev_b"
    runtime_root.mkdir(parents=True, exist_ok=True)
    jsonl_path = runtime_root / "session_dev_b_test.jsonl"
    
    history_record = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "evaluation": {"verdict": "FAIL"},
        "understanding": {
            "confidence": 0.9,
            "incivility": {"tier": 1}
        }
    }
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record) + "\n")
        
    policy_repeat = FlightSmallTalkDiagnosticPolicy(runtime_root=runtime_root)
    decision_repeat = policy_repeat.decide_conversational(payload_warn)
    
    assert decision_repeat.verdict == "CRITICAL_FAIL"
    assert decision_repeat.branch_type == "bad_end"
    assert decision_repeat.next_node_id == "FLIGHT_BAD_END_VERBAL_ABUSE"


def test_flight_smalltalk_ability_based_level_estimation(tmp_path: Path) -> None:
    runtime_root = tmp_path / "openkb" / "dev_b"
    runtime_root.mkdir(parents=True, exist_ok=True)
    controller = LevelAdaptationController(runtime_root=runtime_root)
    
    # Write history with high rubric scores
    jsonl_path = runtime_root / "session_dev_b_test.jsonl"
    
    # 1. Advanced level test (avg total = 10.0)
    history_record_adv = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "rubric_scores": {"total": 10}
    }
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record_adv) + "\n")
        f.write(json.dumps(history_record_adv) + "\n")
        
    context = _node_context("FLIGHT_A_001_SEATMATE_SMALLTALK")
    payload = _policy_input(node_context=context, player_text="Yes")
    payload.session_id = "session_dev_b_test"
    payload.player_profile.english_confidence = None
    
    level_adv = controller.english_level(payload)
    assert level_adv == "advanced"
    
    # 2. Intermediate level test (avg total = 6.0)
    history_record_int = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "rubric_scores": {"total": 6}
    }
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record_int) + "\n")
        
    level_int = controller.english_level(payload)
    assert level_int == "intermediate"
    
    # 3. Beginner level test (avg total = 2.0)
    history_record_beg = {
        "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
        "rubric_scores": {"total": 2}
    }
    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(history_record_beg) + "\n")
        
    level_beg = controller.english_level(payload)
    assert level_beg == "beginner"
    
    # Clean up test session records
    if jsonl_path.exists():
        jsonl_path.unlink()
