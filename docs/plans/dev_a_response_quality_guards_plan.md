# Developer A — 응답 품질 가드 작업계획서 (Hale 22턴 회귀 대응)

작성일: 2026-06-21
대상 실행 에이전트: **사용자 직접** 또는 Gemini (Developer A 페르소나)
선행 문서:
- `docs/plans/dev_a_persona_5section_realignment_plan.md` (페르소나 5섹션 완료 후)
- `docs/plans/dev_a_unified_memory_plan.md` (정본 메모리/꼬리물기 작업)

본 계획서는 2026-06-21 Hale 22턴 청취 검증에서 발견한 **A 영역 응답 품질 결함
2건**만 다룬다. B/C 영역 결함(슬롯 추출 관용도, GIVE_HINT 응답 누락, 분기
정확도)은 §6 후속에 change request로 분리.

---

## 0. 작업 가드레일

### 0.1 수정 가능 파일 (Developer A 소유 한정)
- `backend/app/agents/agent_a/npc_dialogue_agent.py` (후처리 가드 추가)
- `backend/app/services/service_a/dialogue_policy_service.py` (fallback 합성 정리)
- `backend/app/services/service_a/developer_a_fallback_service.py` (필요 시)
- `backend/app/prompts/npc_dialogue_prompt.md` (가이드 한 줄)
- `backend/app/prompts/npc_dialogue_prompt.short.md` (가이드 한 줄)
- `backend/tests/test_developer_a_npc_dialogue.py` (회귀 테스트 2종)
- `backend/tests/eval_harness/scenarios/immigration_hale.yaml` 또는
  신규 `backend/tests/eval_harness/scenarios/immigration_hale_full_flow.yaml`
- 본 계획서
- `docs/handoff.md` (Developer A 섹션 한 단락 append)

### 0.2 절대 수정 금지 파일
- B/C 영역 전부 (`agent_b`, `service_b`, `agent_c`, `service_c`, `api`,
  `schemas`, `integrations`, `tool_b`, `tool_c`, `middleware_c`,
  `scenario_nodes.json`, `kb`, `openkb`)
- `npc_roster_service.py` 페르소나 (이미 완료, 추가 변경 불필요)

### 0.3 핵심 원칙 — Fail-fast 유지 + 새 가드는 의미적 결함에만
- 본 계획의 가드는 LLM 출력의 **명백한 양립 불가 패턴**만 잡는다.
- 사용자가 처음에 지적한 "가드 누적 안티패턴"을 피하기 위해, 키워드 매칭으로
  잡을 수 있는 **명확한 2가지 결함만** 다룬다. 추가 결함이 발견되면 평가
  하네스 시나리오로 등록.

---

## 1. 문제 정의 — Hale 22턴 회귀 발견

### 1.1 문제 A: "같은 의미 질문 두 번 반복" 패턴
다음 응답들이 한 응답에 paraphrase + canonical question 두 개를 출력함.

```
턴 9:  "What brings you to the United States. What is the purpose of your visit?"
턴 12: "Where are you going to stay. Where will you stay in the United States?"
턴 13: "Could you tell me the address of your stay. Where will you stay in the United States?"
턴 20: "What is your job. What is your occupation?"
```

증상:
- 두 문장이 거의 동일한 의미 → 어색하고 길어짐
- 첫 문장 끝이 `.`로 처리되어 punctuation 어색 (질문인데 마침표)
- 학습자 입장에서 두 번 들으니 어떤 게 정답 형식인지 헷갈림

추정 원인:
- `dialogue_policy_service.py`의 `get_retry_variation`이 변주를 만들 때
  paraphrase를 생성하고, fallback 경로에서 다시 canonical question을 append
- 또는 LLM 자체가 paraphrase + canonical 둘 다 출력하도록 학습됨

### 1.2 문제 B: 종결 노드 모순 메시지
턴 22:
```
플레이어: "I don't have a return ticket. It's okay?"
Hale:    "All right. Go to baggage claim. Sir, since you cannot provide the
         details, we cannot complete the report."
분기: END_SECONDARY_INSPECTION | FAIL_END
```

증상:
- "All right. Go to baggage claim." — success closing 톤
- "we cannot complete the report." — fail closing 톤
- 한 응답에 양립 불가 두 메시지가 합쳐짐

추정 원인:
- 직전 IMM_007_FINAL_DECISION의 success closing이 메모리 또는 LLM 컨텍스트에
  남아 있고, 현재 END_SECONDARY_INSPECTION의 fail message가 함께 출력됨
- 후처리에서 분기 의도와 응답 톤이 일치하는지 검증 안 함

