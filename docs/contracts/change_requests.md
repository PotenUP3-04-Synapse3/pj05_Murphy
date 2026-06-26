# Change Requests

본 문서는 Murphy 프로젝트의 부서 간 변경 요청 / 변경 알림을 정리한다.
각 CR은 발신 / 수신 / 상태 / 사유 / 변경 범위를 명시한다.

상태 라벨: `open` / `acknowledged` / `in_progress` / `resolved` /
`deferred` / `closed`.

---

## CR-A-NPC-PERSONA-V2

- **유형**: A 자체 변경 알림 (B/C 영역 코드 변경 없음)
- **발신**: Developer A
- **수신**: Developer B, Developer C (FYI)
- **상태**: `open`
- **작성일**: 2026-06-26

### 요약

6명 NPC 페르소나를 NVIDIA `Nemotron-Personas-USA` 데이터셋 기반으로
전면 재구축. 동시에 청취 검증 결과 발견된 행동 패턴 결함을 페르소나
룰로 정리.

### 변경 범위

A 영역 한정:
- `backend/app/services/service_a/npc_roster_service.py` — NPCProfile
  6명의 `persona_instruction`, `non_verbal_palette` 전면 교체. `npc_id`,
  `display_name`, `elevenlabs_voice_id`, `role`은 그대로 유지.
- `backend/tests/test_developer_a_npc_roster.py` — 기대값 동기화 필요
  (`NPCProfile ==` 완전 일치 테스트).

### 주요 페르소나 룰 (신규)

각 NPC 페르소나는 다음 룰을 일관 적용한다.

1. **brush-off 범위 한정**: In-Character Rule의 AI/bot 회피 라인은
   AI/bot/program/chatbot 질문에만 발동. 일반 개인 질문(나이, 직업,
   이름)에는 정상 답변.
2. **Answer-first** (Seatmate, Brielle): 학습자 직접 질문에 1문장 답한
   뒤 의제 이어가기.
3. **Player-question handling** (Officer): 절차 질문 짧은 답, 일반
   질문 redirect.
4. **Standard-answer leniency**: 표준 답변(tourism / hotel / 3 days /
   clothes 등)은 grammatical 오류 있어도 즉시 ACCEPT.
5. **Quest-aware plausibility 3단계** (Officer, Brielle): 비현실적
   답변(underground bunker / refrigerator 등)에만 STRONG / MEDIUM /
   WEAK 평가. 단어 누설 금지.

### 입출력 계약 영향

없음. NPC 응답 키 구조, dialogue payload, 라우팅 결정 모두 그대로.
다른 개발자 영역에 코드 변경 요청 없음.

### 검증

- `uv run pytest backend/tests/test_developer_a_npc_roster.py` 기대값
  업데이트 후 통과 확인.
- 청취 검증: 본 handoff의 검증 시나리오 6종 통과 확인.

---

## CR-A-NPC-SINGLE-NODE-DISCIPLINE

- **유형**: A 자체 후속 작업
- **발신**: Developer A
- **수신**: Developer A (self)
- **상태**: `open`
- **작성일**: 2026-06-26
- **블로커**: CR-A-NPC-PERSONA-V2 적용 후 청취 검증

### 요약

NPC가 현재 노드의 surface_goal에 응답하면서 다음 노드의 npc_question을
미리 함께 발화해 학습자를 혼란시키고 평가-슬롯 불일치를 일으키는 패턴
발견. BAG_001 → BAG_002 전환 구간에서 무한 루프 발생.

### 발견 사례

```
노드: BAG_001_REPORT_MISSING_AT_DESK
  npc_question: "Hi. How can I help you?"
  required_slot: missing_bag_statement
  success → BAG_002_PROVIDE_CLAIM_TAG ("Do you have your claim tag?")

실제 NPC 응답: "I see. Do you have your baggage claim tag or ticket?"
→ BAG_001 acknowledgement + BAG_002 질문 동시 발화

학습자: "Yes, I have."
→ BAG_001 슬롯(missing_bag_statement) 검사 → 미충족 → REASK | UNCLEAR
→ 학습자는 BAG_002에 답했지만 BAG_001에서 평가됨
→ 무한 루프
```

