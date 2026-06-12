# Developer B JSON Final v1

> AGENTS.md 정합성 메모: 이 문서는 Developer B 관점에서 정리한 최종 JSON 데이터 구조이다. Developer B는 English Level, Hint, Evaluation, Scenario State Machine, Level Adaptation, Scenario Node Content, rule-based branch policy를 담당한다. FastAPI endpoint, STT/TTS, NPC 최종 대사 생성, Validator, Unreal response assembly, command 실행은 Developer C 또는 다른 담당 범위이다.

## 0. 최종 역할 구분

```text
Unreal
= 현재 게임 상황, 플레이어 입력, 클라이언트에서 허용한 다음 노드 후보를 보낸다.

STT Pipeline
= wav 음성을 normalized player_text로 바꾼다.

Developer C Orchestrator
= 요청을 정규화하고, OpenKB/node_context를 붙이고, Understanding Agent와 Developer B policy를 순서대로 호출한다.

Understanding Agent
= 플레이어 발화의 의미 신호를 만든다. intent, slot, relevance, ambiguity, risk, clarification 여부를 반환한다.

Developer B Evaluation / Level / Hint / Feedback / Branch Policy
= Understanding 결과와 node_context를 받아 verdict, score, in-game feedback strategy, error capture, out-game feedback seed, state_delta, branch recommendation을 반환한다.

Developer A NPC Dialogue Agent
= Developer B의 평가/힌트/분기 맥락을 참고해 NPC 대사와 피드백 문장을 만든다.

Developer C Validator / Response Builder
= Developer B가 추천한 next_node_id와 Developer A 대사를 검증하고 Unreal-safe response JSON으로 조립한다.
```

핵심 원칙은 다음과 같다.

> Understanding Agent는 "의미 해석"을 한다. Developer B는 "학습 평가, 힌트, 상태 변화 제안, 분기 추천"을 한다. Developer C는 "오케스트레이션, 검증, 최종 응답 조립"을 한다.

## 1. 최종 AI Turn 흐름

```text
Unreal request
  -> Developer C input normalization
  -> STT, when input_type is voice
  -> OpenKB node_context lookup
  -> Understanding Agent
  -> Developer B Evaluation / Level / Hint / Feedback / Branch Policy
  -> Developer A NPC Dialogue Agent
  -> Developer C Response Builder
  -> Developer C Validator
  -> Unreal response
```

Developer B가 직접 받는 것은 raw Unreal request가 아니라 Developer C가 정리한 policy input이다.

## 2. Unreal -> Backend 최종 request 예시

Unreal은 게임 상태와 플레이어 입력을 보낸다. Developer B가 직접 이 request를 처리하지는 않지만, B가 평가에 필요한 필드는 이 요청 안에서 유지되어야 한다.

```json
{
  "request_id": "req_imm_0001",
  "session": {
    "session_id": "session_001",
    "player_id": "player_001",
    "chapter_id": "CH0_IMMIGRATION",
    "scene_id": "JFK_IMMIGRATION_HALL",
    "current_node_id": "IMM_002_PURPOSE"
  },
  "npc": {
    "npc_id": "OFFICER_MILLER",
    "npc_role": "immigration_officer",
    "last_npc_message": "What is the purpose of your visit?"
  },
  "player_input": {
    "input_type": "voice",
    "text": null,
    "language_hint": "en-US"
  },
  "audio": {
    "file_field": "audio",
    "mime_type": "audio/wav",
    "sample_rate_hz": 16000,
    "channels": 1,
    "duration_ms": 2800
  },
  "player_profile": {
    "nickname": "Sean",
    "english_confidence": "beginner",
    "tier": "Bronze",
    "travel_speaking_level": "TSL_1_SURVIVAL"
  },
  "scenario_state": {
    "patience": 100,
    "suspicion": 0,
    "retry_count": 0,
    "hint_count": 0,
    "previous_fail_count": 0
  },
  "game_state": {
    "inventory": [
      "passport",
      "boarding_pass",
      "return_ticket"
    ],
    "flags": [
      "arrived_at_jfk",
      "passport_submitted"
    ],
    "completed_intents": [
      "submit_passport"
    ],
    "current_objective": "방문 목적을 말하기"
  },
  "previous_node_results": [
    {
      "node_id": "IMM_001_PASSPORT",
      "verdict": "SUCCESS",
      "next_action": "ADVANCE"
    }
  ],
  "client_allowed_next_nodes": [
    "IMM_003_DURATION",
    "IMM_002_RETRY_PURPOSE",
    "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "END_SECONDARY_INSPECTION"
  ],
  "client_context": {
    "platform": "windows",
    "input_device": "microphone",
    "locale": "ko-KR",
    "build_version": "0.1.0"
  }
}
```

Developer B 관점에서 Unreal request에 반드시 살아 있어야 하는 필드는 다음이다.

| 필드 | 이유 |
| --- | --- |
| `session.current_node_id` | 현재 노드별 평가 기준 선택 |
| `npc.last_npc_message` | 답변 relevance 판단 보조 |
| `player_profile.tier` | Bronze/Silver/Gold 평가 엄격도 조절 |
| `player_profile.travel_speaking_level` | 힌트 빈도와 추천 표현 난이도 조절 |
| `scenario_state` | retry, hint, patience, suspicion 상태 변화 계산 |
| `previous_node_results` | 최종 판정과 결과 리포트 누적 |
| `client_allowed_next_nodes` | B 추천 분기의 안전 범위 확인 |

