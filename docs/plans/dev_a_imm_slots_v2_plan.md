# [DEPRECATED] Developer A — Immigration 신규 9 슬롯 / 27 노드 대응 작업계획서 (슬림판)

> ⚠️ **이 계획서는 `docs/plans/dev_a_unified_memory_plan.md`로 통합되었습니다.**
> 신규 작업은 통합본만 참조하세요. 본 파일은 기록 보존 목적으로만 유지됩니다.

---



작성일: 2026-06-19 (개정 2026-06-19)
대상 실행 에이전트: **Gemini (Developer A 페르소나)**

**개정 메모:** 초안에 있던 압박 톤(suspicion) 연출, PRESSURE 프롬프트 블록,
페르소나 미세조정, few-shot 압박 예시(A2-5~A2-9)는 본 계획서에서 **분리**한다.
이번 PR은 "신규 슬롯/노드에 대해 A가 silently fallback default로 떨어지지 않게
하는 최소 변경"만 다룬다. 게임 연출용 압박 톤은 추후 별도 계획서에서 다룬다.

연관 변경:
- Developer B: `scenario_nodes.json` 신규 27노드 + 분기 재배선. **이미 적용 완료.**
- Developer C (CR-B-IMM-SLOTS): `understanding_agent.py` 슬롯 키워드 9종 등록.
  **이미 적용 완료.**
- 본 작업: **Developer A**의 fallback / retry / 세션 메모리 슬롯 매핑만 보강.

선행 문서:
- `AGENTS.md`
- `docs/plans/dev_a_memory_followup_plan.md` (세션 컨텍스트 카드 신설)
- `docs/plans/dev_a_npc_memory_langgraph_plan.md` (NPC별 단기 메모리)

---

## 0. 작업 가드레일 (필독)

### 0.1 수정 가능 파일 (Developer A 소유 한정)
- `backend/app/services/service_a/dialogue_policy_service.py`
- `backend/app/services/service_a/developer_a_fallback_service.py`
- `backend/app/services/service_a/session_context_card_service.py`
- 본 계획서 (`docs/plans/dev_a_imm_slots_v2_plan.md`)
- Developer A 테스트 (`backend/tests/test_developer_a_npc_dialogue.py`)

### 0.2 절대 수정 금지 파일 (Developer B/C 소유)
이번 PR은 변경 범위가 좁아 §0.1 외 파일은 모두 건드릴 일이 없다.
필요해진다고 판단되면 작업을 중단하고 사용자에게 보고한다.

### 0.3 의존성 / 검증 규약
- `langchain==1.3.2`, `langgraph==1.2.2` 고정.
- 테스트는 실제 OpenAI 키 없이 통과해야 한다.

---

## 1. 핵심 원칙 — Fail-fast

본 계획서의 작업은 **silently fallback 동작을 금지하고 명시적 오류를 우선**
한다. 등록되지 않은 키가 들어왔을 때 "어떻게든 돌아가게" 두지 않는다.

- 등록되지 않은 `surface_goal` → `fallback` 합성에서 `KeyError`를 발생시켜
  fallback 경로 자체가 명시적으로 실패. 그래프는 `apply_fallback` 노드가
  이를 잡아 `error` 키를 세팅하고 호출자(C)가 명시적으로 보게 한다.
- 등록되지 않은 슬롯 → `session_context_card_service`에서 로그 warning을
  남기고 strict 모드에서는 `ValueError` 발생. 기본은 warning + skip.
- 신규 키가 추가될 때마다 본 계획서 §3 표를 갱신하고, 누락된 키는 단위
  테스트가 잡아낸다.

---

## 2. 신규 슬롯·노드 사양 (실페이로드 기준)

Developer B가 추가한 9개 1차 질문 노드와 슬롯. **§4의 키 동기화 단계에서
`scenario_nodes.json`을 1회 grep으로 확인 후 본 표를 확정한다.**

| 노드(예) | 슬롯 | 추정 surface_goal |
| --- | --- | --- |
| IMM_002L | `long_stay_reason` | `ask_long_stay_reason` |
| IMM_004 | `hotel_reservation_status` | `ask_hotel_reservation_status` |
| IMM_004C | `hotel_choice_reason` | `ask_hotel_choice_reason` |
| IMM_005I | `itinerary_status` | `ask_itinerary_status` |
| IMM_007F | `first_visit_status` | `ask_first_visit_status` |
| IMM_008 | `occupation` | `ask_occupation` |
| IMM_010 | `cash_amount` | `ask_cash_amount` |
| IMM_010B | `payment_source` | `ask_payment_source` |
| IMM_011 | `denied_entry_status` | `ask_denied_entry_status` |

---

## 3. 작업 항목

### 작업 S-1. surface_goal → 룰베이스 질문 매핑 확장
**파일:** `backend/app/services/service_a/dialogue_policy_service.py`

- `SURFACE_GOAL_QUESTIONS`에 9개 키 추가. 라인은 짧고 직설적 immigration 톤:
  - `ask_long_stay_reason`: `"What is the reason for the long stay?"`
  - `ask_hotel_reservation_status`: `"Do you have a hotel reservation?"`
  - `ask_hotel_choice_reason`: `"Why did you choose that hotel?"`
  - `ask_itinerary_status`: `"Do you have a detailed itinerary?"`
  - `ask_first_visit_status`: `"Is this your first visit to the United States?"`
  - `ask_occupation`: `"What do you do for a living?"`
  - `ask_cash_amount`: `"How much cash are you carrying?"`
  - `ask_payment_source`: `"Who is paying for this trip?"`
  - `ask_denied_entry_status`: `"Have you ever been denied entry to any country?"`