---

## 2. 목표 (Definition of Done)

1. 같은 의미 질문이 한 응답에 두 번 나오지 않는다.
2. success closing과 fail closing이 한 응답에 동시 출현하지 않는다.
3. 평가 하네스의 immigration_hale 시나리오에 해당 회귀 케이스가 등록되어
   결정형 채점으로 자동 감지된다.
4. `dev_a_npc_dialogue_client.py`가 보는 입력/출력 키 구조 변경 없음.
5. `uv run pytest`, `ruff check`, `mypy` 통과.

---

## 3. 작업 항목

### T-1. 두 문장 반복 패턴 차단

#### T-1-1. 프롬프트 가이드 추가
**파일:** `backend/app/prompts/npc_dialogue_prompt.md`,
`backend/app/prompts/npc_dialogue_prompt.short.md`

`# HARD CONSTRAINTS` 섹션에 한 줄 추가:

```
- Never state the same question twice in different forms within one response.
  Pick one phrasing. If you have both a paraphrase and a canonical question,
  output only the one that best fits the player's level. Repeating the same
  intent twice (e.g., "What is your job. What is your occupation?") is
  forbidden.
```

short 프롬프트에도 동일 의미 한 줄 추가:
```
- One question per response. Never output the same intent twice in different
  phrasings (forbidden: "What is your job. What is your occupation?").
```

#### T-1-2. fallback 합성 로직 정리
**파일:** `backend/app/services/service_a/dialogue_policy_service.py`

`get_retry_variation` 또는 `synthesize_fallback_next_question`이 paraphrase와
canonical question을 합치는 경로가 있는지 점검:

1. **`get_retry_variation`** 검토: 반환값에 두 문장이 합쳐져 있으면 한쪽만
   반환하도록 수정.
2. **`synthesize_fallback_next_question`** 검토: fallback_text에 이미 질문이
   있고 surface_goal 기반 question을 또 append하는지 확인. 이미 같은 의미
   질문이 fallback_text에 있으면 append 스킵.

검증:
```python
# 단위 테스트 예시
def test_synthesize_fallback_does_not_duplicate_question():
    text = "What is your job."
    result = synthesize_fallback_next_question(text, "ask_occupation")
    # 결과에 "What is your occupation?"이 append되면 안 됨 (이미 같은 의미)
    assert result.count("?") + result.count(".") <= 2
```

#### T-1-3. 후처리 가드 신설 — `duplicate_intent_question`
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

`node_generate_dialogue_llm` 후처리에 추가:

```python
# [신규 가드] duplicate_intent_question
# 한 응답에 같은 의도의 질문이 두 번 나오면 차단
import re
sentences = [s.strip() for s in re.split(r'[.!?]', npc_text) if s.strip()]
# 질문 의도 키워드 그룹
INTENT_KEYWORDS_GROUPS = [
    {"purpose", "visit", "brings you"},
    {"how long", "stay", "duration", "days"},
    {"where", "stay", "staying", "address"},
    {"return ticket", "ticket"},
    {"job", "occupation", "do you do", "work"},
    {"first visit", "first time"},
]
question_sentences = [s for s in sentences if "?" in s or any(
    s.lower().startswith(w) for w in ("what", "where", "how", "do you",
                                       "could you", "may i", "is this")
)]
if len(question_sentences) >= 2:
    text_lower = npc_text.lower()
    for group in INTENT_KEYWORDS_GROUPS:
        hit_count = sum(1 for sent in question_sentences
                        if any(kw in sent.lower() for kw in group))
        if hit_count >= 2:
            logger.error(
                "Duplicate intent question detected: %r", npc_text[:120]
            )
            return {"error": "duplicate_intent_question"}
```

`apply_fallback`로 전환되어 단일 질문 fallback이 출력됨.

### T-2. 종결 노드 모순 메시지 차단

#### T-2-1. 후처리 가드 신설 — `clearance_failure_contradiction`
**파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py`

같은 위치에 추가:

```python
# [신규 가드] clearance_failure_contradiction
# success closing과 fail closing이 한 응답에 동시 출현하면 차단
SUCCESS_CLOSING_MARKERS = (
    "enjoy your stay", "enjoy your trip", "go to baggage claim",
    "you are good to go", "you're good to go", "all set", "have a nice day",
    "all cleared", "you may proceed",
)
FAILURE_CLOSING_MARKERS = (
    "cannot complete", "secondary inspection", "interview is over",
    "denied", "must wait", "cannot proceed", "this is over",
)
npc_lower = npc_text.lower()
has_success = any(m in npc_lower for m in SUCCESS_CLOSING_MARKERS)
has_failure = any(m in npc_lower for m in FAILURE_CLOSING_MARKERS)
if has_success and has_failure:
    logger.error(
        "Clearance/failure contradiction detected: %r", npc_text[:160]
    )
    return {"error": "clearance_failure_contradiction"}
