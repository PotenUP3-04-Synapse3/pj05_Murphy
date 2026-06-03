from fastapi import APIRouter

from backend.app.schemas.game_turn import PrePrototypeRequest, UnrealResponse
from backend.app.services.orchestrator import Orchestrator

router = APIRouter(prefix="/api/game/ai", tags=["game-ai"])


@router.post("/respond", response_model=UnrealResponse)
def respond(request: PrePrototypeRequest) -> UnrealResponse:
    return Orchestrator().run_turn(request)
