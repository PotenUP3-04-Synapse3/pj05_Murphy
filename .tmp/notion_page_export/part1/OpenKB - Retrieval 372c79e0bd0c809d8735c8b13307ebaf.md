# OpenKB - Retrieval

담당자: Sean Han
상태: 대기
시작일: 06/01/2026
마감일: 06/03/2026
우선순위: 보통
작업 유형: Data, OpenKB
마감기한: 프로토
요약:   • 현재 노드에 필요한 정보를 OpenKB에서 가져오는 기능

> OpenKB를 조회하고 Agent에게 필요한 컨텍스트로 변환
> 

콘텐츠 설계는 개발자 B와 같이 해야 함.

## OpenKB에서 가져와야 하는 정보

예를 들어 현재 노드가 `IMM_002_PURPOSE`라면:

```json
{
  "node_id":"IMM_002_PURPOSE",
  "npc_question":"What is the purpose of your visit?",
  "objective_kr":"방문 목적을 말하기",
  "success_intents": [
"visit_purpose_travel",
"visit_purpose_vacation",
"visit_purpose_visit_friend"
  ],
  "required_slots": [
"visit_purpose"
  ],
  "recommended_expression":"I'm here for travel.",
  "base_hint_kr":"미국에 온 목적을 말해보세요.",
  "retry_question":"Are you here for travel, business, or something else?",
  "risk_keywords": [
"illegal",
"forever",
"secret",
"disappear",
"no return ticket"
  ],
  "allowed_next_nodes": [
"IMM_003_DURATION",
"IMM_002_RETRY_PURPOSE",
"IMM_EXTRA_001_CLARIFY_PURPOSE",
"END_BAD_HANDCUFF"
  ]
}
```

## 해야 할 일

| 작업 | 설명 |
| --- | --- |
| OpenKB 조회 함수 구현 | `current_node_id`로 노드 정보 가져오기 |
| node_context 표준화 | Agent들이 같은 형태로 사용할 수 있게 정리 |
| 누락 데이터 fallback | OpenKB에 정보 없을 때 기본 노드 정보 반환 |
| 캐싱 | 프로토타입에서는 간단한 메모리 캐시도 충분 |
| 개발자 B와 스키마 합의 | 노드, 힌트, 성공 조건, 위험 키워드 구조 확정 |