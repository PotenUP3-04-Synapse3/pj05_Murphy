# Developer A — SPEAKER DISCIPLINE 강화 + speaker_role_confusion 가드 작업계획서

작성일: 2026-06-19
대상 실행 에이전트: **Gemini (Developer A 페르소나)**
선행 문서: `docs/plans/dev_a_unified_memory_plan.md` (정본)

본 계획서는 통합 계획서의 patch로, 화자 혼동(speaker confusion) 버그를 잡는
최소 변경을 다룬다.

---

## 0. 작업 가드레일

### 0.1 수정 가능 파일 (Developer A 소유 한정)
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/services/service_a/developer_a_fallback_service.py`
- `backend/app/services/service_a/dialogue_policy_service.py`
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`
- `backend/app/prompts/npc_dialogue_few_shots.md`
- 본 계획서 (`docs/plans/dev_a_speaker_role_guard_plan.md`)
- 테스트: `backend/tests/test_developer_a_npc_dialogue.py`

### 0.2 절대 수정 금지 파일
- `backend/app/agents/agent_b/**`, `backend/app/services/service_b/**`
- `backend/app/agents/agent_c/**`, `backend/app/services/service_c/**`
- `backend/app/api/**`, `backend/app/schemas/**`,
  `backend/app/integrations/**`, `backend/app/data/scenario_nodes.json`
- 위 영역에 속하는 모든 테스트

### 0.3 핵심 원칙 — Fail-fast
SPEAKER DISCIPLINE 위반은 명시적 fallback으로 전환한다.
silently 통과시키지 않는다.

---

## 1. 문제 정의 (재현)

- 노드: `FLIGHT_A_001_SEATMATE_SMALLTALK`
- NPC(Emily) 부탁: `"Could I borrow your pen for this arrival form?"`
- 플레이어: `"Hello?"` (모호한 인사)
- NPC 응답: `"Hi there. Sure, here you are."` ← **버그**

`"Sure, here you are"`는 펜을 건네주는 사람(=플레이어)의 대사다. NPC가 자기
요청에 자기가 응답하는 **speaker role confusion**이 발생했다.

원인 두 층:
1. 프롬프트의 `# SPEAKER DISCIPLINE` 섹션이 "echo 금지"만 다루고, "자기 요청에
   자기가 응답 금지" 규칙이 없음.
2. 후처리 가드에 `repeats_confirmed_fact`, `weak_followup_no_hook` 등은 있지만
   speaker confusion은 잡지 못함.

(B/C 분기 정확도 문제도 있으나 본 PR 범위 밖. §6 참조.)

---

## 2. 목표 (Definition of Done)

1. NPC가 자기 직전 요청문에 응답자 표현을 쓰면 `speaker_role_confusion` 에러로
   fallback 전환된다.
2. 프롬프트 SPEAKER DISCIPLINE 섹션이 "asker → responder 역할 바뀜" 패턴을
   명시적으로 금지한다.
3. `dev_a_npc_dialogue_client.py`가 보는 입출력 키 구조 변경 없음.
4. `uv run pytest`, `ruff check`, `mypy` 통과.

---

## 3. 작업 항목

### S-1. 프롬프트 SPEAKER DISCIPLINE 섹션 강화
**파일:** `backend/app/prompts/npc_dialogue_prompt.md`,
`backend/app/prompts/npc_dialogue_prompt.short.md`

긴 프롬프트 `# SPEAKER DISCIPLINE` 섹션 아래에 추가:

```
- If the NPC's previous turn was a REQUEST/FAVOR/QUESTION directed at the player
  (e.g., "Could I borrow your pen?", "May I see your passport?",
  "Can you help me with this form?"), the NPC MUST NOT play the responder role
  in this turn.
- Specifically, NEVER output responder phrases like: "Sure, here you are",
  "Of course, here it is", "Yes, you can have it", "Here you go",
  "Take it", "No problem, take this". Those are the PLAYER's lines.
- When the NPC was the asker, the NPC's next valid turns are exactly:
  (a) thank the player and pivot to a follow-up question,
  (b) re-ask the same request if the player's answer was unclear,
  (c) acknowledge the player's response and move the conversation forward.
- Never simulate that the NPC's own request was fulfilled by the NPC itself.
```

short 프롬프트에도 같은 의미를 한 단락으로 압축:

```
SPEAKER ROLE: If the NPC's previous turn asked/requested something from the player,
do NOT respond as the giver. Never say "Sure, here you are" / "Here you go" /
"Of course, take it" — those are the player's lines. The NPC may only thank,
re-ask, or pivot.
```

### S-2. 후처리 가드 `speaker_role_confusion` 신설
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

`node_generate_dialogue_llm` 후처리에 추가 가드 (기존
`repeats_confirmed_fact` / `weak_followup_no_hook` 옆):

