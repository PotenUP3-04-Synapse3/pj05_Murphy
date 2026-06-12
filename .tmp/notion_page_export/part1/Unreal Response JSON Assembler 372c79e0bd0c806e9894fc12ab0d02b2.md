# Unreal Response JSON Assembler

담당자: Sean Han
상태: Archive
시작일: 06/01/2026
마감일: 06/04/2026
우선순위: 높음
작업 유형: Data
마감기한: 프로토
요약:   • 각 모듈의 결과를 언리얼이 실행할 수 있는 응답으로 조립하는 영역

## 하위 작업

- [ ]  
- [ ]  
- [ ]  

## 최종 응답 예시

```json
{
  "request_id":"req_001",
  "session_id":"session_001",
  "status":"success",
  "analysis": {
    "intent":"visit_purpose_travel",
    "intent_success":true,
    "meaning_summary_kr":"플레이어는 여행 목적으로 방문했다고 말했습니다.",
    "konglish_detected":true,
    "risk_delta":0,
    "extracted_slots": {
      "visit_purpose":"travel"
    }
  },
  "level_hint": {
    "english_level":"beginner",
    "hint_level":"medium",
    "hint_kr":"좋아요. 더 자연스럽게는 'I'm here for travel.'이라고 말할 수 있어요.",
    "recommended_expression":"I'm here for travel."
  },
  "branch": {
    "branch_type":"success",
    "next_node_id":"IMM_003_DURATION",
    "reason":"방문 목적이 명확하게 확인됨"
  },
  "npc_response": {
    "speaker":"Officer Miller",
    "text":"Travel. Okay. How long will you stay?",
    "tone":"formal_neutral",
    "animation":"officer_check_passport"
  },
  "commands": [
    {
      "type":"SHOW_SUBTITLE",
      "payload": {
        "speaker":"Officer Miller",
        "text":"Travel. Okay. How long will you stay?",
        "duration":3.0
      }
    },
    {
      "type":"SHOW_FEEDBACK",
      "payload": {
        "text":"의미 전달 성공! Better: I'm here for travel.",
        "duration":4.0
      }
    },
    {
      "type":"LOAD_NODE",
      "payload": {
        "node_id":"IMM_003_DURATION"
      }
    }
  ]
}
```