import json
from pathlib import Path
from typing import Any

from backend.app.services.shared.agent_run_markdown_formatter import format_agent_run_markdown


class AgentRunLogStore:
    """A/B/C AgentRun 기록을 공통 JSONL과 Markdown 파일에 append하는 저장소."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def append(self, record: dict[str, Any]) -> Path:
        path = self.root / "unified_agent_runs.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    def append_markdown(self, markdown: str) -> Path:
        path = self.root / "unified_agent_runs.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(markdown.rstrip() + "\n\n")
        return path

    def append_with_markdown(self, record: dict[str, Any]) -> tuple[Path, Path]:
        jsonl_path = self.append(record)
        markdown_path = self.append_markdown(format_agent_run_markdown(record))
        return jsonl_path, markdown_path


def build_unified_agent_run_record(
    *,
    agent_run_id: str,
    agent_name: str,
    owner: str,
    request_id: str | None,
    session_id: str | None,
    turn_index: int | None,
    status: str,
    source_window: dict[str, Any],
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    events: list[dict[str, Any]],
    summary: dict[str, Any],
    metadata: dict[str, Any],
    started_at: Any,
    completed_at: Any,
) -> dict[str, Any]:
    """각 agent의 실행 정보를 동일한 공통 AgentRun schema로 정규화한다."""
    total_tokens = input_tokens + output_tokens
    return {
        "schema_version": "unified_agent_run.v1",
        "agent_run_id": agent_run_id,
        "agent_name": agent_name,
        "owner": owner,
        "request_id": request_id,
        "session_id": session_id,
        "turn_index": turn_index,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "source_window": source_window,
        "model": {
            "model_name": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        },
        "events": events,
        "summary": summary,
        "metadata": metadata,
    }
