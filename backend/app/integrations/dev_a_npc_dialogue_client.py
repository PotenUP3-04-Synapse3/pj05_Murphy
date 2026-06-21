"""Developer C adapter for calling Developer A dialogue and TTS logic.

Beginner guide:
This file is C-owned even though it calls Developer A.  It translates C/B turn
state into the level-design payload that A's voice output service expects, then
wraps A's result back into the `DevADialogueOutput` contract.  C does not create
A's NPC voice logic here; it only adapts inputs and validates the boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import DevADialogueInput, DevADialogueOutput, NpcContext, UnderstandingOutput
from backend.app.services.service_c.incivility_classifier import default_incivility_classification
from backend.app.services.service_a.voice_output_service import build_voice_output_from_level_design
from backend.app.services.service_c.openkb_service import OpenKBService, public_node_context
from backend.app.services.service_c.settings_service import AppSettings, get_settings

VoiceOutputBuilder = Callable[..., dict[str, Any]]


# Developer A는 최종 NPC 대사와 TTS 문장을 직접 생성해야 하므로,
# B가 만든 정답 예문/질문 문장/분기 제어 정책은 A-facing payload에서 제거합니다.
_A_BLOCKED_NODE_CONTEXT_FIELDS = frozenset(
    {
        "npc_question",
        "npc_question_goal",
        "recommended_expression",
    }
)
_A_BLOCKED_IN_GAME_FEEDBACK_FIELDS = frozenset(
    {
        "npc_recast_line_candidate",
        "recommended_expression",
    }
)
_A_BLOCKED_LEVEL_HINT_FIELDS = frozenset({"recommended_expression"})
_A_BLOCKED_DIALOGUE_DIRECTIVE_FIELDS = frozenset(
    {
        "do_not_generate_npc_text",
        "hint_frequency",
        "pressure_level",
    }
)


class DevANpcDialogueClient:
    def __init__(
        self,
        *,
        runtime_root: Path | None = None,
        audio_url_base: str = "/runtime/audio",
        use_real_tts: bool | None = None,
        use_llm_dialogue: bool | None = None,
        openkb_service: OpenKBService | None = None,
        settings: AppSettings | None = None,
        voice_output_builder: VoiceOutputBuilder = build_voice_output_from_level_design,
    ) -> None:
        resolved_settings = settings or get_settings()
        self.runtime_root = runtime_root or Path("backend/runtime/generated")
        self.audio_url_base = audio_url_base
        self.use_real_tts = (
            use_real_tts
            if use_real_tts is not None
            else resolved_settings.murphy_tts_mode == "real"
        )
        self.use_llm_dialogue = (
            use_llm_dialogue
            if use_llm_dialogue is not None
            else resolved_settings.murphy_npc_dialogue_mode == "llm"
        )
        self.openkb_service = openkb_service or OpenKBService()
        self.voice_output_builder = voice_output_builder

    def generate_dialogue(self, payload: DevADialogueInput) -> DevADialogueOutput:
        session_id = payload.session_id
        npc_id = payload.npc.npc_id if payload.npc else ""
        if not session_id or not session_id.strip() or not npc_id or not npc_id.strip():
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="session_id and npc_id are required for memory isolation",
            )

        expected_npc = _a_facing_npc_context(payload)
        level_design_payload = self._build_level_design_payload(payload, expected_npc)
        result = self.voice_output_builder(
            level_design_payload,
            runtime_root=self.runtime_root,
            request_id=payload.request_id,
            session_id=payload.session_id,
            user_id=payload.session_id,
            use_real_tts=self.use_real_tts,
            use_llm_dialogue=self.use_llm_dialogue,
            audio_url_base=self.audio_url_base,
        )

        speaker = str(result.get("speaker", "Officer Miller"))
        return DevADialogueOutput(
            contract_version="dev_a_dialogue.v1",
            speaker=speaker,
            text=_normalize_dialogue_text(
                str(result.get("npc_text") or result.get("text") or "Okay. Please continue.")
            ),
            tone=str(result.get("tone", "formal_neutral")),
            animation=str(result.get("animation", "officer_check_passport")),
            feedback_kr=_optional_string(result.get("feedback_kr")),
            audio_url=_extract_audio_url(result),
            diagnostics=_speaker_mismatch_diagnostics(expected_npc, speaker),
        )

    def _build_level_design_payload(
        self,
        payload: DevADialogueInput,
        expected_npc: NpcContext,
    ) -> dict[str, Any]:
        policy = payload.developer_b_policy
        evaluation = policy.evaluation
        feedback = policy.in_game_feedback.model_dump()
        level_hint = policy.level_hint.model_dump()
        
        public_context = public_node_context(payload.node_context)
        node_context = public_context.model_dump()
        
        branch = policy.branch.model_dump()
        dialogue_directive = policy.dialogue_directive.model_dump() if policy.dialogue_directive else {}

        # A가 B의 정답 예문이나 고정 질문을 그대로 대사화하지 않도록 경계에서 제거합니다.
        _sanitize_a_facing_level_design_payload(
            feedback=feedback,
            level_hint=level_hint,
            node_context=node_context,
            dialogue_directive=dialogue_directive,
        )

        npc = expected_npc.model_dump()
        npc["emotion"] = policy.npc_emotion

        random_customs_item_dump = (
            payload.random_customs_item.model_dump()
            if payload.random_customs_item is not None
            else None
        )
        game_state_dump = (
            payload.game_state.model_dump()
            if payload.game_state is not None
            else None
        )
        dialogue_seed_dump = (
            policy.dialogue_seed.model_dump()
            if policy.dialogue_seed is not None
            else None
        )

        if _is_flight_smalltalk_turn(payload.current_node_id, payload.node_context.chapter_id):
            node_context["required_slots"] = []
            node_context["optional_slots"] = []
            node_context["critical_slots"] = []
            dialogue_directive["target_slot"] = None
            if dialogue_seed_dump is not None:
                dialogue_seed_dump["required_slots"] = []

        game_state_dump, random_customs_item_dump, dialogue_seed_dump = _filter_suspicion_data(
            required_slots=payload.node_context.required_slots,
            game_state=game_state_dump,
            top_customs_item=random_customs_item_dump,
            dialogue_seed=dialogue_seed_dump,
        )

        return {
            "node_id": payload.current_node_id,
            "player_text": payload.player_text,
            "npc": npc,
            "node_context": node_context,
            "understanding": payload.understanding.model_dump(),
            "incivility": _a_facing_incivility(payload.understanding),
            "transition": payload.transition.model_dump() if payload.transition is not None else None,
            "game_state": game_state_dump,
            "random_customs_item": random_customs_item_dump,
            "dialogue_seed": dialogue_seed_dump,
            "evaluation_summary": {
                "feedback_note": evaluation.feedback_note or "",
                "main_feedback_tag": evaluation.feedback_tags[0] if evaluation.feedback_tags else "",
                "task_success": evaluation.scores.task_success,
                "clarity": evaluation.scores.clarity,
            },
            "level_hint": level_hint,
            "in_game_feedback": feedback,
            "branch": branch,
            "dialogue_directive": dialogue_directive,
        }

    def _llm_candidate_text(self, payload: DevADialogueInput) -> str:
        if payload.developer_b_policy.branch.branch_type not in {"success", "final"}:
            return ""
        return self._next_node_question(payload)

    def _candidate_text(self, payload: DevADialogueInput) -> str:
        policy = payload.developer_b_policy
        feedback = policy.in_game_feedback
        if policy.branch.branch_type not in {"success", "final"}:
            return feedback.npc_recast_line_candidate or ""

        if policy.branch.branch_type == "final":
            return payload.node_context.npc_question

        next_question = self._next_node_question(payload)
        recast = _second_person_recast(feedback.npc_recast_line_candidate)
        if recast and next_question:
            return f"{recast} {next_question}"
        if next_question:
            return next_question
        return recast

    def _next_node_question(self, payload: DevADialogueInput) -> str:
        next_node_id = payload.developer_b_policy.branch.next_node_id
        try:
            node_context = self.openkb_service.get_node_context(payload.node_context.chapter_id, next_node_id)
        except ValueError:
            return ""

        if node_context.node_id == payload.current_node_id:
            return ""

        return node_context.npc_question


def _is_flight_smalltalk_turn(current_node_id: str, chapter_id: str) -> bool:
    return current_node_id.startswith("FLIGHT_") or chapter_id == "CH0_01_FLIGHT_SMALLTALK"


def _second_person_recast(text: str | None) -> str:
    if not text:
        return ""

    normalized = text.strip()
    if normalized.startswith("I'm "):
        normalized = "You're " + normalized.removeprefix("I'm ")
    return normalized if normalized.endswith((".", "?", "!")) else f"{normalized}."


def _sanitize_a_facing_level_design_payload(
    *,
    feedback: dict[str, Any],
    level_hint: dict[str, Any],
    node_context: dict[str, Any],
    dialogue_directive: dict[str, Any],
) -> None:
    """Developer A에게 넘기면 안 되는 B-authored 필드를 제거합니다.

    초보자용 설명:
    Developer B의 결과에는 학습 UI에 보여줄 정답 예문, 시나리오 노드의 고정 질문,
    분기 정책처럼 유용하지만 "NPC가 그대로 말하면 안 되는" 데이터가 섞여 있습니다.
    이 함수는 C-to-A 경계에서 그런 값을 키 자체로 삭제해 A가 B 문장을 베끼지 않고
    `dialogue_seed`와 슬롯 메타데이터를 바탕으로 자기 대사를 생성하게 만듭니다.
    """

    _remove_keys(feedback, _A_BLOCKED_IN_GAME_FEEDBACK_FIELDS)
    _remove_keys(level_hint, _A_BLOCKED_LEVEL_HINT_FIELDS)
    _remove_keys(node_context, _A_BLOCKED_NODE_CONTEXT_FIELDS)
    _remove_keys(dialogue_directive, _A_BLOCKED_DIALOGUE_DIRECTIVE_FIELDS)


def _remove_keys(target: dict[str, Any], keys: frozenset[str]) -> None:
    """딕셔너리에서 금지된 키를 안전하게 지웁니다.

    초보자용 설명:
    `pop(key, None)`을 쓰면 키가 없을 때도 오류가 나지 않습니다. 그래서 B의 출력
    스키마가 조금 달라져도 어댑터는 필요한 필드만 조용히 제거하고 계속 동작합니다.
    """

    for key in keys:
        target.pop(key, None)


def _normalize_dialogue_text(text: str) -> str:
    normalized = text.strip()
    if normalized.startswith("Alright."):
        return "All right." + normalized.removeprefix("Alright.")
    if normalized.startswith("Alright,"):
        return "All right," + normalized.removeprefix("Alright,")
    return normalized


def _extract_audio_url(result: dict[str, Any]) -> str | None:
    tts = result.get("tts")
    if not isinstance(tts, dict):
        return None

    return _optional_string(tts.get("audio_url"))


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _a_facing_incivility(understanding: UnderstandingOutput) -> dict[str, Any]:
    """Return the top-level incivility object Developer A expects.

    초보자용 설명:
    최신 C Understanding은 `incivility`를 붙이지만, 오래된 테스트나 임시 mock은
    아직 이 값을 비울 수 있습니다. A 쪽 payload 모양을 항상 일정하게 만들기 위해
    값이 없으면 tier 0 기본값을 넣어 보냅니다.
    """

    incivility = understanding.incivility or default_incivility_classification()
    return incivility.model_dump()


def _a_facing_npc_context(payload: DevADialogueInput) -> NpcContext:
    """Return the NPC identity Developer A should see for this Alpha node.

    Beginner guide:
    Unreal can sometimes carry the previous NPC while the scenario moves from
    the baggage service desk to the customs hold.  Developer C does not edit A's
    dialogue logic here; it only normalizes the C-to-A boundary so BAG_001-004
    are service-staff turns and BAG_005-007 are customs-officer turns.
    """

    node_id = payload.node_context.node_id
    if _is_baggage_service_node(node_id):
        return NpcContext(
            npc_id="BAGGAGE_STAFF",
            npc_role="baggage_service_staff",
            last_npc_message=payload.npc.last_npc_message,
        )
    if _is_customs_hold_node(node_id):
        return NpcContext(
            npc_id="CUSTOMS_OFFICER",
            npc_role="customs_officer",
            last_npc_message=payload.npc.last_npc_message,
        )
    return payload.npc


def _is_baggage_service_node(node_id: str) -> bool:
    """Return whether a BAG node belongs to the service-desk staff phase."""

    return node_id.startswith(("BAG_001", "BAG_002", "BAG_003", "BAG_004"))


def _is_customs_hold_node(node_id: str) -> bool:
    """Return whether a BAG node belongs to the customs-officer hold phase."""

    return node_id.startswith(("BAG_005", "BAG_006", "BAG_007"))


def _speaker_mismatch_diagnostics(expected_npc: NpcContext, actual_speaker: str) -> list[dict[str, str]]:
    """Return a warning when A's speaker looks different from the requested NPC.

    Beginner guide:
    Developer C does not rewrite Developer A's dialogue here.  It only compares
    the A-facing NPC identity with the speaker name A returned.  When
    the names share no useful identity token, C adds a diagnostic so logs and
    debug payloads can reveal likely routing mistakes.
    """

    expected_npc_id = expected_npc.npc_id
    expected_tokens = _identity_tokens(expected_npc_id)
    actual_tokens = _identity_tokens(actual_speaker)
    if expected_tokens and expected_tokens.intersection(actual_tokens):
        return []

    return [
        {
            "code": "npc_speaker_mismatch",
            "severity": "warning",
            "message": "Developer A returned a speaker that does not match the requested NPC context.",
            "expected_npc_id": expected_npc_id,
            "expected_npc_role": expected_npc.npc_role,
            "actual_speaker": actual_speaker,
        }
    ]


def _identity_tokens(value: str) -> set[str]:
    """Extract comparison tokens from NPC ids or speaker names.

    Beginner guide:
    Names come in different forms, such as `BAGGAGE_STAFF`, `Officer Hale`, or
    `customs-officer`.  This helper lowercases them, splits separators, removes
    generic words, and keeps the meaningful pieces for a loose mismatch check.
    """

    generic_tokens = {"a", "the", "npc", "officer", "staff", "agent", "service"}
    normalized = value.lower().replace("_", " ").replace("-", " ")
    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and not token.isdigit() and token not in generic_tokens
    }


def _filter_suspicion_data(
    required_slots: list[str],
    game_state: dict[str, Any] | None,
    top_customs_item: dict[str, Any] | None,
    dialogue_seed: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """노드의 required_slots에 따라 A가 보아야 할 suspicion 데이터를 일원화하여 필터링합니다.
    
    비-세관 노드에서는 세관 데이터가 유출되지 않게 game_state, top-level, dialogue_seed 경로에서 지우며,
    비-장소 노드에서는 location suspicion 정보가 유출되지 않게 지웁니다.
    """
    is_declaration_node = "customs_item_explanation" in required_slots
    is_location_node = "stay_location" in required_slots or "visit_purpose" in required_slots

    # 1. Declaration suspicion filtering
    if not is_declaration_node:
        top_customs_item = None
        if game_state is not None:
            game_state["random_customs_item"] = None
        if dialogue_seed is not None:
            dialogue_seed["random_customs_item"] = None
            dialogue_seed["item_id"] = None
            dialogue_seed["item_name"] = None
            dialogue_seed["item_category"] = None
            dialogue_seed["item_difficulty"] = None
            dialogue_seed["item_suspicion_reason"] = None
            if dialogue_seed.get("suspicion_scope") == "declaration":
                dialogue_seed["suspicion_scope"] = "none"

    # 2. Location suspicion filtering
    if not is_location_node:
        if game_state is not None:
            game_state["assigned_visit_location"] = None
            game_state["assigned_visit_location_ko"] = None
            game_state["visit_location_difficulty"] = None
            game_state["visit_location_suspicion_reason"] = None
        if dialogue_seed is not None:
            dialogue_seed["assigned_visit_location"] = None
            dialogue_seed["assigned_visit_location_ko"] = None
            dialogue_seed["visit_location_difficulty"] = None
            dialogue_seed["visit_location_suspicion_reason"] = None
            if dialogue_seed.get("suspicion_scope") == "location":
                dialogue_seed["suspicion_scope"] = "none"

    return game_state, top_customs_item, dialogue_seed
