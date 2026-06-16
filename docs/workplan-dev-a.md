# Developer A 작업계획서

> 작성일: 2026-06-16
> 작성자: Developer A / kimyonghee
> 소스: `docs/handoff.md`, `docs/contracts/change_requests.md`, `AGENTS.md`
> 소유 영역: `backend/app/agents/agent_a/`, `backend/app/services/service_a/`, `backend/app/tools/tool_a/`, `backend/app/middleware/middleware_a/`, `docs/prompts/developer_a_start_prompt.md`

---

## 0. 요약

handoff와 change_requests를 검토한 결과, Developer A에 할당된 follow-up은 크게 네 갈래로 정리됩니다.
① **Dialogue Agent 품질 결함**(CR 2026-06-16): 화자 역할 혼동/환각, dialogue_seed.surface_goal을 활용한 다음 질문 작문 누락 — 게임 현장에서 직접 관찰된 품질 결함으로 최우선.
② **Alpha 시나리오 확장 미적용**(CR 2026-06-11 / -12 / Consolidated): 시트메이트 A/B/C, 수하물 서비스 직원, 세관 공무원 NPC의 로스터·보이스 프로필·대사 생성이 누락되어 비-입국심사 노드가 여전히 Hale로 폴백.
③ **Chapter 경계 처리**(CR 2026-06-12 chapter boundary, emotion enum): `next_action=COMPLETE_CHAPTER`를 종료 대사 컨텍스트로만 처리하고, `npc.emotion` enum(13종)을 TTS/애니메이션 튜닝 신호로 정식 채택.
④ **LangChain 1.0+ 리팩토링 잔여 + 코드 위생**: 미완료 Phase 5/6 항목과 `polish_tts_text` unused import 등.

본 계획서는 위 네 갈래를 P0~P3으로 분리해 머지 단위로 잘게 쪼개고, 각 PR이 끝날 때마다 `voice_output_service` 통합 테스트와 `/respond-dialog` 시나리오가 그린이도록 게이트를 두는 것을 목표로 합니다.

가드레일(`AGENTS.md`): Developer A는 NPC 대사·음성·페르소나·아티팩트만 다룬다. Developer B의 분기/검증/점수, Developer C의 오케스트레이터/스키마/검증/응답 어셈블러는 침범하지 않는다. 필요한 경우 `change_requests.md`에 신규 항목을 등록한다.

---

## 1. Open 상태 변경 요청 인벤토리 (Developer A 영역)

| # | 변경 요청 | Status | 우선순위 | 이 계획서 매핑 |
|---|---|---|---|---|
| CR1 | 2026-06-16 Dialogue Agent Speaker Role Confusion and Missing Follow-up Question | Open | **P0** | §3 P0 |
| CR2 | 2026-06-12 Consolidated Alpha Follow-up (Developer A Required Follow-up 섹션) | Open | **P1** | §3 P1 |
| CR3 | 2026-06-11 Adopt Alpha Scenario Node Expansion (Developer A follow-up) | Open | **P1** | §3 P1 |
| CR4 | 2026-06-12 Add Alpha Flight Smalltalk Route Variants (Developer A follow-up) | B/C 구현됨, A 잔여 | **P1** | §3 P1 |
| CR5 | 2026-06-12 Replace Baggage Missing-Bag Route with Customs Hold Required Flow (Developer A follow-up) | B/C 구현됨, A 잔여 | **P1** | §3 P1 |
| CR6 | 2026-06-12 Adopt Alpha Chapter Boundary Transition Nodes (Developer A follow-up) | B/C 구현됨, A 잔여 | **P2** | §3 P2 |
| CR7 | 2026-06-12 Propagate Developer B NPC Emotion Enum (Developer A follow-up) | B/C 구현됨, A 잔여 | **P2** | §3 P2 |
| CR8 | 2026-06-12 Expand NPC Dialogue Client Payload for Dynamic Emotion & Audio Parameters | Open(A 요청자) | **P2** | §3 P2 |
| 잔여 | LangChain 1.0+ 마이그레이션 Phase 5/6 잔여 (recorder/inspect.signature/configurable/stale 별칭) | 부분 진행 | **P3** | §3 P3 |
| 잔여 | `backend/app/agents/agent_a/npc_dialogue_agent.py` `polish_tts_text` unused import | Open | **P3** | §3 P3 |