## 3. Developer C 내부 정규화 결과

Developer C는 STT와 OpenKB 조회 후 아래 형태로 내부 데이터를 만든다.

```json
{
  "normalized_input": {
    "input_type": "voice",
    "player_text": "I'm here for tourism.",
    "stt_confidence": 0.87,
    "language_detected": "en-US",
    "needs_repeat": false
  },
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "chapter_id": "CH0_IMMIGRATION",
    "npc_question": "What is the purpose of your visit?",
    "npc_question_goal": "ask_visit_purpose",
    "required_intents": [
      "state_visit_purpose"
    ],
    "required_slots": [
      "visit_purpose"
    ],
    "optional_slots": [
      "destination",
      "activity",
      "companion",
      "duration"
    ],
    "critical_slots": [
      "illegal_work_intent",
      "unclear_purpose",
      "suspicious_purpose"
    ],
    "allowed_slot_values": {
      "visit_purpose": [
        "tourism",
        "business",
        "family_visit",
        "friend_visit",
        "study",
        "transit"
      ]
    },
    "risk_keywords": [
      "illegal",
      "forever",
      "secret",
      "disappear",
      "no return ticket"
    ],
    "recommended_expression": "I'm here for tourism.",
    "base_hint_kr": "미국에 온 목적을 말해보세요.",
    "hint_policy": {
      "keyword": [
        "tourism",
        "business",
        "vacation"
      ],
      "sentence_pattern": "I'm here for ___.",
      "situation_hint": "방문 목적을 말해야 합니다.",
      "action_hint": "목적을 한 단어로 먼저 말한 뒤 짧은 문장으로 다시 말하게 유도합니다."
    },
    "success_next_node": "IMM_003_DURATION",
    "retry_next_node": "IMM_002_RETRY_PURPOSE",
    "clarify_next_node": "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "hint_next_node": "IMM_002_RETRY_PURPOSE",
    "warning_next_node": "END_SECONDARY_INSPECTION",
    "allowed_next_nodes": [
      "IMM_003_DURATION",
      "IMM_002_RETRY_PURPOSE",
      "IMM_EXTRA_001_CLARIFY_PURPOSE",
      "END_SECONDARY_INSPECTION"
    ]
  }
}
```

`success_intents`라는 이름을 사용할 수도 있지만, Developer B 최종 문서에서는 `required_intents`를 기준 이름으로 사용한다.

## 4. Understanding Agent 최종 출력

Understanding Agent는 Developer B가 평가 근거로 사용할 의미 신호를 반환한다. 여기서 `next_node_id`, 최종 힌트 문구, 점수, branch는 만들지 않는다.

```json
{
  "intent": "state_visit_purpose",
  "intent_success": true,
  "confidence": 0.94,
  "meaning_summary_kr": "플레이어는 여행 목적으로 미국에 방문했다고 말했습니다.",
  "emotion": "nervous_humor",
  "answer_relevance": "on_topic",
  "ambiguity_type": "none",
  "risk_delta": 0,
  "risk_reason": "방문 목적이 명확하고 위험 표현이 없습니다.",
  "risk_tags": [],
  "extracted_slots": {
    "visit_purpose": "tourism"
  },
  "missing_slots": [],
  "needs_clarification": false
}
```

Developer B가 사용하는 Understanding 필드는 다음이다.

| Understanding 필드 | B 사용처 |
| --- | --- |
| `intent` | required intent 충족 확인 |
| `intent_success` | task success와 branch 기본 판단 |
| `confidence` | 낮은 신뢰도일 때 `UNCLEAR` 또는 `REASK` 보정 |
| `answer_relevance` | 질문 이해 여부 평가 |
| `ambiguity_type` | 힌트 타입 선택 |
| `risk_delta`, `risk_tags`, `risk_reason` | suspicion 변화와 warning 판단 |
| `extracted_slots`, `missing_slots` | required slot 충족 판단 |
| `needs_clarification` | clarify branch 판단 |

## 5. Developer B 최종 input

Developer C adapter는 위 데이터를 모아 Developer B policy에 아래 구조를 전달한다.

