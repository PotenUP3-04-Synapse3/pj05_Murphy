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


def test_developer_c_graph_tools_are_exposed_as_langchain_structured_tools() -> None:
    from langchain_core.tools import StructuredTool

    from backend.app.graphs.graph import DEVELOPER_C_GRAPH_NODE_NAMES, build_initial_developer_c_state
    from backend.app.tools.tool_c.developer_c_graph_tools import DeveloperCGraphTools

    tools = DeveloperCGraphTools()
    state = build_initial_developer_c_state(
        request=_preprototype_request(),
        tools=tools,
    )

    assert set(tools.structured_tools) == set(DEVELOPER_C_GRAPH_NODE_NAMES)
    for node_name in DEVELOPER_C_GRAPH_NODE_NAMES:
        structured_tool = tools.structured_tools[node_name]
        assert isinstance(structured_tool, StructuredTool)
        assert structured_tool.name == f"developer_c_{node_name}"
    assert [tool.name for tool in tools.as_tool_node_tools()] == [
        f"developer_c_{node_name}" for node_name in DEVELOPER_C_GRAPH_NODE_NAMES
    ]

    start_result = tools.invoke_structured_tool("start_agent_run", state)

    assert "agent_run" in start_result
    assert start_result["agent_run"]["metadata"]["runtime"]["tool_style"] == "langchain_structured_tools"


def test_orchestrator_runs_turn_through_structured_tool_wrappers_and_records_graph_metadata(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.graphs.graph import DEVELOPER_C_GRAPH_NODE_NAMES
    from backend.app.tools.tool_c.developer_c_graph_tools import DeveloperCGraphTools

    invoked_node_names: list[str] = []
    original_invoke = DeveloperCGraphTools.invoke_structured_tool

    def invoke_spy(
        self: DeveloperCGraphTools,
        node_name: str,
        state: dict,
    ) -> dict:
        invoked_node_names.append(node_name)
        return original_invoke(self, node_name, state)

    monkeypatch.setattr(DeveloperCGraphTools, "invoke_structured_tool", invoke_spy)

    orchestrator = Orchestrator(agent_run_root=tmp_path)

    response = orchestrator.run_turn(_preprototype_request())

    records = [
        json.loads(line)
        for line in (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    developer_c_record = next(record for record in records if record["owner"] == "developer_c")

    assert isinstance(orchestrator.graph_tools, DeveloperCGraphTools)
    assert response.next_node_id == "IMM_003_DURATION"
    assert invoked_node_names == list(DEVELOPER_C_GRAPH_NODE_NAMES)
    assert developer_c_record["metadata"]["runtime"]["orchestrator"] == "langgraph"
    assert developer_c_record["metadata"]["runtime"]["graph_name"] == "developer_c_turn_graph"
    assert developer_c_record["metadata"]["runtime"]["tool_style"] == "langchain_structured_tools"
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
    assert developer_c_record["metadata"]["runtime"]["structured_tool_names"] == [
        "developer_c_start_agent_run",
        "developer_c_transcribe_audio",
        "developer_c_load_node_context",
        "developer_c_understand_player_text",
        "developer_c_evaluate_dev_b_policy",
        "developer_c_validate_dev_b_policy",
        "developer_c_record_error_capture",
        "developer_c_generate_dev_a_dialogue",
        "developer_c_build_unreal_response",
        "developer_c_validate_unreal_response",
        "developer_c_finish_agent_run",
    ]


def test_developer_c_failed_agent_run_records_structured_error_details(tmp_path) -> None:
    from backend.app.tools.tool_c.developer_c_graph_tools import DeveloperCGraphTools

    request = _preprototype_request()
    tools = DeveloperCGraphTools(agent_run_root=tmp_path)
    tools.start_agent_run_tool({"request": request})

    tools.complete_failed_run(request, ValueError("simulated graph failure"))

    records = [
        json.loads(line)
        for line in (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    developer_c_record = next(record for record in records if record["owner"] == "developer_c")
    failed_event = developer_c_record["events"][-1]

    assert failed_event["status"] == "failed"
    assert failed_event["error_details"] == {
        "error_type": "ValueError",
        "error_message": "simulated graph failure",
        "phase": "developer_c_langgraph",
        "tool_name": "developer_c_turn_graph",
    }
    assert developer_c_record["summary"]["output"]["error_details"] == failed_event["error_details"]


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
