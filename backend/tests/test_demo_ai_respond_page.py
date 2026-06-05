import json

from fastapi.testclient import TestClient

from backend.app.api import ai_respond
from backend.app.main import app


def test_demo_ai_respond_page_is_served() -> None:
    client = TestClient(app)

    response = client.get("/demo/ai-respond")

    assert response.status_code == 200
    assert "Murphy AI Respond Tester" in response.text
    assert 'id="audioFile"' in response.text


def test_latest_agent_run_endpoint_returns_compact_node_summaries(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_respond, "AGENT_RUN_LOG_ROOT", tmp_path)
    log_path = tmp_path / "unified_agent_runs.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "agent_run_id": "old_run",
                        "agent_name": "ai_backend_orchestrator",
                        "owner": "developer_c",
                        "request_id": "req_old",
                        "status": "completed",
                        "events": [],
                    }
                ),
                json.dumps(
                    {
                        "agent_run_id": "latest_run",
                        "agent_name": "ai_backend_orchestrator",
                        "owner": "developer_c",
                        "request_id": "req_demo",
                        "status": "completed",
                        "events": [
                            {
                                "event": "tool_call",
                                "status": "completed",
                                "tool_name": "stt_service.transcribe_wav",
                                "input_summary": {"file_name": "uncle.wav"},
                                "output_summary": {
                                    "player_text_preview": "I'm here to visit my uncle.",
                                    "runtime_used": "local",
                                },
                            },
                            {
                                "event": "tool_call",
                                "status": "completed",
                                "tool_name": "understanding_agent.analyze_player_text",
                                "input_summary": {"node_id": "IMM_002_PURPOSE"},
                                "output_summary": {
                                    "understanding": {
                                        "intent": "state_visit_purpose",
                                        "intent_success": True,
                                    }
                                },
                            },
                            {
                                "event": "tool_call",
                                "status": "completed",
                                "tool_name": "dev_b_client.evaluate_turn",
                                "input_summary": {"node_id": "IMM_002_PURPOSE"},
                                "output_summary": {
                                    "evaluation": {"verdict": "SUCCESS"},
                                    "branch": {"next_node_id": "IMM_003_DURATION"},
                                },
                            },
                            {
                                "event": "tool_call",
                                "status": "completed",
                                "tool_name": "dev_a_client.generate_dialogue",
                                "input_summary": {"branch_type": "success"},
                                "output_summary": {
                                    "text_preview": "How long will you stay?",
                                    "audio_url": "/runtime/audio/kokoro/demo.wav",
                                },
                            },
                            {
                                "event": "tool_call",
                                "status": "completed",
                                "tool_name": "response_builder.build_unreal_response",
                                "input_summary": {"request_id": "req_demo"},
                                "output_summary": {
                                    "next_node_id": "IMM_003_DURATION",
                                    "next_action": "ADVANCE",
                                },
                            },
                        ],
                        "summary": {
                            "output": {
                                "next_node_id": "IMM_003_DURATION",
                                "evaluation_verdict": "SUCCESS",
                            }
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    response = client.get("/api/game/ai/agent-runs/latest", params={"request_id": "req_demo"})

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["agent_run_id"] == "latest_run"
    assert body["request_id"] == "req_demo"
    assert [node["tool_name"] for node in body["nodes"]] == [
        "stt_service.transcribe_wav",
        "understanding_agent.analyze_player_text",
        "dev_b_client.evaluate_turn",
        "dev_a_client.generate_dialogue",
        "response_builder.build_unreal_response",
    ]
    assert body["nodes"][0]["output"]["player_text_preview"] == "I'm here to visit my uncle."
    assert body["summary"]["output"]["next_node_id"] == "IMM_003_DURATION"
