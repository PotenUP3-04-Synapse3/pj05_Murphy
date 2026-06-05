import json

from backend.app.middleware.middleware_a.npc_dialogue_agent_run_middleware import (
    NPCDialogueAgentRunMiddleware,
)
from backend.app.services.service_a.npc_dialogue_agent_run_store import (
    NPCDialogueAgentRunStore,
)
from backend.app.services.service_a.voice_output_service import build_voice_output_from_level_design
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
        "npc": {"npc_id": "officer_miller", "emotion": "neutral"},
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
        "source_window": {"source_type": "level_design_json", "chapter_id": "CH0_IMMIGRATION"},
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
        npc_id="officer_miller",
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
        "npc": {"npc_id": "officer_miller", "emotion": "neutral"},
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
    assert "tts_service.build_kokoro_provider_request" in tool_names
    assert "tts_provider_service.KokoroProvider.synthesize" in tool_names
    assert unified_runs[0]["agent_run_id"] == output["agent_run_id"]
    assert unified_runs[0]["owner"] == "developer_a"
    assert unified_runs[0]["request_id"] == "req_1"
    assert "## Agent Run: npc_dialogue_agent / developer_a" in readable_log
    assert "### Timeline" in readable_log
    assert output["unified_agent_run_path"].endswith("unified_agent_runs.jsonl")
    assert output["readable_agent_run_path"].endswith("unified_agent_runs.md")
