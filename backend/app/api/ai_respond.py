import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket
from pydantic import ValidationError as PydanticValidationError
from starlette.datastructures import UploadFile
from starlette.websockets import WebSocketDisconnect

from backend.app.integrations.dev_b_level_hint_client import DevBPolicyClient
from backend.app.schemas.game_turn import (
    MockAudioInput,
    PrePrototypeRequest,
    RealtimeSubtitlePayload,
    RealtimeTranscriptClientEvent,
    RealtimeTranscriptServerEvent,
    UnrealResponse,
    UnrealResultResponse,
    UnrealTurnRequest,
)
from backend.app.services.service_c.agent_run_summary_service import AgentRunSummaryService
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.orchestrator import Orchestrator
from backend.app.services.service_c.settings_service import AppSettings, get_settings
from backend.app.services.service_c.unreal_request_capture_service import UnrealRequestCaptureService
from backend.app.services.service_c.validator import Validator

router = APIRouter(prefix="/api/game/ai", tags=["game-ai"])
AGENT_RUN_LOG_ROOT = Path("backend/runtime/generated/agent_runs")


@router.post("/respond", response_model=UnrealResponse)
async def respond(request: Request) -> UnrealResponse:
    settings = get_settings()
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        preprototype_request = await _parse_multipart_request(request, settings=settings)
    else:
        preprototype_request = PrePrototypeRequest.model_validate(await request.json())

    return Orchestrator().run_turn(preprototype_request)


@router.websocket("/stt/stream")
async def realtime_stt_stream(websocket: WebSocket) -> None:
    await websocket.accept()

    validator = Validator()
    session_started = False
    last_sequence: int | None = None

    while True:
        try:
            payload = await websocket.receive_json()
        except WebSocketDisconnect:
            return

        try:
            event = RealtimeTranscriptClientEvent.model_validate(payload)
            validator.validate_realtime_transcript_event(
                event,
                session_started=session_started,
                last_sequence=last_sequence,
            )
        except (PydanticValidationError, ValueError) as exc:
            await _send_realtime_event(websocket, _realtime_contract_error(payload, str(exc)))
            continue

        last_sequence = event.sequence

        if event.event_type == "session_start":
            session_started = True
            await _send_realtime_event(
                websocket,
                RealtimeTranscriptServerEvent(
                    event_type="session_started",
                    request_id=event.request_id,
                    session_id=event.session_id,
                    turn_index=event.turn_index,
                    sequence=event.sequence,
                    provider=event.provider,
                ),
            )
            continue

        if event.event_type == "cancel":
            await _send_realtime_event(
                websocket,
                RealtimeTranscriptServerEvent(
                    event_type="session_cancelled",
                    request_id=event.request_id,
                    session_id=event.session_id,
                    turn_index=event.turn_index,
                    sequence=event.sequence,
                    provider=event.provider,
                ),
            )
            await websocket.close()
            return

        is_final = event.event_type == "final_transcript"
        server_event_type: Literal["partial_transcript", "final_transcript"] = (
            "final_transcript" if is_final else "partial_transcript"
        )
        await _send_realtime_event(
            websocket,
            RealtimeTranscriptServerEvent(
                event_type=server_event_type,
                request_id=event.request_id,
                session_id=event.session_id,
                turn_index=event.turn_index,
                sequence=event.sequence,
                provider=event.provider,
                subtitle=RealtimeSubtitlePayload(
                    text=(event.transcript or "").strip(),
                    is_final=is_final,
                ),
                committed=is_final,
                target_endpoint="POST /api/game/ai/respond" if is_final else None,
            ),
        )


@router.get("/agent-runs/latest")
def latest_agent_run(request_id: str | None = None) -> dict[str, Any]:
    return AgentRunSummaryService(AGENT_RUN_LOG_ROOT).latest(request_id=request_id)


@router.get("/agent-runs/session-usage")
def session_agent_run_usage(
    session_id: str | None = None,
    request_ids: list[str] | None = Query(default=None),
) -> dict[str, Any]:
    return AgentRunSummaryService(AGENT_RUN_LOG_ROOT).session_usage(
        session_id=session_id,
        request_ids=request_ids,
    )


@router.get("/demo/node/{node_id}")
def demo_node_context(node_id: str) -> dict[str, Any]:
    try:
        node_context = OpenKBService().get_node_context("CH0_IMMIGRATION", node_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "node_id": node_context.node_id,
        "chapter_id": node_context.chapter_id,
        "npc_question": node_context.npc_question,
        "objective_kr": node_context.objective_kr,
        "recommended_expression": node_context.recommended_expression,
        "allowed_next_nodes": node_context.allowed_next_nodes,
    }


@router.get("/result/{session_id}", response_model=UnrealResultResponse)
def result(session_id: str) -> UnrealResultResponse:
    response = UnrealResultResponse(
        contract_version="dev_c_unreal_result.v1",
        session_id=session_id,
        final_result=DevBPolicyClient().final_result_for_session(session_id),
    )
    Validator().validate_unreal_result_response(response)
    return response


async def _parse_multipart_request(
    request: Request,
    *,
    settings: AppSettings,
) -> PrePrototypeRequest:
    form = await request.form()
    turn_part = form.get("turn")
    audio_part = form.get("audio")

    if turn_part is None:
        raise HTTPException(status_code=422, detail="Missing multipart field: turn")

    if not isinstance(audio_part, UploadFile):
        raise HTTPException(status_code=422, detail="Missing multipart wav file field: audio")

    turn_text = await _read_form_text(turn_part)
    audio_bytes = await audio_part.read()
    if settings.murphy_unreal_request_capture_mode == "debug":
        UnrealRequestCaptureService(settings.murphy_unreal_request_capture_root).capture_multipart_request(
            request=request,
            turn_text=turn_text,
            audio_bytes=audio_bytes,
            audio_filename=audio_part.filename,
            audio_content_type=audio_part.content_type,
        )

    try:
        turn_payload = json.loads(turn_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid multipart turn JSON: {exc.msg}") from exc

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


async def _send_realtime_event(websocket: WebSocket, event: RealtimeTranscriptServerEvent) -> None:
    await websocket.send_json(event.model_dump(mode="json", exclude_none=True))


def _realtime_contract_error(payload: Any, error_message: str) -> RealtimeTranscriptServerEvent:
    request_id = payload.get("request_id") if isinstance(payload, dict) else None
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    turn_index = payload.get("turn_index") if isinstance(payload, dict) else None
    sequence = payload.get("sequence") if isinstance(payload, dict) else None

    return RealtimeTranscriptServerEvent(
        event_type="contract_error",
        request_id=request_id if isinstance(request_id, str) else None,
        session_id=session_id if isinstance(session_id, str) else None,
        turn_index=turn_index if isinstance(turn_index, int) else None,
        sequence=sequence if isinstance(sequence, int) else None,
        error_message=error_message,
    )
