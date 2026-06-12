# Validator

담당자: Sean Han
상태: 대기
시작일: 06/01/2026
마감일: 06/04/2026
우선순위: 보통
작업 유형: Rule-Based
마감기한: 프로토
요약:   • AI가 만든 결과가 언리얼에서 실행 가능한지 마지막으로 검사하는 영역

## 하위 작업

- [ ]  
- [ ]  
- [ ]  

## 개발자 C가 검증해야 하는 것

| 검증 항목 | 규칙 |
| --- | --- |
| `next_node_id` | 반드시 `allowed_next_nodes` 안에 있어야 함 |
| `commands[].type` | 정의된 command type만 허용 |
| `npc_id` | 존재하는 NPC만 허용 |
| `animation` | 등록된 animation ID만 허용 |
| `ending_id` | 정의된 ending ID만 허용 |
| `risk_score_delta` | 허용 범위 내인지 확인 |
| JSON schema | 필수 필드 누락 여부 확인 |
| 텍스트 길이 | NPC 대사, 피드백이 너무 길지 않은지 확인 |

## Validator 실패 시 fallback 예시

```json
{
  "status":"error",
  "error": {
    "code":"VALIDATION_FAILED",
    "message":"Invalid next_node_id detected.",
    "fallback_node_id":"IMM_002_RETRY_PURPOSE"
  },
  "commands": [
    {
      "type":"SHOW_SUBTITLE",
      "payload": {
        "speaker":"Officer Miller",
        "text":"Could you say that again?",
        "duration":3.0
      }
    },
    {
      "type":"LOAD_NODE",
      "payload": {
        "node_id":"IMM_002_RETRY_PURPOSE"
      }
    }
  ]
}
```