참고로 **이미 해소된** 항목은 본 계획서 범위 외이지만 컨텍스트로 명시: CR 2026-06-15 Recorder 분리(Shim 잔존), CR 2026-06-13 Miller→Hale 기본값 변경, CR 2026-06-13 TTS Slimming, CR 2026-06-09 B Wording 차단(부분 해소).

---

## 2. 컴포넌트 영향도 매트릭스

| 변경 영역 | 파일 | P0 | P1 | P2 | P3 |
|---|---|:---:|:---:|:---:|:---:|
| 프롬프트(시스템) | `agents/agent_a/npc_llm_client.py` `_developer_instructions()`, `prompts/npc_dialogue_prompt.md` | ● | ● | ● | |
| 룰베이스 시드/폴백 | `agents/agent_a/npc_dialogue_agent.py` (`node_initialize_state`, helpers) | ● | ● | ● | ● |
| LLM 노드 | `agents/agent_a/npc_dialogue_agent.py` (`node_generate_dialogue_llm`) | ● | | | ● |
| LLM 응답 스키마 | `agents/agent_a/schemas.py` | | | ● | |
| 로스터 | `services/service_a/npc_roster_service.py` | | ● | | |
| 음성 프로필 | `services/service_a/voice_profile_service.py` | | ● | ● | |
| TTS 파이프라인 | `services/service_a/voice_output_service.py`, `tts_service.py`, `tts_provider_service.py` | | | ● | |
| 정책/감정/언어 프로필 | `services/service_a/dialogue_policy_service.py`, `npc_emotion_service.py`, `player_language_profile_service.py` | | ● | ● | |
| 입력 정규화 | `services/service_a/developer_a_input_service.py` | | ● | ● | |
| 폴백 텍스트/오디오 | `services/service_a/developer_a_fallback_service.py` | | ● | | |
| 기록기 | `services/service_a/agent_run_recorder.py`, `middleware/middleware_a/...` | | | | ● |
| 도구 | `tools/tool_a/*` | | | | ● |
| 테스트 | `backend/tests/test_developer_a_*` | ● | ● | ● | ● |

(Developer C 소유 `integrations/dev_a_npc_dialogue_client.py`, `schemas/game_turn.py` 는 직접 변경 금지. 계약 변경 필요 시 change request 발행.)

---

## 3. Phased Work Plan

각 Phase는 독립 머지 가능하도록 작게 쪼개고, 머지 직전 `uv run pytest`, `uv run ruff check .`, `uv run mypy .` 그리고 `/respond-dialog` 회귀 스모크를 통과해야 합니다.

### Phase P0 — Dialogue Agent 품질 결함 해소 (CR 2026-06-16) — 1.5d

**문제 (관찰된 두 증상):**
1. **화자 역할 혼동/환각**: 플레이어가 발화해야 할 추천 표현(`"Sure, here you are."`)을 NPC 본인의 대사로 흡수해 `"Sure, here you are. Thanks."` 같은 비자연적 응답을 생성.
2. **다음 질문 작문 누락**: `dialogue_seed.surface_goal=ask_travel_purpose_smalltalk` 가 주어졌는데도 첫 턴에서 짧은 리액션만 내고 다음 노드 질문(`"Are you visiting New York for a trip?"`)을 잇지 못함.