```json
{
  "contract_version": "dev_b_policy.v1",
  "request_id": "req_imm_0001",
  "session_id": "session_001",
  "player_id": "player_001",
  "chapter_id": "CH0_IMMIGRATION",
  "scene_id": "JFK_IMMIGRATION_HALL",
  "current_node_id": "IMM_002_PURPOSE",
  "turn_index": 2,
  "player_text": "I'm here for tourism.",
  "input_source": {
    "input_type": "voice",
    "stt_confidence": 0.87,
    "language_detected": "en-US",
    "needs_repeat": false
  },
  "player_profile": {
    "nickname": "Sean",
    "english_confidence": "beginner",
    "tier": "Bronze",
    "travel_speaking_level": "TSL_1_SURVIVAL"
  },
  "scenario_state": {
    "retry_count": 0,
    "hint_count": 0,
    "patience": 100,
    "suspicion": 0,
    "previous_fail_count": 0,
    "completed_intents": [
      "submit_passport"
    ]
  },
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?",
    "required_intents": [
      "state_visit_purpose"
    ],
    "required_slots": [
      "visit_purpose"
    ],
    "optional_slots": [
      "destination",
      "activity",
      "companion",
      "duration"
    ],
    "critical_slots": [
      "illegal_work_intent",
      "unclear_purpose",
      "suspicious_purpose"
    ],
    "recommended_expression": "I'm here for tourism.",
    "base_hint_kr": "미국에 온 목적을 말해보세요.",
    "hint_policy": {
      "keyword": [
        "tourism",
        "business",
        "vacation"
      ],
      "sentence_pattern": "I'm here for ___.",
      "situation_hint": "방문 목적을 말해야 합니다.",
      "action_hint": "목적을 한 단어로 먼저 말한 뒤 짧은 문장으로 다시 말하게 유도합니다."
    },
    "success_next_node": "IMM_003_DURATION",
    "retry_next_node": "IMM_002_RETRY_PURPOSE",
    "clarify_next_node": "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "hint_next_node": "IMM_002_RETRY_PURPOSE",
    "warning_next_node": "END_SECONDARY_INSPECTION",
    "allowed_next_nodes": [
      "IMM_003_DURATION",
      "IMM_002_RETRY_PURPOSE",
      "IMM_EXTRA_001_CLARIFY_PURPOSE",
      "END_SECONDARY_INSPECTION"
    ]
  },
  "understanding": {
    "intent": "state_visit_purpose",
    "intent_success": true,
    "confidence": 0.94,
    "answer_relevance": "on_topic",
    "ambiguity_type": "none",
    "risk_delta": 0,
    "risk_tags": [],
    "extracted_slots": {
      "visit_purpose": "tourism"
    },
    "missing_slots": [],
    "needs_clarification": false
  },
  "previous_node_results": [
    {
      "node_id": "IMM_001_PASSPORT",
      "verdict": "SUCCESS",
      "next_action": "ADVANCE",
      "feedback_tags": [
        "passport_submitted"
      ]
    }
  ],
  "client_allowed_next_nodes": [
    "IMM_003_DURATION",
    "IMM_002_RETRY_PURPOSE",
    "IMM_EXTRA_001_CLARIFY_PURPOSE",
    "END_SECONDARY_INSPECTION"
  ]
}
```

## 6. Developer B 최종 output

Developer B는 최종 응답 JSON을 만들지 않는다. 대신 Developer C가 검증하고 조립할 수 있는 정책 결과를 반환한다.

```json
{
  "contract_version": "dev_b_policy.v1",
  "node_id": "IMM_002_PURPOSE",
  "evaluation": {
    "verdict": "SUCCESS",
    "detected_intents": [
      "state_visit_purpose"
    ],
    "required_intents_passed": true,
    "filled_slots": {
      "visit_purpose": "tourism"
    },
    "missing_slots": [],
    "scores": {
      "task_success": 3,
      "clarity": 2,
      "grammar": 1,
      "vocabulary": 2,
      "problem_solving": 2,
      "politeness": 3
    },
    "feedback_tags": [
      "intent_matched",
      "required_slot_filled",
      "minor_grammar_issue"
    ],
    "feedback_note": "방문 목적은 전달됐지만 완전한 문장으로 말하면 더 자연스럽습니다."
  },
  "level_hint": {
    "english_level": "beginner",
    "travel_speaking_level": "TSL_1_SURVIVAL",
    "cefr_estimate": "A1-A2",
    "needs_hint": false,
    "hint_level": "none",
    "hint_type": null,
    "hint_kr": null,
    "example_en": "I'm here for tourism.",
    "avoid_expression": "I came to work illegally.",
    "recommended_expression": "I'm here for tourism."
  },
  "in_game_feedback": {
    "show": true,
    "feedback_strategy": "recast",
    "timing": "during_dialogue_turn",
    "priority": "low",
    "purpose": "maintain_communication",
    "focus": "sentence_naturalness",
    "npc_recast_line_candidate": "You're here for tourism. How long will you be staying?",
    "clarification_prompt_candidate": null,
    "elicitation_cue_candidate": null,
    "scaffolding_hint": null,
    "recommended_expression": "I'm here for tourism.",
    "display_duration_ms": null,
    "blocks_progression": false
  },
  "error_capture": {
    "should_record": true,
    "storage_format": "markdown",
    "error_items": [
      {
        "error_id": "err_imm_002_001",
        "node_id": "IMM_002_PURPOSE",
        "turn_index": 2,
        "npc_question": "What is the purpose of your visit?",
        "original_utterance": "I here tourism.",
        "intended_meaning_kr": "관광 목적으로 왔다고 말하려고 했습니다.",
        "error_type": "grammar",
        "error_scope": "local",
        "focus_on_form_target": "be_verb_in_self_introduction",
        "suggested_expression": "I'm here for tourism.",
        "severity": "minor",
        "affected_scores": [
          "grammar",
          "clarity"
        ],
        "should_surface_in_game": false,
        "should_surface_out_game": true
      }
    ],
    "markdown_entry": "### IMM_002_PURPOSE - err_imm_002_001\n- Turn: 2\n- NPC Question: What is the purpose of your visit?\n- Original: I here tourism.\n- Intended Meaning: 관광 목적으로 왔다고 말하려고 했습니다.\n- Error Type: grammar\n- Error Scope: local\n- Focus on Form: be_verb_in_self_introduction\n- Suggested: I'm here for tourism.\n- Severity: minor"
  },
  "out_game_feedback_seed": {
    "include_in_final_report": true,
    "openkb_query_tags": [
      "be_verb_in_self_introduction",
      "immigration_visit_purpose",
      "sentence_completion"
    ],
    "focus_on_form_targets": [
      "be_verb_in_self_introduction"
    ],
    "report_priority": "medium"
  },
  "branch": {
    "branch_type": "success",
    "next_action": "ADVANCE",
    "next_node_id": "IMM_003_DURATION",
    "branch_reason": "Required intent and visit_purpose slot were satisfied.",
    "allowed_next_node_checked": true
  },
  "state_delta": {
    "patience_delta": 0,
    "suspicion_delta": 0,
    "retry_count_delta": 0,
    "hint_count_delta": 0
  },
  "dialogue_directive": {
    "purpose": "continue_to_next_question",
    "tone_hint": "neutral",
    "target_slot": "stay_duration",
    "do_not_generate_npc_text": true
  },
  "report_item": {
    "summary": "방문 목적을 전달했습니다.",
    "improvement": "단어 하나보다 완전한 문장으로 말하면 더 자연스럽습니다.",
    "example_answer": "I'm here for tourism.",
    "score_tags": [
      "task_success_good",
      "grammar_minor_issue"
    ]
  }
}
```

