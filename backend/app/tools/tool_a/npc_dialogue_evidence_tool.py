from datetime import UTC, datetime
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    """Null 또는 잘못된 개체 타입을 안전하게 딕셔너리(Dictionary)로 형변환합니다."""
    return value if isinstance(value, dict) else {}


def _text(value: Any, default: str = "") -> str:
    """Null 또는 비정형 문자열을 다듬어 문자열 데이터로 안전 변환합니다."""
    return value.strip() if isinstance(value, str) and value.strip() else default


def build_npc_dialogue_evidence_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """에이전트 실행에 인가된 인풋 데이터(Payload)로부터 나중에 역추적이 용이하도록 요약된 근거 정보(Evidence Summary)를 추출 및 가공합니다.
    
    대용량의 원본 입력 객체를 모두 로그에 담는 대신, 필수 분석용 메타 데이터(플레이어 입력 텍스트, 분기 등)만 경량화하여 저장합니다.
    """
    player = _as_dict(payload.get("player"))
    evaluation = _as_dict(payload.get("evaluation"))
    node_id = _text(payload.get("node_id"), "unknown_node")
    turn_id = _text(payload.get("turn_id"), "unknown_turn")
    player_text = _text(player.get("utterance"), _text(payload.get("player_text"), ""))
    branch_type = _text(evaluation.get("branch_type"), _text(payload.get("branch_type"), "neutral"))
    target_slot = _text(evaluation.get("target_slot"), _text(payload.get("target_slot"), "unknown_slot"))

    return {
        "source_type": "level_design",
        "cache_hit": False,
        "selection_strategy": "single_turn_level_design_payload",
        # 공통 로그 DB 규격(Contract)에 부합하는 타임라인 근거 명세 어레이를 빌드합니다.
        "evidence_summary": [
            {
                "rank": 1,
                "source_id": f"{node_id}:{turn_id}", # 소스 연결 고리 정보
                "source_url": None,
                "timestamp": datetime.now(UTC).isoformat(),
                "author": "level_design_agent",
                "permission_level": "runtime_user_session",
                "channel_id": None,
                "importance_score": 100,
                "snippet": (
                    f"Player answered: {player_text}. "
                    f"Branch: {branch_type}. Target slot: {target_slot}."
                ),
            }
        ],
    }