**작업:**
1. **시스템 프롬프트 강화 (`_developer_instructions`)**: 화자 역할 분리 규칙을 명시.
   - "The player utterance comes from the **PLAYER**, not the NPC. Do NOT echo the player's recommended phrasing or `npc_recast_line_candidate` as if the NPC said it."
   - "If `dialogue_seed.surface_goal` is provided, the NPC MUST (a) briefly acknowledge the prior turn AND (b) ask the next question that fulfills `surface_goal` (e.g., `ask_travel_purpose_smalltalk` → ask a travel-purpose follow-up). Do not output reaction-only lines when a `surface_goal` exists."
   - "Recommended expression (`recommended_expression`) is a model answer for the player to learn — never insert it into `npc_text`/`tts_text` unless paraphrased as the NPC's own question (e.g., 'So, where are you headed?')."
2. **payload에 `dialogue_seed.surface_goal` 강제 전달 확인**: `node_generate_dialogue_llm`에서 LLM에 넘기는 payload dict에 `dialogue_seed`가 항상 포함되도록 검증 (CR1 본문에 따르면 이미 어댑터에서 전달되고 있음 — 누락 시 진단 로깅 추가).
3. **룰베이스 시드(`node_initialize_state`)에 다음 질문 합성 헬퍼 추가**: `surface_goal` 기반 룰베이스 다음 질문 템플릿 맵을 두어, LLM 실패 시 폴백도 "리액션 + 다음 질문" 형태를 유지하도록 한다. 위치: `services/service_a/dialogue_policy_service.py` 또는 신규 `services/service_a/next_question_seeder.py`.
4. **출력 검증 강화 (`_is_safe_english_dialogue_text` 인근)**:
   - 추천 표현 문자열이 `npc_text`에 그대로 포함될 경우 `error="recommended_expression_echo"` 로 폴백 노드 라우팅.
   - `surface_goal` 이 있는데 `npc_text` 가 문장 1개 + 물음표 없음인 경우 `error="missing_followup_question"` 으로 폴백.
5. **테스트:**
   - 신규: `backend/tests/test_developer_a_npc_dialogue.py` 에 (a) 화자 흡수 케이스, (b) `surface_goal=ask_travel_purpose_smalltalk` 케이스 회귀 추가.
   - 룰베이스만 검증(LLM 모킹) 1건, LLM 경로 검증(JSON 응답 모킹) 1건.

**수용 기준:**
- `"Sure, here is my pen. So, where are you headed?"` 형태가 합리적으로 나오고, 추천 표현이 NPC 대사에 직접 포함되지 않음.
- `surface_goal` 이 있을 때 NPC 응답에 물음표가 포함되는 비율이 회귀 테스트에서 100% 보장.
- `/respond-dialog` `FLIGHT_A_001 → FLIGHT_A_002` 수동 검증으로 다음 질문이 끊김 없이 이어짐.

**가드레일 확인:**
- `npc_recast_line_candidate` 강제 None 필터링이 다음 질문 후보까지 함께 제거하지는 않는지 점검(CR 2026-06-16 본문 3번 항목). C 어댑터 동작은 변경 금지 — 점검 후 영향 있으면 별도 change request 발행.

---

### Phase P1 — Alpha 시나리오 확장 NPC 라인업/대사 생성 (CR 2026-06-11/-12 Consolidated/Flight Variants/Baggage Customs) — 5d

P0가 안정화된 다음 진행. 본 Phase는 4개 PR로 분할.

#### P1-1 — NPC 로스터/보이스 프로필 매핑 추가 (1d)

**대상 NPC 그룹:**
- **시트메이트 라인**: A 루트(`FLIGHT_A_*` Friendly Seatmate), B 루트(`FLIGHT_B_*` Curious Seatmate), C 루트(`FLIGHT_C_*` Travel Form Help)
- **수하물 서비스 직원**: `BAG_001`~`BAG_004`
- **세관 공무원(Customs Officer)**: `BAG_005`~`BAG_007`

