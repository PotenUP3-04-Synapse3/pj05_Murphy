"""Expose Developer C HTTP and WebSocket endpoints for Unreal and demos.

Beginner guide:
This module is the public door into the backend.  `POST /respond` receives one
player turn, normalizes multipart or JSON input, and passes it to the C
orchestrator.  `WebSocket /stt/stream` is separate: it streams subtitle-like STT
events for Unreal while the player is speaking.  Partial STT events are only UI
previews; committed final text is the only text that should later enter the
normal `/respond` turn flow.
"""

import json
from pathlib import Path
from typing import Any, Literal, Sequence, cast

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
    SttRuntimeUsed,
    UnrealResponse,
    UnrealResultResponse,
    UnrealTurnRequest,
)
from backend.app.services.service_c.agent_run_summary_service import AgentRunSummaryService
from backend.app.services.service_c.elevenlabs_realtime_stt_relay import (
    ElevenLabsRealtimeRelayError,
    ElevenLabsRealtimeSttRelay,
)
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.orchestrator import Orchestrator
from backend.app.services.service_c.realtime_stt_debug_log_service import RealtimeSttDebugLogSession
from backend.app.services.service_c.settings_service import AppSettings, get_settings
from backend.app.services.service_c.unreal_request_capture_service import UnrealRequestCaptureService
from backend.app.services.service_c.validator import Validator

router = APIRouter(prefix="/api/game/ai", tags=["game-ai"])
AGENT_RUN_LOG_ROOT = Path("backend/runtime/generated/agent_runs")
_STT_RUNTIME_USED_VALUES = frozenset(
    {
        "local",
        "api",
        "unreal_bridge",
        "stt_provider_websocket",
        "elevenlabs_relay",
        "local_batch_fallback",
        "mock",
    }
)


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

    settings = get_settings()
    validator = Validator()
    session_started = False
    last_sequence: int | None = None
    relay: ElevenLabsRealtimeSttRelay | None = None
    debug_log_session: RealtimeSttDebugLogSession | None = None

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except WebSocketDisconnect:
                return
            except RuntimeError as exc:
                if _is_websocket_receive_after_disconnect(exc):
                    return
                raise

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
                if settings.murphy_stt_debug_log_mode == "debug":
                    debug_log_session = RealtimeSttDebugLogSession(
                        root=AGENT_RUN_LOG_ROOT,
                        settings=settings,
                        start_event=event,
                    )

                if event.provider == "elevenlabs_relay":
                    relay = _build_elevenlabs_realtime_relay()
                    try:
                        relay_events = await relay.start(event)
                    except ElevenLabsRealtimeRelayError as exc:
                        await _send_realtime_events(
                            websocket,
                            [_realtime_provider_error(event, str(exc))],
                            debug_log_session=debug_log_session,
                            complete_on_terminal=True,
                        )
                        continue

                    await _send_realtime_events(
                        websocket,
                        relay_events,
                        debug_log_session=debug_log_session,
                    )
                    continue

                await _send_realtime_events(
                    websocket,
                    [
                        RealtimeTranscriptServerEvent(
                            event_type="session_started",
                            request_id=event.request_id,
                            session_id=event.session_id,
                            turn_index=event.turn_index,
                            sequence=event.sequence,
                            provider=event.provider,
                        )
                    ],
                    debug_log_session=debug_log_session,
                )
                continue

            if event.event_type == "audio_chunk":
                if debug_log_session is not None:
                    debug_log_session.record_client_event(event)

                if relay is None:
                    await _send_realtime_events(
                        websocket,
                        [_realtime_contract_error(payload, "audio_chunk requires an active ElevenLabs relay session")],
                        debug_log_session=debug_log_session,
                        complete_on_terminal=True,
                    )
                    continue

                try:
                    relay_events = await relay.send_audio_chunk(event)
                except ElevenLabsRealtimeRelayError as exc:
                    await _send_realtime_events(
                        websocket,
                        [_realtime_provider_error(event, str(exc))],
                        debug_log_session=debug_log_session,
                        complete_on_terminal=True,
                    )
                    continue

                await _send_realtime_events(
                    websocket,
                    relay_events,
                    debug_log_session=debug_log_session,
                    complete_on_terminal=True,
                )
                continue

            if event.event_type == "cancel":
                if relay is not None:
                    await relay.close()
                    relay = None
                await _send_realtime_events(
                    websocket,
                    [
                        RealtimeTranscriptServerEvent(
                            event_type="session_cancelled",
                            request_id=event.request_id,
                            session_id=event.session_id,
                            turn_index=event.turn_index,
                            sequence=event.sequence,
                            provider=event.provider,
                        )
                    ],
                    debug_log_session=debug_log_session,
                    complete_on_terminal=True,
                )
                await websocket.close()
                return

            is_final = event.event_type == "final_transcript"
            server_event_type: Literal["partial_transcript", "final_transcript"] = (
                "final_transcript" if is_final else "partial_transcript"
            )
            await _send_realtime_events(
                websocket,
                [
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
                    )
                ],
                debug_log_session=debug_log_session,
                complete_on_terminal=is_final,
            )
    finally:
        if relay is not None:
            await relay.close()


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
        node_context = OpenKBService().get_node_context(_chapter_id_for_demo_node(node_id), node_id)
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
@router.get("/demo/npc-roster")
def demo_npc_roster() -> dict[str, list[dict[str, Any]]]:
    """임시 데모 페이지용으로, 챕터별 선택 가능한 NPC 프로필 목록을 반환합니다.

    초보자용 설명:
    원래 게임은 시나리오 노드에 고정된 NPC가 나오지만, 데모/테스트 페이지에서는 
    각 챕터에 어울리는 NPC를 직접 선택해 대화해볼 수 있어야 합니다. 
    이 엔드포인트는 Dev A의 Roster를 읽어 프론트 드롭다운 옵션에 채울 데이터를 내려줍니다.
    """
    from backend.app.services.service_a.npc_roster_service import _NPC_ROSTER

    chapters_mapping = {
        "CH0_01_FLIGHT_SMALLTALK": ["arabella", "novak", "emily"],
        "CH0_03_IMMIGRATION_CHECK": ["hale", "harris"],
        "CH0_04_BAGGAGE_CLAIM": ["brielle", "dan"],
    }

    result = {}
    for chapter_id, npc_ids in chapters_mapping.items():
        candidates = []
        for npc_id in npc_ids:
            if npc_id in _NPC_ROSTER:
                profile = _NPC_ROSTER[npc_id]
                candidates.append({
                    "id": profile.npc_id,
                    "display_name": profile.display_name,
                    "role": profile.role,
                })
        result[chapter_id] = candidates

    return result


