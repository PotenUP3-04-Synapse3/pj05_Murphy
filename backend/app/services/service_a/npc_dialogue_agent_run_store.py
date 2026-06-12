from pathlib import Path
from typing import Any

from backend.app.services.shared.agent_run_log_store import (
    AgentRunLogStore,
    build_unified_agent_run_record,
)


# 개발자 A가 수집한 에이전트 실행 정보(AgentRun)를 공통 로그 파일 및 마크다운(Markdown) 보고서로 가공하여 디스크에 누적 저장하는 저장소 클래스(Class)입니다.
class NPCDialogueAgentRunStore:
    def __init__(self, root: Path) -> None:
        # 로그 파일이 저장될 루트 디렉토리(Root Directory) 경로입니다.
        self.root = root

    def append_unified_agent_run(
        self,
        run: dict[str, Any],
        *,
        owner: str,
        request_id: str | None,
        session_id: str | None,
        turn_index: int | None,
        summary: dict[str, Any],
        artifact_path: Path | None,
    ) -> tuple[Path, Path]:
        """수집된 실행 이력 사전을 입력받아 통합 공통 로그 레코드(Unified Record)로 변환 후 디스크에 물리적으로 씁니다."""
        # 공통 로그의 메타데이터(Metadata)를 보존하면서 타임라인 이벤트 목록을 안전하게 분리 추출합니다.
        metadata = dict(run.get("metadata", {}))
        raw_events = metadata.pop("events", [])
        events = raw_events if isinstance(raw_events, list) else []
        if artifact_path is not None:
            metadata["artifact_path"] = str(artifact_path)

        # 공통 로그 시스템과의 규격(Contract)을 맞추기 위해 빌더 함수를 사용하여 포맷팅합니다.
        record = build_unified_agent_run_record(
            agent_run_id=str(run["agent_run_id"]),
            agent_name=str(run["agent_name"]),
            owner=owner,
            request_id=request_id,
            session_id=session_id,
            turn_index=turn_index,
            status=str(run["status"]),
            source_window=dict(run.get("source_window", {})),
            model_name=str(run.get("model_name", "")),
            input_tokens=_int_or_zero(run.get("input_tokens")),
            output_tokens=_int_or_zero(run.get("output_tokens")),
            estimated_cost_usd=_float_or_zero(run.get("estimated_cost_usd")),
            events=[event for event in events if isinstance(event, dict)],
            summary=summary,
            metadata=metadata,
            started_at=run.get("created_at"),
            completed_at=run.get("completed_at"),
        )
        # 헬퍼 모듈을 호출하여 최종적으로 파일(JSONL 및 마크다운)에 저장하고 저장 완료된 파일 경로 쌍을 반환합니다.
        return AgentRunLogStore(self.root).append_with_markdown(record)


def _int_or_zero(value: Any) -> int:
    """Null 또는 잘못된 형식을 0 정수로 보정하는 타입 캐스팅(Type Casting) 함수입니다."""
    return value if isinstance(value, int) else 0


def _float_or_zero(value: Any) -> float:
    """비용 등 실수형 연산이 필요한 값의 타입을 정밀하게 검증하여 부동 소수점(Float) 값으로 변환합니다."""
    return float(value) if isinstance(value, int | float) else 0.0
