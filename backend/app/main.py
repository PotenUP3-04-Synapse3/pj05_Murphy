from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.ai_respond import router as ai_respond_router

RUNTIME_AUDIO_DIR = Path("backend/runtime/generated/audio")

app = FastAPI(
    title="Murphy Developer C Backend",
    version="0.1.0",
)

app.include_router(ai_respond_router)
app.mount(
    "/runtime/audio",
    StaticFiles(directory=RUNTIME_AUDIO_DIR, check_dir=False),
    name="runtime_audio",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "developer_c_backend",
    }
