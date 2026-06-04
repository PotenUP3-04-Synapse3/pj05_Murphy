import json
from pathlib import Path
from typing import Any

from backend.app.services.shared.agent_run_log_store import (
    AgentRunLogStore,
    build_unified_agent_run_record,
)


class NPCDialogueAgentRunStore:
    """Developer A 전용 AgentRun table-like JSONL 저장소."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def append_agent_run(self, run: dict[str, Any]) -> Path:
        path = self.root / "npc_dialogue_agent_runs.jsonl"
        self._append_jsonl(path, run)
        return path

    def append_artifact(self, artifact: dict[str, Any]) -> Path:
        path = self.root / "npc_dialogue_artifacts.jsonl"
        self._append_jsonl(path, artifact)
        return path

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
        # 공통 로그는 원본 metadata를 보존하되, timeline event는 최상위 events로 분리한다.
        metadata = dict(run.get("metadata", {}))
        raw_events = metadata.pop("events", [])
        events = raw_events if isinstance(raw_events, list) else []
        if artifact_path is not None:
            metadata["artifact_path"] = str(artifact_path)

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
        return AgentRunLogStore(self.root).append_with_markdown(record)

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _float_or_zero(value: Any) -> float:
    return float(value) if isinstance(value, int | float) else 0.0
