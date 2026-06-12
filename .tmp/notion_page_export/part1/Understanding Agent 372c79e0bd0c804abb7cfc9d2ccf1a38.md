# Understanding Agent

담당자: Sean Han
상태: 진행 중
시작일: 06/01/2026
마감일: 06/04/2026
우선순위: 높음
작업 유형: Agent
마감기한: 프로토
요약:   • 플레이어 발화를 보고 아래를 판단
      ◦ 의도
      ◦ 슬롯
      ◦ 콩글리쉬 여부
      ◦ 감정
      ◦ 위험도
      ◦ 현재 노드 성공 여부
      ◦ 의미 요약

## Understanding Agent가 판단해야 하는 것

| 항목 | 설명 |
| --- | --- |
| `intent` | 현재 답변의 의도 |
| `intent_success` | 현재 노드 성공 여부 |
| `extracted_slots` | 체류 기간, 숙소, 귀국 항공권 등 추출 |
| `konglish_detected` | 한국어+영어 혼합 여부 |
| `emotion` | nervous, confused, humor 등 |
| `risk_delta` | 이번 발화로 증가한 위험도 |
| `risk_reason` | 왜 위험하거나 안전한지 |
| `needs_clarification` | 재질문 필요 여부 |

## 입력

```json
{
  "current_node_id":"IMM_002_PURPOSE",
  "npc_question":"What is the purpose of your visit?",
  "player_text":"Travel이요. Trouble 아니에요. 진짜 clean human입니다.",
  "success_intents": [
"visit_purpose_travel",
"visit_purpose_vacation",
"visit_purpose_visit_friend"
  ],
  "required_slots": [
"visit_purpose"
  ],
  "risk_keywords": [
"illegal",
"forever",
"secret"
  ],
  "game_state": {
    "risk_score":0,
    "retry_count":0
  }
}
```

---

## Understanding Agent 출력 변수

| 변수 | 생성/소유 | 소비 | 왜 필요한가 |
| --- | --- | --- | --- |
| `intent` | Understanding | Level/Hint, State Machine, NPC Dialogue | 플레이어 발화의 핵심 의도. 예: `visit_purpose_travel` |
| `intent_success` | Understanding | State Machine, Level/Hint | 현재 노드의 의미 조건을 만족했는지. 다음 노드 진행의 핵심 신호 |
| `confidence` | Understanding | Orchestrator, Logger | 분석 신뢰도. 너무 낮으면 clarify 또는 fallback 가능 |
| `meaning_summary_kr` | Understanding | NPC Dialogue, Debug UI, Portfolio Log | 발화 의미를 한국어로 요약. 디버깅과 피드백에 매우 유용 |
| `konglish_detected` | Understanding | Level/Hint, NPC Dialogue | 콩글리쉬 모드 반응과 피드백 스타일 조정에 필요 |
| `konglish_interpretation_kr` | Understanding | Level/Hint, UI | 콩글리쉬가 어떤 의미인지 설명 |
| `emotion` | Understanding | NPC Dialogue | NPC 말투와 표정 결정. 예: `nervous_humor`, `confused` |
| `answer_relevance` | Understanding | Level/Hint, State Machine | 질문에 맞는 답인지. 예: `on_topic`, `off_topic`, `partially_related` |
| `ambiguity_type` | Understanding | Level/Hint, State Machine | 왜 애매한지. 예: 목적 대신 장소를 답함 |
| `risk_delta` | Understanding | State Machine, Validator, Level/Hint | 이번 답변으로 증가한 위험도. 배드엔딩/추가심사 판단에 필요 |
| `risk_reason` | Understanding | Level/Hint, Debug | 위험 판단 이유. 피드백 문구 생성에 사용 |
| `risk_tags` | Understanding | State Machine, Level/Hint | 위험 유형 태그. 예: `forever_stay`, `missing_return_ticket` |
| `extracted_slots` | Understanding | State Machine, Level/Hint, Result | 추출된 핵심 정보. 예: `stay_duration: five days` |
| `missing_slots` | Understanding | Level/Hint, State Machine | 부족한 정보. 힌트와 재질문에 사용 |
| `needs_clarification` | Understanding | State Machine, NPC Dialogue | 의미가 불명확해 NPC가 다시 물어봐야 하는지 |