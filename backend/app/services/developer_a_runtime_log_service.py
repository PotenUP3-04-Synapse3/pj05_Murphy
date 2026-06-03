from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json
import uuid

PRIVATE_KEYS = {"player_text"}


def write_developer_a_event(
    log_path: Path,
    component_name: str,
    event: str,
    status: str,
    request_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Developer A component 실행 상태를 JSONL로 기록한다."""
    safe_metadata = {
        key: value for key, value in (metadata or {}).items() if key not in PRIVATE_KEYS
    }
    entry = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "request_id": request_id or f"req_{uuid.uuid4().hex}",
        "session_id": session_id or "session_unknown",
        "component_name": component_name,
        "event": event,
        "status": status,
        "metadata": safe_metadata,
        "created_at": datetime.now(UTC).isoformat(),
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