### 작업 S-2. retry 변주 풀 확장
**파일:** `backend/app/services/service_a/dialogue_policy_service.py`

- `RETRY_PARAPHRASES`에 위 9개 키마다 3개 변주 등록.
- 각 변주는 ASCII-only, 영문 단문 또는 짧은 두 문장.

### 작업 S-3. fallback 라인 + 분기 우선순위 정리
**파일:** `backend/app/services/service_a/developer_a_fallback_service.py`

- `SURFACE_GOAL_FALLBACK_TEXTS`에 9개 키 추가 (S-1과 동일 라인 재사용 가능).
- `build_text_fallback` 분기 우선순위 변경:
  1. `transition_status == complete_chapter` 또는 `next_action == COMPLETE_CHAPTER`
  2. `surface_goal in SURFACE_GOAL_FALLBACK_TEXTS`
  3. `surface_goal == "explain_random_customs_item"` 특수 처리
  4. `purpose == "smalltalk_diagnostic"` (surface_goal이 위 매핑에 없을 때만)
  5. assigned_visit_location / random_customs_item seeded
  6. target_slot 기반
  7. **마지막 default fallback도 silently 동작 금지**: `surface_goal`이
     비어 있지 않은데도 위 단계에서 매핑이 없으면 `KeyError(f"unknown surface_goal: {surface_goal}")` 발생.

이 변경의 결과: "펜 빌려달라"에 "I hear you. Let's move forward."가 나가는
사고가 원천 차단되고, 신규 surface_goal 누락은 곧바로 테스트/로그로 드러난다.

### 작업 S-4. 세션 메모리에 신규 슬롯 등록
**파일:** `backend/app/services/service_a/session_context_card_service.py`

- `SLOT_TO_PHRASE`에 9개 슬롯 자연어 변환 추가.
- `SLOT_TO_FORBIDDEN_QUESTIONS`에 각 슬롯마다 3개 이상 forbidden 패턴 추가.
- 카드 빌드 함수에 strict 모드 옵션 추가:
  ```python
  def build_session_context_card(..., strict_unknown_slot: bool = False) -> dict:
      ...
      for slot, value in accumulated_slots.items():
          if slot not in SLOT_TO_PHRASE:
              if strict_unknown_slot:
                  raise ValueError(f"unknown slot in session memory: {slot}")
              logger.warning("unknown slot in session memory: %s", slot)
              continue
          ...
  ```
- 기본은 warning + skip, 테스트는 strict=True로 호출하여 누락을 잡아낸다.

### 작업 S-5. 테스트 (필수 회귀 5종)
**파일:** `backend/tests/test_developer_a_npc_dialogue.py`

- 신규 9개 surface_goal이 `SURFACE_GOAL_QUESTIONS`에 존재하는지.
- 신규 9개 surface_goal이 `RETRY_PARAPHRASES`에 3개 이상 변주를 갖는지.
- 신규 9개 surface_goal이 `SURFACE_GOAL_FALLBACK_TEXTS`에 존재하는지.
- 알 수 없는 surface_goal로 `build_text_fallback`을 호출하면 `KeyError`가
  나는지 (silently 동작하지 않는 것을 보장).
- 신규 9개 슬롯이 `SLOT_TO_PHRASE`와 `SLOT_TO_FORBIDDEN_QUESTIONS`에 있는지.

---

## 4. surface_goal 키 동기화 단계 (1회 필수)

Gemini는 작업 시작 직전에 다음을 한 번만 수행한다.

```
grep -oE '"surface_goal":\s*"[^"]+"' backend/app/data/scenario_nodes.json | sort -u
```

§2 표의 추정 키와 다르면 §3 작업의 키만 실제 값으로 치환한다. 라인 텍스트는
유지. `docs/handoff.md`에 "키 동기화: 추정 X → 실제 Y" 한 줄 기록.

---

## 5. 검증 체크리스트

- [ ] `uv sync` 성공.
- [ ] `uv run pytest` 그린.
- [ ] `uv run ruff check .` 그린.
- [ ] `uv run mypy .` 그린.
- [ ] `git diff --name-only` 결과가 §0.1 화이트리스트 내부만.
- [ ] 알 수 없는 surface_goal을 fallback에 던지면 `KeyError`가 발생한다.
- [ ] `dev_a_npc_dialogue_client.py`가 보는 입출력 키 구조 변경 없음.

---

## 6. 분리된 작업 (별도 PR 후보)

다음 항목은 본 계획서에서 제외했다. 게임 연출/체감 강화가 필요해질 때 별도
계획서로 진행한다.

- PRESSURE_SURFACE_GOALS (압박 톤 감정 분기)
- 프롬프트 PRESSURE INTERROGATION 블록
- `add_officer_ack` 정책 가드 보강
- few-shot 압박형 예시 3개
- `harris` 페르소나 한 줄 보강

이번 PR 범위가 작아질수록 회귀 위험이 줄고, 압박 톤은 한 번에 일관되게
설계할 수 있다.
