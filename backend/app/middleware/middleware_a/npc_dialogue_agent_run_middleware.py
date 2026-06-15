import warnings
from backend.app.services.service_a.agent_run_recorder import NPCDialogueAgentRunRecorder

class NPCDialogueAgentRunMiddleware(NPCDialogueAgentRunRecorder):
    """NPCDialogueAgentRunMiddleware는 더 이상 사용되지 않는 레거시 미들웨어 클래스이며, 하위 호환성을 제공하는 shim 클래스입니다."""
    def __init__(self, *args, **kwargs) -> None:
        warnings.warn(
            "NPCDialogueAgentRunMiddleware는 더 이상 사용되지 않습니다(Deprecated). "
            "대신 backend.app.services.service_a.agent_run_recorder.NPCDialogueAgentRunRecorder를 사용해 주세요.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)

