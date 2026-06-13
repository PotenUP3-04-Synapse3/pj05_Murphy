import json
import wave

from backend.app.middleware.middleware_a.npc_dialogue_agent_run_middleware import (
    NPCDialogueAgentRunMiddleware,
)
from backend.app.services.service_a.npc_dialogue_agent_run_store import (
    NPCDialogueAgentRunStore,
)
from backend.app.services.service_a.tts_provider_service import ElevenLabsTTSProvider
from backend.app.services.service_a.voice_output_service import build_voice_output_from_level_design
from backend.app.services.service_a.tts_provider_service import TTSProviderRequest
from backend.app.services.shared.agent_run_log_store import AgentRunLogStore
from backend.app.services.shared.agent_run_markdown_formatter import format_agent_run_markdown
from backend.app.tools.tool_a.npc_dialogue_artifact_tool import (
    build_npc_dialogue_artifact,
    build_user_visible_run_summary,
)
from backend.app.tools.tool_a.npc_dialogue_cost_tool import estimate_openai_cost_usd
from backend.app.tools.tool_a.npc_dialogue_evidence_tool import (
    build_npc_dialogue_evidence_summary,
)


def test_build_npc_dialogue_evidence_summary_uses_short_traceable_snippet() -> None:
    payload = {
        "chapter_id": "chapter_0_immigration",
        "turn_id": "turn_003",
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "miller", "emotion": "neutral"},
        "player": {"utterance": "I will stay five days", "language_level": "beginner"},
        "evaluation": {"branch_type": "success", "target_slot": "stay_address"},
    }

    summary = build_npc_dialogue_evidence_summary(payload)

    assert summary["source_type"] == "level_design"
    assert summary["selection_strategy"] == "single_turn_level_design_payload"
    assert summary["evidence_summary"][0]["source_id"] == "IMM_003_DURATION:turn_003"
    assert summary["evidence_summary"][0]["author"] == "level_design_agent"
    assert summary["evidence_summary"][0]["importance_score"] == 100
    assert summary["evidence_summary"][0]["snippet"] == (
        "Player answered: I will stay five days. Branch: success. Target slot: stay_address."
    )


def test_estimate_openai_cost_usd_for_gpt_4o_mini() -> None:
    cost = estimate_openai_cost_usd(
        model_name="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500,
    )

    assert cost == 0.0003


def test_agent_run_middleware_builds_structured_agent_run() -> None:
    middleware = NPCDialogueAgentRunMiddleware()
    metadata = {"source_type": "level_design", "evidence_summary": []}
    middleware.record_event(
        metadata,
        event="agent_start",
        status="started",
        data_loaded={"node_id": "IMM_003_DURATION"},
    )

    run = middleware.start_run(
        prompt_version="npc_dialogue_prompt_v1",
        source_window={
            "source_type": "level_design_json",
            "node_id": "IMM_003_DURATION",
            "turn_id": "turn_003",
            "chapter_id": "chapter_0_immigration",
        },
        cache_key="sha256:test",
        model_name="gpt-4o-mini",
        permission_level="runtime_user_session",
        metadata=metadata,
    )
    completed = middleware.complete_run(
        run,
        input_tokens=100,
        output_tokens=20,
        estimated_cost_usd=0.000021,
    )

    assert completed["agent_name"] == "npc_dialogue_agent"
    assert completed["status"] == "completed"
    assert completed["total_tokens"] == 120
    assert completed["estimated_cost_usd"] == 0.000021
    assert completed["metadata"]["events"][0]["event"] == "agent_start"
    assert completed["metadata"]["events"][0]["data_loaded"]["node_id"] == "IMM_003_DURATION"


def test_agent_run_store_appends_only_unified_agent_run_jsonl(tmp_path) -> None:
    store = NPCDialogueAgentRunStore(root=tmp_path)
    run = {
        "agent_run_id": "run_1",
        "agent_name": "npc_dialogue_agent",
        "status": "completed",
        "source_window": {"source_type": "level_design_json"},
        "model_name": "rule_based",
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "metadata": {"events": []},
    }

    jsonl_path, markdown_path = store.append_unified_agent_run(
        run,
        owner="developer_a",
        request_id="req_1",
        session_id="session_1",
        turn_index=1,
        summary={"input": "hello", "output": "Okay.", "fallback_used": False},
        artifact_path=None,
    )

    assert jsonl_path == tmp_path / "unified_agent_runs.jsonl"
    assert markdown_path == tmp_path / "unified_agent_runs.md"
    assert not (tmp_path / "npc_dialogue_agent_runs.jsonl").exists()
    assert not (tmp_path / "npc_dialogue_artifacts.jsonl").exists()