**작업:**
1. `services/service_a/npc_roster_service.py` 에 신규 `NPCProfile` 엔트리 추가.
   - 시트메이트 3종 (display_name, persona_instruction, default_animation, role) — Developer C가 보낸 canonical NPC IDs(`arabella`, `novak` 등 또는 신규 ID)와 정합. CR 2026-06-15 handoff에서 `arabella`가 사용된 사례 참고.
   - 수하물 서비스 직원(예: `harris`, `dan`) 페르소나 (helpful/empathetic) 정의.
   - 세관 공무원 페르소나 (formal/firm/by-the-book) 정의.
2. `_normalize_npc_id` 매핑 보강: B/C에서 들어오는 비-canonical 표기(예: `SEATMATE_A_01`)를 폴백시키되, **Hale 으로 폴백하지 않고** 해당 챕터의 기본 시트메이트/수하물 staff/customs officer로 정확히 라우팅.
3. `services/service_a/voice_profile_service.py` 에 각 신규 NPC ID에 대응하는 voice_profile_id, voice_id, ElevenLabs 보정 디폴트 추가. (Edge TTS 폴백용 voice도 함께.)
4. 테스트: `backend/tests/test_developer_a_npc_roster.py` 에 신규 NPC 4종 이상 조회 + 폴백 검증.

**수용 기준:**
- 비-입국심사 NPC ID로 호출했을 때 Hale로 떨어지지 않음.
- `/respond-dialog` Flight/Baggage 프리셋에서 speaker 표시가 시트메이트/수하물 staff/customs officer로 정상.

#### P1-2 — Flight 시트메이트 대사 생성 (1.5d)

**대상:** `FLIGHT_A_001`~`FLIGHT_A_005`, `FLIGHT_B_001`~`FLIGHT_B_005`, `FLIGHT_C_001`~`FLIGHT_C_005`

**작업:**
1. **룰베이스 시드**(`developer_a_input_service.normalize_level_design_payload` + `dialogue_policy_service` + `node_initialize_state`): `dialogue_seed.surface_goal`, `npc_question_goal`, `target_slot` 으로부터 시트메이트 톤(`formal_supportive`, `formal_neutral` casual variant) 룰베이스 후보 텍스트 생성. (B의 final lines는 사용 금지.)
2. **LLM 시스템 프롬프트** (`_developer_instructions`)에 시트메이트 컨텍스트 분기 추가: "If `npc_role` is `seatmate`, use casual, warm, conversational tone. Keep sentences short. Avoid officer-style directives."
3. **페르소나 주입**: 로스터의 `persona_instruction`가 시트메이트별로 다르게 적용되도록 `node_generate_dialogue_llm`이 정확한 NPC profile을 사용하는지 확인.
4. **종결 전 처리**: 각 루트의 5번째 노드 응답이 자연스럽게 마무리되도록 룰베이스/프롬프트 가이드 추가 (예: `FLIGHT_*_005` 에서 짧은 작별/마무리 멘트).
5. 테스트: 신규 루트별 시드→다음질문 합성 회귀 1건씩 (총 3건).

#### P1-3 — Baggage 서비스 데스크 대사 생성 (1d)

**대상:** `BAG_001_REPORT_MISSING_AT_DESK`~`BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD`

**작업:**
1. 룰베이스 시드: `missing_bag_statement`, `claim_tag_status`, `carousel_search_confirmation`, `customs_hold_redirect_acknowledgement` 슬롯에 부합하는 helpful/clarifying 톤 후보 생성.
2. LLM 프롬프트: `npc_role=baggage_service_staff` 분기 — empathetic + procedural 톤 가이드.
3. `BAG_004` 응답이 `BAG_005` 로의 재지시 멘트(customs hold로 보낸다는 안내)를 포함하도록 룰베이스 보강.
4. 테스트: BAG_001~004 루트별 회귀 2건.

#### P1-4 — Baggage 세관 공무원 대사 생성 + `random_customs_item` 통합 (1.5d)

