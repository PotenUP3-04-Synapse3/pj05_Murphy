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
    """게임 디버그 및 검증 플랫폼에 등록하여 추적할 수 있도록 구조화된 대화 실행 아티팩트(Artifact)를 조립합니다."""
    now = datetime.now(UTC).isoformat()
    # 고유한 아티팩트 ID를 해시로 생성하기 위한 바이트 시드(Seed)를 구성합니다.
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
        # 어떤 소스 파일 또는 페이로드에 의존했는지에 대한 연결 정보(Source Link)입니다.
        "source_links": [
            {
                "source_type": "level_design_json",
                "source_id": source_id,
            }
        ],
        "source_snippets": [source_snippet], # 역추적 시 가시적으로 식별 가능한 텍스트 조각입니다.
        "created_at": now,
    }


def build_user_visible_run_summary(agent_run: dict[str, Any]) -> dict[str, Any]:
    """에이전트 실행 내역(AgentRun) 사전을 바탕으로 개발자 도구 대시보드(Dashboard) 등에서 한눈에 파악할 수 있는 사용자 가시 요약을 작성합니다."""
    metadata = agent_run.get("metadata", {})
    evidence_items = metadata.get("evidence_summary", [{}])
    evidence = evidence_items[0] if evidence_items else {}
    tts = metadata.get("tts_summary", {})
    fallback = metadata.get("fallback", {})
    return {
        "Agent": agent_run.get("agent_name"),
        "Status": agent_run.get("status"),
        "Evidence Summary": evidence.get("snippet"),
        "Model": agent_run.get("model_name"),
        "Tokens": agent_run.get("total_tokens"),
        "Estimated Cost USD": agent_run.get("estimated_cost_usd"),
        "TTS Voice": tts.get("voice_id"),
        "Audio URL": tts.get("audio_url"),
        "Fallback Used": fallback.get("used"),
    }
