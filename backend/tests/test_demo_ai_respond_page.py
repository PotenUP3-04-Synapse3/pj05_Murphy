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


def test_respond_dialog_page_is_served_without_changing_original_demo() -> None:
    client = TestClient(app)

    original = client.get("/demo/ai-respond")
    response = client.get("/respond-dialog")

    assert original.status_code == 200
    assert "Murphy AI Respond Tester" in original.text
    assert response.status_code == 200
    assert "Murphy Respond Dialog" in response.text
    assert 'id="audioFile"' in response.text
    assert 'id="turnJson"' in response.text
    assert 'id="chapterButtons"' in response.text
    assert 'id="transcript"' in response.text
    assert 'id="elapsedTotal"' in response.text
    assert 'id="httpStatus"' in response.text
    assert 'id="sttRuntime"' in response.text
    assert 'id="verdict"' in response.text
    assert 'id="sessionTokens"' in response.text
    assert 'id="sessionCost"' in response.text
    assert 'id="runButton"' in response.text
    assert 'id="quickAudioFile"' in response.text
    assert 'id="quickRecordButton"' in response.text
    assert 'id="quickUseRecordingButton"' in response.text
    assert 'id="continueButton"' in response.text
    assert 'id="runningStopwatch"' in response.text
    assert 'id="realtimeSubtitleText"' in response.text
    assert "Realtime STT Subtitles" in response.text
    assert '"/api/game/ai/stt/stream"' in response.text
    assert '"event_type": "audio_chunk"' in response.text
    assert 'event.event_type === "final_transcript"' in response.text
    assert "submitFinalRealtimeTranscript(refs.quickUseRecordingButton)" in response.text
    assert "turn.audio.transcript = finalTranscript" in response.text
    assert '"transcript_provider": dialogState.realtimeFinalProvider || "elevenlabs_relay"' in response.text
    assert "getUserMedia" in response.text
    assert "submitAudio(audio, refs.continueButton)" in response.text
    assert 'const firstNodeId = "FLIGHT_A_001_SEATMATE_SMALLTALK";' in response.text
    assert 'data-chapter-id="CH0_01_FLIGHT_SMALLTALK"' in response.text
    assert 'data-chapter-id="CH0_03_IMMIGRATION_CHECK"' in response.text
    assert 'data-chapter-id="CH0_04_BAGGAGE_CLAIM"' in response.text
    assert 'data-chapter-id="CH0_05_RESULT"' in response.text
    assert "chapter_id: node.chapter_id" in response.text
    assert 'sceneId: "AIRPLANE_CABIN"' in response.text
    assert 'npcId: "arabella"' in response.text
    assert 'npcId: "hale"' in response.text
    assert 'speaker: "Officer Hale"' in response.text
    assert 'body.npc?.speaker || "Officer Hale"' in response.text
    assert "Officer Miller" not in response.text
    assert 'nextNodeId.startsWith("FLIGHT_")' in response.text
    assert "preferredNpcId" in response.text
    assert "selectedNpc?.start_node_id || chapter.nodeId" in response.text
    assert "startChapter(dialogState.selectedChapterId, selectedNpcId)" in response.text
    assert "function startChapter" in response.text
    assert "Upload WAV" in response.text
    assert "Recorded or Next WAV" in response.text
    assert "Send Recording" in response.text
    assert "submitAudio(dialogState.quickRecordingFile, refs.quickUseRecordingButton)" in response.text
    assert 'id="turnFile"' not in response.text


def test_demo_node_endpoint_returns_safe_node_context() -> None:
    client = TestClient(app)

    purpose = client.get("/api/game/ai/demo/node/IMM_002_PURPOSE")
    duration = client.get("/api/game/ai/demo/node/IMM_003_DURATION")

    assert purpose.status_code == 200
    purpose_body = purpose.json()
    assert purpose_body == {
        "node_id": "IMM_002_PURPOSE",
        "chapter_id": "CH0_03_IMMIGRATION_CHECK",
        "npc_question": "What is the purpose of your visit?",
        "objective_kr": purpose_body["objective_kr"],
        "recommended_expression": "I'm here for tourism.",
        "allowed_next_nodes": [
            "IMM_003_DURATION",
            "IMM_002_RETRY_PURPOSE",
            "IMM_EXTRA_001_CLARIFY_PURPOSE",
            "END_SECONDARY_INSPECTION",
        ],
    }
    assert isinstance(purpose_body["objective_kr"], str)
    assert purpose_body["objective_kr"]
    assert duration.status_code == 200
    assert duration.json()["node_id"] == "IMM_003_DURATION"
    assert duration.json()["npc_question"] == "How long will you be staying?"