**대상:** `BAG_005_CUSTOMS_HOLD_EXPLANATION`, `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`, `BAG_007_CUSTOMS_CLEARANCE`

**작업:**
1. LLM 프롬프트: `npc_role=customs_officer` 분기 — formal/firm 톤, 안전·관세 절차 어휘 가이드.
2. **`BAG_006` 핵심**: C 어댑터가 이미 `game_state.random_customs_item` 을 페이로드에 전달 중(CR 2026-06-15 handoff 확인). 이를 `npc_question_goal=explain_random_customs_item` 컨텍스트로 사용해 NPC가 해당 아이템에 대해 구체적으로 질문하도록 시드 강화. (예: 아이템이 "red ginseng medicine" 이면 NPC 질문이 "What is this red item, sir?")
3. `BAG_007` 응답이 clearance 멘트로 자연스럽게 마무리되도록 (그리고 `BAG_999_COMPLETE` 전 마지막 NPC 라인 처리).
4. 테스트: `random_customs_item` 컨텍스트 주입 회귀 2건 (medicine / electronics 등 2가지 카테고리).

**P1 전체 수용 기준:**
- `/respond-dialog` Flight(A/B/C 각 1회) + Baggage 전 구간 1회씩 수동 회귀 시 speaker/톤/다음 질문이 모두 NPC 역할에 맞게 나옴.
- 모든 신규 회귀 테스트 그린.
- 기존 immigration(`IMM_*`) 회귀 무영향.

**가드레일 확인:**
- B의 분기/검증/판정·점수에 영향이 가지 않는지: 로스터/voice/persona/대사 텍스트 외에는 변경 없음.
- C의 `integrations/dev_a_npc_dialogue_client.py` 는 변경 금지. 페이로드 컨트랙트 변경이 필요하면 change request로 등록.

---

### Phase P2 — Chapter 경계 + Emotion enum + 동적 TTS 파라미터 정착 (CR 2026-06-12 boundary/emotion/expand-payload) — 2d

#### P2-1 — `COMPLETE_CHAPTER` 종결 대사 컨텍스트 처리 (0.5d)

**작업:**
1. payload에 들어오는 `transition.status == "complete_chapter"` 신호(또는 `next_action == "COMPLETE_CHAPTER"`)를 `node_initialize_state` 에서 감지.
2. 감지 시 룰베이스 시드를 "현재 챕터를 닫는 짧은 마무리 멘트"로 고정 (예: 시트메이트 → `"Enjoy your trip!"`, 입국심사 → `"All right, you're cleared."`, 수하물 staff → `"You're all set."`).
3. LLM 프롬프트에 추가 지시: "If `transition.status == complete_chapter`, output a closing line only. Do NOT ask the next chapter's opening question. Do NOT reference scenes Unreal hasn't shown."
4. 다음 질문 합성 헬퍼(P0에서 만든 것)를 `complete_chapter` 컨텍스트에서는 우회.
5. 테스트: 3개 챕터 종료 노드 (`FLIGHT_999_COMPLETE`, `IMM_999_CLEARED`, `BAG_999_COMPLETE`) 회귀.

#### P2-2 — `npc.emotion` enum(13종) 적용 강화 (1d)

**현재 상태:** `schemas.py` 의 `NPCDialogueLLMResult.npc_emotion` 은 이미 13종 enum 입력을 받음. LLM이 자체적으로 npc_emotion을 산출하기도 함.

**추가 작업:**
1. **A-facing payload의 `npc.emotion` 을 LLM의 자체 산출보다 우선**하도록 `node_generate_dialogue_llm` 의 우선순위 정렬:
   - 우선순위: `payload.npc.emotion (B 제공)` > `llm_result.npc_emotion (LLM 자체 결정)` > `emotion_state.emotion (룰베이스)`.
   - 단, 시스템 프롬프트에는 "Use `npc.emotion` as the dominant cue for tone/style/speed/animation. If absent, infer from context." 명시.
