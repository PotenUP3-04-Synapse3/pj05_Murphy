import json
from collections.abc import Generator
from typing import Any

import pytest

from backend.app.agents.agent_c.understanding_agent import UnderstandingAgent
from backend.app.schemas.game_turn import MockAudioInput, PrePrototypeRequest, UnrealTurnRequest
from backend.app.services.service_c.orchestrator import Orchestrator
from backend.app.services.service_c.settings_service import AppSettings, get_settings


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


def test_orchestrator_appends_unified_agent_run_with_data_flow_events(tmp_path) -> None:
    response = Orchestrator(agent_run_root=tmp_path).run_turn(_preprototype_request())

    records = [
        json.loads(line)
        for line in (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    record = next(item for item in records if item["owner"] == "developer_c")
    developer_b_record = next(item for item in records if item["owner"] == "developer_b")
    tool_names = [
        event.get("tool_name")
        for event in record["events"]
        if event.get("event") == "tool_call"
    ]

    assert response.next_node_id == "IMM_003_DURATION"
    assert len(records) == 2
    assert record["schema_version"] == "unified_agent_run.v1"
    assert record["agent_name"] == "ai_backend_orchestrator"
    assert record["owner"] == "developer_c"
    assert record["request_id"] == "req_imm_0001"
    assert record["session_id"] == "session_001"
    assert record["turn_index"] == 2
    assert record["status"] == "completed"
    assert record["summary"]["output"]["next_node_id"] == "IMM_003_DURATION"
    assert record["metadata"]["data_flow"][0]["from"] == "unreal_request"
    assert record["metadata"]["data_flow"][-1]["to"] == "unreal_response"
    assert tool_names == [
        "stt_service.transcribe_wav",
        "openkb_service.get_node_context",
        "understanding_agent.analyze_player_text",
        "dev_b_client.evaluate_turn",
        "validator.validate_dev_b_policy_output",
        "logging_service.record_error_capture",
        "dev_a_client.generate_dialogue",
        "response_builder.build_unreal_response",
        "validator.validate_unreal_response",
    ]
    dev_b_event = next(event for event in record["events"] if event.get("tool_name") == "dev_b_client.evaluate_turn")
    understanding_event = next(
        event for event in record["events"] if event.get("tool_name") == "understanding_agent.analyze_player_text"
    )
    assert dev_b_event["output_summary"]["branch"]["next_node_id"] == "IMM_003_DURATION"
    assert understanding_event["output_summary"]["understanding_trace"]["mode"] == "rule"
    assert developer_b_record["schema_version"] == "unified_agent_run.v1"
    assert developer_b_record["agent_name"] == "english_level_hint_agent"
    assert developer_b_record["owner"] == "developer_b"
    assert developer_b_record["summary"]["output"]["next_node_id"] == "IMM_003_DURATION"
    assert developer_b_record["summary"]["output"]["feedback_generation_mode"] == "rule"

    readable_log = (tmp_path / "unified_agent_runs.md").read_text(encoding="utf-8")
    assert "## Agent Run: ai_backend_orchestrator / developer_c" in readable_log
    assert "## Agent Run: english_level_hint_agent / developer_b" in readable_log
    assert "understanding_agent.analyze_player_text" in readable_log
    assert "validator.validate_unreal_response" in readable_log


def test_orchestrator_unified_agent_run_includes_understanding_llm_tokens_and_cost(tmp_path) -> None:
    orchestrator = Orchestrator(agent_run_root=tmp_path)
    orchestrator.understanding_agent = UnderstandingAgent(
        settings=AppSettings(murphy_understanding_mode="llm"),
        llm_client=FakeUnderstandingLLMClient(),
    )

    orchestrator.run_turn(_preprototype_request(transcript="I'm here to visit my uncle."))

    records = [
        json.loads(line)
        for line in (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    record = next(item for item in records if item["owner"] == "developer_c")
    understanding_event = next(
        event for event in record["events"] if event.get("tool_name") == "understanding_agent.analyze_player_text"
    )
    understanding_trace = understanding_event["output_summary"]["understanding_trace"]

    assert record["model"] == {
        "model_name": "gpt-4o-mini",
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_tokens": 1500,
        "estimated_cost_usd": 0.00045,
    }
    assert understanding_trace["model_usage"] == record["model"]
    assert understanding_trace["tool_calls"][0]["model_usage"] == record["model"]
    assert understanding_trace["tool_calls"][0]["output_summary"]["estimated_cost_usd"] == 0.00045


def test_orchestrator_agent_run_logs_understanding_incivility_summary(tmp_path) -> None:
    Orchestrator(agent_run_root=tmp_path).run_turn(_preprototype_request(transcript="fuck you"))

    records = [
        json.loads(line)
        for line in (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    record = next(item for item in records if item["owner"] == "developer_c")
    understanding_event = next(
        event for event in record["events"] if event.get("tool_name") == "understanding_agent.analyze_player_text"
    )

    assert understanding_event["output_summary"]["understanding"]["incivility"] == {
        "tier": 3,
        "category": "profanity",
        "source": "rule",
    }


class FakeUnderstandingLLMClient:
    model = "gpt-4o-mini"

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": "state_visit_purpose",
            "intent_success": True,
            "confidence": 0.91,
            "meaning_summary_kr": "The player is visiting family.",
            "emotion": "calm",
            "answer_relevance": "on_topic",
            "ambiguity_type": "none",
            "risk_delta": 0,
            "risk_reason": "No risk expression was found.",
            "risk_tags": [],
            "extracted_slots": {"visit_purpose": "family_visit"},
            "missing_slots": [],
            "needs_clarification": False,
            "__llm_usage": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
            },
        }


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
