from datetime import UTC, datetime
from hashlib import sha256
from typing import Any


class NPCDialogueAgentRunMiddleware:
    """NPC Dialogue Agent 실행 1회를 구조화된 AgentRun 기록으로 조립한다."""

    def start_run(
        self,
        *,
        prompt_version: str,
        source_window: dict[str, Any],
        cache_key: str,
        model_name: str,
        permission_level: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        run_id_seed = f"{now}:{cache_key}:{model_name}".encode("utf-8")
        return {
            "agent_run_id": f"npcdlg_run_{sha256(run_id_seed).hexdigest()[:12]}",
            "agent_name": "npc_dialogue_agent",
            "prompt_version": prompt_version,
            "status": "running",
            "source_window": source_window,
            "cache_key": cache_key,
            "model_name": model_name,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "permission_level": permission_level,
            "metadata": metadata,
            "created_at": now,
            "completed_at": None,
        }

    def complete_run(
        self,
        run: dict[str, Any],
        *,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: float,
    ) -> dict[str, Any]:
        run["status"] = "completed"
        run["input_tokens"] = input_tokens
        run["output_tokens"] = output_tokens
        run["total_tokens"] = input_tokens + output_tokens
        run["estimated_cost_usd"] = estimated_cost_usd
        run["completed_at"] = datetime.now(UTC).isoformat()
        return run

    def fail_run(self, run: dict[str, Any], *, error: str) -> dict[str, Any]:
        run["status"] = "failed"
        run["metadata"]["error"] = error
        run["completed_at"] = datetime.now(UTC).isoformat()
        return run
