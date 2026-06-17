"""Developer C rule-based classifier for rude or abusive player language.

초보자용 설명:
Understanding Agent는 사용자의 답변이 현재 시나리오 질문에 맞는지 분석합니다.
그와 별개로 욕설, 모욕, 위협 같은 표현은 게임 분기와 NPC 반응에 중요한 안전
신호입니다. 이 파일은 LLM이 없어도 항상 같은 결과를 내는 규칙 기반 classifier를
제공합니다. C는 이 결과를 `UnderstandingOutput.incivility`에 붙이기만 하고,
실제 bad ending 분기 결정은 Developer B에게 맡깁니다.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from backend.app.schemas.game_turn import IncivilityClassification

IncivilityCategory = Literal["rudeness", "insult", "profanity", "slur", "threat"]


@dataclass(frozen=True)
class _IncivilityRule:
    """하나의 무례 표현 규칙을 표현합니다.

    초보자용 설명:
    `tier`는 심각도이고, `category`는 표현의 종류입니다. `patterns`는 정규식
    목록이며, 높은 tier 규칙을 먼저 검사해서 "fuck you"처럼 강한 표현이
    "you" 같은 약한 표현으로 잘못 낮아지지 않도록 합니다.
    """

    tier: int
    category: IncivilityCategory
    confidence: float
    patterns: tuple[str, ...]


_INCIVILITY_RULES: tuple[_IncivilityRule, ...] = (
    _IncivilityRule(
        tier=3,
        category="threat",
        confidence=0.96,
        patterns=(
            r"\bkill\s+yourself\b",
            r"\bgo\s+die\b",
            r"\bdie\b",
            r"죽어",
        ),
    ),
    _IncivilityRule(
        tier=3,
        category="profanity",
        confidence=0.95,
        patterns=(
            r"\bf[\W_]*(?:u[\W_]*)?(?:c[\W_]*)?k\b",
            r"\bph[\W_]*u[\W_]*c[\W_]*k\b",
            r"\bshit\b",
            r"\bbitch\b",
            r"씨발",
            r"시발",
            r"ㅅㅂ",
            r"개새끼",
            r"병신",
        ),
    ),
    _IncivilityRule(
        tier=2,
        category="insult",
        confidence=0.88,
        patterns=(
            r"\byou\s+idiot\b",
            r"\byou'?re\s+useless\b",
            r"\bmoron\b",
            r"\basshole\b",
            r"멍청이",
            r"바보",
        ),
    ),
    _IncivilityRule(
        tier=1,
        category="rudeness",
        confidence=0.72,
        patterns=(
            r"\bshut\s+up\b",
            r"\bstupid\b",
            r"\bdumb\b",
            r"\bloser\b",
            r"\bpathetic\b",
            r"꺼져",
        ),
    ),
)


def classify_incivility_rule(player_text: str) -> IncivilityClassification:
    """Return a deterministic incivility classification for one player answer.

    초보자용 설명:
    이 함수는 텍스트를 소문자화하고 공백을 정리한 뒤, 심각한 표현부터 순서대로
    검사합니다. 매칭되는 규칙이 없으면 tier 0을 반환합니다. 매칭되는 규칙이
    있으면 그 규칙의 tier/category/source를 그대로 `IncivilityClassification`
    객체로 돌려줍니다.
    """

    normalized_text = _normalize_for_rule_match(player_text)
    for rule in _INCIVILITY_RULES:
        detected_terms = _matched_terms(normalized_text, rule.patterns)
        if detected_terms:
            return IncivilityClassification(
                tier=rule.tier,
                detected_terms=detected_terms,
                confidence=rule.confidence,
                category=rule.category,
                source="rule",
            )

    return IncivilityClassification(
        tier=0,
        detected_terms=[],
        confidence=0.0,
        category="none",
        source="rule",
    )


def default_incivility_classification() -> IncivilityClassification:
    """Return the safe default used when older payloads do not include incivility.

    초보자용 설명:
    기존 테스트나 오래된 코드가 `UnderstandingOutput.incivility`를 아직 넣지
    않아도 A 어댑터는 항상 같은 모양의 payload를 넘겨야 합니다. 이 기본값은
    "감지 결과가 없다"는 뜻이라 source를 `none`으로 둡니다.
    """

    return IncivilityClassification(
        tier=0,
        detected_terms=[],
        confidence=0.0,
        category="none",
        source="none",
    )


def _normalize_for_rule_match(player_text: str) -> str:
    """Normalize only enough for stable rule matching."""

    return " ".join(player_text.lower().split())


def _matched_terms(text: str, patterns: tuple[str, ...]) -> list[str]:
    """Return unique text fragments matched by the current rule group."""

    terms: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            term = match.group(0).strip()
            if term and term not in terms:
                terms.append(term)
    return terms
