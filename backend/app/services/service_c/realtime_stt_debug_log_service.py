from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import RealtimeTranscriptClientEvent, RealtimeTranscriptServerEvent
from backend.app.services.service_c.settings_service import AppSettings
from backend.app.services.shared.agent_run_log_store import AgentRunLogStore, build_unified_agent_run_record


class RealtimeSttDebugLogSession:
    def __init__(
        self,
        *,
        root: Path,
        settings: AppSettings,
        start_event: RealtimeTranscriptClientEvent,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        self.root = root
        self.settings = settings
        self.start_event = start_event
        self.started_at = now
        self.completed = False
        self.events: list[dict[str, Any]] = [
            {
                "event": "session_start",
                "status": "received",
                "recorded_at": now,
                "tool_name": "realtime_stt_websocket",
                "input_summary": {
                    "provider": start_event.provider,
                    "language_hint": start_event.language_hint,
                    "sequence": start_event.sequence,
                },
            }
        ]
        self.chunk_count = 0
        self.total_audio_bytes = 0
        self.sample_rate_hz = start_event.sample_rate_hz or 16000
        self.final_transcript: str | None = None
        self.final_provider: str | None = None
        self.target_endpoint: str | None = None
        self.provider_error_count = 0
        self.fallback_used = False

    def record_client_event(self, event: RealtimeTranscriptClientEvent) -> None:
        if self.completed:
            return

        if event.sample_rate_hz is not None:
            self.sample_rate_hz = event.sample_rate_hz

        if event.event_type == "audio_chunk":
            chunk_bytes = _safe_base64_byte_count(event.audio_base64)
            self.chunk_count += 1
            self.total_audio_bytes += chunk_bytes
            self.events.append(
                {
                    "event": "audio_chunk",
                    "status": "received",
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "tool_name": "realtime_stt_websocket",
                    "input_summary": {
                        "sequence": event.sequence,
                        "audio_bytes": chunk_bytes,
                        "commit": event.commit,
                        "sample_rate_hz": event.sample_rate_hz,
                    },
                }
            )

    def record_server_event(self, event: RealtimeTranscriptServerEvent | dict[str, Any]) -> None:
        if self.completed:
            return

        event_payload = _event_to_dict(event)
        event_type = _string_or_none(event_payload.get("event_type"))
        provider = _string_or_none(event_payload.get("provider"))
        if event_type == "provider_error":
            self.provider_error_count += 1

        subtitle = event_payload.get("subtitle")
        transcript = subtitle.get("text") if isinstance(subtitle, dict) else None
        if event_type == "final_transcript" and isinstance(transcript, str):
            self.final_transcript = transcript
            self.final_provider = provider
            self.target_endpoint = _string_or_none(event_payload.get("target_endpoint"))
            self.fallback_used = provider == "local_batch_fallback"

        self.events.append(
            {
                "event": event_type or "unknown_server_event",
                "status": "emitted",
                "recorded_at": datetime.now(UTC).isoformat(),
                "tool_name": "realtime_stt_relay",
                "output_summary": {
                    "provider": provider,
                    "committed": bool(event_payload.get("committed", False)),
                    "text_length": len(transcript) if isinstance(transcript, str) else 0,
                    "target_endpoint": event_payload.get("target_endpoint"),
                    "error_message": event_payload.get("error_message"),
                },
            }
        )

    def complete_and_append(self, *, status: str) -> tuple[Path, Path] | None:
        if self.completed:
            return None

        self.completed = True
        completed_at = datetime.now(UTC).isoformat()
        estimated_duration_ms = _estimate_duration_ms(
            audio_bytes=self.total_audio_bytes,
            sample_rate_hz=self.sample_rate_hz,
        )
        estimated_cost_usd = _estimate_cost_usd(
            duration_ms=estimated_duration_ms,
            cost_per_minute_usd=self.settings.elevenlabs_realtime_estimated_cost_per_minute_usd,
        )
        run_id_seed = (
            f"{self.start_event.request_id}:{self.start_event.session_id}:"
            f"{self.start_event.turn_index}:{self.started_at}"
        ).encode("utf-8")
        record = build_unified_agent_run_record(
            agent_run_id=f"c_stt_run_{sha256(run_id_seed).hexdigest()[:12]}",
            agent_name="realtime_stt_relay",
            owner="developer_c",
            request_id=self.start_event.request_id,
            session_id=self.start_event.session_id,
            turn_index=self.start_event.turn_index,
            status=status,
            source_window={
                "source_type": "realtime_stt_websocket",
                "chapter_id": self.start_event.chapter_id,
                "scene_id": self.start_event.scene_id,
                "node_id": self.start_event.current_node_id,
            },
            model_name="elevenlabs_realtime_stt",
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=estimated_cost_usd,
            events=self.events,
            summary={
                "input": {
                    "provider": self.start_event.provider,
                    "language_hint": self.start_event.language_hint,
                    "chunk_count": self.chunk_count,
                    "total_audio_bytes": self.total_audio_bytes,
                },
                "output": {
                    "final_transcript": self.final_transcript,
                    "final_provider": self.final_provider,
                    "target_endpoint": self.target_endpoint,
                    "committed": self.final_transcript is not None,
                },
            },
            metadata={
                "debug_scope": "developer_c_realtime_stt",
                "permission_level": "runtime_user_session",
                "audio": {
                    "chunk_count": self.chunk_count,
                    "total_audio_bytes": self.total_audio_bytes,
                    "sample_rate_hz": self.sample_rate_hz,
                    "estimated_duration_ms": estimated_duration_ms,
                },
                "cost": {
                    "currency": "USD",
                    "estimated_cost_usd": estimated_cost_usd,
                    "estimated_cost_per_minute_usd": (
                        self.settings.elevenlabs_realtime_estimated_cost_per_minute_usd
                    ),
                    "estimation_basis": "configured_per_minute_rate",
                },
                "runtime": {
                    "primary_provider": "elevenlabs_relay",
                    "fallback_provider_used": self.fallback_used,
                    "final_provider": self.final_provider,
                    "provider_error_count": self.provider_error_count,
                },
                "token_usage_note": "Realtime STT audio does not report LLM token usage; tokens are logged as 0.",
            },
            started_at=self.started_at,
            completed_at=completed_at,
        )
        return AgentRunLogStore(self.root).append_with_markdown(record)


def _event_to_dict(event: RealtimeTranscriptServerEvent | dict[str, Any]) -> dict[str, Any]:
    if isinstance(event, RealtimeTranscriptServerEvent):
        return event.model_dump(mode="json", exclude_none=True)
    return event


def _safe_base64_byte_count(value: str | None) -> int:
    if not value:
        return 0

    try:
        return len(base64.b64decode(value, validate=True))
    except binascii.Error:
        return 0


def _estimate_duration_ms(
    *,
    audio_bytes: int,
    sample_rate_hz: int,
    channels: int = 1,
    sample_width_bytes: int = 2,
) -> int:
    bytes_per_second = sample_rate_hz * channels * sample_width_bytes
    if bytes_per_second <= 0:
        return 0

    return round((audio_bytes / bytes_per_second) * 1000)


def _estimate_cost_usd(*, duration_ms: int, cost_per_minute_usd: float) -> float:
    if duration_ms <= 0 or cost_per_minute_usd <= 0:
        return 0.0

    return round((duration_ms / 60000) * cost_per_minute_usd, 8)


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None
