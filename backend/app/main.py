"""Create the Developer C FastAPI application.

Beginner guide:
This file is the web server entry point.  FastAPI reads the `app` object,
mounts runtime audio files under `/runtime/audio`, and connects the game AI
routes from `backend.app.api.ai_respond`.  The small page routes at the bottom
only serve local demo HTML files; the real gameplay API lives in the router.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.ai_respond import router as ai_respond_router

RUNTIME_AUDIO_DIR = Path("backend/runtime/generated/audio")
DEMO_AI_RESPOND_PAGE = Path("demo/ai-respond/index.html")
RESPOND_DIALOG_PAGE = Path("demo/respond-dialog/index.html")

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


@app.get("/demo/ai-respond", tags=["demo"])
def demo_ai_respond() -> FileResponse:
    return FileResponse(DEMO_AI_RESPOND_PAGE)


@app.get("/respond-dialog", tags=["demo"])
def respond_dialog() -> FileResponse:
    return FileResponse(RESPOND_DIALOG_PAGE)
