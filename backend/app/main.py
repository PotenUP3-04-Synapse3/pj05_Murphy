from fastapi import FastAPI

from backend.app.api.ai_respond import router as ai_respond_router

app = FastAPI(
    title="Murphy Developer C Backend",
    version="0.1.0",
)

app.include_router(ai_respond_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "developer_c_backend",
    }