## 7. Developer B output 필드 정의

| 필드 | 생성/소유 | 소비 | 의미 |
| --- | --- | --- | --- |
| `evaluation.verdict` | Developer B | C adapter, State Machine, Result Report | 현재 답변 판정 |
| `evaluation.detected_intents` | Developer B | Debug, Report | 감지된 의도 |
| `evaluation.filled_slots` | Developer B | State Machine, Report | 채워진 정보 |
| `evaluation.missing_slots` | Developer B | Hint, Retry | 부족한 정보 |
| `evaluation.scores` | Developer B | Level, Report | 학습 점수 |
| `level_hint` | Developer B | UI, A/C context | 레벨과 힌트 추천 |
| `in_game_feedback` | Developer B | C adapter, Developer A, Unreal UI | 플레이 중 의사소통 유지를 위한 Recast/Clarification/Elicitation/Scaffolding 전략 |
| `error_capture` | Developer B | C storage/logging, final report builder | 최종 피드백용 오류 markdown 저장 후보 |
| `out_game_feedback_seed` | Developer B | C OpenKB retrieval, final report builder | Focus on Form 최종 피드백 생성을 위한 OpenKB query seed |
| `report_seed_summary` | Developer B | C/Unreal final report assembler | 최종 UI payload가 아니라 결과 화면 조립용 후보 seed |
| `branch` | Developer B | C adapter, Validator | 다음 행동과 노드 추천 |
| `state_delta` | Developer B | C state handler | 상태 변화 제안 |
| `dialogue_seed` | Developer B | Developer A, C adapter | NPC 최종 대사가 아니라 대사 생성을 위한 목적/평가/슬롯 seed |
| `dialogue_directive` | Developer B | A/C optional | NPC 대사 생성을 위한 방향값 |
| `report_item` | Developer B | Result Screen | 최종 리포트 누적 항목 |

## 8. In-game feedback 최종 구조

In-game feedback은 결과 리포트와 다르다. `data/assets/dev-b/feedback-plan.md` 기준으로, 인게임 피드백의 목적은 정확한 교정이 아니라 **의사소통 유지와 미션 지속**이다. 따라서 플레이 중에는 오류를 길게 설명하지 않고, Recast, Clarification Request, Elicitation, Scaffolding Hint를 사용한다.

Developer B는 어떤 피드백 전략을 써야 하는지 제안한다. NPC 최종 대사 작성은 Developer A 범위이고, UI 표시와 실행은 Developer C/Unreal 범위이다.

```json
{
  "in_game_feedback": {
    "show": true,
    "feedback_strategy": "recast",
    "timing": "during_dialogue_turn",
    "priority": "medium",
    "purpose": "maintain_communication",
    "focus": "sentence_naturalness",
    "npc_recast_line_candidate": "You're here for tourism. How long will you be staying?",
    "clarification_prompt_candidate": null,
    "elicitation_cue_candidate": null,
    "scaffolding_hint": null,
    "recommended_expression": "I'm here for tourism.",
    "display_duration_ms": null,
    "blocks_progression": false
  }
}
```

In-game feedback 전략:

| feedback_strategy | 사용 조건 | 처리 방식 |
| --- | --- | --- |
| `recast` | 의미는 통하지만 형태가 어색함 | NPC 대사 안에서 자연스러운 표현으로 바꿔 받아줌 |
| `clarification_request` | 의미가 모호해 분기 판단이 어려움 | NPC가 선택지나 확인 질문으로 되묻는다 |
| `elicitation` | 사용자가 문장을 끝내지 못하거나 멈칫함 | 문장 앞부분이나 핵심 단서를 제공해 말하게 유도 |
| `scaffolding_hint` | 의사소통이 끊길 위험이 있음 | 화면 또는 짧은 프롬프트로 단어/패턴 힌트 제공 |
| `warning` | 위험 답변 또는 의심도 상승 | 학습 교정보다 상황상 주의 반응을 우선 |

