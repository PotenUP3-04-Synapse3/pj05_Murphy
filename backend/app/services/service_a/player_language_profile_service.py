from dataclasses import dataclass
from typing import Any, Literal

LanguageComplexity = Literal["simple", "guided", "natural"]
FeedbackDepth = Literal["minimal", "brief_recast", "explicit_hint"]


@dataclass(frozen=True)
class PlayerLanguageProfile:
    english_level: str
    task_success: int
    clarity: int
    needs_hint: bool
    feedback_tag: str
    complexity: LanguageComplexity
    feedback_depth: FeedbackDepth


def build_player_language_profile(normalized: dict[str, Any]) -> PlayerLanguageProfile:
    """유저 영어 실력과 현재 응답 품질을 대사 생성용 profile로 바꾼다."""
    english_level = str(normalized.get("english_level", "beginner"))
    task_success = int(normalized.get("task_success", 0) or 0)
    clarity = int(normalized.get("clarity", 0) or 0)
    needs_hint = bool(normalized.get("needs_hint", False))
    feedback_tag = str(normalized.get("feedback_tag", ""))

    complexity = _complexity_for_level(english_level, clarity)
    feedback_depth = _feedback_depth(
        task_success=task_success,
        clarity=clarity,
        needs_hint=needs_hint,
        feedback_tag=feedback_tag,
    )
    return PlayerLanguageProfile(
        english_level=english_level,
        task_success=task_success,
        clarity=clarity,
        needs_hint=needs_hint,
        feedback_tag=feedback_tag,
        complexity=complexity,
        feedback_depth=feedback_depth,
    )


def _complexity_for_level(english_level: str, clarity: int) -> LanguageComplexity:
    if english_level == "beginner" or clarity <= 2:
        return "simple"
    if english_level == "intermediate":
        return "guided"
    return "natural"


def _feedback_depth(
    task_success: int,
    clarity: int,
    needs_hint: bool,
    feedback_tag: str,
) -> FeedbackDepth:
    if needs_hint or task_success <= 1:
        return "explicit_hint"
    if clarity <= 2 or feedback_tag:
        return "brief_recast"
    return "minimal"
