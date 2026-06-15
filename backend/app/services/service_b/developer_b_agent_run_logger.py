from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import DevBPolicyInput
from backend.app.services.shared.agent_run_log_store import (
    AgentRunLogStore,
    build_unified_agent_run_record,
)


class DeveloperBAgentRunLogger:
    """
    Developer B의 에이전트 실행 기록(AgentRun 로그)을 생성하고 보관하는 로거 클래스입니다.
    
    초보자 가이드: 에이전트가 어떤 데이터(입력)를 받아서 각 단계별로 어떤 연산을 수행했고, 
    최종 결과(출력)는 무엇인지를 JSONL 및 Markdown 포맷의 파일로 기록해 둡니다. 
    이를 통해 나중에 버그가 발생했을 때 히스토리를 분석하고 디버깅하기 쉬워집니다.
    """

    def __init__(self, root: Path | None = None) -> None:
        """
        로그 파일이 저장될 루트 폴더 경로를 설정하여 로거 인스턴스를 초기화합니다.
        
        Args:
            root: 로그 파일이 저장될 경로 (지정하지 않으면 기본값으로 'backend/runtime/generated/agent_runs' 사용)
        """
        self.root = root or Path("backend/runtime/generated/agent_runs")
        self.store = AgentRunLogStore(self.root)

    def start_run(self, payload: DevBPolicyInput) -> dict[str, Any]:
        """
        새로운 에이전트 실행 주기(Run)를 시작하고, 추적을 위한 초기 로그 구조(딕셔너리)를 생성합니다.
        
        Args:
            payload: 입력받은 대화 턴 데이터
            
        Returns:
            초기화된 실행 기록 로그 객체(딕셔너리)
        """
        now = datetime.now(UTC).isoformat()
        run_id_seed = (
            f"{payload.request_id}:{payload.session_id}:{payload.turn_index}:{now}"
        ).encode("utf-8")
        return {
            "agent_run_id": f"b_policy_run_{sha256(run_id_seed).hexdigest()[:12]}",
            "agent_name": "english_level_hint_agent",
            "owner": "developer_b",
            "request_id": payload.request_id,
            "session_id": payload.session_id,
            "turn_index": payload.turn_index,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "source_window": {
                "source_type": "dev_b_policy_input",
                "chapter_id": payload.chapter_id,
                "scene_id": payload.scene_id,
                "node_id": payload.current_node_id,
            },
            "events": [],
            "metadata": {
                "data_flow": [],
                "permission_level": "runtime_user_session",
                "debug_scope": "developer_b_policy",
            },
        }

    def record_event(
        self,
        run: dict[str, Any],
        *,
        event: str,
        status: str,
        tool_name: str | None = None,
        data_loaded: dict[str, Any] | None = None,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """
        에이전트 실행 과정 중 특정 사건(함수 호출, 데이터 수신 등)을 이벤트 형태로 기록합니다.
        
        Args:
            run: 업데이트할 로그 객체
            event: 이벤트 명칭 (예: 'tool_call', 'agent_start')
            status: 이벤트의 상태 (예: 'completed', 'failed')
            tool_name: (선택) 호출한 함수 또는 툴 이름
            data_loaded: (선택) 로드된 상세 데이터
            input_summary: (선택) 입력 요약 정보
            output_summary: (선택) 출력 결과 요약 정보
            error: (선택) 발생한 에러 메시지
        """
        events = run.setdefault("events", [])
        if not isinstance(events, list):
            events = []
            run["events"] = events

        item: dict[str, Any] = {
            "event": event,
            "status": status,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        if tool_name is not None:
            item["tool_name"] = tool_name
        if data_loaded is not None:
            item["data_loaded"] = data_loaded
        if input_summary is not None:
            item["input_summary"] = input_summary
        if output_summary is not None:
            item["output_summary"] = output_summary
        if error is not None:
            item["error"] = error
        events.append(item)

    def record_data_flow(
        self,
        run: dict[str, Any],
        *,
        from_node: str,
        to_node: str,
        payload_summary: dict[str, Any],
    ) -> None:
        """
        그래프 노드 간에 어떤 데이터가 오갔는지(Data Flow)를 기록합니다.
        
        Args:
            run: 업데이트할 로그 객체
            from_node: 데이터를 전송한 출발지 노드 이름
            to_node: 데이터를 수신한 목적지 노드 이름
            payload_summary: 전달된 데이터의 요약 정보
        """
        metadata = run.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            run["metadata"] = metadata

        data_flow = metadata.setdefault("data_flow", [])
        if not isinstance(data_flow, list):
            data_flow = []
            metadata["data_flow"] = data_flow

        data_flow.append(
            {
                "from": from_node,
                "to": to_node,
                "payload_summary": payload_summary,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )

    def complete_and_append(
        self,
        run: dict[str, Any],
        *,
        status: str,
        summary: dict[str, Any],
        model_name: str,
    ) -> tuple[Path, Path] | None:
        """
        에이전트 실행을 완료 처리하고, 누적된 전체 기록을 최종 파일(JSONL 및 Markdown)로 저장합니다.
        
        Args:
            run: 저장할 최종 로그 객체
            status: 최종 완료 상태 (예: 'completed')
            summary: 실행 결과 요약 정보
            model_name: 사용된 LLM 모델 이름 또는 'rule_based'
            
        Returns:
            저장된 JSONL 파일 경로와 Markdown 파일 경로의 튜플 (실패 시 None)
        """
        try:
            run["status"] = status
            run["completed_at"] = datetime.now(UTC).isoformat()
            record = build_unified_agent_run_record(
                agent_run_id=str(run["agent_run_id"]),
                agent_name=str(run["agent_name"]),
                owner=str(run["owner"]),
                request_id=_optional_string(run.get("request_id")),
                session_id=_optional_string(run.get("session_id")),
                turn_index=_optional_int(run.get("turn_index")),
                status=status,
                source_window=_dict_or_empty(run.get("source_window")),
                model_name=model_name,
                input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=0.0,
                events=[event for event in _list_or_empty(run.get("events")) if isinstance(event, dict)],
                summary=summary,
                metadata=_dict_or_empty(run.get("metadata")),
                started_at=run.get("started_at"),
                completed_at=run.get("completed_at"),
            )
            return self.store.append_with_markdown(record)
        except Exception:
            return None

    def fail_and_append(
        self,
        run: dict[str, Any],
        *,
        error: Exception,
        summary: dict[str, Any],
    ) -> tuple[Path, Path] | None:
        """
        에이전트 실행 중 처리되지 않은 예외(에러)가 발생하여 비정상 종료되었을 때, 
        실패 상태로 기록을 마감하고 파일에 저장합니다.
        
        Args:
            run: 저장할 로그 객체
            error: 발생한 예외 객체
            summary: 에러 상황 요약 정보
            
        Returns:
            저장된 파일 경로 튜플 (실패 시 None)
        """
        return self.complete_and_append(
            run,
            status="failed",
            summary=summary,
            model_name="rule_based",
        )


def _optional_string(value: Any) -> str | None:
    """
    주어진 값을 문자열로 안전하게 변환하여 반환하며, None인 경우 None을 반환합니다.
    """
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    """
    주어진 값이 정수형인 경우 그대로 반환하고, 그렇지 않은 경우 None을 반환합니다.
    """
    return value if isinstance(value, int) else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    """
    주어진 값이 딕셔너리 형태인 경우 그대로 반환하고, 그렇지 않은 경우 빈 딕셔너리를 반환합니다.
    """
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    """
    주어진 값이 리스트 형태인 경우 그대로 반환하고, 그렇지 않은 경우 빈 리스트를 반환합니다.
    """
    return value if isinstance(value, list) else []