def test_unified_agent_run_log_store_appends_jsonl_and_markdown(tmp_path) -> None:
    store = AgentRunLogStore(root=tmp_path)
    record = {
        "schema_version": "unified_agent_run.v1",
        "agent_run_id": "run_1",
        "agent_name": "npc_dialogue_agent",
        "owner": "developer_a",
        "request_id": "req_1",
        "session_id": "session_1",
        "turn_index": 1,
        "status": "completed",
        "started_at": "2026-06-04T00:00:00+00:00",
        "completed_at": "2026-06-04T00:00:01+00:00",
        "source_window": {"source_type": "level_design_json", "chapter_id": "CH0_03_IMMIGRATION_CHECK"},
        "model": {
            "model_name": "rule_based",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        },
        "events": [],
        "summary": {"input": "Player answered.", "output": "Okay.", "fallback_used": False},
        "metadata": {},
    }

    jsonl_path, markdown_path = store.append_with_markdown(record)

    assert json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0]) == record
    assert "## Agent Run: npc_dialogue_agent / developer_a" in markdown_path.read_text(encoding="utf-8")


def test_format_agent_run_markdown_makes_readable_timeline() -> None:
    markdown = format_agent_run_markdown(
        {
            "agent_run_id": "run_1",
            "agent_name": "npc_dialogue_agent",
            "owner": "developer_a",
            "request_id": "req_1",
            "session_id": "session_1",
            "turn_index": 1,
            "status": "completed",
            "started_at": "2026-06-04T00:00:00+00:00",
            "completed_at": "2026-06-04T00:00:01+00:00",
            "source_window": {"source_type": "level_design_json", "node_id": "IMM_002_PURPOSE"},
            "model": {"model_name": "rule_based", "total_tokens": 0, "estimated_cost_usd": 0.0},
            "events": [
                {
                    "event": "agent_start",
                    "status": "started",
                    "data_loaded": {"payload_keys": ["node_id", "player_text"]},
                },
                {
                    "event": "tool_call",
                    "status": "completed",
                    "tool_name": "tts_service.build_kokoro_provider_request",
                    "output_summary": {"voice": "am_michael", "sample_rate": 24000},
                },
            ],
            "summary": {
                "input": "Player answered: I will stay five days.",
                "output": "Okay. Please continue.",
                "fallback_used": True,
            },
        }
    )

    assert "## Agent Run: npc_dialogue_agent / developer_a" in markdown
    assert "| 1 | agent_start | started | -" in markdown
    assert "tts_service.build_kokoro_provider_request" in markdown
    assert "- Fallback Used: `True`" in markdown


def test_build_npc_dialogue_artifact_links_to_agent_run() -> None:
    artifact = build_npc_dialogue_artifact(
        agent_run_id="run_1",
        npc_id="miller",
        npc_text="Where will you be staying?",
        tts_text="Where will you be staying?",
        feedback_kr="좋습니다.",
        audio_url="http://localhost/audio.wav",
        audio_path="backend/runtime/audio.wav",
        source_id="IMM_003_DURATION:turn_003",
        source_snippet="Player answered: I will stay five days.",
    )

    assert artifact["agent_run_id"] == "run_1"
    assert artifact["artifact_type"] == "npc_dialogue_voice_output"
    assert artifact["payload"]["npc_text"] == "Where will you be staying?"
    assert artifact["source_links"][0]["source_id"] == "IMM_003_DURATION:turn_003"


