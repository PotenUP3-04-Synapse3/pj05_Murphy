import json
from collections.abc import Generator

import pytest

from backend.app.schemas.game_turn import MockAudioInput, PrePrototypeRequest, UnrealTurnRequest
from backend.app.services.service_c.orchestrator import Orchestrator
from backend.app.services.service_c.settings_service import get_settings


@pytest.fixture(autouse=True)
def _use_deterministic_runtime_modes(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("MURPHY_STT_MODE", "mock")
    monkeypatch.setenv("MURPHY_TTS_MODE", "fake")
    monkeypatch.setenv("MURPHY_NPC_DIALOGUE_MODE", "rule")
    monkeypatch.setenv("MURPHY_UNDERSTANDING_MODE", "rule")
    monkeypatch.setenv("DEV_B_FEEDBACK_LLM_MODE", "rule")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_developer_c_graph_exposes_beginner_readable_state_and_compiled_langgraph() -> None:
    from backend.app.graphs.graph import (
        DEVELOPER_C_GRAPH_NODE_NAMES,
        DeveloperCTurnState,
        build_developer_c_graph,
    )

    graph_app = build_developer_c_graph()

    assert callable(graph_app.invoke)
    assert list(DEVELOPER_C_GRAPH_NODE_NAMES) == [
        "start_agent_run",
        "transcribe_audio",
        "load_node_context",
        "understand_player_text",
        "evaluate_dev_b_policy",
        "validate_dev_b_policy",
        "record_error_capture",
        "generate_dev_a_dialogue",
        "build_unreal_response",
        "validate_unreal_response",
        "finish_agent_run",
    ]
    assert set(DeveloperCTurnState.__annotations__) >= {
        "request",
        "normalized_input",
        "node_context",
        "understanding",
        "dev_b_input",
        "dev_b_output",
        "transition",
        "logging_summary",
        "dev_a_output",
        "response",
        "timing_ms",
        "turn_started",
        "tools",
    }


def test_orchestrator_runs_turn_through_langgraph_tools_and_records_graph_metadata(tmp_path) -> None:
    from backend.app.tools.tool_c.developer_c_graph_tools import DeveloperCGraphTools

    orchestrator = Orchestrator(agent_run_root=tmp_path)

    response = orchestrator.run_turn(_preprototype_request())

    records = [
        json.loads(line)
        for line in (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    developer_c_record = next(record for record in records if record["owner"] == "developer_c")

    assert isinstance(orchestrator.graph_tools, DeveloperCGraphTools)
    assert response.next_node_id == "IMM_003_DURATION"
    assert developer_c_record["metadata"]["runtime"]["orchestrator"] == "langgraph"
    assert developer_c_record["metadata"]["runtime"]["graph_name"] == "developer_c_turn_graph"
    assert developer_c_record["metadata"]["runtime"]["tool_style"] == "developer_c_graph_tools"
    assert developer_c_record["metadata"]["runtime"]["graph_nodes"] == [
        "start_agent_run",
        "transcribe_audio",
        "load_node_context",
        "understand_player_text",
        "evaluate_dev_b_policy",
        "validate_dev_b_policy",
        "record_error_capture",
        "generate_dev_a_dialogue",
        "build_unreal_response",
        "validate_unreal_response",
        "finish_agent_run",
    ]


def _preprototype_request(transcript: str = "I'm here for tourism.") -> PrePrototypeRequest:
    return PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(
            {
                "contract_version": "dev_c_unreal_turn.v1",
                "request_id": "req_imm_0001",
                "session": {
                    "session_id": "session_001",
                    "player_id": "player_001",
                    "chapter_id": "CH0_03_IMMIGRATION_CHECK",
                    "scene_id": "JFK_IMMIGRATION_HALL",
                    "current_node_id": "IMM_002_PURPOSE",
                    "turn_index": 2,
                },
                "npc": {
                    "npc_id": "miller",
                    "npc_role": "immigration_officer",
                    "last_npc_message": "What is the purpose of your visit?",
                },
                "audio": {
                    "mime_type": "audio/wav",
                    "sample_rate_hz": 16000,
                    "channels": 1,
                    "duration_ms": 2800,
                    "language_hint": "en-US",
                },
                "player_profile": {
                    "nickname": "Sean",
                    "english_confidence": "beginner",
                    "tier": "Bronze",
                    "travel_speaking_level": "TSL_1_SURVIVAL",
                },
                "scenario_state": {
                    "patience": 100,
                    "suspicion": 0,
                    "retry_count": 0,
                    "hint_count": 0,
                    "previous_fail_count": 0,
                },
                "game_state": {
                    "inventory": ["passport", "boarding_pass", "return_ticket"],
                    "flags": ["arrived_at_jfk", "passport_submitted"],
                    "completed_intents": ["submit_passport"],
                    "current_objective": "State the visit purpose",
                },
                "previous_node_results": [
                    {
                        "node_id": "IMM_001_PASSPORT",
                        "verdict": "SUCCESS",
                        "next_action": "ADVANCE",
                    }
                ],
                "client_allowed_next_nodes": [
                    "IMM_003_DURATION",
                    "IMM_002_RETRY_PURPOSE",
                    "IMM_EXTRA_001_CLARIFY_PURPOSE",
                    "END_SECONDARY_INSPECTION",
                ],
                "client_context": {
                    "platform": "windows",
                    "input_device": "microphone",
                    "locale": "ko-KR",
                    "build_version": "0.1.0",
                },
            }
        ),
        audio=MockAudioInput(
            mock_wav_path="mock://immigration/purpose_tourism.wav",
            transcript=transcript,
        ),
    )
