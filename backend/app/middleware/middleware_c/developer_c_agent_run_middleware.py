"""Create unified AgentRun log records for Developer C orchestration.

Beginner guide:
An AgentRun is a structured timeline of what happened during one backend turn.
This middleware does not decide gameplay.  It only builds a record, appends
events as C services run, and finally writes JSONL/Markdown through the shared
log store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import PrePrototypeRequest
from backend.app.services.shared.agent_run_log_store import (
    AgentRunLogStore,
    build_unified_agent_run_record,
)


class DeveloperCAgentRunMiddleware:
    """Build and append Developer C orchestration AgentRun records."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("backend/runtime/generated/agent_runs")
        self.store = AgentRunLogStore(self.root)

    def start_run(self, request: PrePrototypeRequest) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        session = request.turn.session
        run_id_seed = (
            f"{request.turn.request_id}:{session.session_id}:{session.turn_index}:{now}"
        ).encode("utf-8")
        return {
            "agent_run_id": f"c_orch_run_{sha256(run_id_seed).hexdigest()[:12]}",
            "agent_name": "ai_backend_orchestrator",
            "owner": "developer_c",
            "request_id": request.turn.request_id,
            "session_id": session.session_id,
            "turn_index": session.turn_index,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "source_window": {
                "source_type": "unreal_turn_request",
                "chapter_id": session.chapter_id,
                "scene_id": session.scene_id,
                "node_id": session.current_node_id,
            },
            "events": [],
            "metadata": {
                "data_flow": [],
                "permission_level": "runtime_user_session",
                "debug_scope": "developer_c_orchestration",
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
        error_details: dict[str, Any] | None = None,
    ) -> None:
        """AgentRun 타임라인에 C 런타임 이벤트 한 줄을 추가합니다.

        초보자용 설명:
        `error`는 사람이 빠르게 읽는 짧은 문자열이고, `error_details`는
        디버깅 도구가 바로 파싱할 수 있는 구조화된 실패 정보입니다. 실패
        원인을 다시 추적할 수 있도록 타입, 메시지, 단계, 도구 이름을 함께
        남깁니다.
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
        if error_details is not None:
            item["error_details"] = error_details
        events.append(item)

    def record_data_flow(
        self,
        run: dict[str, Any],
        *,
        from_node: str,
        to_node: str,
        payload_summary: dict[str, Any],
    ) -> None:
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
        model_usage: dict[str, Any] | None = None,
    ) -> tuple[Path, Path]:
        run["status"] = status
        run["completed_at"] = datetime.now(UTC).isoformat()
        resolved_model_usage = _model_usage_or_default(model_usage)
        record = build_unified_agent_run_record(
            agent_run_id=str(run["agent_run_id"]),
            agent_name=str(run["agent_name"]),
            owner=str(run["owner"]),
            request_id=_optional_string(run.get("request_id")),
            session_id=_optional_string(run.get("session_id")),
            turn_index=_optional_int(run.get("turn_index")),
            status=status,
            source_window=_dict_or_empty(run.get("source_window")),
            model_name=resolved_model_usage["model_name"],
            input_tokens=resolved_model_usage["input_tokens"],
            output_tokens=resolved_model_usage["output_tokens"],
            estimated_cost_usd=resolved_model_usage["estimated_cost_usd"],
            events=[event for event in _list_or_empty(run.get("events")) if isinstance(event, dict)],
            summary=summary,
            metadata=_dict_or_empty(run.get("metadata")),
            started_at=run.get("started_at"),
            completed_at=run.get("completed_at"),
        )
        return self.store.append_with_markdown(record)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _model_usage_or_default(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "model_name": "mixed_runtime",
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": 0.0,
        }
    return {
        "model_name": str(value.get("model_name", "mixed_runtime")),
        "input_tokens": _int_or_zero(value.get("input_tokens")),
        "output_tokens": _int_or_zero(value.get("output_tokens")),
        "estimated_cost_usd": _float_or_zero(value.get("estimated_cost_usd")),
    }


def _int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _float_or_zero(value: Any) -> float:
    return float(value) if isinstance(value, int | float) else 0.0