2. **TTS 보정 매핑 보강**: `voice_output_service._elevenlabs_*_for_tone()` 류 헬퍼를 `for_emotion()` 변형으로 확장하여 13종 emotion 각각에 대한 `stability/style/speed/similarity_boost` 기본값을 두고, LLM이 산출한 값이 있으면 그것을 우선 사용(현재 동작) + 없을 때 emotion 기반 기본값 폴백.
3. **애니메이션 결정**: 현재 `animation`은 NPCProfile의 `default_animation` 사용. emotion(anger/fear 등)에 따른 micro-variant 매핑 표를 `npc_roster_service` 또는 신규 `services/service_a/animation_mapping_service.py` 로 도입 (P3 후속이 아닌 P2에서 최소 셋만).
4. 테스트: 5개 emotion(`normal/joy/anger/confusion/suspicion`) × 3개 톤 회귀 매트릭스로 stability/style/speed 산출 검증.

#### P2-3 — Expand NPC Dialogue Client Payload(CR 2026-06-12 A 요청자) 정합성 점검 (0.5d)

**현재 상태:** handoff에 의하면 LLM이 stability/style/speed/similarity_boost 를 동적 산출하고 voice_output_service 가 ElevenLabs에 우선 주입하도록 이미 연동됨.

**작업:**
1. C가 보내는 페이로드의 `npc.emotion` 이 B로부터 정상 전달되는지 회귀로 확인 (P2-2와 연동).
2. C 어댑터/스키마 측에서 추가로 확장 필드가 필요한 경우 새 change request 등록 (예: P2-2 에서 LLM이 anim micro-variant를 산출하고자 한다면 Unreal 응답 `npc.animation` 자유 문자열 확장 요청).
3. handoff에 해당 PR 결과를 정리.

**P2 전체 수용 기준:**
- `complete_chapter` 응답이 다음 장 질문을 일으키지 않음 (P0 의 다음 질문 합성과 충돌하지 않게 우선순위 정합).
- 13 emotion enum 회귀 매트릭스 그린.
- `voice_output_service` 토큰 사용량/cost 추적 무회귀.

---

### Phase P3 — LangChain 1.0+ 잔여 정리 + 코드 위생 (1d)

> handoff의 `agent_a_langchain1_refactoring_plan.md` 기준 Phase 5/6 미완료 잔여와 ruff 잔여를 정리.

**작업:**
1. **`polish_tts_text` unused import 제거** (`backend/app/agents/agent_a/npc_dialogue_agent.py:24`).
   - 또는 룰베이스 경로에서 `polish_tts_text` 호출이 의도되었으나 누락이라면 다시 연결 후 회귀.
2. **`NPCDialogueAgentRunMiddleware` Shim 단계적 제거** (CR 2026-06-15):
   - 호출 측 잔존 여부 grep: `from backend.app.middleware.middleware_a` import 사용처가 deprecation warning을 띄우는지 확인.
   - 모든 호출자가 `NPCDialogueAgentRunRecorder` 직접 사용으로 전환되었으면 Shim 제거 PR + 1주 deprecation 알림.
3. **`inspect.signature` 잔여 검색**: `grep -rn "inspect.signature" backend/app/agents/agent_a backend/app/services/service_a` → 0건 확인.
4. **`callbacks` state 키 잔여 검색**: 0건 확인.
5. **`RunnableConfig.configurable["llm_chain"]` DI 사용처 점검**: P0에서 추가된 분기들이 동일 표준에 정렬되는지 확인.
6. **`samples/`, `demo/` 폴더의 fixture/스냅샷** 이 위 변경과 정합한지 검증.

**수용 기준:**
- `uv run ruff check .` 그린 (`agent_a/npc_dialogue_agent.py` 잔여 경고 0건).
- `uv run mypy .` 그린.
- handoff에 정리 PR 기록.

