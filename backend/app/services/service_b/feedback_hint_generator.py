from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from backend.app.agents.agent_b.feedback_hint_llm_client import (
    FeedbackHintLLMClient,
    OpenAIFeedbackHintLLMClient,
)
from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    DevBPolicyOutput,
    FeedbackGenerationTrace,
    RubricScores,
)
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyResult


FeedbackMode = Literal["rule", "llm"]

FORBIDDEN_FEEDBACK_LLM_KEYS = {
    "branch",
    "next_node_id",
    "next_action",
    "state_delta",
    "verdict",
    "evaluation",
    "npc_dialogue",
    "npc_text",
    "npc_utterance",
    "final_dialogue_line",
    "tts",
    "tts_text",
    "audio_url",
    "animation",
    "unreal_command",
    "unreal_commands",
}


class _LLMRubricScores(BaseModel):
    comprehension: int = Field(ge=0, le=2)
    fluency: int = Field(ge=0, le=2)
    grammar_accuracy: int = Field(ge=0, le=2)
    vocabulary_range: int = Field(ge=0, le=2)
    clarity: int = Field(ge=0, le=2)
    interaction_problem_solving: int = Field(ge=0, le=2)


class _LLMFeedbackPayload(BaseModel):
    hint_kr: str | None = None
    feedback_note: str = Field(min_length=1)
    report_summary: str = Field(min_length=1)
    report_improvement: str = Field(min_length=1)
    example_answer: str = Field(min_length=1)
    focus_on_form_explanation_kr: str = Field(min_length=1)
    rubric_scores: _LLMRubricScores | None = None


@dataclass(frozen=True)
class FeedbackHintGeneration:
    """
    LLM 또는 규칙 기반 정책을 통해 최종 생성된 힌트와 피드백 정보를 담고 있는 데이터 클래스입니다.
    
    초보자 가이드: 이 클래스는 한글 힌트(hint_kr), 학습자용 피드백 노트(feedback_note), 
    평가 요약 및 개선 방향, 세부 루브릭 점수 등 화면에 표시되거나 리포트에 저장될 피드백 결과들을 묶어주는 바구니 역할을 합니다.
    """
    hint_kr: str | None
    feedback_note: str
    report_summary: str
    report_improvement: str
    example_answer: str
    focus_on_form_explanation_kr: str
    rubric_scores: RubricScores | None
    trace: FeedbackGenerationTrace
    llm_usage: dict[str, int] | None = None