def test_session_usage_endpoint_can_filter_by_request_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_respond, "AGENT_RUN_LOG_ROOT", tmp_path)
    log_path = tmp_path / "unified_agent_runs.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "agent_run_id": "old_run",
                        "request_id": "req_old",
                        "session_id": "shared_session",
                        "model": {
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "total_tokens": 150,
                            "estimated_cost_usd": 0.01,
                        },
                    }
                ),
                json.dumps(
                    {
                        "agent_run_id": "current_c",
                        "request_id": "req_current",
                        "session_id": "shared_session",
                        "model": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                            "estimated_cost_usd": 0.001,
                        },
                    }
                ),
                json.dumps(
                    {
                        "agent_run_id": "current_a",
                        "request_id": "req_current",
                        "session_id": "shared_session",
                        "model": {
                            "input_tokens": 20,
                            "output_tokens": 7,
                            "total_tokens": 27,
                            "estimated_cost_usd": 0.0025,
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    response = client.get(
        "/api/game/ai/agent-runs/session-usage",
        params=[
            ("session_id", "shared_session"),
            ("request_ids", "req_current"),
        ],
    )

    assert response.status_code == 200
    assert response.json() == {
        "found": True,
        "sessions": [
            {
                "session_id": "shared_session",
                "agent_run_count": 2,
                "request_count": 1,
                "input_tokens": 30,
                "output_tokens": 12,
                "total_tokens": 42,
                "estimated_cost_usd": 0.0035,
                "models": [],
            }
        ],
    }


def test_session_usage_endpoint_normalizes_alternate_usage_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_respond, "AGENT_RUN_LOG_ROOT", tmp_path)
    log_path = tmp_path / "unified_agent_runs.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "agent_run_id": "run_prompt_completion",
                "request_id": "req_prompt_completion",
                "session_id": "session_prompt_completion",
                "model": {
                    "prompt_tokens": "12",
                    "completion_tokens": "8",
                    "total_tokens": "20",
                    "cost_usd": "0.000009",
                },
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    response = client.get(
        "/api/game/ai/agent-runs/session-usage",
        params={"session_id": "session_prompt_completion"},
    )

    assert response.status_code == 200
    assert response.json()["sessions"][0] == {
        "session_id": "session_prompt_completion",
        "agent_run_count": 1,
        "request_count": 1,
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
        "estimated_cost_usd": 0.000009,
        "models": [],
    }


def test_session_usage_endpoint_sums_top_level_model_usage(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_respond, "AGENT_RUN_LOG_ROOT", tmp_path)
    log_path = tmp_path / "unified_agent_runs.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "agent_run_id": "c_run_1",
                        "request_id": "req_1",
                        "session_id": "session_a",
                        "model": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                            "estimated_cost_usd": 0.001,
                        },
                    }
                ),
                json.dumps(
                    {
                        "agent_run_id": "a_run_1",
                        "request_id": "req_1",
                        "session_id": "session_a",
                        "model": {
                            "input_tokens": 20,
                            "output_tokens": 7,
                            "total_tokens": 27,
                            "estimated_cost_usd": 0.0025,
                        },
                    }
                ),
                json.dumps(
                    {
                        "agent_run_id": "c_run_2",
                        "request_id": "req_2",
                        "session_id": "session_b",
                        "model": {
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "total_tokens": 150,
                            "estimated_cost_usd": 0.01,
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    response = client.get("/api/game/ai/agent-runs/session-usage")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["sessions"] == [
        {
            "session_id": "session_b",
            "agent_run_count": 1,
            "request_count": 1,
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "estimated_cost_usd": 0.01,
            "models": [],
        },
        {
            "session_id": "session_a",
            "agent_run_count": 2,
            "request_count": 1,
            "input_tokens": 30,
            "output_tokens": 12,
            "total_tokens": 42,
            "estimated_cost_usd": 0.0035,
            "models": [],
        },
    ]


def test_session_usage_endpoint_filters_by_session_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_respond, "AGENT_RUN_LOG_ROOT", tmp_path)
    log_path = tmp_path / "unified_agent_runs.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "agent_run_id": "run_a",
                        "request_id": "req_a",
                        "session_id": "session_a",
                        "model": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
                    }
                ),
                json.dumps(
                    {
                        "agent_run_id": "run_b",
                        "request_id": "req_b",
                        "session_id": "session_b",
                        "model": {"input_tokens": 4, "output_tokens": 5, "total_tokens": 9},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    response = client.get(
        "/api/game/ai/agent-runs/session-usage",
        params={"session_id": "session_a"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "found": True,
        "sessions": [
            {
                "session_id": "session_a",
                "agent_run_count": 1,
                "request_count": 1,
                "input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 3,
                "estimated_cost_usd": 0.0,
                "models": [],
            }
        ],
    }


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
                        "session_id": "session_demo",
                        "model": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                            "estimated_cost_usd": 0.001,
                        },
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
                                    "audio_url": "/runtime/audio/edge/demo.wav",
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
    assert body["model_usage"] == {
        "model_name": "",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.001,
    }
    assert [node["tool_name"] for node in body["nodes"]] == [
        "stt_service.transcribe_wav",
        "understanding_agent.analyze_player_text",
        "dev_b_client.evaluate_turn",
        "dev_a_client.generate_dialogue",
        "response_builder.build_unreal_response",
    ]
    assert body["nodes"][0]["output"]["player_text_preview"] == "I'm here to visit my uncle."
    assert body["summary"]["output"]["next_node_id"] == "IMM_003_DURATION"


def test_demo_npc_roster_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/game/ai/demo/npc-roster")
    assert response.status_code == 200
    data = response.json()
    assert "CH0_01_FLIGHT_SMALLTALK" in data
    assert "CH0_03_IMMIGRATION_CHECK" in data
    assert "CH0_04_BAGGAGE_CLAIM" in data
    assert any(npc["id"] == "hale" for npc in data["CH0_03_IMMIGRATION_CHECK"])
    assert any(npc["id"] == "brielle" for npc in data["CH0_04_BAGGAGE_CLAIM"])
    flight_by_id = {npc["id"]: npc for npc in data["CH0_01_FLIGHT_SMALLTALK"]}
    assert flight_by_id["arabella"]["start_node_id"] == "FLIGHT_A_001_SEATMATE_SMALLTALK"
    assert flight_by_id["novak"]["start_node_id"] == "FLIGHT_A_001_SEATMATE_SMALLTALK"
    novak_node = client.get(f"/api/game/ai/demo/node/{flight_by_id['novak']['start_node_id']}")
    assert novak_node.status_code == 200
    baggage_by_id = {npc["id"]: npc for npc in data["CH0_04_BAGGAGE_CLAIM"]}
    assert baggage_by_id["brielle"]["start_node_id"] == "BAG_001_REPORT_MISSING_AT_DESK"
    assert baggage_by_id["dan"]["start_node_id"] == "BAG_005_CUSTOMS_HOLD_EXPLANATION"
    assert baggage_by_id["dan"]["scene_id"] == "JFK_BAGGAGE_CLAIM"


def test_demo_eokkka_options_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/game/ai/demo/eokkka/options")
    assert response.status_code == 200
    data = response.json()
    assert "locations" in data
    assert "customs_items" in data
    assert len(data["locations"]) > 0
    assert len(data["customs_items"]) > 0


def test_demo_eokkka_assign_endpoint() -> None:
    client = TestClient(app)

    # 1. Deterministic assignment by level
    response_lvl5 = client.get("/api/game/ai/demo/eokkka/assign?level=5")
    assert response_lvl5.status_code == 200
    data_lvl5_a = response_lvl5.json()

    response_lvl5_b = client.get("/api/game/ai/demo/eokkka/assign?level=5")
    data_lvl5_b = response_lvl5_b.json()

    # Must be deterministic (same output for same seed level)
    assert data_lvl5_a == data_lvl5_b
    assert "assigned_visit_location" in data_lvl5_a
    assert "random_customs_item" in data_lvl5_a

    # 2. Random assignment when no level is given
    response_rand = client.get("/api/game/ai/demo/eokkka/assign")
    assert response_rand.status_code == 200
    data_rand = response_rand.json()
    assert "assigned_visit_location" in data_rand
    assert "random_customs_item" in data_rand