---

## 4. 일정 / 의존성

| Phase | 의존성 | 예상 공수 |
|---|---|---|
| P0 (CR 2026-06-16) | 없음 — 즉시 시작 | 1.5d |
| P1-1 로스터/보이스 | P0 머지 후 (충돌 없음이면 병행 가능) | 1.0d |
| P1-2 Flight 대사 | P1-1 | 1.5d |
| P1-3 Baggage staff | P1-1 | 1.0d |
| P1-4 Customs officer + random item | P1-1, P1-3 | 1.5d |
| P2-1 complete_chapter | P0 | 0.5d |
| P2-2 emotion enum | P1-1 (로스터의 default_animation 표 활용) | 1.0d |
| P2-3 payload 정합성 | P2-2 | 0.5d |
| P3 정리 | 모든 P0/P1/P2 머지 후 | 1.0d |
| **합계** | | **~9.5d (영업일)** |

---

## 5. 위험 요소 및 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| P0 프롬프트 변경이 immigration(`IMM_*`) 회귀를 깰 가능성 | 기존 그린 테스트 깨짐 | 변경 전 baseline 스냅샷, 변경 후 immigration 회귀 우선 그린 확인 |
| P1 신규 NPC 페르소나의 LLM 응답이 일정치 않음 | A/B 테스트로 톤 흔들림 | 룰베이스 시드를 충분히 강하게 만들어 LLM 실패/이상 시에도 자연스러운 폴백 보장 |
| P1-4 `random_customs_item` 데이터 형식이 B/C에서 변경될 가능성 | NPC 질문 부정합 | C 어댑터 스펙 변경 발생 시 change request 협의 후 진행. 현재 schema는 `RandomCustomsItemContext` (handoff 2026-06-15) |
| P2-2 emotion enum 13종을 모두 매핑하기 어려운 경우 | 일부 emotion에 기본값 폴백 | `joy/anger/confusion/suspicion/normal` 5종 최소 강제, 나머지는 톤 기반 fallback로 회귀 안전망 |
| Shim 미들웨어 제거 PR이 외부(C-side) 잔존 호출에 영향 | import 실패 | 사전 grep 검증, 모든 호출자 마이그레이션 확인 후에만 제거 |
| C-side 스키마/어댑터에 영향이 가는 변경이 필요해질 때 | 가드레일 위반 | 즉시 change request 등록 후 협의. A 단독으로 C 영역 수정 금지 |

---

## 6. PR 단위 체크리스트 (모든 머지에 공통)

- [ ] `uv run pytest backend/tests` 그린
- [ ] `uv run ruff check .` 그린 (`agent_a/`, `service_a/`, `tool_a/`, `middleware_a/`)
- [ ] `uv run mypy .` 그린
- [ ] `/respond-dialog` 수동 스모크 (해당 PR이 다루는 챕터의 1회 이상)
- [ ] `docs/handoff.md` 에 변경 요약 추가
- [ ] 관련 change request에 "Developer A update" 섹션 또는 Status 갱신 기재
- [ ] B/C 영역 파일 변경 0건 (gardrail check: `git diff --stat | grep -E "(agent_b|agent_c|service_b|service_c|tool_b|tool_c|middleware_b|middleware_c|integrations|schemas|api|graphs)"` 결과 0)

---

## 7. 후속(별도 RFC) 항목

- `create_agent` 도입과 tool_a 의 `@tool` 데코레이션화(`agent_a_langchain1_refactoring_plan.md` Phase 5 옵션 B).
- 비동기화(`ainvoke`/`astream`) — FastAPI 경로의 처리량 개선.
- LangSmith/Tracing 연동 — `RunnableConfig` 정렬이 끝났으므로 1줄 추가 수준.
- Unreal 응답의 `npc.animation` 확장(emotion 기반 micro-variant) 필요 시 change request 발행.