class FeedbackHintGenerator:
    """
    학습자를 위한 영어 힌트와 피드백 문구를 생성하는 관리 클래스입니다.
    
    초보자 가이드: 설정에 따라 LLM(OpenAI)을 사용하여 유연하고 자연스러운 영어 피드백을 생성하거나, 
    인터넷 연결이 없거나 비용을 절약하기 위해 규칙 기반(Rule-based)의 템플릿 피드백으로 대체(Fallback)할 수 있습니다.
    """
    def __init__(
        self,
        *,
        mode: str | None = None,
        llm_client: FeedbackHintLLMClient | None = None,
        env_path: Path | None = None,
    ) -> None:
        """
        피드백 생성 방식을 설정하고 필요한 클라이언트를 주입받아 초기화합니다.
        
        Args:
            mode: 피드백 생성 모드 ('llm' 또는 'rule', 지정하지 않으면 .env에서 읽음)
            llm_client: 사용할 LLM 클라이언트 인스턴스 (선택 사항)
            env_path: 설정 값을 읽어올 .env 파일의 경로
        """
        self.mode = self._normalize_mode(mode or self._mode_from_environment(env_path))
        self.llm_client = llm_client
        self.env_path = env_path

    def generate(
        self,
        *,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        base_output: DevBPolicyOutput,
        tier_result: TierDifficultyResult,
        focus_on_form_explanation_kr: str,
    ) -> FeedbackHintGeneration:
        """
        설정된 모드(LLM 혹은 Rule)에 맞춰 최적의 영어 학습 피드백을 생성합니다.
        
        Args:
            payload: 학습자의 이번 턴 발화 텍스트, 이해 결과 등이 담긴 입력 데이터
            decision: 상태 머신이 판정한 시나리오 분기 결과 (합격/불합격 등)
            base_output: 1차적으로 계산된 기본 정책 출력 데이터
            tier_result: 학습자 등급 및 루브릭 결과 데이터
            focus_on_form_explanation_kr: 문법 형태 초점 한국어 해설 문구
            
        Returns:
            최종 한글 힌트, 피드백, 모범 예문 등이 구성된 FeedbackHintGeneration 인스턴스
        """
        if self.mode == "rule":
            return self._fallback_generation(
                payload=payload,
                base_output=base_output,
                tier_result=tier_result,
                focus_on_form_explanation_kr=focus_on_form_explanation_kr,
                mode="rule",
                reason=None,
            )

        try:
            client = self.llm_client or OpenAIFeedbackHintLLMClient.from_environment(self.env_path)
            raw_result = client.generate(
                self._llm_payload(
                    payload=payload,
                    decision=decision,
                    base_output=base_output,
                    tier_result=tier_result,
                    focus_on_form_explanation_kr=focus_on_form_explanation_kr,
                )
            )
            forbidden_keys = FORBIDDEN_FEEDBACK_LLM_KEYS.intersection(raw_result)
            if forbidden_keys:
                raise ValueError(f"Feedback LLM returned forbidden keys: {', '.join(sorted(forbidden_keys))}")
            llm_usage = self._llm_usage(raw_result.get("__llm_usage"))
            validation_payload = {key: value for key, value in raw_result.items() if key != "__llm_usage"}
            validated = _LLMFeedbackPayload.model_validate(validation_payload)
        except Exception as exc:
            return self._fallback_generation(
                payload=payload,
                base_output=base_output,
                tier_result=tier_result,
                focus_on_form_explanation_kr=focus_on_form_explanation_kr,
                mode="fallback",
                reason=str(exc),
            )

        rubric_scores = self._rubric_scores_from_llm(validated)
        return FeedbackHintGeneration(
            hint_kr=validated.hint_kr if base_output.level_hint.needs_hint else None,
            feedback_note=validated.feedback_note,
            report_summary=validated.report_summary,
            report_improvement=validated.report_improvement,
            example_answer=validated.example_answer,
            focus_on_form_explanation_kr=validated.focus_on_form_explanation_kr,
            rubric_scores=rubric_scores,
            trace=FeedbackGenerationTrace(
                mode="llm",
                model=getattr(client, "model", None),
                used_llm=True,
                fallback_reason=None,
            ),
            llm_usage=llm_usage,
        )

    def _fallback_generation(
        self,
        *,
        payload: DevBPolicyInput,
        base_output: DevBPolicyOutput,
        tier_result: TierDifficultyResult,
        focus_on_form_explanation_kr: str,
        mode: Literal["rule", "fallback"],
        reason: str | None,
    ) -> FeedbackHintGeneration:
        """
        LLM 호출이 실패했거나 Rule 모드일 때, 안전하게 준비된 템플릿(규칙 기반) 데이터를 활용하여 
        기본 피드백을 생성하는 대체(Fallback) 메서드입니다.
        """
        hint_kr = None
        if base_output.level_hint.needs_hint:
            hint_kr = payload.node_context.base_hint_kr or base_output.level_hint.hint_kr

        return FeedbackHintGeneration(
            hint_kr=hint_kr,
            feedback_note=base_output.evaluation.feedback_note or "규칙 기반 정책으로 평가된 답변입니다.",
            report_summary=base_output.report_item.summary,
            report_improvement=base_output.report_item.improvement,
            example_answer=base_output.report_item.example_answer,
            focus_on_form_explanation_kr=focus_on_form_explanation_kr,
            rubric_scores=tier_result.rubric_scores,
            trace=FeedbackGenerationTrace(
                mode=mode,
                model=None,
                used_llm=False,
                fallback_reason=reason,
            ),
            llm_usage=None,
        )

    def _llm_usage(self, raw_usage: object) -> dict[str, int] | None:
        """
        API 응답에서 토큰 사용량 데이터를 정형화된 사전 형식으로 추출합니다.
        """
        if not isinstance(raw_usage, dict):
            return None
        usage: dict[str, int] = {}
        for key in ["input_tokens", "output_tokens", "total_tokens"]:
            value = raw_usage.get(key)
            if isinstance(value, int):
                usage[key] = value
        return usage or None

    def _llm_payload(
        self,
        *,
        payload: DevBPolicyInput,
        decision: ScenarioDecision,
        base_output: DevBPolicyOutput,
        tier_result: TierDifficultyResult,
        focus_on_form_explanation_kr: str,
    ) -> dict[str, Any]:
        """
        OpenAI 피드백 LLM API를 호출할 때 전달할 입력 JSON 페이로드를 생성합니다.
        """
        return {
            "contract_version": payload.contract_version,
            "node_id": payload.current_node_id,
            "player_text": payload.player_text,
            "player_profile": payload.player_profile.model_dump(),
            "node_context": {
                "npc_question": payload.node_context.npc_question,
                "npc_question_goal": payload.node_context.npc_question_goal,
                "recommended_expression": payload.node_context.recommended_expression,
                "base_hint_kr": payload.node_context.base_hint_kr,
                "required_slots": payload.node_context.required_slots,
            },
            "understanding": payload.understanding.model_dump(),
            "rule_policy": {
                "verdict": decision.verdict,
                "branch_type": decision.branch_type,
                "feedback_tags": base_output.evaluation.feedback_tags,
                "needs_hint": base_output.level_hint.needs_hint,
                "hint_type": base_output.level_hint.hint_type,
            },
            "rule_feedback": {
                "hint_kr": base_output.level_hint.hint_kr,
                "feedback_note": base_output.evaluation.feedback_note,
                "report_item": base_output.report_item.model_dump(),
                "focus_on_form_explanation_kr": focus_on_form_explanation_kr,
            },
            "rule_rubric_scores": tier_result.rubric_scores.model_dump(),
            "safety": {
                "do_not_generate": [
                    "branch",
                    "next_node_id",
                    "next_action",
                    "state_delta",
                    "verdict",
                    "npc_dialogue",
                    "npc_text",
                    "npc_utterance",
                    "final_dialogue_line",
                    "tts",
                    "tts_text",
                    "unreal_command",
                ]
            },
        }

    def _rubric_scores_from_llm(self, validated: _LLMFeedbackPayload) -> RubricScores | None:
        """
        LLM이 생성한 각 루브릭 영역 점수를 취합하여 종합 합계가 검증된 RubricScores 객체로 변환합니다.
        """
        if validated.rubric_scores is None:
            return None
        values = validated.rubric_scores
        total = (
            values.comprehension
            + values.fluency
            + values.grammar_accuracy
            + values.vocabulary_range
            + values.clarity
            + values.interaction_problem_solving
        )
        try:
            return RubricScores(
                comprehension=values.comprehension,
                fluency=values.fluency,
                grammar_accuracy=values.grammar_accuracy,
                vocabulary_range=values.vocabulary_range,
                clarity=values.clarity,
                interaction_problem_solving=values.interaction_problem_solving,
                total=total,
            )
        except ValidationError:
            return None

    def _mode_from_environment(self, env_path: Path | None) -> str:
        """
        환경 변수 또는 .env 설정 파일에서 피드백 생성 모드 설정을 읽어옵니다.
        """
        values = self._read_env_file(env_path or Path(".env"))
        return os.getenv("DEV_B_FEEDBACK_LLM_MODE") or values.get("DEV_B_FEEDBACK_LLM_MODE", "rule")

    def _normalize_mode(self, mode: str) -> FeedbackMode:
        """
        모드 문자열을 'llm' 또는 'rule'의 유효한 값으로 정규화합니다.
        """
        if mode == "llm":
            return "llm"
        return "rule"

    def _read_env_file(self, path: Path) -> dict[str, str]:
        """
        .env 설정 파일을 읽어와 키-값 사전으로 변환하는 헬퍼 메서드입니다.
        """
        if not path.exists():
            return {}
        values: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values
