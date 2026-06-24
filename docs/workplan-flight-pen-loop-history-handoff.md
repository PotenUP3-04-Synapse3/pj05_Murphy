# Flight pen-loop / dialogue_history 인계 후속 정리 작업 계획서

> 작성일: 2026-06-24
> 작성자: wd14177 (level_agent)
> 소스: 이번 세션 워킹트리 변경(`developer_c_graph_tools.py` history 비활성화 + 관련 테스트) 코드리뷰 결과
> 범위: C가 Dev A에 전달하던 레거시 `dialogue_history`를 끄면서 발생한 pen-loop 회귀 보호 공백 및 설정 컨벤션 정리. 점수/티어(B 도메인) 작업은 무관.
> 영향: `backend/app/tools/tool_c/developer_c_graph_tools.py`, `backend/app/services/service_c/settings_service.py`, `backend/tests/test_preprototype_flow.py`, (선택) `.gitignore`

---

## 0. 배경 — 왜 pen-loop이 영향을 받았나

- pen-loop 버그(커밋 "Fix flight smalltalk pen loop")의 기존 해결책 = **C가 세션 history를 읽어 `dialogue_seed.dialogue_history`로 Dev A에 전달** → Dev A가 직전 대화를 보고 같은 질문(펜) 반복을 회피.
- 이번 A→C 인계: "Dev A가 자체 NPC 단기 메모리를 보유하므로 C의 레거시 history 전달은 불필요" → [developer_c_graph_tools.py:433-445](backend/app/tools/tool_c/developer_c_graph_tools.py:433)에서 `MURPHY_C_LEGACY_HISTORY == "1"`일 때만 전달, **디폴트는 `dialogue_history = []`**.
- 부작용: 유일한 pen-loop 회귀 테스트가 디폴트에서 깨져, [test_preprototype_flow.py:1611](backend/tests/test_preprototype_flow.py:1611)에 `monkeypatch.setenv("MURPHY_C_LEGACY_HISTORY", "1")`를 붙여 **레거시 모드 전용**으로 고정됨.

결론: 인계 자체는 의도된 방향(Dev A 메모리)이나, **디폴트(프로덕션) 경로의 pen-loop 방지가 무검증 상태**가 되었고, 설정 방식이 프로젝트 컨벤션을 벗어났다.

### D2 검증 완료 (2026-06-24) — 디폴트 경로는 무방비 아님, 단 백스톱 약화

코드 추적 결과 **롤백은 불필요**하다. pen-loop 방지의 1차 방어가 실제로 Dev A 자체 메모리로 이전돼 있다:
- [session_context_card_service.py:119-127](backend/app/services/service_a/session_context_card_service.py:119): NPC `turn_buffer`가 있으면 **메모리 우선**(`use_memory=True`), C의 `dialogue_history`는 cold-start fallback.
- 2턴째부터 `node_persist_memory`의 `append_turn`([npc_dialogue_agent.py:1126](backend/app/agents/agent_a/npc_dialogue_agent.py:1126))이 turn_buffer를 채워 → 메모리에서 `forbidden_repeat_questions`/`recent_turns_compact` 생성 → 프롬프트([:671-674](backend/app/agents/agent_a/npc_dialogue_agent.py:671))로 LLM에 "반복 금지" 전달. **LLM 1차 예방은 디폴트에서도 유효.**

**그러나** `dialogue_history`를 직접 읽는 **결정론적 백스톱은 메모리로 안 옮겨져 디폴트에서 약화**됨:
- 선제적 펜-스캔 가드 [:351-358](backend/app/agents/agent_a/npc_dialogue_agent.py:351) → 빈 history로 무력화. reactive player 불평 신호([:347-349](backend/app/agents/agent_a/npc_dialogue_agent.py:347))만 잔존.
- retry/clarify 반응 [:510-514](backend/app/agents/agent_a/npc_dialogue_agent.py:510), [:772-774](backend/app/agents/agent_a/npc_dialogue_agent.py:772)도 빈 history.

→ D2 결정: **롤백(보류) 불필요. P1은 "디폴트 경로 회귀 테스트 추가"로 확정.** 추가로 백스톱 메모리 이전(신규 P1.5)이 필요.