In-game feedback 규칙:

```text
1. SUCCESS 또는 의미 전달 성공이면 explicit correction보다 recast를 우선한다.
2. PARTIAL이면 recast 또는 elicitation을 우선한다.
3. UNCLEAR이면 clarification_request를 우선한다.
4. FAIL이 반복되면 scaffolding_hint를 사용한다.
5. CRITICAL_FAIL이면 warning을 우선한다.
6. 인게임에서는 문법 설명을 길게 하지 않는다.
7. 명시적 오류 분석은 out-game feedback으로 넘긴다.
```

## 9. Error capture와 out-game feedback I/O

Out-game feedback은 세션 종료 후 결과창에서 제공하는 사후 분석 피드백이다. `feedback-plan.md` 기준으로, 인게임에서 흐름 유지를 위해 직접 교정하지 않았던 오류를 모아 정확성, 반복 패턴, Focus on Form 중심으로 정리한다.

전체 흐름은 다음과 같다.

```text
Developer B turn evaluation
  -> error_capture.error_items 생성
  -> Developer C가 session error log를 markdown으로 저장
  -> final decision 시 markdown error log를 Developer B final feedback input으로 전달
  -> Developer C/OpenKB가 focus_on_form_targets에 맞는 설명/예문을 검색
  -> Developer B가 out_game_feedback 최종 payload 생성
  -> Developer C/Unreal이 결과창에 표시
```

### 9.1 Per-turn error capture output

```json
{
  "error_capture": {
    "should_record": true,
    "storage_format": "markdown",
    "error_items": [
      {
        "error_id": "err_imm_002_001",
        "node_id": "IMM_002_PURPOSE",
        "turn_index": 2,
        "npc_question": "What is the purpose of your visit?",
        "original_utterance": "I here tourism.",
        "intended_meaning_kr": "관광 목적으로 왔다고 말하려고 했습니다.",
        "error_type": "grammar",
        "error_scope": "local",
        "focus_on_form_target": "be_verb_in_self_introduction",
        "suggested_expression": "I'm here for tourism.",
        "severity": "minor",
        "affected_scores": [
          "grammar",
          "clarity"
        ],
        "should_surface_in_game": false,
        "should_surface_out_game": true
      }
    ],
    "markdown_entry": "### IMM_002_PURPOSE - err_imm_002_001\n- NPC Question: What is the purpose of your visit?\n- Original: I here tourism.\n- Intended Meaning: 관광 목적으로 왔다고 말하려고 했습니다.\n- Error Type: grammar\n- Focus on Form: be_verb_in_self_introduction\n- Suggested: I'm here for tourism.\n- Severity: minor"
  }
}
```

Markdown 저장은 Developer C의 logging/storage 범위이다. Developer B는 저장될 구조와 markdown entry 후보를 반환한다.

### 9.2 Final report input

```json
{
  "contract_version": "dev_b_policy.v1",
  "out_game_feedback_input": {
    "session_id": "session_001",
    "chapter_id": "CH0_IMMIGRATION",
    "error_log_markdown_path": "logs/session_001/error_log.md",
    "error_log_markdown": "### IMM_002_PURPOSE - err_imm_002_001\n- Original: I here tourism.\n- Focus on Form: be_verb_in_self_introduction\n- Suggested: I'm here for tourism.",
    "node_results": [
      {
        "node_id": "IMM_002_PURPOSE",
        "verdict": "SUCCESS",
        "scores": {
          "task_success": 3,
          "clarity": 2,
          "grammar": 1,
          "vocabulary": 2,
          "problem_solving": 2,
          "politeness": 3
        }
      }
    ],
    "openkb_focus_on_form_context": [
      {
        "focus_on_form_target": "be_verb_in_self_introduction",
        "rule_summary_kr": "영어에서 자신의 목적이나 상태를 말할 때는 주어 뒤에 be 동사를 넣어 문장을 완성합니다.",
        "good_examples": [
          "I'm here for tourism.",
          "I'm here for a business meeting."
        ],
        "practice_prompt": "I'm here for ___."
      }
    ]
  }
}
```

### 9.3 Final report out-game feedback output

