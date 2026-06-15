"""Capture raw Unreal multipart requests for local debugging.

Beginner guide:
When debug capture is enabled, this service writes the incoming turn JSON,
audio WAV, and metadata to a generated runtime folder.  It is intentionally
separate from the normal orchestrator so request capture can be turned on for
diagnosis without changing gameplay behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from fastapi import Request


class UnrealRequestCaptureService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def capture_multipart_request(
        self,
        *,
        request: Request,
        turn_text: str,
        audio_bytes: bytes,
        audio_filename: str | None,
        audio_content_type: str | None,
    ) -> Path:
        captured_at = datetime.now(UTC)
        request_id = _extract_request_id(turn_text)
        capture_dir = self.root / _capture_dir_name(
            captured_at=captured_at,
            request_id=request_id,
            turn_text=turn_text,
            audio_bytes=audio_bytes,
        )
        capture_dir.mkdir(parents=True, exist_ok=False)

        (capture_dir / "turn.json").write_text(turn_text, encoding="utf-8")
        (capture_dir / "audio.wav").write_bytes(audio_bytes)
        (capture_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "schema_version": "unreal_request_capture.v1",
                    "captured_at": captured_at.isoformat(),
                    "request_id": request_id,
                    "remote_addr": request.client.host if request.client else None,
                    "content_type": request.headers.get("content-type", ""),
                    "turn_field_bytes": len(turn_text.encode("utf-8")),
                    "audio_filename": audio_filename,
                    "audio_content_type": audio_content_type,
                    "audio_bytes": len(audio_bytes),
                    "files": {
                        "turn": "turn.json",
                        "audio": "audio.wav",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return capture_dir


def _capture_dir_name(
    *,
    captured_at: datetime,
    request_id: str,
    turn_text: str,
    audio_bytes: bytes,
) -> str:
    timestamp = captured_at.strftime("%Y%m%dT%H%M%S%fZ")
    digest = sha256(turn_text.encode("utf-8") + audio_bytes).hexdigest()[:12]
    return f"{timestamp}_{_safe_path_token(request_id)}_{digest}"


def _extract_request_id(turn_text: str) -> str:
    try:
        payload: Any = json.loads(turn_text)
    except ValueError:
        return "unknown_request"
    if isinstance(payload, dict) and isinstance(payload.get("request_id"), str):
        return payload["request_id"]
    return "unknown_request"


def _safe_path_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return token[:80] or "unknown_request"
