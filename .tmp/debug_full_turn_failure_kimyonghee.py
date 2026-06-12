from pathlib import Path
import json
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.main import app


def main() -> None:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    os.environ["MURPHY_STT_MODE"] = "local"
    os.environ["MURPHY_TTS_MODE"] = "real"
    os.environ["MURPHY_TTS_PROVIDER"] = "edge"
    os.environ["MURPHY_UNDERSTANDING_MODE"] = "llm"
    os.environ["MURPHY_NPC_DIALOGUE_MODE"] = "llm"
    os.environ["DEV_B_FEEDBACK_LLM_MODE"] = "llm"

    payload = json.loads(Path("demo/input/imm_002_purpose.json").read_text(encoding="utf-8"))
    with TestClient(app) as client:
        response = client.post(
            "/api/game/ai/respond",
            data={"turn": json.dumps(payload, ensure_ascii=False)},
            files={"audio": ("tour.wav", Path("samples/tour.wav").read_bytes(), "audio/wav")},
        )
        print(response.status_code)
        print(response.text[:2000])


if __name__ == "__main__":
    main()