```json
{
  "contract_version": "dev_b_policy.v1",
  "out_game_feedback": {
    "report_mode": "focus_on_form",
    "overall_summary_kr": "입국심사 질문의 핵심 의미는 전달했지만, 짧은 답변에서 be 동사 누락이 반복되었습니다.",
    "quantitative_scores": {
      "task_success": 82,
      "clarity": 76,
      "grammar": 64,
      "vocabulary": 70,
      "politeness": 85,
      "problem_solving": 72
    },
    "focus_on_form_items": [
      {
        "target": "be_verb_in_self_introduction",
        "title_kr": "I'm here for ___ 패턴",
        "original_utterance": "I here tourism.",
        "corrected_expression": "I'm here for tourism.",
        "explanation_kr": "방문 목적을 말할 때는 `I'm here for + 목적` 패턴을 쓰면 자연스럽습니다.",
        "openkb_source_tags": [
          "immigration_visit_purpose",
          "be_verb",
          "travel_purpose_expression"
        ],
        "micro_practice": {
          "prompt_kr": "출장 목적으로 왔다고 말해보세요.",
          "answer_example": "I'm here for a business meeting."
        }
      }
    ],
    "personalized_next_step": {
      "focus_kr": "짧은 단어 답변을 완전한 문장으로 확장하기",
      "recommended_card_ids": [
        "FORM_BE_VERB_001",
        "IMM_PURPOSE_PATTERN_001"
      ]
    }
  }
}
```

Out-game feedback 규칙:

```text
1. 인게임에서는 흐름을 끊지 않기 위해 오류 설명을 최소화한다.
2. 모든 오류를 결과창에 노출하지 않고, 반복되거나 학습 가치가 큰 오류만 고른다.
3. Focus on Form 항목은 error_log_markdown + OpenKB context를 근거로 만든다.
4. 원래 발화, 추천 표현, 짧은 설명, 마이크로 연습을 함께 제공한다.
5. 저장과 OpenKB retrieval 실행은 Developer C 범위이고, 기준 설계와 output payload는 Developer B 범위이다.
```

## 10. Verdict와 branch 최종 매핑

| Verdict | next_action | branch_type | 기본 next node |
| --- | --- | --- | --- |
| `SUCCESS` | `ADVANCE` | `success` | `success_next_node` |
| `PARTIAL` | `REASK` | `retry` | `retry_next_node` |
| `PARTIAL` | `ADVANCE` | `success` | Bronze 또는 낮은 중요도 노드에서만 허용 |
| `UNCLEAR` | `REASK` | `clarify` | `clarify_next_node` |
| `FAIL` | `REASK` | `retry` | `retry_next_node` |
| `FAIL` | `GIVE_HINT` | `hint` | `hint_next_node` |
| `CRITICAL_FAIL` | `WARNING` | `warning` | `warning_next_node` |
| `CRITICAL_FAIL` | `FAIL_END` | `bad_end` | `END_SECONDARY_INSPECTION` 또는 실패 엔딩 |
| final node | `FINAL_DECISION` | `final` | 최종 판정 노드 |

분기 안전 규칙:

```text
1. Developer B는 branch recommendation만 반환한다.
2. branch.next_node_id는 node_context.allowed_next_nodes 안에 있어야 한다.
3. client_allowed_next_nodes가 있으면 그 안에도 있어야 한다.
4. Developer C Validator가 최종 next_node_id를 다시 검증한다.
5. Developer B는 Unreal command, animation, camera event를 만들지 않는다.
```

## 11. Hint policy 최종 규칙

힌트는 사용자의 레벨, retry_count, missing_slots, ambiguity_type에 따라 결정한다.

| 조건 | needs_hint | hint_type | 예시 |
| --- | --- | --- | --- |
| 첫 성공 | false | null | 힌트 없음 |
| Bronze 첫 실패 | true 가능 | `sentence_pattern` | `I'm here for ___.` |
| Silver 첫 실패 | false 또는 true | `keyword` | tourism, business |
| Gold 첫 실패 | false | null | 재질문 우선 |
| 같은 노드 2회 실패 | true | `sentence_pattern` | 완성 문장 패턴 제공 |
| 질문 자체 오해 | true | `situation_hint` | 무엇을 말해야 하는지 한국어 설명 |
| 행동 요령 필요 | true | `action_hint` | 먼저 목적을 말하고, 짧게 이유를 덧붙이기 |
| 위험 답변 | false | null | 힌트보다 warning 우선 |

## 12. Travel Speaking Level 최종 구조

Developer B는 CEFR를 그대로 쓰기보다 프로젝트용 Travel Speaking Level을 함께 반환한다.

```json
{
  "travel_speaking_profile": {
    "travel_speaking_level": "TSL_2_FUNCTIONAL",
    "cefr_estimate": "A2-B1",
    "scores": {
      "comprehension": 1,
      "clarity": 2,
      "grammar": 1,
      "vocabulary": 1,
      "fluency": 1,
      "problem_solving": 1
    },
    "strengths": [
      "basic intent is understandable",
      "can answer simple travel questions"
    ],
    "weaknesses": [
      "answers are short",
      "limited explanation under unexpected questions"
    ],
    "recommended_game_difficulty": {
      "npc_speech_speed": "slow",
      "question_complexity": "basic",
      "hint_frequency": "medium",
      "pressure_level": "low"
    }
  }
}
```

레벨 매핑:

| 총점 | Level | 의미 |
| --- | --- | --- |
| 0-3 | `TSL_1_SURVIVAL` | 단어와 짧은 문장으로 생존형 의사 전달 |
| 4-6 | `TSL_2_FUNCTIONAL` | 기본 문장으로 여행 목적과 상황 설명 가능 |
| 7-9 | `TSL_3_INDEPENDENT` | 돌발 질문에도 비교적 대응 가능 |
| 10-12 | `TSL_4_STRATEGIC` | 정중한 설명, 협상, 대안 제시 가능 |

## 13. 최종 판정 input

`IMM_007_FINAL_DECISION`은 단일 사용자 발화가 아니라 누적 평가 결과를 입력으로 받는다.

