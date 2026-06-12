from pathlib import Path
import json
import os
import sys
import time

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.main import app


def main() -> None:
    _load_dotenv()
    os.environ["MURPHY_STT_MODE"] = "local"
    os.environ["MURPHY_TTS_MODE"] = "real"
    os.environ["MURPHY_TTS_PROVIDER"] = "elevenlabs"
    os.environ["MURPHY_UNDERSTANDING_MODE"] = "llm"
    os.environ["MURPHY_NPC_DIALOGUE_MODE"] = "llm"
    os.environ["DEV_B_FEEDBACK_LLM_MODE"] = "llm"

    payload = json.loads(Path("demo/input/imm_002_purpose.json").read_text(encoding="utf-8"))
    payload["request_id"] = f"req_elevenlabs_integrated_{int(time.time() * 1000)}"
    payload["session"]["session_id"] = "session_elevenlabs_integrated"

    started_at = time.perf_counter()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/game/ai/respond",
            data={"turn": json.dumps(payload, ensure_ascii=False)},
            files={"audio": ("tour.wav", Path("samples/tour.wav").read_bytes(), "audio/wav")},
        )
    elapsed_seconds = time.perf_counter() - started_at
    body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    print(
        json.dumps(
            {
                "status": response.status_code,
                "elapsed_seconds": round(elapsed_seconds, 3),
                "request_id": payload["request_id"],
                "next_action": body.get("next_action"),
                "next_node_id": body.get("next_node_id"),
                "npc": body.get("npc"),
            },
            ensure_ascii=False,
        )
    )


def _load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
