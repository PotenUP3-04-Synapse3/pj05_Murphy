from fastapi import FastAPI

app = FastAPI(
    title="Murphy Developer C Backend",
    version="0.1.0",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "developer_c_backend",
    }
