from dataclasses import dataclass
from typing import Any, Literal

# NPC가 답변 시 구사할 언어 복잡도(Language Complexity) 단계를 정의하는 리터럴(Literal) 타입입니다.
LanguageComplexity = Literal[
    "simple",  # 쉬운 단어 및 단문 중심
    "guided",  # 문법적 뼈대를 제공하는 형태
    "natural", # 원어민 수준의 자연스러운 문장
]

# 플레이어 수준에 맞춘 피드백 깊이(Feedback Depth) 단계를 정의하는 리터럴(Literal) 타입입니다.
FeedbackDepth = Literal[
    "minimal",      # 최소한의 확인 피드백
    "brief_recast", # 간결한 문장 재구성 피드백
    "explicit_hint",# 구체적 힌트가 들어간 피드백
]


# 플레이어의 현재 영어 수준, 발화 명확성 및 피드백 요건을 취합한 플레이어 언어 프로필 클래스(Class)입니다.
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
    """정규화된 플레이어 실력 분석 페이로드 데이터를 입력받아 대사 조정에 활용할 PlayerLanguageProfile 인스턴스(Instance)를 생성합니다."""
    english_level = str(normalized.get("english_level", "beginner"))
    task_success = int(normalized.get("task_success", 0) or 0)
    clarity = int(normalized.get("clarity", 0) or 0)
    needs_hint = bool(normalized.get("needs_hint", False))
    feedback_tag = str(normalized.get("feedback_tag", ""))

    # 플레이어 레벨과 발음 명확성(Clarity) 정보를 조합하여 사용할 언어의 복잡도(Complexity)를 판단합니다.
    complexity = _complexity_for_level(english_level, clarity)
    # 태스크 수행 성공 여부와 힌트 필요 유무를 토대로 피드백 깊이(Feedback Depth)를 도출합니다.
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
    """플레이어의 영어 레벨(English Level) 및 명확성(Clarity) 점수를 분석하여 적합한 답변 언어의 난이도를 연산합니다."""
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
    """플레이어의 학습 요구사항 및 과제 성공 여부(Task Success)에 따라 제공할 피드백 가이드의 상세 수준을 판단합니다."""
    if needs_hint or task_success <= 1:
        return "explicit_hint"
    if clarity <= 2 or feedback_tag:
        return "brief_recast"
    return "minimal"