### 변경 범위 후보

A 영역 한정:
- `backend/app/services/service_a/npc_dialogue_agent.py` — LLM 컨텍스트에
  success_next_node의 npc_question을 노출하는지 점검. 노출 시 차단.
- `backend/app/prompts/npc_dialogue_prompt.md` — "Single-node
  discipline" 룰 명시: "응답은 현재 노드의 surface_goal에만 한정,
  다음 노드 질문 미리 금지".
- 후처리 가드 추가 검토: `preempts_next_node_question` — 응답에 다음
  노드 npc_question 키워드 포함 시 trim 또는 재생성.
- `backend/app/services/service_a/npc_roster_service.py` — Brielle/
  Officer 페르소나에 Single-node discipline 룰 추가 (페르소나 v3).

### 입출력 계약 영향

없음. A 영역 자체 정비.

### 우선순위

높음 — BAG 챕터 진행 자체가 막히는 결함.

---

## CR-C-LENIENT-INTENT-MATCH

- **유형**: B/C 영역 변경 요청
- **발신**: Developer A
- **수신**: Developer C
- **상태**: `open`
- **작성일**: 2026-06-26

### 요약

학습자 답변에 grammatical 오류가 있어도 의도(긍정/부정/정보 제공)가
명확하면 슬롯 매칭을 허용하는 의도 평가 완화.

### 발견 사례

```
BAG_002_PROVIDE_CLAIM_TAG
  npc_question: "Do you have your baggage claim tag or ticket?"
  required_slot: claim_tag_status
  allowed_slot_values: [has_claim_tag, has_ticket, has_boarding_pass]

학습자: "Yes, I am."
→ 의미: "Yes, I do" (긍정, 클레임 태그 보유)
→ 현재 평가: UNCLEAR (의도 인식 실패)
→ 기대 평가: claim_tag_status = has_claim_tag (ACCEPT)
```

### 요청 내용

Agent C 의도 평가 로직에서 다음을 완화:
- 학습자 답변의 grammatical 오류(be 동사 vs do 동사 혼동 등)를 의도
  인식에 반영하지 않음
- 단순 긍정/부정 응답("Yes, I am", "Yes I have", "No I don't have")
  은 적절한 슬롯 값으로 매칭
- 학습자의 의도가 명확하면 정확한 표현이 아니어도 ACCEPT

### 입출력 계약 영향

`intent_satisfied` 평가 결과만 변경. 응답 페이로드 구조는 그대로.

### 우선순위

높음 — 학습자가 의도는 맞지만 grammatical 오류로 진행 못 하는 케이스
다수.

---

## CR-B-NODE-EXPECTED-CONTEXT

- **유형**: B 영역 변경 요청
- **발신**: Developer A
- **수신**: Developer B
- **상태**: `open`
- **작성일**: 2026-06-26

### 요약

시나리오 노드에 학습자의 적합 답변 예시를 메타데이터로 제공해 Agent
A/C의 plausibility 판단 정확도 향상.

### 배경

CR-A-NPC-PERSONA-V2의 Quest-aware plausibility 룰은 LLM 일반 상식에
기반해 비현실적 답변을 판단한다. 그러나 학습자에게 사전에 주어진
퀘스트(예: "산업 박물관 견학을 위해 지하 벙커 방문")가 있을 경우,
NPC는 이 퀘스트 컨텍스트를 모르므로 잘 설명된 답변도 보수적으로
거부할 위험이 있다.

### 요청 내용

각 노드의 JSON 스키마에 다음 필드 추가:

