# English Level & Hint Agent 변수

담당자: William Kim
상태: 진행 중
시작일: 06/02/2026
마감일: 06/04/2026
우선순위: 보통
작업 유형: Agent, Data
마감기한: 프로토
요약:   • 변수 관련 자료

| 변수 | 생성/소유 | 소비 | 왜 필요한가 |
| --- | --- | --- | --- |
| `english_level` | Level/Hint Agent | NPC Dialogue, UI, Result | 사용자 영어 수준. 예: `beginner`, `survival`, `confident` |
| `grammar_score` | Level/Hint Agent | Result Screen | 문법 평가 점수 |
| `vocabulary_score` | Level/Hint Agent | Result Screen | 어휘 수준 점수 |
| `fluency_score` | Level/Hint Agent | Result Screen | 문장 완성도/유창성 |
| `meaning_delivery_score` | Level/Hint Agent | Result Screen | 의미 전달 점수. `intent_success`보다 세밀한 학습 평가 |
| `survival_score` | Level/Hint Agent | Result Screen | 여행 상황 해결 능력 점수 |
| `mistake_type` | Level/Hint Agent | NPC Dialogue, UI | 실수 유형. 예: `question_misunderstanding`, `dangerous_expression` |
| `feedback_focus` | Level/Hint Agent | NPC Dialogue | 이번 피드백이 무엇에 집중해야 하는지 |
| `needs_hint` | Level/Hint Agent | Response Builder | 힌트를 UI에 보여줄지 판단 |
| `hint_level` | Level/Hint Agent | UI | 힌트 강도. `none`, `low`, `medium`, `high` |
| `hint_kr` | Level/Hint Agent | UI | 한국어 힌트 문구 |
| `example_en` | Level/Hint Agent | UI, Feedback | 추천 영어 예문 |
| `example_konglish` | Level/Hint Agent | UI | 초보자를 위한 허용 가능한 콩글리쉬 예시 |
| `avoid_expression` | Level/Hint Agent | UI, Feedback | 피해야 할 표현 |
| `recommended_expression` | Level/Hint Agent / OpenKB | UI, NPC Dialogue | 더 자연스러운 표현 |