@router.get("/demo/eokkka/options")
def demo_eokkka_options() -> dict[str, Any]:
    """임시 데모 페이지용으로, 전체 억까 방문지 및 수화물 품목 목록을 반환합니다.

    초보자용 설명:
    프론트엔드 드롭다운 메뉴를 채우기 위한 정적 테이블 데이터 전체를 전달합니다.
    """
    from backend.app.data.challenge_tables import LOCATIONS, CUSTOMS_ITEMS

    # Convert dataclasses to dicts
    locations_list = []
    for loc in LOCATIONS:
        locations_list.append({
            "location_id": loc.location_id,
            "name_en": loc.name_en,
            "name_ko": loc.name_ko,
            "difficulty": loc.difficulty,
            "suspicion_reason": loc.suspicion_reason,
        })

    customs_items_list = []
    for item in CUSTOMS_ITEMS:
        customs_items_list.append({
            "item_id": item.item_id,
            "name_en": item.name_en,
            "name_ko": item.name_ko,
            "item_category": item.item_category,
            "difficulty": item.difficulty,
            "suspicion_reason": item.suspicion_reason,
        })

    return {
        "locations": locations_list,
        "customs_items": customs_items_list,
    }


@router.get("/demo/eokkka/assign")
def demo_eokkka_assign(level: int | None = Query(default=None)) -> dict[str, Any]:
    """임시 데모 페이지용으로, 영어 레벨 총점에 맞게 결정적 또는 랜덤으로 억까 방문지와 수화물을 선택해 반환합니다.

    초보자용 설명:
    level이 0~12 사이 정수이면 시드 고정 RNG(Random) 객체를 생성하여
    매번 해당 난이도 풀에서 고정된 값을 할당(결정론적 부여)해 줍니다.
    level이 비어(None/null) 있으면 전체 목록에서 임의로 랜덤 선택하여 반환합니다.
    """
    import random
    from backend.app.data.challenge_tables import LOCATIONS, CUSTOMS_ITEMS
    from backend.app.services.service_b.challenge_assignment_service import (
        pick_location,
        pick_customs_item,
        to_random_customs_item_context,
    )
    from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyController

    if level is not None:
        clamped_level = max(0, min(12, level))
        tsl = TierDifficultyController().travel_speaking_level_for_total(clamped_level)
        rng = random.Random(clamped_level)
        loc = pick_location(tsl, rng=rng)
        item = pick_customs_item(tsl, rng=rng)
    else:
        loc = random.choice(LOCATIONS)
        item = random.choice(CUSTOMS_ITEMS)

    customs_item_context = to_random_customs_item_context(item)

    return {
        "assigned_visit_location": loc.name_en,
        "assigned_visit_location_ko": loc.name_ko,
        "visit_location_difficulty": loc.difficulty,
        "visit_location_suspicion_reason": loc.suspicion_reason,
        "random_customs_item": customs_item_context.model_dump(),
    }