```

이 가드는 분기 정확도와 무관하게 양립 불가 톤이 한 응답에 합쳐지는 것만 잡음.

### T-3. 평가 하네스 시나리오 추가
**파일 (신규 또는 추가):** `backend/tests/eval_harness/scenarios/immigration_hale_full_flow.yaml`

22턴 흐름을 골든 시나리오로 등록. 핵심 회귀 케이스 3개만:

```yaml
- id: hale_no_duplicate_intent_question
  npc_id: hale
  node_id: IMM_002_PURPOSE
  description: "occupation/job 같은 의도가 한 응답에 두 번 나오면 fail"
  payload_overrides:
    branch:
      branch_type: retry
  player_inputs:
    - "What does mean, 'our corporation'?"
  expected:
    must_not_include_pattern_count:
      - pattern: "your job"
        max: 1
      - pattern: "your occupation"
        max: 1
    rubric_for_judge: |
      "Does Hale output only one question (either 'What is your job?' OR
      'What is your occupation?'), not both in one response?"

- id: hale_no_clearance_failure_contradiction
  npc_id: hale
  node_id: IMM_007_FINAL_DECISION
  description: "success closing과 fail message가 함께 나오면 fail"
  payload_overrides:
    branch:
      branch_type: fail
      next_node_id: END_SECONDARY_INSPECTION
  player_inputs:
    - "I don't have a return ticket. It's okay?"
  expected:
    must_not_include_simultaneously:
      success_markers: ["enjoy your stay", "go to baggage claim", "all cleared"]
      failure_markers: ["cannot complete", "secondary inspection"]
    rubric_for_judge: |
      "Does Hale output a coherent failure-only message without mentioning
      'go to baggage claim' or 'enjoy your stay' alongside?"

- id: hale_stay_location_hotel_only
  npc_id: hale
  node_id: IMM_004_STAY_LOCATION
  description: "회귀 기준: stay_location 슬롯이 호텔명만으로 인식되어야 (C 영역)"
  player_inputs:
    - "Downtown Luxury Hotel."
  expected:
    branch_type_in: ["success", "advance"]
    rubric_for_judge: |
      "Does the system accept 'Downtown Luxury Hotel.' as a valid stay
      location, advancing to the next node?"
  notes: "이 시나리오는 C 영역 결함 추적용. A 작업으로는 통과시킬 수 없음."
```

**참고**: 위 시나리오 스키마(`must_not_include_pattern_count`,
`must_not_include_simultaneously`)가 현재 deterministic scorer에 없으면
`backend/tests/eval_harness/scorers/deterministic.py`에 추가 필요. 신규 scorer
함수 2개만 추가하면 됨 (각 5~10줄).

### T-4. 회귀 테스트 2종 추가
**파일:** `backend/tests/test_developer_a_npc_dialogue.py`

```python
def test_duplicate_intent_question_guard_blocks_repeated_phrasing():
    """LLM이 'What is your job. What is your occupation?' 같이 같은 의도를
    두 번 출력할 때 duplicate_intent_question 가드가 fallback으로 전환되는지 검증."""
    # mock LLM client that returns duplicate intent text
    # invoke graph
    # assert result["llm"]["reason"] == "duplicate_intent_question"
    # assert result["fallback"]["used"] is True

def test_clearance_failure_contradiction_guard_blocks_mixed_tone():
    """LLM이 success closing과 fail message를 함께 출력할 때 가드 발동."""
    # mock LLM returns "All right. Go to baggage claim. Sir, since you cannot
    # provide the details, we cannot complete the report."
    # assert result["llm"]["reason"] == "clearance_failure_contradiction"
```

### T-5. handoff.md 한 단락 기록
**파일:** `docs/handoff.md`

```
## 2026-06-21 Developer A: 응답 품질 가드 추가 (Hale 22턴 회귀)
- duplicate_intent_question 가드: 같은 의도 질문 두 번 반복 차단
  (예: "What is your job. What is your occupation?").
- clearance_failure_contradiction 가드: success closing과 fail message가
  한 응답에 동시 출현 시 차단 (예: "Go to baggage claim ... cannot complete").
- dialogue_policy_service의 fallback 합성 로직 정리 (paraphrase + canonical
  중복 차단).
