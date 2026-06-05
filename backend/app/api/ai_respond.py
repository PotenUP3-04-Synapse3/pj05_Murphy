import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile

from backend.app.integrations.dev_b_level_hint_client import DevBPolicyClient
from backend.app.schemas.game_turn import (
    MockAudioInput,
    PrePrototypeRequest,
    UnrealResponse,
    UnrealResultResponse,
    UnrealTurnRequest,
)
from backend.app.services.service_c.agent_run_summary_service import AgentRunSummaryService
from backend.app.services.service_c.orchestrator import Orchestrator
from backend.app.services.service_c.validator import Validator

router = APIRouter(prefix="/api/game/ai", tags=["game-ai"])
AGENT_RUN_LOG_ROOT = Path("backend/runtime/generated/agent_runs")


@router.post("/respond", response_model=UnrealResponse)
async def respond(request: Request) -> UnrealResponse:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        preprototype_request = await _parse_multipart_request(request)
    else:
        preprototype_request = PrePrototypeRequest.model_validate(await request.json())

    return Orchestrator().run_turn(preprototype_request)


@router.get("/agent-runs/latest")
def latest_agent_run(request_id: str | None = None) -> dict[str, Any]:
    return AgentRunSummaryService(AGENT_RUN_LOG_ROOT).latest(request_id=request_id)


@router.get("/result/{session_id}", response_model=UnrealResultResponse)
def result(session_id: str) -> UnrealResultResponse:
    response = UnrealResultResponse(
        contract_version="dev_c_unreal_result.v1",
        session_id=session_id,
        final_result=DevBPolicyClient().final_result_for_session(session_id),
    )
    Validator().validate_unreal_result_response(response)
    return response


async def _parse_multipart_request(request: Request) -> PrePrototypeRequest:
    form = await request.form()
    turn_part = form.get("turn")
    audio_part = form.get("audio")

    if turn_part is None:
        raise HTTPException(status_code=422, detail="Missing multipart field: turn")

    if not isinstance(audio_part, UploadFile):
        raise HTTPException(status_code=422, detail="Missing multipart wav file field: audio")

    turn_payload = json.loads(await _read_form_text(turn_part))
    audio_bytes = await audio_part.read()

    return PrePrototypeRequest(
        turn=UnrealTurnRequest.model_validate(turn_payload),
        audio=MockAudioInput(
            mock_wav_path=f"samples/{audio_part.filename}",
            file_name=audio_part.filename,
            content_type=audio_part.content_type,
            audio_bytes=audio_bytes,
        ),
    )


async def _read_form_text(part: Any) -> str:
    if isinstance(part, UploadFile):
        return (await part.read()).decode("utf-8")

    if isinstance(part, str):
        return part

    raise HTTPException(status_code=422, detail="Multipart turn field must be JSON text")