def _chapter_id_for_demo_node(node_id: str) -> str:
    if node_id.startswith("FLIGHT_"):
        return "CH0_01_FLIGHT_SMALLTALK"
    if node_id.startswith("BAG_"):
        return "CH0_04_BAGGAGE_CLAIM"
    if node_id.startswith("ALPHA_"):
        return "CH0_05_RESULT"
    return "CH0_03_IMMIGRATION_CHECK"


def _is_websocket_receive_after_disconnect(error: RuntimeError) -> bool:
    """이미 닫힌 WebSocket에서 receive를 시도한 Starlette 오류인지 확인한다.

    Starlette는 클라이언트가 먼저 연결을 닫은 뒤 `receive_json()`이 호출되면
    `WebSocketDisconnect` 대신 RuntimeError를 던지는 경로가 있다. 이 문구만
    정상적인 클라이언트 종료로 보고, 다른 RuntimeError는 실제 버그일 수 있어
    그대로 다시 올린다.
    """

    return 'WebSocket is not connected. Need to call "accept" first.' in str(error)


@router.get("/result/{session_id}", response_model=UnrealResultResponse)
def result(session_id: str) -> UnrealResultResponse:
    dev_b_client = DevBPolicyClient()
    response = UnrealResultResponse(
        contract_version="dev_c_unreal_result.v1",
        session_id=session_id,
        final_result=dev_b_client.final_result_for_session(session_id),
        out_game_feedback=dev_b_client.out_game_feedback_for_session(session_id),
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
        audio=_multipart_audio_input_from_turn_payload(
            turn_payload=turn_payload,
            audio_filename=audio_part.filename,
            audio_content_type=audio_part.content_type,
            audio_bytes=audio_bytes,
        ),
    )


async def _read_form_text(part: Any) -> str:
    if isinstance(part, UploadFile):
        return (await part.read()).decode("utf-8")

    if isinstance(part, str):
        return part

    raise HTTPException(status_code=422, detail="Multipart turn field must be JSON text")


def _multipart_audio_input_from_turn_payload(
    *,
    turn_payload: dict[str, Any],
    audio_filename: str | None,
    audio_content_type: str | None,
    audio_bytes: bytes,
) -> MockAudioInput:
    """multipart 요청에서 실제 STT 입력으로 쓸 오디오 정보를 만듭니다.

    초보자용 설명:
    Unreal의 realtime STT 경로는 이미 WebSocket에서 final transcript를 얻은 뒤에도
    호환성 때문에 짧은 WAV 파일을 multipart에 함께 보낼 수 있습니다. 이때 정답
    텍스트는 `turn.audio.transcript`에 들어 있으므로, C backend는 WAV를 다시
    STT하지 않고 이 값을 `MockAudioInput.transcript`로 옮겨야 합니다.
    """

    transcript, transcript_provider = _extract_realtime_transcript_from_turn_audio(turn_payload)
    return MockAudioInput(
        mock_wav_path=f"samples/{audio_filename}",
        transcript=transcript,
        transcript_provider=transcript_provider,
        file_name=audio_filename,
        content_type=audio_content_type,
        audio_bytes=audio_bytes,
    )


def _extract_realtime_transcript_from_turn_audio(
    turn_payload: dict[str, Any],
) -> tuple[str | None, SttRuntimeUsed | None]:
    """`turn.audio`에 섞여 들어온 realtime STT 결과를 안전하게 꺼냅니다.

    초보자용 설명:
    `UnrealTurnRequest.audio`는 원래 오디오 메타데이터 스키마라서 Pydantic 검증 후에는
    `transcript` 같은 추가 키가 사라집니다. 그래서 검증 전에 원본 dict에서 필요한
    값을 읽어 별도의 STT 입력 객체로 복사합니다.
    """

    audio_payload = turn_payload.get("audio")
    if not isinstance(audio_payload, dict):
        return None, None

    transcript = _optional_stripped_text(audio_payload.get("transcript"))
    if transcript is None:
        return None, None

    return transcript, _optional_stt_runtime_used(audio_payload.get("transcript_provider"))