- 평가 하네스에 immigration_hale_full_flow 시나리오 3건 추가.
- B/C 영역 결함은 별도 CR로 분리 (§후속 참조).
- 검증: uv run pytest / ruff / mypy 통과.
```

---

## 4. 실행 순서 권장

1. T-1-1 프롬프트 가이드 추가 (5분, 가장 가벼움. LLM이 따라줄 가능성 큼)
2. T-1-2 fallback 합성 로직 점검 (15분, 코드 1~2곳 수정)
3. T-1-3 + T-2-1 후처리 가드 신설 (30분, 두 가드 한 번에)
4. T-4 회귀 테스트 2종 (20분)
5. T-3 평가 하네스 시나리오 (20분, scorer 함수 신설 포함)
6. `uv run pytest` 회귀 그린 확인
7. 수동 청취: Hale 22턴 시나리오 재현 → 두 결함 모두 사라졌는지 확인
8. T-5 handoff 기록

총 작업 시간 추정: **1.5~2시간**.

---

## 5. 검증 체크리스트

- [ ] `uv run pytest` 그린 (회귀 테스트 2종 추가 후)
- [ ] `uv run ruff check .` 그린
- [ ] `uv run mypy .` 그린
- [ ] `git diff --name-only` 결과가 §0.1 화이트리스트 내부만
- [ ] respond-dialog에서 Hale 22턴 시나리오 재현 시:
  - [ ] "What is your job. What is your occupation?" 같은 응답 없음
  - [ ] "Go to baggage claim ... cannot complete" 같은 모순 응답 없음
- [ ] `dev_a_npc_dialogue_client.py`가 보는 입출력 키 구조 변경 없음
- [ ] 평가 하네스 결정형 채점 통과 (immigration_hale_full_flow 3건)

---

## 6. 후속 (B/C 영역, 본 계획서 범위 밖)

Hale 22턴 테스트에서 발견된 결함 중 **B/C 영역**은 별도 change request로
등록한다.

### [CR-C-IMM-SLOT-EXTRACTION-LOOSEN] — C 대상
**증상**:
- `"Hunker House."`, `"Downtown Luxury Hotel."` 같은 호텔명 단독이
  stay_location으로 인식되지 않음 (`"I'm going to ..."` 구문 필요)
- `"No, I don't have."` 같은 부정 응답이 return_ticket=no로 인식되지 않음
  (`"No."` 단독만 통과)

**요청**: `understanding_agent.py`의 `ALPHA_SLOT_VALUE_KEYWORDS` 및 LLM 모드
프롬프트에서 stay_location, return_ticket 슬롯 추출 패턴 확장. 한국 학습자
단답형 응답에 대응.

**참고**: Hale 22턴 흐름 (특히 12~17번 턴).

### [CR-AB-HINT-EMISSION-IN-GIVE-HINT] — B/A 통합
**증상**: branch_type=GIVE_HINT 분기인데 응답에 실제 학습 hint
(예: "Try saying 'I'm staying at ...'") 가 없음.

**요청**:
- B가 GIVE_HINT 분기 emit 시 dialogue_directive에 `hint_text` 필드 포함
- A가 그 hint_text를 페르소나에 맞게 자연스럽게 통합 (Hale의 stern 톤은
  유지하되 학습 hint 한 줄 포함)

**참고**: Hale 22턴 흐름 15, 17, 20번 턴 (GIVE_HINT인데 hint 부재).

---

## 7. 본 작업의 한계

- T-1, T-2 가드는 명백한 키워드 매칭 기반. 우회 케이스 발생 가능 (예: 두 질문
  사이에 다른 문장 끼우면 가드 통과). 이건 평가 하네스 통과율로 측정.
- 페르소나가 잘 작동하고 있어서(Hale 7/7) 본 가드는 **운영 빈도가 낮은 결함의
  안전망** 역할. 빈도 측정 후 가드 유지/제거 결정.
- 사용자가 처음에 지적한 "가드 누적 안티패턴"을 피하기 위해 2건만 추가.
  추가 결함은 평가 하네스 시나리오로만 등록하고 가드는 만들지 않는다.

---

## 8. 영향 분석

| 영역 | 영향 |
|---|---|
| LLM 호출 비용 | 변동 없음 |
| 응답 지연 | 가드 후처리 +1ms 미만 |
| 다른 개발자 | 영향 없음 (A 영역만) |
| 회귀 위험 | 낮음 (가드 발동 시 기존 fallback 경로로 안전 전환) |
| 페르소나 작업 | 영향 없음 (페르소나는 이미 완료, 본 작업은 후처리 가드만) |
