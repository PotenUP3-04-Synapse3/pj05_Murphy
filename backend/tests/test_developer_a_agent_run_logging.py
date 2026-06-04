import json

from backend.app.middleware.middleware_a.npc_dialogue_agent_run_middleware import (
    NPCDialogueAgentRunMiddleware,
)
from backend.app.services.service_a.npc_dialogue_agent_run_store import (
    NPCDialogueAgentRunStore,
)
from backend.app.services.service_a.voice_output_service import build_voice_output_from_level_design
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


def test_agent_run_middleware_builds_slack_style_agent_run() -> None:
    middleware = NPCDialogueAgentRunMiddleware()

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
        metadata={"source_type": "level_design", "evidence_summary": []},
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


def test_agent_run_store_appends_run_and_artifact_jsonl(tmp_path) -> None:
    store = NPCDialogueAgentRunStore(root=tmp_path)
    run = {"agent_run_id": "run_1", "agent_name": "npc_dialogue_agent"}
    artifact = {"artifact_id": "artifact_1", "agent_run_id": "run_1"}

    run_path = store.append_agent_run(run)
    artifact_path = store.append_artifact(artifact)

    assert json.loads(run_path.read_text(encoding="utf-8").splitlines()[0]) == run
    assert json.loads(artifact_path.read_text(encoding="utf-8").splitlines()[0]) == artifact


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

    assert summary["실행 Agent"] == "npc_dialogue_agent"
    assert summary["상태"] == "completed"
    assert summary["근거 요약"] == "Player answered: I will stay five days."
    assert summary["모델"] == "gpt-4o-mini"
    assert summary["TTS 목소리"] == "am_michael"


def test_voice_output_writes_agent_run_and_artifact_records(tmp_path) -> None:
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
        use_llm_dialogue=False,
        use_real_tts=False,
        agent_run_root=tmp_path,
    )

    runs = [
        json.loads(line)
        for line in (tmp_path / "npc_dialogue_agent_runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    artifacts = [
        json.loads(line)
        for line in (tmp_path / "npc_dialogue_artifacts.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert runs[0]["agent_name"] == "npc_dialogue_agent"
    assert runs[0]["status"] == "completed"
    assert runs[0]["metadata"]["evidence_summary"][0]["author"] == "level_design_agent"
    assert artifacts[0]["agent_run_id"] == runs[0]["agent_run_id"]
    assert artifacts[0]["payload"]["npc_text"] == output["npc_text"]
    assert output["agent_run_id"] == runs[0]["agent_run_id"]