def _optional_stt_runtime_used(value: Any) -> SttRuntimeUsed | None:
    """STT provider 문자열을 C 내부에서 쓰는 안전한 runtime 값으로 바꿉니다.

    초보자용 설명:
    외부 JSON은 문자열이면 무엇이든 보낼 수 있지만, backend 스키마는 정해진 provider만
    허용합니다. 여기서 한 번 검증하면 잘못된 provider가 조용히 `local`처럼 보이는
    일을 막고, 타입 검사기에도 "이 값은 허용된 STT runtime"이라고 알려줄 수 있습니다.
    """

    stripped = _optional_stripped_text(value)
    if stripped is None:
        return None
    if stripped not in _STT_RUNTIME_USED_VALUES:
        raise HTTPException(status_code=422, detail=f"Unsupported transcript_provider: {stripped}")

    return cast(SttRuntimeUsed, stripped)


def _optional_stripped_text(value: Any) -> str | None:
    """문자열이면 공백을 정리하고, 비어 있으면 `None`으로 바꿉니다."""

    if not isinstance(value, str):
        return None

    stripped = value.strip()
    return stripped or None


async def _send_realtime_event(websocket: WebSocket, event: RealtimeTranscriptServerEvent | dict[str, Any]) -> bool:
    """Realtime STT 서버 이벤트 1개를 보내고, 전송 성공 여부를 돌려준다.

    클라이언트가 녹음 중단, 페이지 이동, Unreal PIE 종료 등으로 WebSocket을
    먼저 닫을 수 있다. 그 경우는 백엔드 장애가 아니라 정상적인 연결 종료로
    보고, uvicorn 에러 스택이 남지 않도록 `False`로 정리한다.
    """

    if isinstance(event, RealtimeTranscriptServerEvent):
        try:
            await websocket.send_json(event.model_dump(mode="json", exclude_none=True))
        except WebSocketDisconnect:
            return False
        return True

    try:
        await websocket.send_json(event)
    except WebSocketDisconnect:
        return False
    return True


async def _send_realtime_events(
    websocket: WebSocket,
    events: Sequence[RealtimeTranscriptServerEvent | dict[str, Any]],
    *,
    debug_log_session: RealtimeSttDebugLogSession | None = None,
    complete_on_terminal: bool = False,
) -> bool:
    """Realtime STT 이벤트 묶음을 순서대로 보내고 연결 종료를 안전하게 처리한다.

    여러 이벤트를 보내는 도중 클라이언트가 이미 닫혀 있으면 남은 이벤트 전송을
    중단한다. 호출자는 반환값을 무시해도 되지만, 테스트와 디버깅에서는 `False`
    를 보고 "클라이언트가 먼저 끊었다"는 사실을 구분할 수 있다.
    """

    for event in events:
        if debug_log_session is not None:
            debug_log_session.record_server_event(event)
        if not await _send_realtime_event(websocket, event):
            return False

    if debug_log_session is not None and complete_on_terminal:
        status = _realtime_debug_completion_status(events)
        if status is not None:
            debug_log_session.complete_and_append(status=status)

    return True


def _realtime_debug_completion_status(events: Sequence[RealtimeTranscriptServerEvent | dict[str, Any]]) -> str | None:
    event_types = {_realtime_event_type(event) for event in events}
    if "final_transcript" in event_types:
        return "success"
    if "session_cancelled" in event_types:
        return "cancelled"
    if "provider_error" in event_types or "contract_error" in event_types:
        return "failed"
    return None


def _realtime_event_type(event: RealtimeTranscriptServerEvent | dict[str, Any]) -> str | None:
    if isinstance(event, RealtimeTranscriptServerEvent):
        return event.event_type
    event_type = event.get("event_type")
    return event_type if isinstance(event_type, str) else None


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


def _realtime_provider_error(event: RealtimeTranscriptClientEvent, error_message: str) -> RealtimeTranscriptServerEvent:
    return RealtimeTranscriptServerEvent(
        event_type="provider_error",
        request_id=event.request_id,
        session_id=event.session_id,
        turn_index=event.turn_index,
        sequence=event.sequence,
        provider=event.provider,
        error_message=error_message,
    )


def _build_elevenlabs_realtime_relay() -> ElevenLabsRealtimeSttRelay:
    return ElevenLabsRealtimeSttRelay()