```python
# [신규 가드] speaker_role_confusion
# NPC가 직전 턴에 요청/부탁을 했을 때, 이번 응답이 응답자(=player) 표현을
# 포함하면 명시적으로 fallback 전환.
LAST_TURN_REQUEST_MARKERS = (
    "could i borrow", "can i borrow", "may i borrow",
    "could you help", "can you help", "would you help",
    "could i have", "may i see", "can i get",
)
RESPONDER_PHRASE_MARKERS = (
    "here you are", "here you go", "here it is",
    "of course, take", "sure, take", "you can have it",
    "take it", "no problem, take",
)

last_npc_text = (state.get("last_npc_intent") or "").lower()
# session_context_card의 recent_turns_compact 마지막 NPC 발화도 함께 확인
card = state.get("session_context_card") or {}
recent = card.get("recent_turns_compact") or []
prev_npc_line = ""
if recent:
    # 마지막 항목에서 NPC 부분만 추출 (포맷에 맞춰)
    prev_npc_line = str(recent[-1]).lower()

was_request = any(m in last_npc_text or m in prev_npc_line
                  for m in LAST_TURN_REQUEST_MARKERS)
is_responder = any(p in npc_text.lower() for p in RESPONDER_PHRASE_MARKERS)

if was_request and is_responder:
    logger.error(
        "Speaker role confusion: NPC played responder role after own request. "
        "prev=%r curr=%r", prev_npc_line[:80], npc_text[:80]
    )
    return {"error": "speaker_role_confusion"}
```

`apply_fallback` 경로로 자연 전환되므로 추가 라우팅 변경 없음.

### S-3. fallback 라인 재검토 (작은 정리)
**파일:** `backend/app/services/service_a/developer_a_fallback_service.py`

`SURFACE_GOAL_FALLBACK_TEXTS["respond_to_arrival_form_help_request"]` 의 현재
값 `"Sure, I can help you with the form. What do you need?"` 는 NPC가 펜을
받은 직후 톤으로는 어색하다 (NPC가 펜을 빌렸는데 자기가 "도와드릴까요?"라고
묻는 모양). 다음으로 교체:

```python
"respond_to_arrival_form_help_request":
    "Thanks. I'm filling out the arrival form — what brings you to New York?",
```

펜을 받은 후 자연스럽게 스몰토크로 넘어가는 톤이다.

### S-4. few-shot 예시 1개 추가
**파일:** `backend/app/prompts/npc_dialogue_few_shots.md`

Example 7로 추가 (현재 6까지 있으므로 다음 번호):

```
### Example 7: SPEAKER ROLE — NPC asked, player unclear, NPC must re-ask (not respond)
- Input payload (요점):
  npc_question: "Could I borrow your pen for this arrival form?"
  player_text: "Hello?"
  surface_goal: "estimate_user_travel_speaking_level"
  branch_type: "clarify"
- Expected NPC output:
  npc_text: "Sorry, I just need your pen for a moment. Could I borrow it?"
  tts_text: "Sorry, <break time='0.3s'/> I just need your pen for a moment. Could I borrow it?"
  feedback_kr: "Good."
  tone: "formal_supportive"
  animation: "move"
  npc_emotion: "normal"
  ...
  llm_reason: "[COHERENT] Player unclear; NPC re-asks the request instead of responding as if pen was handed over."
```

### S-5. 테스트 추가
**파일:** `backend/tests/test_developer_a_npc_dialogue.py`

신규 테스트 2종:
1. `test_speaker_role_confusion_guard_blocks_giver_phrase`:
   - 직전 NPC가 `"Could I borrow your pen?"`
   - LLM이 `"Sure, here you are."`로 응답 (mock)
   - 결과: `result["llm"]["reason"] == "speaker_role_confusion"`, fallback 사용.
2. `test_speaker_role_confusion_guard_allows_legitimate_response`:
   - 직전 NPC가 `"What is the purpose of your visit?"` (요청 아님)
   - LLM이 `"Tourism. Got it."` 응답
   - 결과: fallback 미사용, 정상 통과.

---

## 4. 실행 순서

1. S-1 (프롬프트 강화)
2. S-2 (후처리 가드)
3. S-3 (fallback 라인 교체)
4. S-4 (few-shot)
5. S-5 (테스트)
6. `uv run pytest -k developer_a` → 전체 스위트 → ruff/mypy.

---

## 5. 검증 체크리스트

- [ ] `uv sync` 성공.
- [ ] `uv run pytest` 그린 (실제 API 키 없이).
- [ ] `uv run ruff check .` 그린.
- [ ] `uv run mypy .` 그린.
- [ ] `git diff --name-only` 결과가 §0.1 화이트리스트 내부만.
- [ ] 펜 빌려달라 시나리오 + `"Hello?"` 입력 시 NPC가 `"Sure, here you are"`
      등 응답자 표현으로 떨어지지 않음 (수동 테스트 또는 통합 테스트).

---

## 6. B/C 영역 요청 (코드는 안 건드림, change_requests.md에만 기록)

`"Hello?"` 같은 모호한 인사가 `polite_response` 슬롯을 충족시켜 success로
분기된 정황이 있다. 본 PR로 A 측 화자 혼동은 잡히지만, 근본 원인 중 하나인
Understanding 슬롯 추출 관용도는 C 영역이다.

**신규 change request 등록 권장 (`[CR-A-FLIGHT-A001-SLOT-STRICTNESS]`):**

- Affected Owner: Developer C / Sean Han
- 요청: `FLIGHT_A_001_SEATMATE_SMALLTALK` 의 `polite_response` 슬롯 추출에서
  단순 인사("Hello", "Hi") 단독으로는 슬롯 충족 처리되지 않도록 키워드/
  LLM 프롬프트 보강.
- 참고: `backend/app/agents/agent_c/understanding_agent.py` 의
  `ALPHA_SLOT_VALUE_KEYWORDS` 또는 LLM 모드 슬롯 evidence 정책.
- 이유: 단순 인사로는 펜 빌려달라 요청에 응답한 것으로 볼 수 없으므로
  retry/clarify로 분기되어야 자연스럽다.

본 계획서 실행 후 위 CR을 `change_requests.md`에 추가하고 `docs/handoff.md`에
한 줄 요약.
