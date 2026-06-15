from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

class NPCDialogueAgentRunRecorder:
    """NPC 대화 에이전트(Dialogue Agent) 실행 과정의 이벤트를 기록하고 관리하는 에이전트 실행 기록기(AgentRun Recorder) 클래스입니다."""
    
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
        """에이전트 최초 기동 시 상태를 'running'으로 기입하고, 실행 세션 고유 식별자(Run ID)를 해시 생성하여 기록지를 시작합니다."""
        metadata.setdefault("events", [])
        now = datetime.now(UTC).isoformat()
        # 시간, 캐시 키, 모델명을 혼합하여 충돌 방지용 고유 시드(Seed) 바이트를 구성합니다.
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

    def record_event(
        self,
        metadata: dict[str, Any],
        *,
        event: str,
        status: str,
        tool_name: str | None = None,
        data_loaded: dict[str, Any] | None = None,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """대화 생성 파이프라인 중간(예: 도구 호출 완료, 번역 등)에 일어나는 세부 실행 타임라인 이벤트(Timeline Event)를 누적 기록합니다."""
        events = metadata.setdefault("events", [])
        if not isinstance(events, list):
            metadata["events"] = []
            events = metadata["events"]

        # 기록할 이벤트의 스냅샷 데이터를 조립합니다.
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

    def complete_run(
        self,
        run: dict[str, Any],
        *,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: float,
    ) -> dict[str, Any]:
        """에이전트가 오류 없이 정상 연산을 완료했을 때 상태를 'completed'로 매핑하고 사용 토큰 수 및 예상 비용을 기록지에 반영하여 완료 마크합니다."""
        run["status"] = "completed"
        run["input_tokens"] = input_tokens
        run["output_tokens"] = output_tokens
        run["total_tokens"] = input_tokens + output_tokens
        run["estimated_cost_usd"] = estimated_cost_usd
        run["completed_at"] = datetime.now(UTC).isoformat()
        return run

    def fail_run(self, run: dict[str, Any], *, error: str) -> dict[str, Any]:
        """파이프라인 구동 중 오류나 예외(Exception)가 발발했을 때 상태를 'failed'로 변경하고 오류 사유를 기입해 로그를 조기 차단(Close)합니다."""
        run["status"] = "failed"
        run["metadata"]["error"] = error
        run["completed_at"] = datetime.now(UTC).isoformat()
        return run
