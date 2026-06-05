from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_AGENT_RUN_ROOT = Path("backend/runtime/generated/agent_runs")
IMPORTANT_TOOL_LABELS = {
    "stt_service.transcribe_wav": "STT",
    "openkb_service.get_node_context": "OpenKB Node Context",
    "understanding_agent.analyze_player_text": "Understanding Agent",
    "dev_b_client.evaluate_turn": "Developer B Policy",
    "validator.validate_dev_b_policy_output": "Developer B Validator",
    "logging_service.record_error_capture": "Error Capture",
    "dev_a_client.generate_dialogue": "Developer A Dialogue",
    "response_builder.build_unreal_response": "Response Builder",
    "validator.validate_unreal_response": "Unreal Response Validator",
}


class AgentRunSummaryService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_AGENT_RUN_ROOT

    def latest(self, request_id: str | None = None) -> dict[str, Any]:
        record = self._latest_record(request_id)
        if record is None:
            return {
                "found": False,
                "request_id": request_id,
                "agent_run_id": None,
                "agent_name": None,
                "owner": None,
                "status": None,
                "summary": None,
                "nodes": [],
            }

        return {
            "found": True,
            "request_id": record.get("request_id"),
            "session_id": record.get("session_id"),
            "turn_index": record.get("turn_index"),
            "agent_run_id": record.get("agent_run_id"),
            "agent_name": record.get("agent_name"),
            "owner": record.get("owner"),
            "status": record.get("status"),
            "started_at": record.get("started_at"),
            "completed_at": record.get("completed_at"),
            "summary": _compact(record.get("summary")),
            "nodes": [_event_summary(event) for event in _tool_call_events(record)],
        }

    def _latest_record(self, request_id: str | None) -> dict[str, Any] | None:
        path = self.root / "unified_agent_runs.jsonl"
        if not path.exists():
            return None

        latest: dict[str, Any] | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if request_id is not None and record.get("request_id") != request_id:
                continue
            latest = record
        return latest


def _tool_call_events(record: dict[str, Any]) -> list[dict[str, Any]]:
    events = record.get("events")
    if not isinstance(events, list):
        return []

    return [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event") == "tool_call"
        and isinstance(event.get("tool_name"), str)
    ]


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(event["tool_name"])
    return {
        "label": IMPORTANT_TOOL_LABELS.get(tool_name, tool_name),
        "tool_name": tool_name,
        "status": event.get("status"),
        "input": _compact(event.get("input_summary") or event.get("data_loaded")),
        "output": _compact(event.get("output_summary")),
        "error": event.get("error"),
        "error_type": event.get("error_type"),
    }


def _compact(value: Any, *, max_string: int = 500, max_list: int = 16) -> Any:
    if isinstance(value, dict):
        return {str(key): _compact(item) for key, item in value.items()}
    if isinstance(value, list):
        items = [_compact(item) for item in value[:max_list]]
        if len(value) > max_list:
            items.append(f"... {len(value) - max_list} more")
        return items
    if isinstance(value, str) and len(value) > max_string:
        return f"{value[: max_string - 3]}..."
    return value