---

## 1. 작업 항목

### P1 — 디폴트 경로 pen-loop 회귀 테스트 신설 (최우선)

**문제:** 디폴트(env 미설정 = Dev A 자체 메모리 의존) 경로에서 pen-loop이 재발하지 않음을 보증하는 테스트가 0건. 기존 테스트는 레거시(C가 history 전달) 경로만 검증.

**작업:**
1. 기존 `test_orchestrator_forwards_flight_history_and_neutral_slots_to_prevent_pen_loop`는 **레거시 경로 검증**으로 유지(이름에 `legacy` 명시 검토).
2. **신규 테스트** 추가: `MURPHY_C_LEGACY_HISTORY` 미설정(디폴트) 상태에서 2턴 pen 시나리오를 돌려 `"pen" not in second_response.npc.text.lower()` 및 `next_action == "ADVANCE"`를 단언.
   - 단, 디폴트 경로에선 `dialogue_seed.dialogue_history`가 비므로, pen-loop 회피는 **Dev A 측 메모리**에 의존 → 테스트는 Dev A NPC 단기 메모리가 활성/주입된 구성으로 구동해야 함. Dev A 메모리 주입 경로 확인 필요(§3-D1).
   - 디폴트 경로에서 `dialogue_seed["dialogue_history"]`가 `[]`임을 단언하는 보조 케이스로, 비활성화가 의도대로 동작함도 함께 고정.

**리스크:** 낮음(D2 검증으로 해소). Dev A 메모리(session_context_card)가 1차 예방을 담당함이 확인되어, 본 항목은 순수 "테스트 추가". 단 §3-D1(메모리 활성 구성)만 확정하면 됨.

### P1.5 — 결정론적 펜-loop 백스톱을 메모리 기반으로 이전

**문제:** LLM 1차 예방(session_context_card)은 메모리로 옮겨졌으나, `dialogue_history`를 **직접 읽는** 결정론적 안전망은 안 옮겨져 디폴트에서 약화됨:
- 선제적 펜-스캔 가드 [npc_dialogue_agent.py:351-358](backend/app/agents/agent_a/npc_dialogue_agent.py:351) — 빈 history로 무력화.
- retry/clarify 반응 [:510-514](backend/app/agents/agent_a/npc_dialogue_agent.py:510), [:772-774](backend/app/agents/agent_a/npc_dialogue_agent.py:772) — 빈 history로 직전 턴 참조 불가.

**작업:** 이들 가드/반응이 `normalized["dialogue_history"]` 대신 **NPC `turn_buffer`(또는 session_context_card의 `recent_turns_compact`)** 를 읽도록 일원화. 두 채널(메모리/legacy history)을 추상화한 단일 "직전 턴 조회" 헬퍼로 모으면 altitude도 개선.

**리스크:** 중간. Dev A 생성 그래프의 메모리 접근부 수정. P1 테스트가 선행 안전망 역할.

### P2 — 설정 컨벤션 정식화 (raw os.environ → AppSettings)

**문제:** [developer_c_graph_tools.py:433-434](backend/app/tools/tool_c/developer_c_graph_tools.py:433)가 매 턴 핫패스에서 `os.environ.get("MURPHY_C_LEGACY_HISTORY")`를 직접 읽고 `import os`도 함수 본문에 인라인. [settings_service.py:5](backend/app/services/service_c/settings_service.py:5)의 명시 규약("Services receive this object instead of reading environment variables directly") 위반이며, 기존 `murphy_*` 플래그는 전부 `AppSettings` 필드.

**작업:**
1. `AppSettings`에 `murphy_c_legacy_history: bool = False` 필드 추가(`pydantic-settings`가 `MURPHY_C_LEGACY_HISTORY` env를 자동 매핑).
2. `developer_c_graph_tools`가 settings 객체를 받아 `settings.murphy_c_legacy_history`로 분기(생성자 주입 경로 확인).
3. 함수 본문 인라인 `import os` 제거.
4. 테스트는 `monkeypatch.setenv` 대신 settings 주입 또는 env 그대로(자동 매핑되므로 setenv도 동작) — 일관성 결정(§3-D3).