```json
{
  "contract_version": "dev_b_policy.v1",
  "session_id": "session_001",
  "chapter_id": "CH0_IMMIGRATION",
  "tier": "Silver",
  "travel_speaking_level": "TSL_2_FUNCTIONAL",
  "node_results": [
    {
      "node_id": "IMM_002_PURPOSE",
      "verdict": "SUCCESS",
      "scores": {
        "task_success": 3,
        "clarity": 3,
        "grammar": 2,
        "vocabulary": 2,
        "problem_solving": 2,
        "politeness": 3
      }
    },
    {
      "node_id": "IMM_003_DURATION",
      "verdict": "SUCCESS"
    },
    {
      "node_id": "IMM_004_STAY_LOCATION",
      "verdict": "PARTIAL"
    },
    {
      "node_id": "IMM_005_RETURN_TICKET",
      "verdict": "SUCCESS"
    },
    {
      "node_id": "IMM_006_DECLARATION_CHECK",
      "verdict": "PARTIAL"
    },
    {
      "node_id": "IMM_006B_PACKED_BAG_CHECK",
      "verdict": "SUCCESS"
    }
  ],
  "final_state": {
    "patience": 72,
    "suspicion": 25,
    "total_retry_count": 2,
    "critical_fail_count": 0,
    "hint_count": 1
  },
  "error_log_markdown_path": "logs/session_001/error_log.md",
  "openkb_focus_on_form_targets": [
    "be_verb_in_self_introduction",
    "sentence_completion"
  ]
}
```

## 14. 최종 판정 output

```json
{
  "contract_version": "dev_b_policy.v1",
  "node_id": "IMM_007_FINAL_DECISION",
  "final_recommendation": "CONDITIONAL_PASS",
  "next_action": "FINAL_DECISION",
  "ending_type": "PARTIAL_PASS",
  "rank": "Silver Pass",
  "reason_tags": [
    "minor_missing_stay_location",
    "partial_declaration_explanation"
  ],
  "final_scores": {
    "task_success": 82,
    "clarity": 76,
    "grammar": 70,
    "vocabulary": 68,
    "problem_solving": 72,
    "politeness": 85
  },
  "reward": [
    "Silver 입국 도장",
    "입국심사 생존 스탬프"
  ],
  "report_summary": {
    "overall": "입국심사 핵심 질문에는 대부분 답변했지만, 일부 답변에서 구체성이 부족했습니다.",
    "best_node": "IMM_003_DURATION",
    "weakest_node": "IMM_006_DECLARATION_CHECK",
    "main_improvement": "돌발 질문에서는 물품의 용도와 개인 사용 목적을 더 구체적으로 설명해야 합니다."
  },
  "out_game_feedback_ref": {
    "report_mode": "focus_on_form",
    "source_error_log_markdown_path": "logs/session_001/error_log.md",
    "focus_on_form_item_count": 2
  }
}
```

최종 판정 기준:

| 조건 | final_recommendation |
| --- | --- |
| 핵심 노드 대부분 `SUCCESS`, suspicion < 30 | `PASS` |
| `PARTIAL` 1-2개, suspicion < 50 | `CONDITIONAL_PASS` |
| 신고 물품/가방 확인 노드 실패, suspicion >= 50 | `SECONDARY_ROOM` |
| `CRITICAL_FAIL` 1개 이상, suspicion >= 70 | `COMIC_FAIL` 또는 `SECONDARY_ROOM` |
| patience <= 0 | `COMIC_FAIL` |
| 필수 노드 3개 이상 `FAIL` | `COMIC_FAIL` |
| 빈 입력, 무응답, 시스템 오류로 정상 평가 불가 | `UNRANKED` |

### 14.1 Implemented FinalResultScorePolicy v1

The implemented Chapter 0 final score policy is owned by Developer B and is
returned as optional `DevBPolicyOutput.final_result` on final-branch outputs.

V1 scoring rules:

- Convert each per-turn `rubric_scores.total` from 0-12 to 0-100.
- Average scored nodes with `simple_average`; no node weights are applied in
  v1.
- Exclude `IMM_007_FINAL_DECISION` from the average when earlier scored records
  exist, so the closing acknowledgement does not inflate the result.
- Use feedback/error/focus-on-form records for `reason_tags` and
  `report_summary`; do not apply an additional numeric penalty outside the
  rubric scores.
- Return `final_recommendation`, `rank`, `final_score_100`,
  `quantitative_scores`, and `report_summary`.

Recommendation thresholds:

| Condition | final_recommendation |
| --- | --- |
| No scored rubric records | `UNRANKED` |
| Any `CRITICAL_FAIL`, patience <= 0, suspicion >= 70, or score < 40 | `COMIC_FAIL` |
| suspicion >= 50 or score < 60 | `SECONDARY_ROOM` |
| score < 80 or any included node verdict is `FAIL`, `PARTIAL`, or `UNCLEAR` | `CONDITIONAL_PASS` |
| Otherwise | `PASS` |

## 15. Chapter 0 노드별 B 평가 기준 요약