def test_build_user_visible_run_summary_formats_agent_run_for_demo() -> None:
    summary = build_user_visible_run_summary(
        {
            "agent_run_id": "run_1",
            "agent_name": "npc_dialogue_agent",
            "status": "completed",
            "model_name": "gpt-4o-mini",
            "total_tokens": 120,
            "estimated_cost_usd": 0.000021,
            "metadata": {
                "evidence_summary": [{"snippet": "Player answered: I will stay five days."}],
                "tts_summary": {"voice_id": "am_michael", "audio_url": "http://localhost/audio.wav"},
                "fallback": {"used": False, "reason": None},
            },
        }
    )

    assert summary["Agent"] == "npc_dialogue_agent"
    assert summary["Status"] == "completed"
    assert summary["Evidence Summary"] == "Player answered: I will stay five days."
    assert summary["Model"] == "gpt-4o-mini"
    assert summary["TTS Voice"] == "am_michael"


def test_voice_output_writes_only_unified_agent_run_records(tmp_path) -> None:
    payload = {
        "chapter_id": "chapter_0_immigration",
        "turn_id": "turn_003",
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "miller", "emotion": "neutral"},
        "player": {"utterance": "I will stay five days", "language_level": "beginner"},
        "evaluation": {"branch_type": "success", "target_slot": "stay_address"},
    }

    output = build_voice_output_from_level_design(
        payload,
        runtime_root=tmp_path / "runtime",
        request_id="req_1",
        session_id="session_1",
        use_llm_dialogue=False,
        use_real_tts=False,
        agent_run_root=tmp_path,
    )

    unified_runs = [
        json.loads(line)
        for line in (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    readable_log = (tmp_path / "unified_agent_runs.md").read_text(encoding="utf-8")

    assert not (tmp_path / "npc_dialogue_agent_runs.jsonl").exists()
    assert not (tmp_path / "npc_dialogue_artifacts.jsonl").exists()
    assert not (tmp_path / "runtime" / "logs").exists()
    assert "agent_run_path" not in output
    assert "artifact_path" not in output
    assert "agent_run_artifact" not in output
    assert unified_runs[0]["agent_name"] == "npc_dialogue_agent"
    assert unified_runs[0]["status"] == "completed"
    assert unified_runs[0]["metadata"]["evidence_summary"][0]["author"] == "level_design_agent"
    assert "artifact_path" not in unified_runs[0]["metadata"]
    event_names = [event["event"] for event in unified_runs[0]["events"]]
    tool_names = [
        event.get("tool_name")
        for event in unified_runs[0]["events"]
        if event.get("event") == "tool_call"
    ]
    assert event_names[0] == "agent_start"
    assert "agent_end" in event_names
    assert "developer_a_input_service.normalize_level_design_payload" in tool_names
    assert "agent_a.npc_dialogue_agent.generate_npc_dialogue_from_level_design" in tool_names
    assert "tts_service.build_edge_provider_request" in tool_names
    assert "tts_provider_service.edge.synthesize" in tool_names
    tts_event = next(
        event
        for event in unified_runs[0]["events"]
        if event.get("tool_name") == "tts_provider_service.edge.synthesize"
    )
    tts_speed = tts_event["output_summary"]["generation_speed"]
    assert tts_speed["generation_seconds"] >= 0
    assert tts_speed["audio_seconds"] > 0
    assert tts_speed["real_time_factor"] >= 0
    assert unified_runs[0]["metadata"]["tts_summary"]["generation_speed"] == tts_speed
    assert unified_runs[0]["agent_run_id"] == output["agent_run_id"]
    assert unified_runs[0]["owner"] == "developer_a"
    assert unified_runs[0]["request_id"] == "req_1"
    assert "## Agent Run: npc_dialogue_agent / developer_a" in readable_log
    assert "### Timeline" in readable_log
    assert output["unified_agent_run_path"].endswith("unified_agent_runs.jsonl")
    assert output["readable_agent_run_path"].endswith("unified_agent_runs.md")


def test_voice_output_uses_npc_id_from_payload_for_voice_profile_and_log(tmp_path) -> None:
    payload = {
        "chapter_id": "chapter_0_immigration",
        "turn_id": "turn_003",
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "MILLER", "npc_role": "immigration_officer"},
        "player": {"utterance": "I will stay five days", "language_level": "beginner"},
        "evaluation": {"branch_type": "success", "target_slot": "stay_address"},
    }

    output = build_voice_output_from_level_design(
        payload,
        runtime_root=tmp_path / "runtime",
        request_id="req_1",
        session_id="session_1",
        use_llm_dialogue=False,
        use_real_tts=False,
        agent_run_root=tmp_path,
    )

    record = json.loads((tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert output["tts"]["voice_profile_id"] == "session_1:hale"
    assert output["tts"]["voice_id"] == "en-US-GuyNeural"
    assert record["metadata"]["npc_context"]["npc_id"] == "hale"


def test_voice_output_logs_dialogue_source_trace_for_next_line_generation(tmp_path) -> None:
    payload = {
        "chapter_id": "chapter_0_immigration",
        "turn_id": "turn_003",
        "node_id": "IMM_003_DURATION",
        "npc": {"npc_id": "MILLER", "npc_role": "immigration_officer"},
        "player_text": "I will stay five days",
        "node_context": {
            "npc_question": "How long will you stay?",
            "npc_question_goal": "ask_stay_duration",
            "recommended_expression": "I will stay for five days.",
        },
        "evaluation_summary": {
            "feedback_note": "Duration was understood.",
            "task_success": True,
            "clarity": 0.9,
        },
        "level_hint": {
            "english_level": "beginner",
            "needs_hint": False,
            "recommended_expression": "I will stay for five days.",
        },
        "in_game_feedback": {
            "npc_recast_line_candidate": "You'll stay for five days. Where are you staying?",
            "feedback_strategy": "recast",
        },
        "branch": {"branch_type": "success", "next_node_id": "IMM_004_ADDRESS"},
        "dialogue_directive": {"do_not_generate_npc_text": False},
    }

    build_voice_output_from_level_design(
        payload,
        runtime_root=tmp_path / "runtime",
        request_id="req_1",
        session_id="session_1",
        use_llm_dialogue=False,
        use_real_tts=False,
        agent_run_root=tmp_path,
    )

    record = json.loads((tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    trace = record["metadata"]["dialogue_source_trace"]

    assert trace["npc_profile"]["npc_id"] == "hale"
    assert trace["used_inputs"]["node_context"] == {
        "used_for": "next_question_and_goal",
        "node_id": "IMM_003_DURATION",
        "npc_question_goal": "ask_stay_duration",
    }
    assert trace["used_inputs"]["player_text"]["used_for"] == "dialogue_evidence_preview"
    assert trace["used_inputs"]["developer_b_feedback"]["used_for"] == "recast_candidate_and_feedback_note"
    assert trace["used_inputs"]["branch"]["next_node_id"] == "IMM_004_ADDRESS"
    assert trace["used_inputs"]["voice_profile"]["voice_id"] == "en-US-GuyNeural"
    assert trace["output_decision"]["npc_text_source"] == "developer_b_recast_candidate"
    assert trace["output_decision"]["tts_text_source"] == "tts_text_polisher_service"


def test_voice_output_logs_llm_dialogue_as_output_source(tmp_path, monkeypatch) -> None:
    class FakeLLMClient:
        model = "google/gemma-4-26B-A4B-it"

        def generate(self, payload: dict) -> dict:
            return {
                "npc_text": "Please answer the question directly.",
                "tts_text": "Please answer the question directly.",
                "feedback_kr": "방문 목적을 짧게 말하면 됩니다.",
                "tone": "formal_firm",
                "animation": "move",
                "llm_reason": "source trace test",
                "__fallback_model": "google/gemma-4-26B-A4B-it",
                "__llm_usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            }

    monkeypatch.setattr(
        "backend.app.agents.agent_a.npc_dialogue_agent.build_npc_dialogue_llm_client_from_environment",
        lambda: FakeLLMClient(),
    )

    payload = {
        "chapter_id": "chapter_0_immigration",
        "turn_id": "turn_003",
        "node_id": "IMM_002_PURPOSE",
        "npc": {"npc_id": "miller"},
        "player_text": "I am Korean.",
        "node_context": {"recommended_expression": "I'm here for tourism."},
        "evaluation_summary": {"feedback_note": "Purpose was unclear.", "task_success": 0, "clarity": 1},
        "level_hint": {"english_level": "beginner", "recommended_expression": "I'm here for tourism."},
        "in_game_feedback": {},
        "branch": {"branch_type": "clarify", "next_node_id": "IMM_002_PURPOSE"},
    }

    build_voice_output_from_level_design(
        payload,
        runtime_root=tmp_path / "runtime",
        request_id="req_1",
        session_id="session_1",
        use_llm_dialogue=True,
        use_real_tts=False,
        agent_run_root=tmp_path,
    )

    record = json.loads((tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    trace = record["metadata"]["dialogue_source_trace"]

    assert trace["output_decision"]["npc_text_source"] == "llm_dialogue_from_fallback_seed"
    assert trace["output_decision"]["tts_text_source"] == "llm_dialogue"


def test_voice_output_can_switch_to_edge_tts_provider_with_wav_output(
    tmp_path,
    monkeypatch,
) -> None:
    def fake_edge_synthesize(self: object, request: TTSProviderRequest, output_path) -> dict:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(request.sample_rate)
            wav.writeframes(b"\x00\x00" * request.sample_rate)
        return {
            "provider": "edge",
            "voice_id": request.provider_options["voice"],
            "audio_path": str(output_path),
            "audio_url": None,
            "sample_rate": request.sample_rate,
            "format": request.output_format,
            "audio_seconds": 1.0,
            "generation_seconds": 0.25,
            "conversion_seconds": 0.05,
            "real_time_factor": 0.25,
            "status": "ok",
        }

    monkeypatch.setenv("MURPHY_TTS_PROVIDER", "edge")
    monkeypatch.setenv("MURPHY_EDGE_TTS_VOICE", "en-US-GuyNeural")
    monkeypatch.setenv("MURPHY_EDGE_TTS_OUTPUT_FORMAT", "wav")
    monkeypatch.setattr(
        "backend.app.services.service_a.tts_provider_service.EdgeTTSProvider.synthesize",
        fake_edge_synthesize,
    )

    output = build_voice_output_from_level_design(
        {
            "chapter_id": "CH0_IMMIGRATION",
            "turn_id": "turn_edge_001",
            "node_id": "IMM_002_PURPOSE",
            "npc": {"npc_id": "miller", "emotion": "neutral"},
            "player": {"utterance": "I'm here for tourism.", "language_level": "beginner"},
            "evaluation": {"branch_type": "success", "target_slot": "visit_purpose"},
        },
        runtime_root=tmp_path / "runtime",
        request_id="req_edge_1",
        session_id="session_edge_1",
        use_llm_dialogue=False,
        use_real_tts=True,
        audio_url_base="/runtime/audio",
        agent_run_root=tmp_path,
    )

    assert output["tts"]["provider"] == "edge"
    assert output["tts"]["voice_id"] == "en-US-GuyNeural"
    assert output["tts"]["audio_path"].endswith(".wav")
    assert "\\edge\\" in output["tts"]["audio_path"] or "/edge/" in output["tts"]["audio_path"]
    assert output["tts"]["audio_url"].startswith("/runtime/audio/edge/")

    run = json.loads((tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    edge_event = next(
        event for event in run["events"] if event.get("tool_name") == "tts_provider_service.edge.synthesize"
    )
    assert edge_event["output_summary"]["provider"] == "edge"
    assert edge_event["output_summary"]["conversion_seconds"] == 0.05



def test_voice_output_can_switch_to_elevenlabs_tts_provider_with_voice_settings(
    tmp_path,
    monkeypatch,
) -> None:
    def fake_elevenlabs_synthesize(self: object, request: TTSProviderRequest, output_path) -> dict:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(request.sample_rate)
            wav.writeframes(b"\x00\x00" * request.sample_rate)
        return {
            "provider": "elevenlabs",
            "voice_id": request.provider_options["voice"],
            "audio_path": str(output_path),
            "audio_url": None,
            "sample_rate": request.sample_rate,
            "format": request.output_format,
            "audio_seconds": 1.0,
            "generation_seconds": 0.31,
            "conversion_seconds": 0.04,
            "real_time_factor": 0.31,
            "status": "ok",
            "provider_options": {
                "model_id": request.provider_options["model_id"],
                "api_output_format": request.provider_options["api_output_format"],
                "stability": request.provider_options["stability"],
                "similarity_boost": request.provider_options["similarity_boost"],
                "style": request.provider_options["style"],
                "speed": request.provider_options["speed"],
            },
        }

    monkeypatch.setenv("MURPHY_TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("MURPHY_ELEVENLABS_API_KEY", "test_key")
    monkeypatch.setenv("MURPHY_ELEVENLABS_VOICE_ID", "voice_miller")
    monkeypatch.setenv("MURPHY_ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
    monkeypatch.setenv("MURPHY_ELEVENLABS_SPEED", "0.80")
    monkeypatch.setattr(
        "backend.app.services.service_a.tts_provider_service.ElevenLabsTTSProvider.synthesize",
        fake_elevenlabs_synthesize,
    )

    output = build_voice_output_from_level_design(
        {
            "chapter_id": "CH0_IMMIGRATION",
            "turn_id": "turn_elevenlabs_001",
            "node_id": "IMM_002_PURPOSE",
            "npc": {"npc_id": "miller", "emotion": "suspicious"},
            "player": {"utterance": "I'm here for tourism.", "language_level": "beginner"},
            "evaluation": {"branch_type": "success", "target_slot": "visit_purpose"},
        },
        runtime_root=tmp_path / "runtime",
        request_id="req_elevenlabs_1",
        session_id="session_elevenlabs_1",
        use_llm_dialogue=False,
        use_real_tts=True,
        audio_url_base="/runtime/audio",
        agent_run_root=tmp_path,
    )

    assert output["tts"]["provider"] == "elevenlabs"
    assert output["tts"]["voice_id"] == "voice_miller"
    assert output["tts"]["audio_path"].endswith(".wav")
    assert "\\elevenlabs\\" in output["tts"]["audio_path"] or "/elevenlabs/" in output["tts"]["audio_path"]
    assert output["tts"]["audio_url"].startswith("/runtime/audio/elevenlabs/")
    assert output["tts"]["provider_options"]["model_id"] == "eleven_flash_v2_5"
    assert output["tts"]["provider_options"]["speed"] == 0.8

    run = json.loads((tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    build_event = next(
        event
        for event in run["events"]
        if event.get("tool_name") == "tts_service.build_elevenlabs_provider_request"
    )
    assert build_event["output_summary"]["provider"] == "elevenlabs"
    assert build_event["output_summary"]["model_id"] == "eleven_flash_v2_5"
    assert build_event["output_summary"]["speed"] == 0.8
    tts_event = next(
        event
        for event in run["events"]
        if event.get("tool_name") == "tts_provider_service.elevenlabs.synthesize"
    )
    assert tts_event["output_summary"]["provider"] == "elevenlabs"


def test_elevenlabs_provider_uses_api_key_without_returning_secret(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        content = b"fake mp3 bytes"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def post(self, url: str, **kwargs) -> FakeResponse:
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse()

    def fake_convert_mp3_to_wav(input_path, output_path, sample_rate: int) -> None:
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"\x00\x00" * sample_rate)

    monkeypatch.setattr("backend.app.services.service_a.tts_provider_service.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "backend.app.services.service_a.tts_provider_service._convert_mp3_to_wav",
        fake_convert_mp3_to_wav,
    )
    request = TTSProviderRequest(
        provider="elevenlabs",
        text="How long will you be staying?",
        speaker_id="miller",
        voice_profile_id="session:miller",
        language="en",
        emotion="firm_official",
        tone="formal_firm",
        intensity=0.6,
        speaking_rate=0.8,
        pitch=0.0,
        sample_rate=24000,
        output_format="wav",
        provider_options={
            "api_key": "secret_test_key",
            "base_url": "https://api.elevenlabs.io/v1",
            "voice": "voice_123",
            "model_id": "eleven_flash_v2_5",
            "api_output_format": "mp3_44100_128",
            "stability": 0.52,
            "similarity_boost": 0.82,
            "style": 0.42,
            "speed": 0.8,
            "use_speaker_boost": True,
            "timeout_seconds": 30.0,
        },
    )

    metadata = ElevenLabsTTSProvider().synthesize(request, tmp_path / "elevenlabs.wav")

    assert metadata["provider"] == "elevenlabs"
    assert metadata["provider_options"]["model_id"] == "eleven_flash_v2_5"
    assert "api_key" not in metadata["provider_options"]
    assert "secret_test_key" not in json.dumps(metadata)
    post_kwargs = captured["kwargs"]
    assert isinstance(post_kwargs, dict)
    assert post_kwargs["headers"]["xi-api-key"] == "secret_test_key"
    assert post_kwargs["json"]["voice_settings"]["speed"] == 0.8