**리스크:** 낮음. 동작 동일, 주입 경로만 정리.

### P3 — deprecated 경로 정리 / 죽은 변수 (altitude, 선택)

**문제:** `DialogueSeed.dialogue_history`는 스키마에서 이미 `[DEPRECATED]`([game_turn.py:464](backend/app/schemas/game_turn.py:464)). 현재는 그 경로를 제거하지 않고 플래그 뒤에 숨기며 "seed history 비우기"를 인라인 중복 구현. 디폴트 모드에서 `dialogue_history` 지역변수는 항상 `[]`인 로그 카운트([developer_c_graph_tools.py:465](backend/app/tools/tool_c/developer_c_graph_tools.py:465))용으로만 남는 사실상 죽은 변수.

**작업(택1 — §3-D4):**
- **옵션 A:** 레거시 경로를 명시적 한시 유지(deprecation 기한/제거 조건 문서화)하되, P2로 settings화하고 죽은 로그 카운트 정리.
- **옵션 B:** Dev A 메모리가 충분함이 P1로 입증되면 레거시 경로(`_sync_dialogue_history_to_dialogue_seed` 분기) 및 플래그 자체를 제거.

**리스크:** 낮음(정리성). 단 옵션 B는 P1 완료가 선행 조건.

### P4 — eval_harness 리포트 추적 정리 (경미)

**문제:** `backend/tests/eval_harness/reports/report_*.json` 8개가 untracked. 생성 산출물로 보임.

**작업:** 커밋 대상인지 확인 → 산출물이면 `.gitignore`에 패턴 추가, 아니면 의도적 커밋.

---

## 2. 권장 순서

1. **P1** — 디폴트 경로 회귀 테스트(D2로 롤백 우려는 해소됐으나, 메모리 기반 예방을 회귀로 고정하는 게 최우선).
2. **P1.5** — 결정론적 백스톱 메모리 이전. P1이 안전망 역할을 하므로 P1 직후.
3. **P2** — 설정 컨벤션 정식화. 독립적·저리스크, 병행 가능.
4. **P3** — deprecated 경로 정리. P1.5 완료 시 레거시 제거(옵션 B) 가능.
5. **P4** — eval_harness 리포트 정리. 독립, 아무 때나.

---

## 3. 결정 필요 (Decisions)

- **D1 — Dev A 메모리 주입 경로:** 디폴트 pen-loop 테스트에서 Dev A NPC 단기 메모리를 어떻게 활성/주입하는가(오케스트레이터 기본 구성으로 충분한가).
- **D2 — 디폴트 비활성화 유효성:** ✅ **해소(2026-06-24).** 디폴트 경로는 session_context_card(turn_buffer 기반)로 1차 예방 유효 → 롤백 불필요. §0 D2 검증 참조.
- **D3 — 플래그 검증 방식:** 테스트에서 env(`setenv`) vs settings 주입 일관화.
- **D4 — 레거시 경로 운명:** 한시 유지(A) vs 제거(B). P1.5로 결정론적 백스톱까지 메모리 이전하면 레거시 경로 제거(B)가 더 깔끔.

---

## 4. 검증 계획

- P1: 신규 디폴트-경로 테스트 + 기존 레거시 테스트 둘 다 그린. 디폴트에서 `"pen"` 미출현 + `dialogue_history == []` 단언.
- P2: `AppSettings(murphy_c_legacy_history=...)` 단위 확인 + 기존 pen-loop 레거시 테스트가 settings/env 어느 쪽으로든 통과.
- 공통: `uv run pytest` 전체 그린(현재 399) 유지 + `uv run ruff check` / `uv run mypy` clean.

---

## 5. 비고

- 본 계획은 **C 도메인 + 설정**에 한정. 이번 세션의 B 도메인 작업(`final_result.tier`, `scoring_policy` 라벨)과 bad-end `/result` 테스트 격리는 리뷰에서 정상 확인되어 본 계획 범위 밖.
- 핵심 트레이드오프: "Dev A 자체 메모리로 일원화"라는 방향은 타당하나, 그 전환의 **검증을 회귀 테스트로 옮겨오지 못한 것**이 본 계획의 본질적 부채다.
