"""Read compact summaries from unified AgentRun logs.

Beginner guide:
The backend writes detailed JSONL logs for each agent run.  The demo/debug API
does not need to return the entire raw log, so this service reads the file,
selects the latest or session-level records, and trims long nested values into
small summaries that are easier to inspect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.agents.agent_c.llm_cost_estimator import estimate_openai_llm_cost_usd


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
                "model_usage": None,
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
            "model_usage": _model_usage(record.get("model")),
            "summary": _compact(record.get("summary")),
            "nodes": [_event_summary(event) for event in _tool_call_events(record)],
        }

    def session_usage(
        self,
        session_id: str | None = None,
        request_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        sessions: dict[str, dict[str, Any]] = {}
        request_id_filter = {
            request_id
            for request_id in request_ids or []
            if isinstance(request_id, str) and request_id
        }

        for order, record in enumerate(self._records()):
            record_session_id = record.get("session_id")
            if not isinstance(record_session_id, str) or not record_session_id:
                continue
            if session_id is not None and record_session_id != session_id:
                continue
            request_id = record.get("request_id")
            if request_id_filter and request_id not in request_id_filter:
                continue

            usage = _model_usage(record.get("model"))
            aggregate = sessions.setdefault(
                record_session_id,
                {
                    "session_id": record_session_id,
                    "agent_run_count": 0,
                    "request_ids": set(),
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "models": set(),
                    "_last_order": order,
                },
            )
            aggregate["agent_run_count"] += 1
            if isinstance(request_id, str) and request_id:
                aggregate["request_ids"].add(request_id)
            aggregate["input_tokens"] += usage["input_tokens"]
            aggregate["output_tokens"] += usage["output_tokens"]
            aggregate["total_tokens"] += usage["total_tokens"]
            aggregate["estimated_cost_usd"] += usage["estimated_cost_usd"]
            if usage.get("model_name"):
                aggregate["models"].add(usage["model_name"])
            aggregate["_last_order"] = order

        response_sessions = []
        for aggregate in sorted(sessions.values(), key=lambda item: item["_last_order"], reverse=True):
            response_sessions.append(
                {
                    "session_id": aggregate["session_id"],
                    "agent_run_count": aggregate["agent_run_count"],
                    "request_count": len(aggregate["request_ids"]),
                    "input_tokens": aggregate["input_tokens"],
                    "output_tokens": aggregate["output_tokens"],
                    "total_tokens": aggregate["total_tokens"],
                    "estimated_cost_usd": round(aggregate["estimated_cost_usd"], 8),
                    "models": sorted(list(aggregate["models"])),
                }
            )

        return {
            "found": bool(response_sessions),
            "sessions": response_sessions,
        }

    def _latest_record(self, request_id: str | None) -> dict[str, Any] | None:
        latest: dict[str, Any] | None = None
        for record in self._records():
            if request_id is not None and record.get("request_id") != request_id:
                continue
            latest = record
        return latest

    def _records(self) -> list[dict[str, Any]]:
        path = self.root / "unified_agent_runs.jsonl"
        if not path.exists():
            return []

        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records


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


def _model_usage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "model_name": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        }

    model_name = str(value.get("model_name") or value.get("model") or "")
    nested_usage = value.get("usage")
    usage = nested_usage if isinstance(nested_usage, dict) else value
    input_tokens = _first_int(usage, "input_tokens", "prompt_tokens")
    output_tokens = _first_int(usage, "output_tokens", "completion_tokens")
    total_tokens = _first_int(usage, "total_tokens") or input_tokens + output_tokens
    estimated_cost_usd = _first_float(usage, "estimated_cost_usd", "cost_usd")
    if estimated_cost_usd == 0.0 and model_name and (input_tokens or output_tokens):
        estimated_cost_usd = estimate_openai_llm_cost_usd(
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return {
        "model_name": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    }


def _first_int(value: dict[str, Any], *keys: str) -> int:
    for key in keys:
        resolved = _int_value(value.get(key))
        if resolved:
            return resolved
    return 0


def _first_float(value: dict[str, Any], *keys: str) -> float:
    for key in keys:
        resolved = _float_value(value.get(key))
        if resolved:
            return resolved
    return 0.0


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _float_value(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


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