| Node ID | Required Intent | Required Slot | 기본 Success Next | 핵심 평가 |
| --- | --- | --- | --- | --- |
| `FLIGHT_001_SEATMATE_SMALLTALK` | `respond_to_seatmate_request` | `polite_response` | `FLIGHT_002_TRAVEL_PURPOSE` | 부탁에 대한 공손한 반응 |
| `FLIGHT_002_TRAVEL_PURPOSE` | `state_travel_purpose` | `travel_purpose` | `FLIGHT_003_STAY_PLAN` | 여행 목적 설명 |
| `FLIGHT_003_STAY_PLAN` | `state_stay_plan` | `stay_plan` | `FLIGHT_004_CLARIFY_OR_ASK_BACK` | 체류 계획 설명 |
| `FLIGHT_004_CLARIFY_OR_ASK_BACK` | `handle_clarification_or_ask_back` | `interaction_repair` | `FLIGHT_005_WRAP_UP` | 되묻기/확인/상호작용 복구 |
| `FLIGHT_005_WRAP_UP` | `close_smalltalk_politely` | `smalltalk_closing` | `IMM_001_PASSPORT` | 스몰토크 마무리 |
| `IMM_001_PASSPORT` | `submit_passport` | `passport_submission_status` | `IMM_002_PURPOSE` | 여권 제출 요청 이해 |
| `IMM_002_PURPOSE` | `state_visit_purpose` | `visit_purpose` | `IMM_003_DURATION` | 방문 목적 명확성 |
| `IMM_003_DURATION` | `state_stay_duration` | `stay_duration` | `IMM_004_STAY_LOCATION` | 체류 기간 구체성 |
| `IMM_004_STAY_LOCATION` | `state_stay_location` | `stay_location` | `IMM_005_RETURN_TICKET` | 숙소 유형/위치 |
| `IMM_005_RETURN_TICKET` | `confirm_return_ticket` | `return_ticket_status` | `IMM_006_DECLARATION_CHECK` | 귀국 항공권과 귀국 의사 |
| `IMM_006_DECLARATION_CHECK` | `explain_declared_item` | `item_purpose` | `IMM_006B_PACKED_BAG_CHECK` | 신고 물품 용도와 문제 해결력 |
| `IMM_006B_PACKED_BAG_CHECK` | `confirm_packed_by_self` | `packed_by_self` | `IMM_007_FINAL_DECISION` | 직접 포장과 내용물 인지 |
| `IMM_007_FINAL_DECISION` | `acknowledge_immigration_clearance` | `immigration_transition_acknowledgement` | `BAG_001_NOTICE_BAG_MISSING` | 입국심사 통과 후 수화물 이동 |
| `BAG_001_NOTICE_BAG_MISSING` | `notice_missing_bag` | `missing_bag_observation` | `BAG_002_FIND_STAFF` | 수화물 미도착 인지 |
| `BAG_002_FIND_STAFF` | `ask_baggage_help` | `missing_bag_status` | `BAG_003_REPORT_MISSING_BAG` | 직원에게 도움 요청 |
| `BAG_003_REPORT_MISSING_BAG` | `report_missing_bag` | `missing_bag_report` | `BAG_004_DESCRIBE_BAG` | 수화물 미도착 설명 |
| `BAG_004_DESCRIBE_BAG` | `describe_missing_bag` | `bag_description` | `BAG_005_PROVIDE_FLIGHT_OR_TAG` | 가방 특징 설명 |
| `BAG_005_PROVIDE_FLIGHT_OR_TAG` | `provide_baggage_tag_or_flight_info` | `baggage_tag_or_flight_info` | `BAG_006_CONTACT_AND_DELIVERY` | 수화물 태그/항공편 정보 제공 |
| `BAG_006_CONTACT_AND_DELIVERY` | `provide_delivery_contact` | `delivery_contact` | `BAG_007_RESOLUTION` | 배송 주소/연락처 제공 |
| `BAG_007_RESOLUTION` | `acknowledge_baggage_resolution` | `resolution_acknowledgement` | `ALPHA_999_FINAL_SCOREBOARD` | 신고 접수 결과 이해 |
| `ALPHA_999_FINAL_SCOREBOARD` | `summarize_alpha_result` | `final_recommendation` | ending node | 알파 전체 누적 결과 최종 판정 |

## 16. Developer B가 만들지 않는 것

```text
- raw wav 처리
- STT confidence 산출
- NPC 최종 대사 본문
- TTS voice id
- Unreal animation command
- Unreal camera/event command
- 최종 API response envelope
- Validator 결과
- game_state 직접 변경
- FastAPI route 또는 multipart/form-data 처리
- markdown 파일 실제 저장 처리
- OpenKB retrieval 실행
```

Developer B가 만드는 것은 다음으로 제한한다.

```text
- evaluation verdict
- required intent and slot 평가
- scores and feedback tags
- level and hint recommendation
- in-game feedback recommendation
- error_capture and markdown entry proposal
- out-game Focus on Form feedback payload
- branch recommendation
- state_delta proposal
- dialogue directive metadata
- report_item
- final recommendation
```

## 17. 최종 한 줄 정의

Developer B의 최종 JSON은 플레이어 발화를 직접 응답으로 바꾸는 구조가 아니라, Developer C가 만든 normalized text와 Understanding 결과를 받아 "평가, 힌트, 인게임 상호작용 피드백 전략, 오류 기록 후보, 아웃게임 Focus on Form 피드백, 상태 변화, 분기 추천"으로 변환하는 정책 데이터 구조이다.
