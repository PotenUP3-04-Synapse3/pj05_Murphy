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
    """Build and append Developer B policy AgentRun records."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("backend/runtime/generated/agent_runs")
        self.store = AgentRunLogStore(self.root)

    def start_run(self, payload: DevBPolicyInput) -> dict[str, Any]:
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
        return self.complete_and_append(
            run,
            status="failed",
            summary=summary,
            model_name="rule_based",
        )


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