```json
{
  "expected_answer_context": {
    "common_examples": ["tourism", "business", "visiting family"],
    "unusual_but_legitimate_examples": [
      "industrial tour",
      "museum research"
    ],
    "required_explanation_depth": 2
  }
}
```

- `common_examples`: Standard-answer leniency가 즉시 ACCEPT할 표준 답변
- `unusual_but_legitimate_examples`: Quest 컨텍스트상 정당하지만 설명이
  필요한 답변
- `required_explanation_depth`: 1=word / 2=word+reason / 3=full context

### 입출력 계약 영향

`scenario_nodes.json` 스키마 확장. 기존 노드는 모두 후방 호환 가능
(필드 누락 시 기본 동작 유지).

### 우선순위

중간 — 페르소나 v2의 Quest-aware plausibility 룰만으로도 일정 효과
있으나, 본 메타데이터 추가 시 정확도 큰 폭 향상 기대.

---

## CR-C-INTENT-EXPLANATION-QUALITY

- **유형**: C 영역 변경 요청
- **발신**: Developer A
- **수신**: Developer C
- **상태**: `open`
- **작성일**: 2026-06-26

### 요약

`intent_satisfied`를 단순 boolean에서 등급제로 확장해 NPC가 답변 품질에
맞춰 정확히 응대 가능하도록.

### 요청 내용

Agent C의 의도 평가 결과에 `explanation_quality` 필드 추가:

```json
{
  "intent_satisfied": true,
  "explanation_quality": "strong" | "medium" | "weak",
  "missing_context": ["who arranged it", "duration"]
}
```

- `strong`: 답변 + 충분한 맥락 → ADVANCE
- `medium`: 답변은 있으나 맥락 부족 → 같은 노드 유지, NPC가 추가 질문
- `weak`: 답변 부적합 또는 거부 → 같은 노드 retry, NPC 강하게 push back

Agent A는 이 등급을 받아 페르소나의 Quest-aware plausibility 3단계
룰과 정확히 매칭해 응대.

### 입출력 계약 영향

`/respond` 응답에 신규 필드 추가 (선택 필드, 후방 호환).

### 우선순위

중간 — 페르소나 v2만으로도 효과 있으나, 본 등급제 도입 시 NPC 응대
정밀도 큰 폭 향상.

### 의존성

CR-B-NODE-EXPECTED-CONTEXT와 함께 적용 시 효과 극대화.

---

## 부록: TTS 볼륨 통일 (별도 메모, CR 미등록)

본 메모는 Developer C(Unreal) 측 작업 요청. 별도 CR로 등록할지 사용자
판단 후 결정.

### 증상

NPC마다 같은 시스템 볼륨에서도 발화 크기 상이.

### 원인

ElevenLabs voice별 학습 원본 라우드니스 차이. ElevenLabs API에 볼륨
제어 파라미터 없음.

### 단기 해결 (Unreal 측)

`AAgentNPCBase`의 음성 재생 직전에 NPC ID별 Volume Multiplier 적용:

```cpp
float AAgentNPCBase::GetVolumeMultiplierForNPC(const FString& NPCId) const
{
    // 청취 후 튜닝
    if (NPCId == TEXT("arabella")) return 1.0f;
    if (NPCId == TEXT("novak"))    return 1.0f;
    if (NPCId == TEXT("hale"))     return 1.0f;
    if (NPCId == TEXT("harris"))   return 1.0f;
    if (NPCId == TEXT("dan"))      return 1.0f;
    if (NPCId == TEXT("brielle"))  return 1.0f;
    return 1.0f;
}

AudioComponent->SetVolumeMultiplier(GetVolumeMultiplierForNPC(NpcId));
```

### 중기 해결 (Developer A 영역, 별도 작업계획서 후보)

`voice_output_service.py`에 라우드니스 정규화 도입 (`pyloudnorm`):
- 합성 직후 WAV를 측정해 TARGET_LUFS(-20)로 정규화
- 모든 NPC가 동일 라우드니스로 도착
