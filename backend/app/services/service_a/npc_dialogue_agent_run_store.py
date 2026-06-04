import json
from pathlib import Path
from typing import Any


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

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
