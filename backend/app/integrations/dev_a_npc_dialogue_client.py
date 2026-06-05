from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import DevADialogueInput, DevADialogueOutput
from backend.app.services.service_a.voice_output_service import build_voice_output_from_level_design
from backend.app.services.service_c.openkb_service import OpenKBService
from backend.app.services.service_c.settings_service import AppSettings, get_settings

VoiceOutputBuilder = Callable[..., dict[str, Any]]


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
        level_design_payload = self._build_level_design_payload(payload)
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

        return DevADialogueOutput(
            contract_version="dev_a_dialogue.v1",
            speaker=str(result.get("speaker", "Officer Miller")),
            text=str(result.get("npc_text") or result.get("text") or "Okay. Please continue."),
            tone=str(result.get("tone", "formal_neutral")),
            animation=str(result.get("animation", "officer_check_passport")),
            feedback_kr=_optional_string(result.get("feedback_kr")),
            audio_url=_extract_audio_url(result),
        )

    def _build_level_design_payload(self, payload: DevADialogueInput) -> dict[str, Any]:
        policy = payload.developer_b_policy
        evaluation = policy.evaluation
        feedback = policy.in_game_feedback.model_dump()
        level_hint = policy.level_hint.model_dump()
        node_context = payload.node_context.model_dump()
        branch = policy.branch.model_dump()
        dialogue_directive = policy.dialogue_directive.model_dump() if policy.dialogue_directive else {}

        candidate_text = "" if self.use_llm_dialogue else self._candidate_text(payload)
        if candidate_text:
            feedback["npc_recast_line_candidate"] = candidate_text
        if self.use_llm_dialogue:
            feedback["npc_recast_line_candidate"] = None
            feedback["recommended_expression"] = None
            level_hint["recommended_expression"] = None
            node_context["recommended_expression"] = None

        if policy.branch.branch_type in {"success", "final"}:
            dialogue_directive["do_not_generate_npc_text"] = False

        return {
            "node_id": payload.current_node_id,
            "player_text": payload.player_text,
            "npc": payload.npc.model_dump(),
            "node_context": node_context,
            "understanding": payload.understanding.model_dump(),
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

    def _candidate_text(self, payload: DevADialogueInput) -> str:
        policy = payload.developer_b_policy
        feedback = policy.in_game_feedback
        if policy.branch.branch_type not in {"success", "final"}:
            return feedback.npc_recast_line_candidate or ""

        next_question = self._next_node_question(payload)
        recast = _second_person_recast(
            feedback.npc_recast_line_candidate
            or feedback.recommended_expression
            or policy.level_hint.recommended_expression
        )
        if recast and next_question:
            return f"{recast} {next_question}"
        if next_question:
            return next_question
        return recast

    def _next_node_question(self, payload: DevADialogueInput) -> str:
        next_node_id = payload.developer_b_policy.branch.next_node_id
        if not next_node_id.startswith("IMM_"):
            return ""

        try:
            node_context = self.openkb_service.get_node_context(payload.node_context.chapter_id, next_node_id)
        except ValueError:
            return ""

        if node_context.node_id == payload.current_node_id:
            return ""

        return node_context.npc_question


def _second_person_recast(text: str | None) -> str:
    if not text:
        return ""

    normalized = text.strip()
    if normalized.startswith("I'm "):
        normalized = "You're " + normalized.removeprefix("I'm ")
    return normalized if normalized.endswith((".", "?", "!")) else f"{normalized}."


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
