from datetime import UTC, datetime
from hashlib import sha256
from typing import Any


def build_npc_dialogue_artifact(
    *,
    agent_run_id: str,
    npc_id: str,
    npc_text: str,
    tts_text: str,
    feedback_kr: str,
    audio_url: str | None,
    audio_path: str | None,
    source_id: str,
    source_snippet: str,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    artifact_seed = f"{agent_run_id}:{npc_text}:{audio_url}".encode("utf-8")
    return {
        "artifact_id": f"npcdlg_artifact_{sha256(artifact_seed).hexdigest()[:12]}",
        "agent_run_id": agent_run_id,
        "artifact_type": "npc_dialogue_voice_output",
        "status": "ready",
        "payload": {
            "npc_id": npc_id,
            "npc_text": npc_text,
            "tts_text": tts_text,
            "feedback_kr": feedback_kr,
            "audio_url": audio_url,
            "audio_path": audio_path,
        },
        "source_links": [
            {
                "source_type": "level_design_json",
                "source_id": source_id,
            }
        ],
        "source_snippets": [source_snippet],
        "created_at": now,
    }


def build_user_visible_run_summary(agent_run: dict[str, Any]) -> dict[str, Any]:
    metadata = agent_run.get("metadata", {})
    evidence_items = metadata.get("evidence_summary", [{}])
    evidence = evidence_items[0] if evidence_items else {}
    tts = metadata.get("tts_summary", {})
    fallback = metadata.get("fallback", {})
    return {
        "실행 Agent": agent_run.get("agent_name"),
        "상태": agent_run.get("status"),
        "근거 요약": evidence.get("snippet"),
        "모델": agent_run.get("model_name"),
        "토큰": agent_run.get("total_tokens"),
        "예상 비용 USD": agent_run.get("estimated_cost_usd"),
        "TTS 목소리": tts.get("voice_id"),
        "오디오 URL": tts.get("audio_url"),
        "Fallback 사용": fallback.get("used"),
    }
