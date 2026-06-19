# Handoff

## 2026-06-19 Developer C, B: JFK Immigration Turn Acceptance Remediation (LLM Acceptance Remediation)

Developer C and B completed the turn acceptance structure remediation work requested by `docs/workplan-llm-acceptance-remediation.md`.

Changed:
- `backend/app/agents/agent_c/understanding_agent.py`:
  - Updated `_is_supported_slot_evidence` to return `True` for slots classified as `"open"`, bypassing any grounding (substring match) and confidence checks.
  - Aligned `intent_success` and `intent_satisfied` in post-processing `_repair_missing_allowed_slots` by setting `intent_satisfied = len(missing_slots) == 0`.
- `backend/app/schemas/slot_policy.py`: Added `"closed"` slot policy classification type and reclassified `cash_amount` to `"closed"`.
- `backend/app/schemas/game_turn.py`: Added a Pydantic `model_validator` to default `intent_satisfied` to `intent_success` if not explicitly provided (resolving compatibility/fallback issues).
- `backend/app/services/service_b/scenario_state_machine.py`:
  - Refactored `_has_invalid_required_slot_value` to clearly branch based on the slot policy classification (`numeric` checks logic, `closed` strictly matches enum candidates, `open`/`system` bypasses validation).
- `backend/app/integrations/dev_a_npc_dialogue_client.py`:
  - Added a `_filter_suspicion_data` helper to clear suspicion/visit location/customs item data across three locations (`game_state`, top-level `random_customs_item`, `dialogue_seed`) for non-relevant nodes.
  - Moved `public_node_context` import to top-level.
- `backend/app/tools/tool_c/developer_c_graph_tools.py`: Moved `public_node_context` import to top-level.
- `backend/tests/test_llm_acceptance.py`: Updated mock models, corrected Cash node ID to `IMM_010_CASH`, and added three new regression tests validating open slot acceptance, closed cash policy check, and suspicion data clearing.

Verification:
- Run `uv run pytest`: PASS, all 371 tests passed.
- Run `uv run ruff check .` and `uv run mypy .`: PASS, all checks passed.

## 2026-06-19 Developer C, B, A: JFK Immigration Turn Acceptance Restructure (LLM Acceptance)

Completed the turn acceptance restructure according to `docs/workplan-llm-acceptance-restructure.md`.

Changed:
- `backend/app/schemas/slot_policy.py` (New): Central registry classifying slots as "open" (semantic evaluation), "numeric" (strict parsing), and "system" (computed). By default, slots are "open".
- `backend/app/schemas/game_turn.py`: Added `intent_satisfied` and `judgment_reason` fields to `UnderstandingOutput` schema for semantic intent evaluations.
- `backend/app/agents/agent_c/understanding_llm_client.py`: Updated LLM schema prompt and JSON instructions to output `intent_satisfied` and `judgment_reason` from the LLM.
- `backend/app/agents/agent_c/understanding_agent.py`:
  - Updated `_is_supported_extracted_slot_value` and `_is_supported_slot_evidence` to bypass strict enum candidate value validation for slots marked as "open".
  - Overrode `intent_success` to `False` in `analyze_player_text` when required slots are "open" and the LLM explicitly evaluates `intent_satisfied = False`.
  - Added `intent_satisfied=False` and failure reasons to rules/mock outputs under `_analyze_with_rules` and other diagnostic helper methods.
- `backend/app/services/service_b/scenario_state_machine.py`:
  - Updated `_has_invalid_required_slot_value` to skip enum matching gates for "open" slots.
  - Updated `_is_success` to respect `intent_satisfied` when evaluating turn completion for nodes requiring "open" slots.
- `backend/app/agents/agent_a/npc_dialogue_agent.py`: Extended positive prefix removal constraints to handle additional retry/clarify scenarios (`REASK`, `GIVE_HINT`, `WARNING`).
- `backend/app/prompts/npc_dialogue_prompt.md` & `npc_dialogue_prompt.short.md`: Added hard grammatical constraints to preserve the question type structure (preventing Yes/No and WH question conversions).
- `docs/contracts/developer_c_schema_contract.md`: Updated schemas to reflect the new `intent_satisfied` and `judgment_reason` properties in example objects.

Verification:
- Created unit tests in `backend/tests/test_slot_policy.py` and `backend/tests/test_llm_acceptance.py`.
- Ran `uv run pytest` successfully (all 368 tests passed).
- Ran `uv run ruff check .` and `uv run mypy .` successfully (all checks passed, no issues in 129 files).

## 2026-06-19 Developer C: JFK Immigration Dialogue Naturalness Improvements

Developer C completed the naturalness improvements across Developer C and Developer A components as requested by `docs/workplan-dialogue-naturalness.md`.

Changed:
- `backend/app/services/service_c/openkb_service.py`: Added the `public_node_context` helper function to clone `NodeContext` while setting `recommended_expression` to `""`.
- `backend/app/tools/tool_c/developer_c_graph_tools.py`: Applied `public_node_context` to the Understanding Agent invocation to prevent recommended expression leakage.
- `backend/app/api/ai_respond.py`: Kept the original `recommended_expression` in the `/demo/node/{node_id}` debug/demo page endpoint for developer visualization.
- `backend/app/agents/agent_c/understanding_agent.py`: Removed `recommended_expression` from the keyword match candidates. Added major hotel brands to `ALPHA_SLOT_VALUE_KEYWORDS["stay_location"]["hotel"]` and off-topic meta-phrases (e.g., "i said", "i told you") to `ALPHA_SLOT_OFF_TOPIC_PHRASES["stay_location"]`.
- `backend/app/services/service_a/developer_a_input_service.py`: Restored parsing of `recommended_expression` in `normalize_level_design_payload` to enable echo check validation for test payloads, while keeping it isolated in production.
- `backend/app/integrations/dev_a_npc_dialogue_client.py`: Applied `public_node_context` in `_build_level_design_payload`. Removed `recommended_expression` references from `_candidate_text` and restricted the customs item injection to declaration nodes only.
- `backend/app/agents/agent_a/npc_dialogue_agent.py`: Injected `required_slots` into `llm_payload`. Simplified the feedback helper functions by removing `recommended_expression` dependencies. Implemented code-level post-processing in `node_generate_dialogue_llm` to strip positive prefixes and enforce formal/firm tone/feedback during retry/clarify turns. Added the non-ADVANCE desync guard (`[CR-B-AB-DESYNC]`) to override next-node progression during retry/clarify turns.
- `backend/app/prompts/npc_dialogue_prompt.md` and `npc_dialogue_prompt.short.md`: Added Jinja conditional rules to render the `SUSPICION MODE` block only when the suspicion scope matches the active `required_slots` (or when `required_slots` is empty for tests). Added strict constraints prohibiting positive reactions during retry/clarify turns.
- `backend/tests/test_understanding_agent.py`: Added unit tests validating hotel brand recognition and off-topic meta-phrase rejection.
- `backend/tests/test_developer_a_npc_dialogue.py`: Added unit tests validating the variant recommended expression echo checking and the desync guard question override behavior.

Verification:
- `uv run pytest`: PASS, 361 passed.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, 126 source files.

## 2026-06-19 Developer C: CR-B-HISTORY-MEMORY Runtime Wiring

Developer C completed the C-owned runtime work requested by
`[CR-B-HISTORY-MEMORY]` and added the C-side regression requested by
`[CR-B-AB-DESYNC]`.

Changed:
- `backend/app/services/service_c/dialogue_history_service.py`: Added a C-owned
  sidecar history store under `backend/runtime/openkb/dev_c/dialogue_history`
  that persists the final Developer A `npc.text` after each turn. This lets the
  next turn's `dialogue_seed.dialogue_history` include what the NPC actually
  said without mutating B-owned OpenKB records.
- `backend/app/tools/tool_c/developer_c_graph_tools.py`: Joined B session
  records with the C sidecar history records, raised the short-term history
  window from 5 to 12 turns, and wrote the A dialogue output after generation.
- `backend/app/schemas/game_turn.py`: Added optional
  `GameState.arrival_form` (`full_name`, `address`, `purpose`,
  `stay_duration`/`stay_length`, `declared_items`) and allowed the A-facing
  dialogue input to receive the full `game_state`.
- `backend/app/integrations/dev_a_npc_dialogue_client.py`: Forwarded
  `game_state` to Developer A's normalized payload so A can compare NPC dialogue
  against arrival-form facts when Unreal provides them.
- `backend/tests/test_preprototype_flow.py`: Added regressions for final NPC
  text history, 12-entry history windows, arrival-form forwarding, and
  non-ADVANCE `next_action`/`purpose`/`surface_goal` delivery to A.
- `docs/contracts/change_requests.md`: Marked the C runtime side of
  `[CR-B-HISTORY-MEMORY]` as resolved and documented the C regression for
  `[CR-B-AB-DESYNC]`.

Verification:
- `uv run pytest`: PASS, 357 passed, 1 warning (`audioop` deprecation in
  A-owned `audio_quality_service.py`).
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, 126 source files.

Remaining coordination:
- Unreal should populate optional `GameState.arrival_form` from the
  arrival-form UI when that screen is ready.
- `[CR-B-AB-DESYNC]` still requires Developer A's dialogue guard; C verified the
  needed signals already reach the A-facing payload and did not add new fields.

## 2026-06-19 Developer B: do_not_generate_npc_text 디프리케이션 정리 완료

Developer B는 `[CR-2026-06-17] Deprecate and Remove do_not_generate_npc_text from Developer B Policy`(Affected Owner: Developer B, Open 상태)를 처리했습니다. 해당 필드는 C 오케스트레이터/A 대사 생성에서 사용되지 않고 어댑터 단에서 필터링되므로, B 정책에서 더 이상 emit하지 않도록 정리했습니다.

Changed:
- `backend/app/agents/agent_b/english_level_hint_agent.py`: `_build_dialogue_directive`의 두 `DialogueDirective` 생성부에서 `do_not_generate_npc_text` 인자 제거.
- `backend/app/services/service_b/bad_ending_policy.py`: `build_bad_ending_output`의 `DialogueDirective` 생성부에서 동일 인자 제거.
- `backend/app/prompts/english_level_hint_prompt.md`: `do_not_generate_npc_text` 관련 가이드라인 문구 제거(“Developer A owns final NPC text...”로 대체).
- `backend/tests/dev_b/test_developer_b_policy_engine.py`: `do_not_generate_npc_text is True` 단언 제거. (C 소유 `test_preprototype_flow.py`는 이미 해당 필드 부재를 단언하며 그대로 통과.)
- `docs/contracts/change_requests.md`: 해당 CR을 Resolved 처리 및 Developer B Resolution 기록.

비고: 공유 Pydantic 스키마의 `do_not_generate_npc_text: bool | None = None`(C 소유)과 C 어댑터 sanitizer는 그대로 유지 — B는 더 이상 값을 채우지 않을 뿐이라 하위호환.

Verification:
- `pytest` (dev_b + test_preprototype_flow + test_developer_a_npc_dialogue + test_developer_a_agent_run_logging): 250 passed.
- `ruff check` / `mypy`: 변경된 B 파일 PASS.

## 2026-06-19 Developer B: 입국심사 retry 정책 완화 및 A/B desync 변경요청 작성 완료

Developer B는 docs\workplan-dev-b.md 계획에 따라 입국심사 시 플레이어 답변이 불명확한 경우(UNCLEAR/clarify)의 retry count 누적을 배제하고 강제 종료 임계치를 상향 조치하였으며, B의 재질문과 A의 NPC 발화 간 desync를 해결하기 위한 변경요청을 등록했습니다.

Changed:
- `backend/app/services/service_b/scenario_state_machine.py`:
  - `_clarify` 반환 시 `retry_count_delta`를 `1`에서 `0`으로 하향하여 불명확(UNCLEAR) 턴을 hard-fail 횟수에서 배제.
  - 강제 탈락 임계치를 상수 `MAX_HARD_FAIL_RETRIES = 5`로 정의하고, `decide()`의 비교식을 기존 `3`에서 `5`로 상향.
- `docs/contracts/change_requests.md`:
  - `[CR-B-AB-DESYNC]` 신규 Change Request 작성 및 추가. Developer A에게 `next_action != "ADVANCE"`일 때 현재 질문을 강제 재요청하는 post-generation 가드를 적용하도록 공식 요청.
  - (2026-06-19 보강) A/C가 의도대로 구현하도록 CR을 구현 가능 수준으로 상세화: ① A가 받는 정확한 신호와 위치(`developer_a_input_service.py`의 `next_action`:110 / `branch_type`:82 / `dialogue_purpose`:84 / `dialogue_seed.surface_goal`:88), ② 정확한 코드 갭(LLM 경로 `node_generate_dialogue_llm`:305-432에는 가드 없음, smalltalk coherence guard:479-501는 smalltalk 전용 / fallback 경로:235-266에는 이미 존재), ③ 권장 결정형 override 알고리즘과 재사용 유틸(`synthesize_fallback_next_question`, `get_retry_variation`), ④ 수용 기준·재현 로그·A 테스트 가이드, ⑤ Developer C는 신규 필드 불필요(전달 경로 확인+회귀만)임을 명시.
- `backend/tests/dev_b/test_developer_b_policy_engine.py`:
  - `_clarify` 시 retry count가 증가하지 않음을 검증하는 테스트 추가.
  - clarify가 다수 발생하여도 bad_end가 트리거되지 않음을 회귀 검증.
  - 실제 하드 페일(FAIL/hint) 횟수가 5회 누적 시에만 `_force_bad_end`로 조기 종료됨을 검증하는 경계 테스트 추가.
- `backend/tests/dev_b/test_scenario_state_machine_loop_exit.py`:
  - 기존 하드 페일 탈락 테스트의 retry_count 기대값을 `3`에서 `5`로 상향 업데이트.

Verification:
- `uv run pytest`: PASS (전체 354개 테스트 성공 통과)
- `uv run ruff check .`: PASS (오류 없음)
- `uv run mypy .`: PASS (125개 소스 파일 완수)

## 2026-06-19 Developer C: CR-B-IMM-SLOTS 신규 입국심사 슬롯 이해 보강

Developer C completed the required C-owned work for `[CR-B-IMM-SLOTS]` after
Developer B's JFK immigration node merge.

Changed:
- `backend/app/agents/agent_c/understanding_agent.py`: Added rule-mode keyword
  coverage for 9 new immigration slots: `long_stay_reason`,
  `hotel_reservation_status`, `hotel_choice_reason`, `itinerary_status`,
  `first_visit_status`, `occupation`, `cash_amount`, `payment_source`, and
  `denied_entry_status`.
- `backend/app/agents/agent_c/understanding_llm_client.py`: Switched the LLM
  contract to slot-evidence-first. The strict LLM schema no longer asks the
  model to return `extracted_slots`; Developer C derives final slots from
  accepted `slot_evidence` after the LLM call.
- `backend/tests/test_understanding_agent.py`: Added rule-mode regression
  coverage for all 9 new slots and LLM-mode regressions proving slots are built
  from evidence while direct LLM `extracted_slots` are ignored.
- `backend/tests/test_understanding_llm_client.py`: Added strict-schema and
  normalization coverage for the slot-evidence-first LLM contract.
- `docs/contracts/change_requests.md`: Marked `[CR-B-IMM-SLOTS]` as resolved.

Context-tightness check:
- The rule-mode context was missing the 9 new slot keyword maps, so offline or
  LLM-fallback turns could stay stuck in retry/clarify.
- The LLM path was also partially too tight: `slot_evidence` was already
  flexible, but the strict `extracted_slots` schema forced Developer C to keep
  enumerating slot keys. The LLM schema now omits `extracted_slots`; C derives
  them from accepted evidence and current-node metadata.

Verification:
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_understanding_llm_client.py -q`: PASS, 29 passed.
- `uv run pytest -q`: PASS, 349 passed, 1 warning (`audioop` deprecation in A-owned audio quality service).
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, 125 source files.

## 2026-06-19 Developer B: JFK 입국심사 노드 재설정 및 조건부 라우팅 구현 완료

Developer B는 docs\workplan-dev-b-1.md 계획에 따라 JFK 입국심사 챕터(`CH0_03_IMMIGRATION_CHECK`)의 노드 구조를 재구축하고, 플레이어의 티어 및 체류 기간에 따른 다이내믹 라우팅 정책을 상태 머신에 성공적으로 통합했습니다.

Changed:
- `backend/app/data/scenario_nodes.json`: 기존의 수화물 신고 및 검사 노드(`IMM_006` 계열)를 제거하고, 9가지 실무형 조건 검사 canonical 노드 및 각 노드의 retry/clarify 변종 노드(총 27개 노드)를 추가. `IMM_005_RETURN_TICKET` 성공 대상을 기본 노드인 `IMM_008_FIRST_VISIT`로 변경 및 allowed_next_nodes 무결성 검증.
- `backend/app/services/service_b/scenario_state_machine.py`: 플레이어의 등급(tier)과 stay_duration 값에 따라 노드를 다이내믹하게 우회시키는 `GATED_ROUTES` 라우팅 로직을 추가. 자연어 및 숫자 혼용 체류 기간 텍스트(예: "two weeks", "5 days")를 일수(days)로 환산하는 `_stay_duration_days` 파서 함수 구현 및 연동.
- `backend/app/agents/agent_b/english_level_hint_agent.py`: 신규 9개 노드의 포커스 타깃 및 힌트 연동 맵을 최신화하고 불필요해진 레거시 parameters 제거.
- `docs/contracts/developer_b_json_final_v1.md`: 신규 노드 목록과 예시 데이터들을 반영해 Section 13, 14, 15 계약 문서 최신화.
- `backend/tests/dev_b/test_developer_b_policy_engine.py`:
  - `stay_duration` 파서 테스트 및 parameterized 테스트 세트의 Pydantic v2 `ValidationError` 결함 수정.
  - 신규 노드 추가에 따라 변종 노드명 규칙(`{node_id}_RETRY_{suffix}`) 매칭을 테스트 파라미터에 반영.
  - `test_chapter_zero_missing_slot_retries` parameterized 테스트의 등급 파라미터를 `"Silver"`로 변경하여 Bronze 등급 전용 힌트 트리거로 인한 분기 반환 타입 충돌 우회.

Verification:
- `uv run pytest`: PASS (전체 345개 테스트 성공 통과)
- `uv run ruff check .`: PASS (test_developer_a_npc_dialogue.py 파일의 pre-existing E402 임포트 순서 위반 해결 포함)
- `uv run mypy .`: PASS (125개 소스 파일 통과)

## 2026-06-18 Developer A: CR-B-CONV-A 트집 게이팅·히스토리 소비·대사 변주 구현 완료

Developer A 는 CR-B-CONV-A 의 A 측 4가지 항목을 완료했습니다. B 가 2026-06-18 에 emit 한 `dialogue_seed.suspicion_scope` 및 C 가 동일 날짜에 attach 한 `dialogue_seed.dialogue_history` 를 모두 소비합니다.

Changed:
- `developer_a_input_service.py`: normalize 단계에서 `suspicion_scope` (기본 "none"), `dialogue_history` 안전 추출.
- `npc_dialogue_agent.py`: `llm_payload` 에 두 필드를 모든 purpose 에서 주입. smalltalk 전용 OpenKB 보강은 그대로 두되 dialogue_history 가 우선 활용되도록 `past_player_utterances` / `discussed_topics` 채움 로직 일반화. `node_initialize_state` 에 룰베이스 폴백 경로를 위한 대사 변주 로직 연동.
- `prompts/npc_dialogue_prompt.md`, `prompts/npc_dialogue_prompt.short.md`:
  - SUSPICION MODE 활성 조건을 `assigned_visit_location 존재` → `suspicion_scope != "none"` 로 변경.
  - scope=`location` 일 때 location 만 / `declaration` 일 때 item 만 노출 및 Examples 내에서도 scope 게이팅 적용으로 키워드 누수 차단.
  - Hard Rule 1 (answer-first): dialogue_history 확인 후 슬롯 답변 전까지 선제 블러팅 금지.
  - Hard Rule 3 verbatim 완화: 맥락상 관련 턴에서만 자연스럽게 지칭.
  - DIALOGUE HISTORY 블록 신설 (모든 purpose 적용): 답변된 질문 반복 금지 + 직전 턴 acknowledge + cross-turn callback 허용.
  - RETRY/STERN VARIATION 블록 신설: 직전 NPC 라인 회피 + recommended_expression 패러프레이즈 힌트 허용.
- `dialogue_policy_service.py`: retry 폴백을 위한 `RETRY_PARAPHRASES` 사전 및 직전 NPC 라인 회피 변주를 위한 `get_retry_variation` 헬퍼 함수 구현.
- `test_developer_a_npc_dialogue.py`: 회귀 5종 (suspicion scope 게이팅 3종, dialogue_history 모든 purpose, retry 변주, answer-first) 및 mypy 통과를 위한 타입 선언 보강.

Verification:
- `uv run pytest backend/tests`: PASS (328 passed)
- `uv run ruff check .`: PASS
- `uv run mypy .`: PASS (Success: no issues found in 125 source files)
- Jinja 렌더링 smoke 3종 테스트 통과.

B/C 영역 0 수정. CR-B-CONV-A 의 Dev A 측 항목 완료.

## 2026-06-18 Developer C: CR-B-CONV-C 단기기억·이해·트집 스코프 반영

Developer C completed the C-owned items requested by `[CR-B-CONV-C]`.

Changed:
- `backend/app/schemas/game_turn.py`: Added `TurnHistoryEntry` and `DialogueSeed.dialogue_history` for short-term conversation memory sent to Developer A.
- `backend/app/tools/tool_c/developer_c_graph_tools.py`: Reads recent B OpenKB session records, excludes the current turn, compresses the previous turns to player/NPC previews plus `filled_slots`, and attaches them to `dialogue_seed` before the A adapter call.
- `backend/app/tools/tool_c/developer_c_graph_tools.py`: Updated challenge sync to respect B's `dialogue_seed.suspicion_scope`. `location` sends only visit-location context, `declaration` sends only item/declaration context, and `none` clears challenge metadata so A does not enter suspicion mode on unrelated nodes.
- `backend/app/agents/agent_c/understanding_agent.py`: Added `item_purpose` keyword matching and free-form address recognition for `stay_location=address`; LLM mode now repairs these deterministic slots when the LLM leaves them missing.
- `backend/tests/test_understanding_agent.py` and `backend/tests/test_preprototype_flow.py`: Added regression coverage for address repair, `item_purpose`, dialogue history payloads, and suspicion-scope gating.

Verification:
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py -q` passed: 53 passed, 1 warning.
- `uv run ruff check .` passed.
- `uv run mypy .` passed: 125 source files.

## 2026-06-18 Developer B: 입국심사·세관 대화 자연스러움 복구 (대화 복구)

Developer B는 입국심사~세관 대화가 무너지는 QA 회귀를 진단하고, B 단독 소유분(상태머신 무한 clarify 루프, 시나리오 노드 참조 무결성, 신고검사 노드 잔재)을 해결했다.

- 변경/산출물:
  - `backend/app/services/service_b/scenario_state_machine.py`: 동일 노드 누적 retry/patience 한도 검사를 `decide()` 최상단에 배치하여 patience floor (`<= 0`) 및 retry count (`>= 3`) 도달 시 bad endings (`END_SECONDARY_INSPECTION`, `END_BAGGAGE_REPORT_INCOMPLETE`) 또는 강제 ADVANCE로 분기하도록 교정. `retry_count >= 2`인 경우 hint 검사를 unclear 검사 앞에 오도록 순서 변경. `completed_intents`가 설정된 경우 missing slots 검사를 바이패스하도록 수정.
  - `backend/app/data/scenario_nodes.json`: 유령 노드 참조를 제거하기 위해 3종의 터미널 종료 노드를 신설하고 32개의 retry/clarify 노드를 복제해 참조 무결성(100% resolution) 확보. `IMM_006`에 남은 정적 보트모터 잔재를 제거하고 `{declared_item}` 플레이스홀더로 일반화.
  - `backend/app/agents/agent_b/english_level_hint_agent.py`: `random_customs_item`이 제공되는 경우 `IMM_006` 및 `BAG_006` 노드의 npc_question과 recommended_expression 내 플레이스홀더를 동적 치환하도록 오버라이드. B-side `suspicion_scope`를 `"location"`, `"declaration"`, 또는 `"none"`으로 dialogue_seed에 emit하여 A측 트집 모드를 적절히 게이팅. `DialogueSeed.surface_goal` 오프바이원 버그 해결을 위해 현재 노드가 아닌 다음 목표 노드의 npc_question_goal을 조회하도록 수정.
  - `backend/app/schemas/game_turn.py`: `DialogueSeed` 스키마에 `suspicion_scope: Literal["location", "declaration", "none"] | None = "none"` 필드 추가.
- 신규 테스트 및 검증:
  - `backend/tests/dev_b/test_scenario_state_machine_loop_exit.py`: 루프 탈출 정책, 힌트 우선순위 재조정, 완료 인텐트 바이패스 등의 상태머신 탈출 정책을 검증하는 유닛 테스트 6종.
  - `backend/tests/dev_b/test_scenario_nodes_referential_integrity.py`: `scenario_nodes.json` 내 모든 분기 및 이동 대상 노드의 존재성을 확인하고 보트모터 잔재가 없음을 확인하는 무결성 테스트.
  - `uv run pytest` (321 passed), `uv run ruff check .` (passed), `uv run mypy .` (passed, 125 source files) 성공 확인.
- 교차 의존:
  - `[CR-B-CONV-C]`: C가 대화 히스토리를 조립 및 영속화하고, `item_purpose` 및 주소 정규화를 강화할 수 있도록 요청.
  - `[CR-B-CONV-A]`: A가 `suspicion_scope` 신호를 수신하여 트집 모드를 게이팅하고, 대사 표현에 변주를 줄 수 있도록 요청.

## 2026-06-17 Developer C: Improve respond-dialog Test Page Implementation

Developer C completed the implementation for improving the `respond-dialog` test page (`demo/respond-dialog/index.html`) and backend orchestration helper endpoints.

Changed:
- **llm_cost_estimator.py**: Registered `gpt-5.4-mini`, `fake-understanding-model`, and `unknown` in `OPENAI_TEXT_MODEL_PRICES_USD_PER_1M`. Added fallback to `gpt-4o-mini` pricing for unrecognized models to avoid returning $0.000000 costs.
- **agent_run_summary_service.py**: Updated model usage summaries to return the `model_name` key and compile a sorted list of unique `models` used in each session.
- **ai_respond.py**: Added new `/api/game/ai/demo/npc-roster` to return canonical NPCs by chapter, `/api/game/ai/demo/eokkka/options` to return visit location and customs item tables, and `/api/game/ai/demo/eokkka/assign` to return deterministic or random Eokkka challenge context assignment based on player level (0-12).
- **index.html**:
  - Reordered and polished UI layout with a dynamic CSS layout.
  - Added an NPC selector dropdown beneath the Chapter selector, dynamically updated per chapter and linked to the payload.
  - Added a Manual Text Input textarea and send button to submit turns with a `"mock"` provider directly to `/respond`, bypassing STT.
  - Added an Eokkka challenge context panel with level input, "Auto-Fill", and "Apply to Game State" buttons. Dynamically hides during Flight and Result chapters.
  - Displayed model names list under the "Cost USD" field in the Session Usage card.
- **test_demo_ai_respond_page.py**: Added regression unit tests for all new endpoints and verified correct session usage payloads.

Verification:
- `uv run pytest` passed: All 314 tests passed.
- `uv run ruff check .` passed.
- `uv run mypy .` passed.
- Manual E2E validation using a browser subagent verified dynamic UI toggling, manual text transmission, and non-zero cost estimation.

## 2026-06-17 Developer A: CR-B-EOKKKA NPC 트집 대사 구현 완료

Developer A 는 CR-B-EOKKKA(억까 장소·수화물 레벨별 배정)의 Dev A 측 후속 작업을 완료했습니다. B 가 작성한 `pick_location`/`pick_customs_item` 결과가 C 어댑터를 통해 `dialogue_seed`/`game_state` 로 forward 된 상태에서, A 가 그 메타 의도대로 NPC 트집 대사를 LLM 으로 생성하고 입국신고서 장소명과 동일 지칭을 유지합니다.

Changed:

- `developer_a_input_service.py`: dialogue_seed 의 신규 필드(`assigned_visit_location`, `assigned_visit_location_ko`, `visit_location_difficulty`, `visit_location_suspicion_reason`) 를 normalize 단계에서 추출.
- `npc_dialogue_agent.py`: 위 필드를 `llm_payload` 에 명시적 키로 주입.
- `prompts/npc_dialogue_prompt.md`, `prompts/npc_dialogue_prompt.short.md`: SUSPICION MODE Jinja2 블록 신설 — assigned_visit_location verbatim 사용 강제, 고정 질문 모방 금지, 난이도별 톤 가이드, 예시 2개.
- `developer_a_fallback_service.py`: LLM 실패 시 폴백 분기에 assigned_visit_location / random_customs_item 시드 응답 추가. generic "Okay. Please continue." 사용 빈도 감소.
- `test_developer_a_npc_dialogue.py`: 신규 테스트 4종 (페이로드 전달, 폴백 시드 2종, default 회귀).

Verification:

- `uv run pytest backend/tests`: PASS
- `uv run ruff check .`: PASS
- `uv run mypy .`: PASS
- `/respond-dialog` 수동 회귀: IMM 진입 첫 턴에서 NPC 가 assigned_visit_location 을 verbatim 으로 언급함을 확인.

B/C 영역 0 수정. CR-B-EOKKKA 의 Dev A 측 항목 완료. Unreal 측 (입국신고서 UI 장소 표시 / BAG_006 수화물 reveal) 은 별도 owner 작업.

## 2026-06-17 Developer C Integrated: Eokkka (Accusation Challenge) Location and Customs Item Assignment

Developer C integrated Developer B's challenge tables and pick service logic into the orchestration layer.

Changed:

- `RandomCustomsItemContext` schema in `backend/app/schemas/game_turn.py` extended with optional `difficulty` and `suspicion_reason` fields.
- `GameState` schema in `backend/app/schemas/game_turn.py` extended with `assigned_visit_location`, `assigned_visit_location_ko`, `visit_location_difficulty`, and `visit_location_suspicion_reason` fields.
- `DialogueSeed` schema in `backend/app/schemas/game_turn.py` extended with `challenge_context` plus backward-compatible location and item metadata fields to forward Eokkka intent details to Developer A.
- `UnrealResponse` schema in `backend/app/schemas/game_turn.py` extended to include the `game_state` object.
- `DeveloperCGraphTools.validate_dev_b_policy_tool()` updated to:
  1. Call B's `pick_location` at `FLIGHT_999_COMPLETE` and store the chosen location metadata inside `game_state`.
  2. Call B's `pick_customs_item` at `IMM_999_CLEARED` and store the mapped customs item inside `game_state.random_customs_item`.
  3. Preserve existing assignments instead of re-picking every turn.
  4. Propagate the assigned location/item metadata from `game_state` to `dev_b_output.dialogue_seed.challenge_context` so Developer A can generate challenge dialogue from intent metadata, not fixed B-authored question text.
- `ResponseBuilder.build_unreal_response()` updated to persist and return `game_state` in the final `UnrealResponse`.
- Added unit tests in `backend/tests/dev_b/test_challenge_assignment.py` to cover TSL assignment ranges, deterministic seeded RNG, pool fallbacks, and Pydantic mapper.
- Updated `backend/tests/test_preprototype_flow.py` assertions to verify both location assignment at `FLIGHT_999_COMPLETE` and customs-item assignment plus A payload `challenge_context` at `IMM_999_CLEARED`.

Verification:

- `uv run pytest` passed: 302 passed, 1 warning.
- `uv run ruff check .` passed.
- `uv run mypy .` passed.
- Latest focused check: `uv run pytest backend/tests/test_preprototype_flow.py::test_orchestrator_marks_flight_wrap_up_as_arrival_cutscene_transition backend/tests/test_preprototype_flow.py::test_orchestrator_marks_immigration_clearance_as_baggage_scene_transition backend/tests/test_preprototype_flow.py::test_orchestrator_passes_random_customs_item_and_routes_customs_npc_to_developer_a backend/tests/dev_b/test_challenge_assignment.py -q` passed: 10 passed, 1 warning.
- Latest static checks passed: `uv run ruff check .`; `uv run mypy backend/app/schemas/game_turn.py backend/app/tools/tool_c/developer_c_graph_tools.py`.

## 2026-06-17 Developer C Schema: Make do_not_generate_npc_text Optional and Filed B Change Request

Developer C resolved the validation issue with `do_not_generate_npc_text`.

Changed:

- `DialogueDirective` schema in `backend/app/schemas/game_turn.py` now defines `do_not_generate_npc_text: bool | None = None` for backward compatibility. This prevents validation crashes in tests and mock payloads.
- Added a formal Change Request in `docs/contracts/change_requests.md` asking Developer B to remove `do_not_generate_npc_text` from their policy prompts and implementation code.

Verification:

- `uv run pytest` passed.
- `uv run ruff check .` and `uv run mypy .` passed.

## 2026-06-17 Developer A: Ruff Cleanup + LLM Fallback Debug Logging + Smalltalk CR Status Sync

Developer A 는 handoff/change_requests 인벤토리 확인 후 다음 4가지 후속 작업을 완료했습니다.

Changed:

- **Ruff Unused Imports 청소 (CR-2026-06-16)**: `npc_dialogue_agent.py`, `tts_text_polisher_service.py` 의 unused import 제거. C 측에서 진단된 lint 차단 해소. full `uv run ruff check .` 그린.
- **LLM Fallback ValueError 디버그 로깅 및 해결**: `node_generate_dialogue_llm` 의 except 블록에 traceback 로깅을 추가하였습니다. 더불어 에러 원인인 ChatPromptTemplate의 f-string 중괄호 파싱 문제를 해결하기 위해, 템플릿 포맷 대신 SystemMessage와 HumanMessage 객체를 직접 생성하여 invoke하도록 수정 완료하였습니다.
- **Bad Ending end-to-end 회귀 청취 검증**: Immigration "fuck you" 시 bad_end 라우팅 + A 측 mirror 응답("This interview is over. Leave now.")이 정상 동작함을 확인 완료하였습니다.
- **CR-2026-06-16 기내 스몰토크 대화형 전환 Status 갱신**: A 측 작업이 06-17 에 완료되었음을 change_requests.md 에 명시.

Verification:

- `uv run pytest backend/tests`: PASS (300 passed)
- `uv run ruff check .`: PASS (All checks passed)
- `uv run mypy .`: PASS (Success: no issues found in 120 source files)
- `/respond-dialog` Immigration 회귀 청취: PASS

## 2026-06-17 Developer C Fixed: Respond Dialog Immigration NPC Default

Developer C updated the `/respond-dialog` browser tester so the immigration
chapter preset sends `npcId="OFFICER_HALE"` and displays `Officer Hale` instead
of the legacy `Officer Miller` fallback. Added a page regression assertion to
keep Miller from returning to the respond-dialog HTML.

Verification:

- `uv run pytest backend/tests/test_demo_ai_respond_page.py -q` passed: 8
  passed, 1 warning.
- `uv run ruff check .` passed.

## 2026-06-17 Developer C Integrated: Flight Smalltalk Diagnostic Slot Neutralization

Developer C reviewed Developer B's merged adaptive flight smalltalk diagnostic
handoff and completed the C-owned integration items.

Changed:

- `UnderstandingAgent` now treats
  `FLIGHT_A_001_SEATMATE_SMALLTALK` with
  `npc_question_goal="estimate_user_travel_speaking_level"` as a slot-neutral
  diagnostic node.
- Rule fallback no longer fills the legacy `polite_response` slot on that
  diagnostic node, even when the player says an old-script answer such as
  `"Sure, here you are."`.
- LLM postprocessing also removes diagnostic-node `slot_evidence`,
  `extracted_slots`, and `missing_slots` so A/B do not mistake the residual
  scenario slot for a live progression condition.
- Added an integration regression test proving repeated
  `FLIGHT_A_001_SEATMATE_SMALLTALK` turns append B OpenKB session records and
  allow the adaptive controller to reach `FLIGHT_999_COMPLETE` instead of
  being stuck at turn 1.

Verification:

- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py -q`
  passed: 51 passed, 1 warning.
- `uv run ruff check backend/app/agents/agent_c/understanding_agent.py backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py`
  passed.
- `uv run pytest` passed: 294 passed, 1 warning.
- `uv run mypy .` passed.
- `uv run ruff check .` passed.

## 2026-06-17 Developer C Integrated: Bad Ending Guard and Smalltalk Slot Safety

Developer C integrated Developer B's bad-ending branch output with the C-owned
orchestration validator and fixed one remaining Understanding guard issue from
CR-B-SMALLTALK.

Changed:

- `DeveloperCGraphTools.validate_dev_b_policy_tool()` now preserves normal
  `allowed_next_nodes` validation, but allows a `branch_type="bad_end"` target
  only when the target node is an actual `node_type="ending"` node with
  `SHOW_BAD_END_SCOREBOARD`.
- `TransitionContext.status` accepts both `chapter_complete` and
  `complete_chapter`, because B's bad-ending nodes use the latter for the same
  chapter-closing transition meaning.
- `response_builder` maps `SHOW_BAD_END_SCOREBOARD` to the Alpha scoreboard
  flow response.
- Rule-mode Understanding now uses the deterministic `visit_purpose`
  classifier only when the current node actually requires `visit_purpose`.
  This prevents travel-purpose-like free speech from passing the
  `FLIGHT_A_001_SEATMATE_SMALLTALK` `polite_response` node.
- Cleaned unused imports from C-owned test files that were reported by ruff.

Verification:

- `uv run pytest` passed: 296 passed, 1 warning.
- `uv run mypy .` passed.
- Focused ruff for touched C-owned/test files passed.
- Full `uv run ruff check .` is still blocked only by Developer A-owned unused
  imports in `backend/app/agents/agent_a/npc_dialogue_agent.py` and
  `backend/app/services/service_a/tts_text_polisher_service.py`. Developer C
  did not edit those A-owned implementation files; the existing change request
  remains the handoff path.

## 2026-06-16 Developer C Implemented: Incivility Signal and A Adapter Forward

Developer C completed the C-owned portion of Developer A's Bad Ending /
Profanity Mirror handoff:

- Added additive `IncivilityClassification` and optional
  `UnderstandingOutput.incivility`.
- Added `backend/app/services/service_c/incivility_classifier.py` as the
  deterministic Alpha classifier for tier 0-3 rude/insult/profanity/threat
  evidence.
- Attached incivility evidence after both rule and LLM Understanding paths.
- Forwarded top-level `incivility` from `DevANpcDialogueClient` to Developer A's
  level-design payload, with a safe tier 0 default for older mocks.
- Added compact `incivility` summaries to C Understanding traces and unified
  AgentRun output summaries.
- Documented the schema/adapter contract and marked CR-A1/CR-A3 with C
  implementation status. CR-A2 bad-ending branch policy and CR-A4 verbal-abuse
  scenario nodes remain Developer B-owned.

Verification:

- `uv run pytest` passed: 287 passed, 1 warning.
- Focused C-owned `uv run ruff check ...` passed for the sprint files.
- `uv run mypy .` passed.
- Full `uv run ruff check .` is still blocked by Developer A-owned unused import
  findings in `backend/app/agents/agent_a/npc_dialogue_agent.py` and
  `backend/app/services/service_a/tts_text_polisher_service.py`. Developer C did
  not edit those A-owned implementation files; a change request was added in
  `docs/contracts/change_requests.md`.

## 2026-06-16 Developer C Sprint Added: Incivility Signal and A Adapter Forward

Developer C reviewed Developer A's latest Bad Ending / Profanity Mirror handoff
and change requests. The C-owned work is now tracked as a sprint:

- `docs/sprints/2026-06-16-incivility-bad-ending-sprint.md`

Developer C scope:

- CR-A1: add additive `incivility` evidence to Understanding output.
- CR-A3: forward `incivility` to the A-facing payload in
  `dev_a_npc_dialogue_client.py`.
- Add C-owned rule classifier, settings, tests, AgentRun/summary visibility, and
  contract docs.

Out of C scope:

- CR-A2 bad-ending branch policy remains Developer B-owned.
- CR-A4 verbal-abuse scenario ending nodes remain Developer B-owned.
- Developer A profanity mirror response wording and TTS behavior remain
  Developer A-owned.

Recommended execution order:

1. INC-1/INC-2: schema + rule classifier.
2. INC-3/INC-4: settings + Understanding integration.
3. INC-5: A adapter forward.
4. INC-6/INC-7: observability + regression tests.
5. INC-8/INC-9: contract docs, full verification, commit.

## 2026-06-17 Developer B 억까 장소·수화물 레벨별 배정 작업계획 확정 및 변경요청 발행

Developer B는 입국심사 "억까 장소 리스트"와 세관 "억까 수화물 리스트"를 플레이어 진단
레벨(TSL)에 맞춰 난이도 구간별로 랜덤 배정하는 기능의 작업계획을 확정하고, 타 팀 의존
작업을 변경요청으로 발행했습니다. (구현은 후속 — 이번 항목은 계획·경계 확정 단계입니다.)

- **방향 확정 (1번 안)**: 배정을 (가) 픽 규칙 / (나) 픽 실행·영속화로 분리. **(가)는
  Dev B**(밸런스 단일 소스, 순수함수 + 유닛 테스트), **(나)는 Dev C/A/Unreal**. 픽 규칙을
  코드 밖(CSV/문서)으로 빼는 2번 안은 TSL 경계가 B·C 두 곳에 중복돼 밸런스 붕괴 위험이
  있어 배제.
- **핵심 매핑**: 억까 난이도 1~12 = 루브릭 total 0~12 동일 척도. 기존
  `tier_difficulty_controller.travel_speaking_level_for_total` 의 TSL 경계
  (0-3/4-6/7-9/10+)를 그대로 난이도 구간(1-3/4-6/7-9/10-12)으로 재사용 →
  `TSL_TO_DIFFICULTY_RANGE` 단일 맵.
- **배선 지점(확정)**: 장소는 `FLIGHT_999_COMPLETE`(입국심사 **전**), 수화물은
  `IMM_999_CLEARED`(`ENTER_BAGGAGE_CLAIM`, BAG_006 **전**) 전환 노드에서 배정. 호출
  주체는 C 런타임.
- **발견사항**:
  - 데이터 갭 — 억까 장소 리스트에 **난이도 3 항목 없음**(수화물은 1~12 전 구간 분포).
    TSL_1 구간 장소 풀은 난이도 1·2만 → 픽 함수 빈 풀 인접 구간 폴백으로 흡수.
  - A 경계 — B 고정 질문은 `_A_BLOCKED_*` 로 차단되므로 억까 사유(`suspicion_reason`)는
    `dialogue_seed` 메타로만 A 전달 가능.
- **산출물**: 작업계획서 `docs/workplan-dev-b.md` 를 본 건으로 교체(이전 기내 스몰토크
  계획은 통합 완료되어 교체). 신설 예정 자산 — `backend/app/data/challenge_tables.py`,
  `backend/app/services/service_b/challenge_assignment_service.py`,
  `backend/tests/dev_b/test_challenge_assignment.py`.
- **교차 의존 (변경 요청)**: Dev C/A/Unreal 작업을
  `docs/contracts/change_requests.md`(**[CR-B-EOKKKA] 억까 장소·수화물 레벨별 배정**)로
  발행.
  - Dev C: `game_turn.py` 스키마 확장(`RandomCustomsItemContext` +difficulty/suspicion_reason,
    `GameState` +assigned_visit_location 계열, `DialogueSeed` 억까 컨텍스트) + 전환 노드에서
    B 픽 함수 호출 + GameState 영속화 + Unreal 전달.
  - Dev A: `suspicion_reason` 의도대로 NPC 트집 대사 생성(고정 질문 모방 금지), 입국신고서
    장소와 동일 지칭 유지.
  - Unreal: 입국신고서 장소 표시, BAG_006 수화물 reveal.
- **검증/후속**: 이번 단계는 문서(계획·CR·handoff) 동기화. 구현 착수 시 B 단독 범위
  (테이블+픽 서비스+유닛 테스트)부터 진행하며 C 스키마와 디커플링.

## 2026-06-17 Developer A 기내 스몰토크 적응형 진단(Adaptive Diagnostic) 연동 구현 완료

Developer A는 [CR-B-SMALLTALK] 변경 요청에 맞춰 기내 스몰토크 단일 self-loop 진단 노드 `FLIGHT_A_001_SEATMATE_SMALLTALK` 및 `smalltalk_diagnostic` 진단 모드에 대응하는 NPC 대사 생성 및 가드 제어 구현을 완료했습니다.

- **프롬프트 템플릿 개정**:
  - [npc_dialogue_prompt.md](file:///c:/5th_project/pj05_Murphy/backend/app/prompts/npc_dialogue_prompt.md) 및 [npc_dialogue_prompt.short.md](file:///c:/5th_project/pj05_Murphy/backend/app/prompts/npc_dialogue_prompt.short.md)에 진단 전용 Jinja2 조건 블록을 추가했습니다.
  - `{competency}_{topic}` 의도 태그 발화 금지, 자연스러운 반응-연결 구조 강제, 길이 미러링(`length_target`), 화제 전환 pivot(`topic_switch`) 적용 및 대화 메모리(`discussed_topics`, `past_player_utterances`)를 통한 중복 방지 규칙을 명시했습니다.
  - 흐름 일관성 검증을 위해 `llm_reason`에 `[COHERENT]` / `[NON-SEQUITUR]` 태그 지시를 주었습니다.
- **LLM 클라이언트 및 페이로드 연동**:
  - [npc_llm_client.py](file:///c:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_llm_client.py)에 대화 메모리 리스트 포맷팅을 추가했습니다.
  - [npc_dialogue_agent.py](file:///c:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py)에서 OpenKB 세션 이력을 로드하여 다룬 화제 및 발화 내역을 `llm_payload`에 주입했습니다.
- **가드 우회 및 Coherence Guard 구현**:
  - [npc_dialogue_agent.py](file:///c:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py)에서 진단 모드일 때 `missing_followup_question` 검사를 우회하여 반응 전용(reaction-only) 턴을 허용했습니다.
  - 반응 없는 맨 질문 및 비연결 턴(llm_reason의 태그 기반)을 reject하는 Coherence Guard를 신설했습니다.
  - `topic_switch=True`일 때 전환구가 없을 시 후처리로 자동 주입되도록 안전 보정 장치를 적용했습니다.
- **질문 합성 스킵 및 중립 폴백 구축**:
  - [npc_dialogue_agent.py](file:///c:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py)에서 진단 모드 시 `synthesize_fallback_next_question`을 스킵해 고정 질문 합성을 비활성화했습니다.
  - [developer_a_fallback_service.py](file:///c:/5th_project/pj05_Murphy/backend/app/services/service_a/developer_a_fallback_service.py)에서 에러 발생 시 고정 사다리로 회귀하지 않고 **generic 중립 응답 목록**에서 랜덤으로 선택하여 대사를 생성하도록 폴백을 보완하고 피드백을 중립형으로 설정했습니다.
- **검증 완료**:
  - [test_developer_a_npc_dialogue.py](file:///c:/5th_project/pj05_Murphy/backend/tests/test_developer_a_npc_dialogue.py)에 5종의 신규 테스트를 추가하였으며, `uv run pytest backend/tests` 명령 결과 283개 전체 테스트의 성공 통과를 완료했습니다.

## 2026-06-17 Developer B 기내 스몰토크 적응형 진단(Adaptive Diagnostic, C안) 통합 및 테스트 갱신 완료

Developer B는 기내 스몰토크를 적응형 진단(C안)으로 전환하는 작업계획에 맞춰 외부 연동 테스트 및 잔여 노드 정리에 따른 테스트 오작동 문제를 해결하고 전체 검증을 완료했습니다.

- **외부 연동 테스트 갱신 및 검증**:
  - [test_preprototype_flow.py](file:///c:/potenup3/pj05_Murphy/backend/tests/test_preprototype_flow.py)에서 `test_orchestrator_marks_flight_wrap_up_as_arrival_cutscene_transition` 테스트를 단일 self-loop 진단 노드 `FLIGHT_A_001_SEATMATE_SMALLTALK` 및 OpenKB 세션 이력 모킹 기반으로 갱신하여, 최소 턴 및 신뢰도 조건을 통과하고 `FLIGHT_999_COMPLETE`로 자연스럽게 종결되는지 검증했습니다.
  - `test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata` 테스트에서 허용 가능한 다음 노드 목록(`allowed_next_nodes`), dialogue directive의 `purpose`("smalltalk_diagnostic"), dialogue seed의 `surface_goal`("travel_purpose_travel") 검증을 갱신하였습니다.
  - `fake_voice_output_builder`에 `"travel_purpose_travel"`을 추가하여 테스트 대화 텍스트가 기대 사항과 맞도록 조정했습니다.
- **Developer A 유닛 테스트 갱신**:
  - [test_developer_a_npc_dialogue.py](file:///c:/potenup3/pj05_Murphy/backend/tests/test_developer_a_npc_dialogue.py)에서 삭제된 레거시 비행 노드(`FLIGHT_A_005_WRAP_UP`, `FLIGHT_B_002_COMPANION_OR_VISIT`, `FLIGHT_C_004_HOTEL_HOSTEL`)를 가리키고 있던 `node_id` 값들을 대표 진단 노드인 `FLIGHT_A_001_SEATMATE_SMALLTALK`로 갱신하여 테스트 실패를 차단했습니다.
- **폴백 대사 연동 배제**:
  - 에이전트 A가 정책 엔진이 제안한 폴백 질문(seed_text)을 그대로 모방하여 출력하는 의존성 오작동을 차단하기 위해, B 정책 클래스(`FlightSmallTalkDiagnosticPolicy`) 내의 `fallback_question` 메서드 및 관련 유닛 테스트를 완전히 제거하였습니다.
- **검증 완료**:
  - `uv run pytest` 실행 결과 278개 전체 테스트 성공 통과를 확인했습니다.
- **핵심 구조 변경 요약 (A/C 인지 필요)**:
  - 시나리오: `FLIGHT_A_*/B_*/C_*` 15개 노드 제거 → 단일 self-loop 진단 노드
    `FLIGHT_A_001_SEATMATE_SMALLTALK`. 역할 반전 원인이던 `npc_question_goal` 을
    `estimate_user_travel_speaking_level` 로 교정. 종료 시 `FLIGHT_999_COMPLETE`.
  - 신규 probe 뱅크 `backend/app/data/flight_smalltalk_probes.json`(역량·난이도·토픽 태깅).
  - 컨트롤러 `FlightSmallTalkDiagnosticPolicy.decide_conversational`: 기회주의적 probe
    선택(steering=0.4) + bounded 종료(`MIN_TURNS=3`, `MAX_TURNS=7`, `CONFIDENCE_THRESHOLD=0.7`).
  - 계약 필드(additive): `DialogueDirective.topic_switch/length_target`,
    `DialogueSeed/LevelHint.cumulative_confidence`, `ScenarioDecision.selected_probe/cumulative_confidence`.
  - `dialogue_seed.surface_goal` 은 진단 씬에서 **의도 문자열 `{competency}_{topic}`**(예:
    `travel_purpose_travel`)로 바뀜 — 고정 질문 아님.
- **교차 의존 (변경 요청)**: Dev A/Dev C 작업을
  `docs/contracts/change_requests.md`(**[CR-B-SMALLTALK] 기내 스몰토크 적응형 진단 전환**)로 발행.
  - Dev A: 반응-먼저 생성 + **coherence guard 신설** + `missing_followup_question` 해제 +
    고정 큐 비활성 + `length_target` 길이 미러링 + `topic_switch` 전환구 + 대화 메모리/콜백.
    **폴백 대사 없음** — 고정 질문 사다리로 회귀 금지, 실패 시 반복되지 않는 generic 중립 폴백.
  - Dev C: 스몰토크 슬롯 강제 추출 완화 + **OpenKB 세션 레코드 턴별 적재 보장**(미적재 시
    턴이 1로 고정되어 종료 불가 위험 — CR 통합 의존성 항목 참조).
  - `ruff check .` 및 `mypy .` 실행 시 어떠한 Lint/Type 검출 사항도 남지 않고 깨끗하게 통과함을 확인했습니다.

## 2026-06-16 Developer B 욕설 처리 및 Bad Ending 분기 정책 완료 (CR-A2, CR-A4)

Developer B는 플레이어의 비속어 발화 시 챕터 강제 강등 및 배드 엔딩 분기 연동을 위한 작업(CR-A2, CR-A4)을 완료했습니다.

### 주요 수정/산출물:

- **시나리오 노드 3종 추가 (CR-A4)**:
  - [scenario_nodes.json](file:///c:/potenup3/pj05_Murphy/backend/app/data/scenario_nodes.json)에 비속어 누적으로 인한 배드 엔딩용 노드 3종(`FLIGHT_BAD_END_VERBAL_ABUSE`, `IMM_BAD_END_VERBAL_ABUSE`, `BAG_BAD_END_VERBAL_ABUSE`)을 `node_type = "ending"` 및 `ALPHA_999_FINAL_SCOREBOARD` 전송 트랜지션 구조로 추가.
- **비속어 배드 엔딩 정책 구현 (CR-A2)**:
  - [bad_ending_policy.py](file:///c:/potenup3/pj05_Murphy/backend/app/services/service_b/bad_ending_policy.py) 신설: `branch_type="bad_end"`, `verdict="FAIL"`, `verbal_abuse` 피드백 태그, `verbal_conduct_card` 형태 초점 카드를 주입하는 `build_bad_ending_output` 구현.
  - [focus_on_form_cards.json](file:///c:/potenup3/pj05_Murphy/backend/app/kb/dev_b/focus_on_form_cards.json)에 비속어 주의를 주는 `verbal_conduct_card` 추가.
  - [english_level_hint_agent.py](file:///c:/potenup3/pj05_Murphy/backend/app/agents/agent_b/english_level_hint_agent.py): `evaluate_turn` 진입 시 `payload.understanding.incivility`를 확인하여 즉각적 T3 혹은 누적 T2 비속어 감지 시 배드 엔딩으로 조기 반환 처리. OpenKB 세션 로그 및 `_test_incivility_t2_streak`로 연속 욕설 상태 추적.
  - [openkb_feedback_writer.py](file:///c:/potenup3/pj05_Murphy/backend/app/services/service_b/openkb_feedback_writer.py): 턴별 피드백 저장 시 `payload.understanding` 정보를 통째로 로깅하여 다음 턴에서 연속 T2 비속어 판단을 가능케 함.
  - [final_result_score_policy.py](file:///c:/potenup3/pj05_Murphy/backend/app/services/service_b/final_result_score_policy.py): 최종 성적표 빌드 시 `verbal_abuse` 피드백 태그가 존재하면 `"COMIC_FAIL"` 추천 결과와 `"verbal_abuse"` 사유 코드를 부여하도록 개선.
- **테스트 및 검증**:
  - [test_dev_b_bad_ending_branch.py](file:///c:/potenup3/pj05_Murphy/backend/tests/dev_b/test_dev_b_bad_ending_branch.py) 신설: T3 욕설 조기종료, T2 1회 시 정상 진행, T2 연속 2회 시 조기종료 및 성적표 `"COMIC_FAIL"` 검증. Pydantic v2 dynamic field 우회를 위한 `MockUnderstandingOutput` 및 `MockDevBPolicyInput` 구현.
  - [test_scenario_nodes_bad_ending.py](file:///c:/potenup3/pj05_Murphy/backend/tests/dev_b/test_scenario_nodes_bad_ending.py) 신설: 3종 배드 엔딩 노드의 트랜지션 필드 존재 및 형상 준수 검증.
  - [test_developer_b_policy_engine.py](file:///c:/potenup3/pj05_Murphy/backend/tests/dev_b/test_developer_b_policy_engine.py): 신규 노드 등록 및 터미널 `ending` 노드에 대한 브랜치 후보 검증을 격리 조치.
  - 검증 완료: `uv run pytest` (279 passed), `ruff check`, `mypy` 모두 결함 없음 통과.

## 2026-06-16 Developer B 기내 스몰토크 적응형 진단(Adaptive Diagnostic, C안) 전환

Developer B는 기내 스몰토크가 "취조처럼" 느껴지고 플레이어의 답을 무시한 채 다음 질문만 이어가는 문제(및 펜 대여 시 NPC가 `"Sure, here you are."`로 역할이 반전되는 버그)의 근본 원인을, **출입국용 채점 상태 머신 재사용 + 15개 고정 노드(A/B/C × 5턴) 일렬 스크립트 + player 관점 `npc_question_goal`이 `surface_goal`로 흘러 NPC를 응답자로 오인시키는 구조**로 진단하고, 이를 **적응형 진단(C안)**으로 전환하는 계획서를 작성했다.

- 변경/산출물:
  - `docs/workplan-dev-b.md` 를 **C안(적응형 진단)** 으로 전면 교체 — 단일 self-loop 진단 노드 + probe 뱅크(역량·난이도·토픽 태깅) + 결정적 컨트롤러(기회주의적 probe 선택 + bounded 종료: 최소·최대 턴 + 신뢰도) + **자연스러움 3중 보증**(구조 제약 / coherence guard / eval 측정) + `steering` 노브(B안은 steering=0의 극단값).
  - 직전 "재미·라포 우선(절충, 사실상 B안)" 계획의 토대(중립 진행 ADVANCE·페널티 0·안전선·out-game 적립)는 유지하고 위 요소를 추가해 격상.
  - Dev B 소유 작업: `scenario_nodes.json`(노드 정리·역할 반전 교정), 신규 `flight_smalltalk_probes.json`, `flight_smalltalk_diagnostic_policy.py`(적응형 선택·종료), `developer_b_policy_graph_tools.py`(배선·seed emit), `english_level_hint_agent.py`(능력 추정치+신뢰도 노출·in-game 억제).
- 교차 의존: Dev A/Dev C 변경 요청을 `docs/contracts/change_requests.md`(**Change Request - 2026-06-16 - [CR-B-SMALLTALK] 기내 스몰토크 적응형 진단 전환**)로 발행. 핵심은 Dev A의 **반응-먼저 대사 생성 + coherence guard 신설 + `missing_followup_question` 해제 + 고정 큐 비활성** 과 Dev C의 **슬롯 추출 완화**. 노드 ID(`FLIGHT_A_001_SEATMATE_SMALLTALK`)는 유지하므로 데모(`respond-dialog`)는 무영향.
- 검증/후속: 본 항목은 계획·계약 문서 작성 단계(코드 미구현). 구현 시 §9 검증 명령(`uv run pytest backend/tests/dev_b/...`, `ruff`, `mypy`) 및 §8 테스트(probe 선택·bounded 종료·steering=0 추종·안전선 회귀·자연스러움 eval) 수행 예정.

## 2026-06-16 Developer C Realtime Transcript Multipart Fallback Fix

Developer C investigated the Unreal log where realtime STT subtitles showed the
player's speech, but the legacy recording path still judged the WAV as too
short and the backend handled the turn as if it only had fallback/short audio.

Root cause:

- The realtime STT WebSocket path can produce a valid final transcript before
  the normal `/api/game/ai/respond` call.
- If Unreal sends the normal `/respond` call as multipart and places that final
  text inside `turn.audio.transcript`, the previous C multipart parser validated
  `turn.audio` as plain audio metadata and lost the extra transcript field.
- After that loss, C saw only the attached WAV bytes. In mock/local batch STT
  paths this could fall back to the WAV-derived/default transcript instead of
  the realtime final transcript.

Changed:

- `backend/app/api/ai_respond.py` now copies `turn.audio.transcript` and
  `turn.audio.transcript_provider` into the internal `MockAudioInput` before
  validating `UnrealTurnRequest`.
- When a multipart request carries both a too-short WAV and a realtime final
  transcript, the transcript wins and batch WAV STT is skipped.
- Added regression coverage in `backend/tests/test_preprototype_flow.py`.

Unreal alignment note:

- In realtime STT mode, Unreal should treat `final_transcript` as the source of
  truth for the AI turn. The legacy WAV-duration guard may still be useful for
  non-realtime uploads, but it should not trigger "too short answer" fallback
  dialogue once a committed realtime final transcript exists.
- Recommended payload for multipart compatibility: keep the WAV attachment if
  needed for capture/debug, but include `turn.audio.transcript` and
  `turn.audio.transcript_provider="elevenlabs_relay"` in the turn JSON.
- Recommended payload for pure realtime flow: send JSON with top-level
  `audio.transcript` and `audio.transcript_provider`, matching the existing
  `/respond-dialog` demo page.

Verification:

- `uv run pytest backend/tests/test_preprototype_flow.py::test_api_prefers_realtime_transcript_embedded_in_multipart_turn_audio -q`
  passed after failing before the fix.
- `uv run pytest backend/tests/test_preprototype_flow.py::test_api_reports_realtime_transcript_provider_as_stt_runtime backend/tests/test_preprototype_flow.py::test_api_accepts_multipart_turn_json_and_sample_wav backend/tests/test_preprototype_flow.py::test_api_prefers_realtime_transcript_embedded_in_multipart_turn_audio backend/tests/test_stt_service.py -q`
  passed.

## 2026-06-16 Developer C Realtime STT Client Disconnect Handling

Developer C fixed a WebSocket noise/error case seen while testing
`/api/game/ai/stt/stream`.

Root cause:

- The client closed the WebSocket first, with uvicorn reporting
  `ConnectionClosedOK` and Starlette raising `WebSocketDisconnect`.
- The backend then tried to send a realtime STT server event to the already
  closed socket, so uvicorn logged `Exception in ASGI application` even though
  the client-side close itself was not an ElevenLabs provider failure.
- A second close path can happen even earlier: the client opens the WebSocket
  and closes it before sending the first JSON message. In that case Starlette
  raises a `RuntimeError` from `receive_json()` with
  `WebSocket is not connected. Need to call "accept" first.`

Changed:

- `backend/app/api/ai_respond.py` now treats `WebSocketDisconnect` during
  realtime server-event sends as a normal client disconnect.
- `_send_realtime_event()` and `_send_realtime_events()` now return `False`
  when the client has already closed, which prevents the noisy ASGI stack trace
  and stops sending the rest of the event batch.
- `realtime_stt_stream()` now also treats Starlette's receive-after-disconnect
  RuntimeError as a normal client disconnect while still re-raising unrelated
  RuntimeErrors.
- Added regression coverage in `backend/tests/test_realtime_stt_websocket.py`.

Verification:

- RED: the new disconnect test failed before the fix with
  `starlette.websockets.WebSocketDisconnect` escaping from
  `_send_realtime_event()`.
- RED: the receive-side disconnect test failed before the fix with
  `RuntimeError: WebSocket is not connected. Need to call "accept" first.`
- `uv run pytest backend/tests/test_realtime_stt_websocket.py
backend/tests/test_elevenlabs_realtime_stt_relay.py -q`: PASS, 16 passed,
  1 existing `audioop` deprecation warning.
- `uv run pytest`: PASS, 261 passed, 1 existing `audioop` deprecation warning.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS.

## 2026-06-16 Developer A Request: Bad Ending End-to-End 연동을 위한 B/C 협조 요청

Developer A는 `MURPHY_NPC_PROFANITY_MIRROR_MODE` 기반의 Profanity Mirror/Firm 모드를 이미 구현 완료(`incivility_tier` 수신부, `profanity_response_policy`, `profanity_lexicon`, `_apply_incivility_bias` 등)했으나, **신호를 만드는 쪽(C Understanding), 어댑터 전달(C Adapter), 분기 정책(B Policy), 시나리오 데이터(B Scenario)** 가 모두 비어 있어 다음 두 가지 증상이 관찰됩니다.

- 플레이어가 `"fuck you"` 류 T3 욕설을 발화해도 NPC가 평이한 정상 응답(`"Sure, go ahead. Are you traveling to New York?"`) 으로 받음.
- A-facing payload 에 `incivility` 키가 없어 항상 `incivility_tier = 0` 으로 평가됨.

원인 검증:

- `.env` / `.env.example` 에 `MURPHY_NPC_PROFANITY_MIRROR_MODE` 키 미정의 → 기본 `"off"`.
- `grep -rn "incivility" backend/app/services/service_c backend/app/agents/agent_c backend/app/integrations backend/app/schemas backend/app/graphs backend/app/services/service_b` → 0 hits. Understanding/B/C 어댑터 모두 미구현.

따라서 본 핸드오프는 **A 측 구현 완료를 알리고, 동시에 B/C 측에 4건의 Change Request(CR-A1~CR-A4)를 발행** 합니다. CR 본문은 `docs/contracts/change_requests.md`, 각 owner를 위한 작업 가이드는 다음 두 문서로 분리되었습니다:

- `docs/contracts/developer_b_bad_ending_codex_prompt.md` — B owner 작업 지침 (CR-A2, CR-A4)
- `docs/contracts/developer_c_incivility_codex_prompt.md` — C owner 작업 지침 (CR-A1, CR-A3)

진행 순서 권장: **CR-A1 (Understanding 분류) → CR-A3 (C 어댑터 forward) → CR-A2 (B 분기 정책) → CR-A4 (시나리오 노드)**.

A 측 임시 우회(QA 한정):

- `.env` 에 `MURPHY_NPC_PROFANITY_MIRROR_MODE=mirror` 추가.
- 추가로 `MURPHY_NPC_DEV_FORCE_INCIVILITY_TIER=2` 같은 dev override 환경변수를 도입하면 payload 에 incivility 가 없을 때 A 단독 룰베이스 분류 또는 강제 tier 주입으로 mirror 응답을 즉시 청취 가능. 다만 bad ending 트리거는 B 분기 권한이라 본 우회로는 동작하지 않음.

본 작업의 A 측 책임 범위 명시:

- A는 payload.incivility 신호 수신·발화 표현·TTS 파라미터 조정·NPC 종결 대사만 책임.
- 욕설 분류 권한은 C, 분기·점수·bad ending 트리거 권한은 B. A는 신호 수신 후 표현만 담당.

## 2026-06-16 Developer A Implementation: 프롬프트 고도화 + 비-텍스트 표현 (Flash v2.5) + Profanity Mirror 모드 완료

Developer A는 `docs/workplan-dev-a-prompt-and-profanity-mirror.md` 계획서를 기준으로 프롬프트 계층화, 비-텍스트 표현(SSML 및 palette) 처리 인프라 구축, Profanity Mirror/Firm 모드 통합 작업을 완료했습니다.

### 주요 수정/산출물:

- **Phase A - 프롬프트 외부화 및 9계층 구조화**:
  - [npc_dialogue_prompt.md](file:///C:/5th_project/pj05_Murphy/backend/app/prompts/npc_dialogue_prompt.md) (기본 프롬프트) 및 [npc_dialogue_prompt.short.md](file:///C:/5th_project/pj05_Murphy/backend/app/prompts/npc_dialogue_prompt.short.md) (Gemma/로컬용 축약본) 신설.
  - [npc_dialogue_few_shots.md](file:///C:/5th_project/pj05_Murphy/backend/app/prompts/npc_dialogue_few_shots.md) (SUCCESS / RETRY / PROFANITY MIRROR 예시) 신설.
  - [npc_llm_client.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_llm_client.py) 를 리팩토링하여 외부 마크다운 프롬프트 파일을 Jinja2로 동적 렌더링하고 few-shot 마크다운을 결합하도록 수정했습니다.

- **Phase B - Flash v2.5 비-텍스트 표현 인프라**:
  - [non_verbal_palette.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/non_verbal_palette.py) 신설하여 NPC별 의성어/침묵 팔레트 정의.
  - [npc_roster_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/npc_roster_service.py)를 확장하여 `NPCProfile`에 `non_verbal_palette` 필드를 추가하고 Roster 정보에 등록했습니다.
  - [tts_text_polisher_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/tts_text_polisher_service.py)를 보강하여 룰베이스 경로에서도 감정에 맞는 비구어 표현 자동 삽입 기능 및 LLM 출력의 SSML `<break>` 시간 유효성 검증/클램프(0.0~3.0s) 헬퍼를 추가했습니다.
  - [schemas.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/schemas.py)에서 `tts_text` 의 `max_length`를 256으로 확장하고, Pydantic field_validator를 통해 `<script>` 등의 위험 태그 차단 로직을 추가했습니다.

- **Phase C - Profanity Mirror/Firm 모드**:
  - [.env.example](file:///C:/5th_project/pj05_Murphy/.env.example) 에 `MURPHY_NPC_PROFANITY_MIRROR_MODE` 및 `MURPHY_NPC_PROFANITY_MIRROR_MAX_INTENSITY` 환경 변수 설명 및 기본값 추가.
  - [change_requests.md](file:///C:/5th_project/pj05_Murphy/docs/contracts/change_requests.md) 에 신규 Change Request (CR-1, CR-2, CR-3) 등록.
  - [profanity_lexicon.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/profanity_lexicon.py) 신설하여 항상 금지되는 욕설(`ALWAYS_BLOCKED`) 및 모드별 비속어 허용 목록 정의 및 검출 함수 구현.
  - [profanity_response_policy.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/profanity_response_policy.py) 신설하여 tier X mode 대응 매트릭스에 따른 룰베이스 응답 및 TTS bias 조율 정책 매핑.
  - [npc_dialogue_agent.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py)에서 `node_initialize_state` 시점에 욕설 룰베이스 폴백 매핑 및 `node_generate_dialogue_llm` 에서 욕설 차단 후처리 검증(감지 시 `profanity_lexicon_violation` 폴백 강제)을 구현했습니다.

- **Phase D - TTS 파라미터 incivility 연동**:
  - [voice_output_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/voice_output_service.py)의 `_build_provider_request` (ElevenLabs 분기) 내에서 LLM이 명시적으로 음성 파라미터를 결정하지 않았을 때 `incivility_tier`에 따른 stability, style, speed 오프셋(Bias)을 동적 보정하는 `_apply_incivility_bias` 로직을 추가했습니다.

- **Phase E - 테스트 구축 및 검증**:
  - [test_developer_a_prompt_rendering.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_prompt_rendering.py) (Jinja 템플릿 및 few-shot 결합 검증), [test_developer_a_non_verbal_expression.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_non_verbal_expression.py) (SSML 클램프 및 의성어 자동 삽입 검증), [test_developer_a_profanity_mirror.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_profanity_mirror.py) (Profanity Mirror 매트릭스 및 금지어 차단 검증) 단위 테스트 파일 3개를 신설했습니다.
  - [test_developer_a_npc_roster.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_npc_roster.py) 내 Roster 기대 단언문을 최신 Roster 규격에 맞게 갱신했습니다.
  - `uv run pytest backend` 실행 결과 272개 전체 테스트 성공 통과를 완료했습니다.

## 2026-06-16 Developer B Implementation: 기내 스몰토크 대화형 모드 전환 완료

Developer B는 기내 스몰토크 씬이 출입국 심사용 채점형 상태 머신을 재사용하여 취조처럼 작동하던 문제를 해결하기 위해, 대화형 모드(패널티 0, in-game 피드백 비노출, 느슨한 주제 힌트) 전환 구현을 완료했습니다.

- 변경/산출물:
  - [flight_smalltalk_diagnostic_policy.py](file:///c:/potenup3/pj05_Murphy/backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py): `decide_conversational` 메서드 신설 및 입국 위험 안전 가드라인 배선.
  - [developer_b_policy_graph_tools.py](file:///c:/potenup3/pj05_Murphy/backend/app/tools/tool_b/developer_b_policy_graph_tools.py): `decide_scenario_branch_tool` 내 기내 스몰토크 씬 판정 라우팅 추가.
  - [english_level_hint_agent.py](file:///c:/potenup3/pj05_Murphy/backend/app/agents/agent_b/english_level_hint_agent.py): `evaluate_turn` (절차형 폴백), `_build_in_game_feedback` (in-game 노출 차단), `_build_error_capture` (in-game 수집 차단), `_allowed_followup_intents` (반응/자기개방/질문 의도 활성화), `_build_dialogue_directive` (purpose="smalltalk_rapport") 구현.
- 교차 의존:
  - Dev A/Dev C 변경 요청 `## Change Request - 2026-06-16 - 기내 스몰토크 대화형 전환 (Flight Smalltalk Conversational Mode)`을 통해 후속 연동 작업 협조 확인.
- 검증/후속:
  - [test_flight_smalltalk_diagnostic_policy.py](file:///c:/potenup3/pj05_Murphy/backend/tests/dev_b/test_flight_smalltalk_diagnostic_policy.py)에 대화형 판정, 오프토픽 무시, 패널티 0, 리스크 감지 가드 유닛 테스트 추가 완료.
  - `uv run pytest` (261 passed), `ruff check`, `mypy` 검증 완료.

## 2026-06-16 Developer B Plan: 기내 스몰토크 대화형 전환 작업계획 및 교차 변경요청

Developer B는 기내(옆자리 승객) 스몰토크가 출입국 심사용 채점형 상태 머신을
재사용해 "취조"처럼 느껴지는 문제(같은 질문 반복, 자연 대화감 부재, 매 턴 교정
노출, 다음 질문 진행에만 집중)에 대해 **재미·라포 우선(절충)** 방향의
작업계획서를 작성했다.

- `docs/workplan-dev-b.md`를 "기내 스몰토크 대화형 전환" 계획으로 교체(이전
  슬롯 값 검증 계획은 구현 완료되어 대체). 계획서 §10에 "작업계획서가 교체되어도
  유지하는 handoff/change_request 문서 틀"을 추가.
- 핵심(Dev B 소유): 기내 씬을 `ScenarioStateMachine` 채점 분기에서 분리한다 —
  `FlightSmallTalkDiagnosticPolicy.decide_conversational` 신설 +
  `decide_scenario_branch_tool` 라우팅, pass/fail·페널티 미적립, in-game 교정
  억제 → out-game 시드 적립, `dialogue_seed.surface_goal`을 느슨한 주제 힌트로.
  중립 진행은 `branch_type` enum 미확장으로 `success`+`ADVANCE` 재사용 +
  `branch_reason="flight_smalltalk_continue"` 신호.
- 교차 의존: Dev A(스몰토크 페르소나 프롬프트, 매 턴 질문 강제 해제,
  `SURFACE_GOAL_QUESTIONS` 고정 큐 비활성, 교정 라인 제거, 발화 기반 후속,
  대화 메모리)와 Dev C(슬롯 강제추출 완화, off-topic 가드 씬 인지화)에 대한
  변경 요청을 `docs/contracts/change_requests.md`
  (2026-06-16 기내 스몰토크 대화형 전환)로 전달.
- 구현/검증은 후속(작업계획서 §7 테스트 계획, §8 검증 명령 참조). 회귀 가드:
  입국심사(IMM*\*)·수하물(BAG*\*) 채점 동작은 그대로 유지.

## 2026-06-16 Developer A 구현: NPC별 voice_id 라우팅 및 환경변수(Environment Variable) 오버라이드 정정 (Phase A ~ Phase E)

Developer A는 `docs/workplan-dev-a-npc-voice-routing.md` 작업 계획서에 따라 ElevenLabs 및 Edge TTS 경로 모두에서 NPC별 고유 voice_id 라우팅을 복구하고, 환경변수 우선순위가 뒤바뀌는 결함 및 캐시 키(Cache Key) 충돌 문제를 해결했습니다.

### Phase A - voice_profile_service 리팩터링:

- **프로바이더 매개변수(Parameter)화**: `voice_profile_service.py`의 `resolve_voice_profile` 함수에 `tts_provider` 인자를 추가하여, 활성화된 TTS 엔진에 맞춰 적절한 목소리를 선택하도록 개선했습니다.
- **NPC별 ElevenLabs 라우팅 복구**: roster에 정의되어 있던 `NPCProfile.elevenlabs_voice_id`가 ElevenLabs 요청 시 실제로 사용되도록 연동하여 죽은 필드(Dead field) 문제를 해결했습니다.
- **캐시(Cache) 격리**: 동일한 NPC라도 엔진별로 오디오 캐시 파일이 충돌 없이 격리될 수 있도록, 생성되는 `voice_profile_id`에 `tts_provider` 정보를 결합(`{user_id}:{npc_id}:{provider}`)했습니다.

### Phase B - voice_output_service 라우팅 구조 수정:

- **호출 순서 조정**: `voice_output_service.py`의 `build_voice_output_from_level_design` 내에서 `resolve_voice_profile`을 호출하기 전에 먼저 `tts_provider_name`을 결정 및 결정된 엔진 정보를 인가하도록 수정했습니다.
- **우선순위 역전 해결 헬퍼(Helper) 신설**: NPC별 고유 목소리가 최우선으로 적용될 수 있도록 `_per_npc_voice_or_override` 헬퍼 함수를 신설하여 **강제 오버라이드 환경변수(\*\_FORCE) > NPC 고유 목소리 > 레거시 단일 오버라이드 환경변수(경고 로깅) > 최종 기본값** 순의 엄격한 우선순위를 확립했습니다.
- **하위 호환성 유지**: 레거시 환경변수(`MURPHY_ELEVENLABS_VOICE_ID` 및 `MURPHY_EDGE_TTS_VOICE`)가 감지될 경우 `logger.warning`으로 경고(Warning)를 출력한 뒤 차선책으로 적용하도록 설정했습니다.

### Phase C - 캐시 키 및 메타데이터(Metadata) 정합성 검증:

- **오디오 캐시 고유성**: `build_audio_cache_key`에 voice 식별자 문자열이 정상적으로 유입되고 있음을 검증했습니다.
- **모델 버전 정보 확장**: `_provider_cache_model_version` 함수의 ElevenLabs 처리 분기 내에 `voice` 식별자가 포함되도록 수정하여 목소리가 바뀔 때 캐시 파일이 고유하게 분리되도록 보장했습니다.

### Phase D - 검증 및 회귀 테스트(Regression Test) 구축:

- **신규 단위 테스트(Unit Test) 추가**: `backend/tests/test_developer_a_voice_profile_routing.py` 파일을 생성하여 NPC별 라우팅 결과, fallback 처리 규칙, 헬퍼 함수의 우선순위 분기 규칙을 검증했습니다.
- **기존 테스트 업데이트**: `test_developer_a_npc_roster.py` 및 `test_developer_a_agent_run_logging.py`에서 새로운 `voice_profile_id` 포맷과 모의 환경변수 환경에 맞도록 테스트 단언(Assertion)문을 보정했습니다.
- **테스트 통과 결과**:
  - `uv run pytest backend/tests/test_developer_a_voice_profile_routing.py` -> PASS (4 Passed)
  - `uv run pytest backend/tests/test_developer_a_npc_roster.py` -> PASS (6 Passed)
  - `uv run pytest backend/tests/test_developer_a_agent_run_logging.py` -> PASS (15 Passed)
  - `uv run ruff check .` -> PASS (전체 통과)
  - `uv run mypy .` -> PASS (오류 없음)

### Phase E - 문서 정리 및 환경 명세 최신화:

- **환경변수 예시 갱신**: `.env.example` 파일에서 옛날 단일 목소리 오버라이드 변수들을 비활성화(Deprecated 주석 처리)하고, 신규 강제 오버라이드 변수인 `*_FORCE` 환경변수 지침을 명시했습니다.
- **구조 설계도 최신화**: `docs/agent_a_structure.md` 파일 내의 Mermaid 시퀀스(Sequence) 및 전체 아키텍처 다이어그램에서 `resolve_voice_profile(tts_provider)`에 매개변수가 주입되는 설계 흐름을 최신 상태로 반영했습니다.

## 2026-06-16 Developer C Realtime STT Model Metadata Fix

Developer C fixed the AI-to-Unreal STT metadata for the realtime transcript
path.

Root cause:

- `/respond` correctly copied `audio.transcript_provider = "elevenlabs_relay"`
  into `stt.runtime_used`, but `WhisperLargeV3TurboSttService` still populated
  `stt_model` from the fixed local batch model label
  `whisper-large-v3-turbo`.
- `NormalizedInput.stt_model` was typed as a literal Whisper-only value, so the
  contract could not represent ElevenLabs realtime model ids.

Changed:

- `backend/app/schemas/game_turn.py` now allows `NormalizedInput.stt_model` to
  be any string model label.
- `backend/app/services/service_c/stt_service.py` now reports
  `settings.elevenlabs_realtime_stt_model` when `runtime_used` is
  `elevenlabs_relay`.
- `backend/tests/test_stt_service.py` and
  `backend/tests/test_preprototype_flow.py` now assert that realtime transcript
  turns return `stt.model` and `debug.stt_model` as `scribe_v2_realtime`.
- Updated Developer C schema/adapter contracts to describe the realtime model
  label behavior.

## 2026-06-16 Developer A Implementation: Chapter Boundary, Emotion Enum & Dynamic TTS Parameter Integration (Phase P2 & Phase P3)

Developer A implemented Phase P2 and Phase P3 from `docs/workplan-dev-a.md` to support chapter transitions, emotion-based voice parameter tuning, emotion-to-animation mapping, and clean up deprecated middleware code.

### Phase P2-1 - Chapter Boundary & Closing Utterances:

- **Payload Normalization**: Added `"transition"` and `"next_action"` fields to the standardized payload in `developer_a_input_service.py`.
- **Role-Specific Fallback Closing Lines**: Updated `build_text_fallback` in `developer_a_fallback_service.py` to check for `complete_chapter` status or `COMPLETE_CHAPTER` next_action. When triggered, it serves role-specific closing lines (e.g., seatmate: `"Enjoy your trip!"`, immigration: `"All right, you're cleared."`) and dynamically resolves speaker names from the resolved NPC profile.
- **LLM System Prompt Alignment**: Enhanced the `_developer_instructions` in `npc_llm_client.py` to guide the LLM to write only closing statements and omit follow-up questions when a chapter completion is signaled.
- **Agent Initialization Alignment**: Updated `node_initialize_state` in `npc_dialogue_agent.py` to skip question fallback synthesis if the turn indicates chapter completion.

### Phase P2-2 - Emotion Enum & Dynamic Animation/TTS Parameters:

- **Emotion Priority**: Sorted the emotion priority in `node_generate_dialogue_llm` so B-provided `npc.emotion` (standardized `npc_emotion` in the payload) is prioritized over LLM-inferred emotions.
- **Animation Mapping Service**: Created `animation_mapping_service.py` to map the 13 supported emotion types to specific Unreal Engine animation micro-variants (e.g. `joy`, `panic`, `sad`, `suspicion`, etc.), integrating it into `npc_dialogue_agent.py`.
- **Emotion-Based TTS Parameter Fallback**: Added the `EMOTION_TTS_PARAMETERS` dictionary in `voice_output_service.py` containing preset voice tuning values (stability, style, speed, similarity_boost) for the 13 emotions. If the LLM doesn't output custom values, the service falls back to these emotion presets first before defaulting to tone-based presets.

### Phase P3 - Code Hygiene & Cleanup:

- **Middleware Cleanup**: Completely deleted the deprecated `npc_dialogue_agent_run_middleware.py` file since all calling paths have migrated to the new `NPCDialogueAgentRunRecorder` standard.
- **Integration Test Alignment**: Updated the assertion in Developer C's integration test `test_preprototype_flow.py` for Hale's chapter completion to expect the correct dynamic response `"All right, you're cleared."` instead of the legacy generic fallback.

### Verification:

- Added 3 new unit tests in `test_developer_a_npc_dialogue.py` covering chapter completion fallback lines, emotion-animation mapping, and emotion-based TTS parameter resolution.
- Executed `uv run pytest backend/tests` -> PASS (All 253 tests passed).
- Executed `uv run ruff check .` -> PASS (All checks passed).
- Executed `uv run mypy .` -> PASS (Success: no issues found in 108 source files).

## 2026-06-16 Developer A Implementation: Resolve Dialogue Agent Quality Defects & NPC Roster Expansion (Phase P0 & P1-1)

Developer A implemented Phase P0 and Phase P1-1 from the `docs/workplan-dev-a.md` workplan to fix dialogue generation quality issues and expand the NPC Roster mapping.

### Phase P0 - Dialogue Agent Quality Defects Resolved:

- **System Prompt Improvements**: Updated [npc_llm_client.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_llm_client.py) to strongly instruct the LLM against player speaker confusion, to never copy the recommended expression verbatim, and to always produce follow-up questions when `dialogue_seed.surface_goal` is present.
- **Dialogue Seed Injection**: Ensured that the `dialogue_seed` metadata is correctly mapped in `developer_a_input_service.py` and forwarded in `npc_dialogue_agent.py` to the LLM.
- **Fallback Next Question Synthesizer**: Added a map of `SURFACE_GOAL_QUESTIONS` and a `synthesize_fallback_next_question` helper in [dialogue_policy_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/dialogue_policy_service.py). This synthesizes fallback dialogue and next questions when the LLM fails while `use_llm` is enabled.
- **Output Validation**: Added validation in [npc_dialogue_agent.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py) to check for recommended expression echo (`recommended_expression_echo` fallback) and missing follow-up questions (`missing_followup_question` fallback) when `surface_goal` is present.
- **Regression Tests**: Added unit tests in [test_developer_a_npc_dialogue.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_npc_dialogue.py) covering next question synthesis, expression echo rejection, and missing follow-up question rejection.

### Phase P1-1 - NPC Roster & Voice Profile Mapping Expansion:

- **New NPC Profile (Emily)**: Added a new seatmate NPC `emily` (for Chapter C Travel Form Help) to [npc_roster_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/npc_roster_service.py) with friendly/helpful persona instruction.
- **Non-canonical Mapping Alignment**: Strengthened `_normalize_npc_id` to prevent falling back to Hale when non-canonical IDs (`SEATMATE_A_01`, `SEATMATE_B_01`, `SEATMATE_C_01`, `SEATMATE_EMILY`, `BAGGAGE_STAFF`, `CUSTOMS_OFFICER`) are passed, routing them correctly to `arabella`, `novak`, `emily`, `brielle`, and `dan`.
- **Voice Profile Registration**: Configured `emily`'s Edge-TTS voice mapping in [voice_profile_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/voice_profile_service.py).
- **Roster Unit Test**: Added new test cases in [test_developer_a_npc_roster.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_npc_roster.py) to verify registration and non-canonical ID resolution.

### Code Hygiene:

- Removed unused `polish_tts_text` import in [npc_dialogue_agent.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py), resolving a Ruff F401 lint warning.

### Verification:

- Executed `uv run pytest backend/tests` -> PASS (All 245 tests passed).
- Executed `uv run ruff check .` -> PASS (All checks passed).
- Executed `uv run mypy .` -> PASS (Success: no issues found in 108 source files).

## 2026-06-15 Developer C Refactor: Fix graph.py Redundant Reassignment and Resolve test_preprototype_flow.py Failures

Developer C resolved the lint warnings in `graph.py` and fixed the pre-prototype flow test failures caused by the recent Developer A refactoring.

Changed:

- **Resolved `graph.py` Lint Warning**: Added an explicit `__all__` list in [graph.py](file:///C:/5th_project/pj05_Murphy/backend/app/graphs/graph.py) to declare `DEVELOPER_C_GRAPH_NODE_NAMES` as a public export. This resolves the Ruff F401 unused import warning while keeping it accessible to external test suites.
- **Fixed `test_preprototype_flow.py` Assertions**: Updated the two forward test suites (`test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata` and `test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata`) to match the new Developer A client behavior. Assertions were updated to expect `npc_recast_line_candidate is None` and an output text of `"Okay."`.
- **Entire Test Suite Green**: Executed `uv run pytest backend/tests` to verify that all 240 tests pass successfully.

## 2026-06-15 Developer C Refactor: Fix graph.py Redundant Reassignment and Resolve test_preprototype_flow.py Failures

Developer C resolved the lint warnings in `graph.py` and fixed the pre-prototype flow test failures caused by the recent Developer A refactoring.

Changed:

- **Resolved `graph.py` Lint Warning**: Added an explicit `__all__` list in [graph.py](file:///C:/5th_project/pj05_Murphy/backend/app/graphs/graph.py) to declare `DEVELOPER_C_GRAPH_NODE_NAMES` as a public export. This resolves the Ruff F401 unused import warning while keeping it accessible to external test suites.
- **Fixed `test_preprototype_flow.py` Assertions**: Updated the two forward test suites (`test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata` and `test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata`) to match the new Developer A client behavior. Assertions were updated to expect `npc_recast_line_candidate is None` and an output text of `"Okay."`.
- **Entire Test Suite Green**: Executed `uv run pytest backend/tests` to verify that all 240 tests pass successfully.

## 2026-06-16 Developer A Implementation: Chapter Boundary, Emotion Enum & Dynamic TTS Parameter Integration (Phase P2 & Phase P3)

Developer A implemented Phase P2 and Phase P3 from `docs/workplan-dev-a.md` to support chapter transitions, emotion-based voice parameter tuning, emotion-to-animation mapping, and clean up deprecated middleware code.

### Phase P2-1 - Chapter Boundary & Closing Utterances:

- **Payload Normalization**: Added `"transition"` and `"next_action"` fields to the standardized payload in `developer_a_input_service.py`.
- **Role-Specific Fallback Closing Lines**: Updated `build_text_fallback` in `developer_a_fallback_service.py` to check for `complete_chapter` status or `COMPLETE_CHAPTER` next_action. When triggered, it serves role-specific closing lines (e.g., seatmate: `"Enjoy your trip!"`, immigration: `"All right, you're cleared."`) and dynamically resolves speaker names from the resolved NPC profile.
- **LLM System Prompt Alignment**: Enhanced the `_developer_instructions` in `npc_llm_client.py` to guide the LLM to write only closing statements and omit follow-up questions when a chapter completion is signaled.
- **Agent Initialization Alignment**: Updated `node_initialize_state` in `npc_dialogue_agent.py` to skip question fallback synthesis if the turn indicates chapter completion.

### Phase P2-2 - Emotion Enum & Dynamic Animation/TTS Parameters:

- **Emotion Priority**: Sorted the emotion priority in `node_generate_dialogue_llm` so B-provided `npc.emotion` (standardized `npc_emotion` in the payload) is prioritized over LLM-inferred emotions.
- **Animation Mapping Service**: Created `animation_mapping_service.py` to map the 13 supported emotion types to specific Unreal Engine animation micro-variants (e.g. `joy`, `panic`, `sad`, `suspicion`, etc.), integrating it into `npc_dialogue_agent.py`.
- **Emotion-Based TTS Parameter Fallback**: Added the `EMOTION_TTS_PARAMETERS` dictionary in `voice_output_service.py` containing preset voice tuning values (stability, style, speed, similarity_boost) for the 13 emotions. If the LLM doesn't output custom values, the service falls back to these emotion presets first before defaulting to tone-based presets.

### Phase P3 - Code Hygiene & Cleanup:

- **Middleware Cleanup**: Completely deleted the deprecated `npc_dialogue_agent_run_middleware.py` file since all calling paths have migrated to the new `NPCDialogueAgentRunRecorder` standard.
- **Integration Test Alignment**: Updated the assertion in Developer C's integration test `test_preprototype_flow.py` for Hale's chapter completion to expect the correct dynamic response `"All right, you're cleared."` instead of the legacy generic fallback.

### Verification:

- Added 3 new unit tests in `test_developer_a_npc_dialogue.py` covering chapter completion fallback lines, emotion-animation mapping, and emotion-based TTS parameter resolution.
- Executed `uv run pytest backend/tests` -> PASS (All 253 tests passed).
- Executed `uv run ruff check .` -> PASS (All checks passed).
- Executed `uv run mypy .` -> PASS (Success: no issues found in 108 source files).

## 2026-06-16 Developer A Implementation: Resolve Dialogue Agent Quality Defects & NPC Roster Expansion (Phase P0 & P1-1)

Developer A implemented Phase P0 and Phase P1-1 from the `docs/workplan-dev-a.md` workplan to fix dialogue generation quality issues and expand the NPC Roster mapping.

### Phase P0 - Dialogue Agent Quality Defects Resolved:

- **System Prompt Improvements**: Updated [npc_llm_client.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_llm_client.py) to strongly instruct the LLM against player speaker confusion, to never copy the recommended expression verbatim, and to always produce follow-up questions when `dialogue_seed.surface_goal` is present.
- **Dialogue Seed Injection**: Ensured that the `dialogue_seed` metadata is correctly mapped in `developer_a_input_service.py` and forwarded in `npc_dialogue_agent.py` to the LLM.
- **Fallback Next Question Synthesizer**: Added a map of `SURFACE_GOAL_QUESTIONS` and a `synthesize_fallback_next_question` helper in [dialogue_policy_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/dialogue_policy_service.py). This synthesizes fallback dialogue and next questions when the LLM fails while `use_llm` is enabled.
- **Output Validation**: Added validation in [npc_dialogue_agent.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py) to check for recommended expression echo (`recommended_expression_echo` fallback) and missing follow-up questions (`missing_followup_question` fallback) when `surface_goal` is present.
- **Regression Tests**: Added unit tests in [test_developer_a_npc_dialogue.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_npc_dialogue.py) covering next question synthesis, expression echo rejection, and missing follow-up question rejection.

### Phase P1-1 - NPC Roster & Voice Profile Mapping Expansion:

- **New NPC Profile (Emily)**: Added a new seatmate NPC `emily` (for Chapter C Travel Form Help) to [npc_roster_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/npc_roster_service.py) with friendly/helpful persona instruction.
- **Non-canonical Mapping Alignment**: Strengthened `_normalize_npc_id` to prevent falling back to Hale when non-canonical IDs (`SEATMATE_A_01`, `SEATMATE_B_01`, `SEATMATE_C_01`, `SEATMATE_EMILY`, `BAGGAGE_STAFF`, `CUSTOMS_OFFICER`) are passed, routing them correctly to `arabella`, `novak`, `emily`, `brielle`, and `dan`.
- **Voice Profile Registration**: Configured `emily`'s Edge-TTS voice mapping in [voice_profile_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/voice_profile_service.py).
- **Roster Unit Test**: Added new test cases in [test_developer_a_npc_roster.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_npc_roster.py) to verify registration and non-canonical ID resolution.

### Code Hygiene:

- Removed unused `polish_tts_text` import in [npc_dialogue_agent.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py), resolving a Ruff F401 lint warning.

### Verification:

- Executed `uv run pytest backend/tests` -> PASS (All 245 tests passed).
- Executed `uv run ruff check .` -> PASS (All checks passed).
- Executed `uv run mypy .` -> PASS (Success: no issues found in 108 source files).

## 2026-06-15 Developer C Refactor: Fix graph.py Redundant Reassignment and Resolve test_preprototype_flow.py Failures

Developer C resolved the lint warnings in `graph.py` and fixed the pre-prototype flow test failures caused by the recent Developer A refactoring.

Changed:

- **Resolved `graph.py` Lint Warning**: Added an explicit `__all__` list in [graph.py](file:///C:/5th_project/pj05_Murphy/backend/app/graphs/graph.py) to declare `DEVELOPER_C_GRAPH_NODE_NAMES` as a public export. This resolves the Ruff F401 unused import warning while keeping it accessible to external test suites.
- **Fixed `test_preprototype_flow.py` Assertions**: Updated the two forward test suites (`test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata` and `test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata`) to match the new Developer A client behavior. Assertions were updated to expect `npc_recast_line_candidate is None` and an output text of `"Okay."`.
- **Entire Test Suite Green**: Executed `uv run pytest backend/tests` to verify that all 240 tests pass successfully.

## 2026-06-15 Developer C Refactor: Fix graph.py Redundant Reassignment and Resolve test_preprototype_flow.py Failures

Developer C resolved the lint warnings in `graph.py` and fixed the pre-prototype flow test failures caused by the recent Developer A refactoring.

Changed:

- **Resolved `graph.py` Lint Warning**: Added an explicit `__all__` list in [graph.py](file:///C:/5th_project/pj05_Murphy/backend/app/graphs/graph.py) to declare `DEVELOPER_C_GRAPH_NODE_NAMES` as a public export. This resolves the Ruff F401 unused import warning while keeping it accessible to external test suites.
- **Fixed `test_preprototype_flow.py` Assertions**: Updated the two forward test suites (`test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata` and `test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata`) to match the new Developer A client behavior. Assertions were updated to expect `npc_recast_line_candidate is None` and an output text of `"Okay."`.
- **Entire Test Suite Green**: Executed `uv run pytest backend/tests` to verify that all 240 tests pass successfully.

## 2026-06-16 Developer C Test and Env Example Cleanup Audit

Developer C audited the current tests after the latest merge for obvious
legacy-retention cases.

Findings:

- No test file was deleted in this pass. Current tests no longer assert Kokoro
  or Chatterbox output paths, and no test imports the deprecated
  `NPCDialogueAgentRunMiddleware` shim.
- The remaining `generate_npc_dialogue_from_level_design` tests still cover the
  current Developer A entry point used by `voice_output_service.py`, so they
  were not removed.
- The B-side legacy route test checks that old unlabeled Flight node IDs are no
  longer present in `scenario_nodes.json`; that is an active regression guard,
  not legacy retention.
- `test_demo_ai_respond_page.py` still covers the current `/respond-dialog`
  tester and demo AgentRun summary endpoints. The older `/demo/ai-respond`
  route is still present in `backend/app/main.py`, so those assertions were left
  intact rather than silently deleting coverage for a still-mounted route.

Changed:

- Updated `.env.example` so `MURPHY_TTS_PROVIDER=edge`.
- Removed unused `MURPHY_CHATTERBOX_*` examples from `.env.example`; current
  runtime code no longer reads these variables after the A-side TTS slimming
  refactor.
- Updated the NPC dialogue mode comment so it refers to the selected TTS
  provider instead of Kokoro.

Verification:

- `rg -n "MURPHY_CHATTERBOX|chatterbox|kokoro|Kokoro|MURPHY_TTS_PROVIDER=kokoro" .env.example backend/tests`:
  no matches.
- `uv run pytest`: PASS, 243 passed, 1 existing `audioop` deprecation warning.
- `uv run mypy .`: PASS, no issues in 108 source files.
- `uv run ruff check .`: FAIL only in A-owned
  `backend/app/agents/agent_a/npc_dialogue_agent.py` because
  `polish_tts_text` is imported but unused. Developer C did not edit that
  A-owned implementation file.

## 2026-06-16 Developer C Understanding Off-Topic Guard

Developer C implemented the urgent Understanding Agent guard requested after
Developer B verified that B-side slot membership validation cannot catch
`"Okay, you're on."` when C already normalizes it to a valid enum value.

Changed:

- Added deterministic postprocessing in
  `backend/app/agents/agent_c/understanding_agent.py` so known off-topic idioms
  for the current required slot cannot remain as successful extracted slots.
- The verified failure case now returns `intent_success = false`,
  `answer_relevance = "off_topic"`, `missing_slots = ["polite_response"]`,
  `needs_clarification = true`, and confidence below `0.9`.
- Added a generic confidence guard: when the LLM fills a required slot but does
  not provide strong accepted `slot_evidence` for that slot, C keeps the slot
  value but lowers confidence below `0.9`.
- Tightened LLM developer instructions in
  `backend/app/agents/agent_c/understanding_llm_client.py` so the model must
  judge required-intent relevance before filling slots and must not assign
  0.9+ confidence to weak or idiomatic slot evidence.
- Added `backend/app/prompts/understanding_prompt.md` as the prompt-policy
  mirror listed in `AGENTS.md`; runtime instructions still live in
  `understanding_llm_client.py`.
- Added regression coverage in `backend/tests/test_understanding_agent.py` for
  both LLM mode and rule mode using `"Okay, you're on."`.

Developer A adapter check:

- Verified `dev_a_npc_dialogue_client.py` still forces
  `in_game_feedback.npc_recast_line_candidate = None`, but does not remove the
  metadata A needs to generate a next prompt.
- Strengthened `backend/tests/test_preprototype_flow.py` assertions to confirm
  `dialogue_directive.purpose = "continue_to_next_question"` and
  `dialogue_seed.allowed_followup_intents` retains `advance_to_next_prompt`
  while `npc_recast_line_candidate` remains `None`.

Verification:

- RED: the new Understanding tests failed before the fix because both LLM and
  rule paths treated `"Okay, you're on."` as successful `short_acknowledgement`.
- `uv run pytest backend/tests/test_understanding_agent.py
backend/tests/test_understanding_llm_client.py
backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata
backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata
backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_next_question_seed_without_generic_recast_in_llm_mode
-q`: PASS, 23 passed, 1 existing `audioop` deprecation warning.
- `uv run pytest backend/tests/test_understanding_agent.py
backend/tests/test_understanding_llm_client.py
backend/tests/test_preprototype_flow.py -q`: PASS, 50 passed, 1 existing
  `audioop` deprecation warning.
- `uv run pytest`: PASS, 243 passed, 1 existing `audioop` deprecation warning.
- `uv run ruff check backend/app/agents/agent_c/understanding_agent.py
backend/app/agents/agent_c/understanding_llm_client.py
backend/tests/test_understanding_agent.py
backend/tests/test_preprototype_flow.py`: PASS.
- `uv run mypy .`: PASS.
- `uv run ruff check .`: FAIL only in A-owned
  `backend/app/agents/agent_a/npc_dialogue_agent.py` because
  `polish_tts_text` is imported but unused. Developer C did not edit that
  A-owned implementation file.

## 2026-06-15 Respond Dialog Flight NPC Roster Alignment and STT Metadata Check

Corrected during `/respond-dialog` realtime testing:

- The AI-only `/respond-dialog` flight preset was using the synthetic Unreal
  integration ID `SEATMATE_A_01`.
- Developer A's current roster uses canonical IDs such as `arabella`, `novak`,
  `hale`, `harris`, `dan`, and `brielle`.
- Updated the flight preset to send `npc_id = "arabella"` and display speaker
  `Arabella`, matching Developer A's seatmate roster for the airplane cabin
  test.
- Removed the temporary Developer A change request because no A-side roster
  change is required for this AI-only backend test.

Also fixed a Developer C metadata issue:

- The realtime subtitle WebSocket can receive ElevenLabs relay final
  transcripts and now submits `audio.transcript_provider` to
  `POST /api/game/ai/respond`.
- `WhisperLargeV3TurboSttService.transcribe_wav()` still bypasses batch STT
  when `audio.transcript` already exists, but now reports the provider runtime
  such as `elevenlabs_relay` instead of the default `local` label.
- Legacy mock transcripts without `transcript_provider` still report `local`
  for backward compatibility.

Verification:

- RED check: the focused `/respond-dialog` page test failed while the HTML still
  contained `SEATMATE_A_01`.
- RED check: focused STT provider tests failed with `runtime_used = local`
  before the fix.
- `uv run pytest backend/tests/test_stt_service.py::test_stt_service_reports_realtime_transcript_provider_without_batch_stt backend/tests/test_preprototype_flow.py::test_api_reports_realtime_transcript_provider_as_stt_runtime backend/tests/test_demo_ai_respond_page.py::test_respond_dialog_page_is_served_without_changing_original_demo -q`:
  PASS, 3 passed, 1 existing `audioop` deprecation warning.
- `uv run pytest backend/tests/test_stt_service.py
backend/tests/test_preprototype_flow.py
backend/tests/test_demo_ai_respond_page.py -q`: PASS, 41 passed, 1 existing
  `audioop` deprecation warning.
- `uv run pytest`: PASS, 238 passed, 1 existing `audioop` deprecation warning.
- `uv run ruff check backend/app/schemas/game_turn.py
backend/app/services/service_c/stt_service.py backend/tests/test_stt_service.py
backend/tests/test_preprototype_flow.py
backend/tests/test_demo_ai_respond_page.py`: PASS.
- `uv run mypy .`: PASS, no issues in 108 source files.
- `uv run ruff check .`: FAIL only on A-owned
  `backend/app/agents/agent_a/npc_dialogue_agent.py:24` for unused import
  `polish_tts_text`; Developer C did not edit the A-owned file.
- `uv run pytest backend/tests/test_demo_ai_respond_page.py -q`: PASS, 8
  passed, 1 existing `audioop` deprecation warning.
- `git diff --check -- demo/respond-dialog/index.html
backend/tests/test_demo_ai_respond_page.py docs/handoff.md
docs/contracts/change_requests.md`: PASS with Git's normal CRLF
  working-copy warnings only.

## 2026-06-15 Developer C Test Cleanup for Developer A Legacy Removal

Developer C cleaned C-owned tests that were keeping Developer A legacy/shim
code alive during the Agent A refactor.

Changed:

- Removed direct test dependency on `OpenAICompatibleNPCDialogueChatModel` and
  the old manual fallback-wrapper style from
  `backend/tests/test_developer_a_npc_llm_client.py`; the file now only keeps
  the current factory fallback contract.
- Removed old `generate_npc_dialogue()` deterministic unit tests from
  `backend/tests/test_developer_a_npc_dialogue.py`.
- Updated AgentRun logging tests to use
  `NPCDialogueAgentRunRecorder` instead of deprecated
  `NPCDialogueAgentRunMiddleware`.
- Updated the markdown formatter fixture from the removed Kokoro tool name to
  the current Edge TTS tool name.
- Updated `test_preprototype_flow.py` so C-to-A adapter tests no longer expect
  `in_game_feedback.npc_recast_line_candidate` to carry the next NPC question.
  The tests now verify `dialogue_seed` metadata as the A-facing generation
  input and keep `npc_recast_line_candidate` as `None`.

Verification:

- Focused regression:
  `uv run pytest backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata backend/tests/test_preprototype_flow.py::test_dev_a_adapter_reports_speaker_mismatch_diagnostic backend/tests/test_preprototype_flow.py::test_orchestrator_passes_random_customs_item_and_routes_customs_npc_to_developer_a -q`
  passed, 29 passed, 1 warning.
- Full tests:
  `uv run pytest -q` passed, 236 passed, 1 warning.
- Changed-file lint:
  `uv run ruff check backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py backend/tests/test_preprototype_flow.py`
  passed.
- `uv run mypy .` passed, no issues in 108 source files.

Remaining A-owned implementation cleanup:

- `uv run ruff check .` still reports one A-owned unused import:
  `backend/app/agents/agent_a/npc_dialogue_agent.py` imports
  `polish_tts_text` but does not use it. Developer C did not edit that A-owned
  implementation file.

## 2026-06-15 Developer C Respond Dialog Realtime STT Subtitle Tester

Developer C updated the local C-owned `/respond-dialog` browser tester so a
solo developer can verify realtime STT subtitles from the existing WebSocket
path before the final transcript enters the normal `/respond` turn flow.

Changed:

- Added a realtime subtitle panel to `demo/respond-dialog/index.html`.
- When the browser Record button starts, the page now opens
  `/api/game/ai/stt/stream` with `provider = "elevenlabs_relay"`.
- Browser microphone chunks are resampled to 16 kHz PCM16 and sent as
  `audio_chunk` events.
- Partial/final transcript server events update the subtitle panel.
- A committed final transcript is copied into `turn.audio.transcript` and sent
  through the existing JSON `/api/game/ai/respond` path, avoiding a second local
  batch STT pass for the same turn.
- Next-turn state clears `turn.audio.transcript` so later WAV uploads do not
  accidentally reuse the previous realtime transcript.

Verification:

- RED:
  `uv run pytest backend/tests/test_demo_ai_respond_page.py::test_respond_dialog_page_is_served_without_changing_original_demo -q`
  failed because `realtimeSubtitleText` was not present.
- GREEN:
  same focused test passed, 1 passed, 1 warning.

## 2026-06-15 Developer C Result Out-Game Feedback Exposure

Developer C completed the pending C-owned response-surface work requested by
Developer B for Focus-on-Form out-game feedback.

Changed:

- Added optional `out_game_feedback` to `UnrealResultResponse`.
- Added `DevBPolicyClient.out_game_feedback_for_session(session_id)`, which
  calls B-owned `FocusOnFormReportPolicy.build_session_report(session_id)`.
- Updated `GET /api/game/ai/result/{session_id}` to return both B
  `final_result` and B `out_game_feedback` learning metadata.
- Documented the additive field in C schema and adapter contracts.
- Marked the relevant change request as implemented.

Authority boundary:

- `out_game_feedback` is final result UI learning-card metadata only.
- It must not affect branch, verdict, next node, state delta, or numeric score
  authority.

Verification:

- ALL GREEN: `uv run pytest backend/tests` passed (240 passed).
- Changed-file lint: `uv run ruff check` passed (except for the A-owned unused import).

## 2026-06-15 Developer B Docstring Update: Add Comprehensive Korean Docstrings to B-owned Core Components and Helper Functions

Developer B는 코드의 가독성 및 신규 진입 개발자의 진입 장벽을 낮추기 위해, Developer B 도메인 영역에 해당하는 모든 핵심 모듈 및 클래스, 메서드뿐만 아니라 **모든 내부 헬퍼 메서드 및 모듈 레벨 private 함수들**까지 한글 초보자용 docstring/주석을 추가했습니다.

구현 및 수정 내용:

- **에이전트 및 그래프 헬퍼 보강**: `backend/app/agents/agent_b` 폴더 내의 `__init__.py`, `english_level_hint_agent.py`, `feedback_hint_llm_client.py`, `policy_graph.py` 에 속한 모든 클래스, 주 메서드, 내부 헬퍼 함수에 한글 docstring 추가.
- **서비스 및 판정 정책 보강**: `backend/app/services/service_b` 폴더 내의 모든 모듈(`__init__.py`, `developer_b_agent_run_logger.py`, `feedback_hint_generator.py`, `final_result_score_policy.py`, `flight_smalltalk_diagnostic_policy.py`, `focus_on_form_report_policy.py`, `level_adaptation_controller.py`, `openkb_feedback_writer.py`, `scenario_state_machine.py`, `tier_difficulty_controller.py`)에 정의된 클래스 및 private/public 메서드 전원에 한글 docstring 및 동작 안내 주석 추가.
- **교차 검증 완료**: `uv run pytest`로 231개 전체 테스트 성공 통과를 확인하였고, `uv run ruff check .` 및 `uv run mypy .`를 에러 없이 완료했습니다.

## 2026-06-15 Developer A Refactor: Migrate Agent A to LangChain 1.0+ and LCEL

Developer A는 Agent A 영역의 NPC 대사 생성 에이전트 및 서비스들을 LangChain 1.0+ 규격과 LCEL(LangChain Expression Language, 랭체인 표현 언어)에 맞게 전면 리팩토링(Refactoring) 및 현대화하여 프레임워크 표준에 정렬했습니다.

구현 및 수정 내용:

- **Pydantic 스키마 정의**: [schemas.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/schemas.py)를 새로 정의하여 LLM 호출 결과를 안정적으로 유효성 검증(Validation) 및 구조화(Structuring)할 수 있는 `NPCDialogueLLMResult` 데이터 모델을 신설했습니다.
- **LCEL 체인(Chain) 도입 및 ChatModel 정형화**: [npc_llm_client.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_llm_client.py)의 자작 HTTP ChatModel 클래스 구조를 제거하고, LangChain 1.0+의 `ChatOpenAI.with_structured_output` 및 `.with_fallbacks`를 조립한 표준 선언형 LCEL 체인 생성을 적용했습니다.
- **상태 기계(StateGraph) config 정렬**: [npc_dialogue_agent.py](file:///C:/5th_project/pj05_Murphy/backend/app/agents/agent_a/npc_dialogue_agent.py) 내의 에이전트 상태 변경(State transition) 노드 함수에서 callbacks 키 전달을 제거하고, `RunnableConfig` (config)를 직접 인수로 받아 콜백 및 로거가 안전하게 하위 체인에 흐르도록 정형화했습니다.
- **기록기(Recorder) 분리 및 미들웨어 Shim화**: [agent_run_recorder.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/agent_run_recorder.py)를 신설해 이벤트 기록(Event recording)과 JSONL/Markdown 작성을 분리 이관했습니다. 기존의 [npc_dialogue_agent_run_middleware.py](file:///C:/5th_project/pj05_Murphy/backend/app/middleware/middleware_a/npc_dialogue_agent_run_middleware.py)는 경고(warnings)를 남기며 신규 `NPCDialogueAgentRunRecorder`를 대리 대리하는 Deprecated Shim 클래스로 대체하여 이전 C-side 연동 부의 호환성을 보존했습니다.
- **Candidate Text(대사 후보) 유입 금지 및 오류 강제**: B-side NPC Wording 제거 사양에 근거해, `npc_dialogue_agent.py`에서 `candidate_text`가 페이로드로 주입될 경우 조용히 폴백하는 대신 명시적으로 `ValueError` 에러를 던지고 로깅하도록 예외 필터링을 강화했습니다.
- **C-side 어댑터 연동 정형화**: [dev_a_npc_dialogue_client.py](file:///C:/5th_project/pj05_Murphy/backend/app/integrations/dev_a_npc_dialogue_client.py)에서 Agent A로 대사 생성 호출 시 B가 작성한 대사 후보군(`npc_recast_line_candidate`)을 `None`으로 무조건 덮어쓰도록 억제 처리하여 유입을 차단했습니다.
- **서비스 및 테스트 갱신**: [voice_output_service.py](file:///C:/5th_project/pj05_Murphy/backend/app/services/service_a/voice_output_service.py)에서 지연 임포트(Lazy Import) 방식을 제거하고 신규 `NPCDialogueAgentRunRecorder` 인스턴스를 직접 사용하게 하였습니다. [test_developer_a_npc_llm_client.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_developer_a_npc_llm_client.py)는 1.0+ 표준 invoke 모킹 테스트 및 구조화된 Mock 데이터 검증 로직으로 업데이트했습니다. `test_developer_a_npc_dialogue.py`, `test_developer_a_agent_run_logging.py`, `test_preprototype_flow.py` 테스트 내에서 `npc_recast_line_candidate`를 전송하거나 이에 의존하던 단언문들을 모두 새 규격(기본 룰 폴백 대사 `"Okay. Please continue."` 또는 `None` 반환)으로 정형화해 패스하도록 조치했습니다.

수정된 파일 목록:

- `backend/app/agents/agent_a/schemas.py` (신설)
- `backend/app/agents/agent_a/npc_llm_client.py`
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/services/service_a/agent_run_recorder.py` (신설)
- `backend/app/services/service_a/voice_output_service.py`
- `backend/app/services/service_a/tts_service.py`
- `backend/app/services/service_a/tts_provider_service.py`
- `backend/app/middleware/middleware_a/npc_dialogue_agent_run_middleware.py`
- `backend/app/integrations/dev_a_npc_dialogue_client.py`
- `backend/tests/test_developer_a_npc_llm_client.py`
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/test_developer_a_agent_run_logging.py`
- `backend/tests/test_preprototype_flow.py`

## 2026-06-15 Developer A & C Refactor: Standardize AgentMiddleware and Align Test Assertions

Developer A는 프로젝트 가상 환경 내 `langchain` 라이브러리가 제공하는 표준 에이전트 미들웨어 프레임워크 규격에 맞게 대사 생성 추적 미들웨어를 정식 리팩터링하였습니다. 추가로, NPC 리플레이스먼트 완료 후 누락되었던 테스트 코드 내 구형 NPC 단언문을 최신 사양으로 수정했습니다.

구현 및 수정 내용:

- **AgentMiddleware 표준화 리팩터링**: `NPCDialogueAgentRunMiddleware`가 `langchain.agents.middleware.AgentMiddleware`를 상속(Inheritance)하도록 수정하고, `@hook_config(can_jump_to=["end"])` 데코레이터를 적용한 `before_model` 및 `after_model` 표준 훅(Hook) 메서드를 선언하여 프레임워크 표준 동작을 만족시켰습니다. 기존 서비스와의 하위 호환성을 위해 수동 `start_run`, `record_event` 메서드들은 그대로 보존했습니다.
- **테스트 코드 단언문 갱신**: `test_developer_a_npc_dialogue.py` 내의 결정적 대사 생성 검증 단언문 중 이전 구형 NPC 명칭(`"Officer Miller"`)을 바라보던 구절을 신규 기본 NPC 명칭인 `"Hale"`로 갱신하여 테스트 실패를 해결했습니다.
- **타입 및 린트 안정화**: `mypy .` 및 `ruff check .`를 실행하여 린트 미사용 임포트 정리 및 정적 분석 경고들을 해소했습니다.

수정된 파일 목록:

- `backend/app/middleware/middleware_a/npc_dialogue_agent_run_middleware.py`
- `backend/tests/test_developer_a_npc_dialogue.py`

## 2026-06-15 Developer C LLM Understanding Smoke and Unreal Realtime STT Alignment Prompt

Developer C verified the Alpha Understanding path in real LLM mode and added a
copy-paste Codex prompt for the Unreal AI communication owner to align with the
current realtime STT WebSocket contract.

LLM smoke:

- Settings read from the local environment used
  `MURPHY_UNDERSTANDING_MODE=llm`, provider `openai`, configured model
  `gpt-5.4-mini`, and fallback mode `none`.
- Direct `UnderstandingAgent` smoke tests returned `trace_mode = "llm"` and
  `fallback_used = false`, so these were not rule-mode results.
- Covered Alpha nodes:
  `FLIGHT_A_001_SEATMATE_SMALLTALK`,
  `FLIGHT_B_002_COMPANION_OR_VISIT`,
  `BAG_002_PROVIDE_CLAIM_TAG`,
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`, and
  `BAG_007_CUSTOMS_CLEARANCE`.
- The baggage customs item case extracted
  `customs_item_explanation = "medicine"`,
  `item_identity = "red ginseng medicine"`, and
  `item_purpose = "for my health"` with no missing slots.
- The `FLIGHT_B_002_COMPANION_OR_VISIT` required slot is
  `travel_companion`; the smoke extracted `travel_companion = "friend"` with no
  missing slots. An earlier manual expected-slot label of
  `companion_or_visit` was only a smoke-script expectation typo.
- Token usage was reported by the LLM client per case. Estimated cost remained
  `0.0` because local pricing configuration for the configured model is not
  populated.

Realtime STT alignment prompt:

- Added
  `docs/contracts/unreal_realtime_stt_alignment_codex_prompt.md`.
- The prompt states that `WebSocket /api/game/ai/stt/stream` is additive and
  does not replace `POST /api/game/ai/respond`.
- Unreal should send `session_start`, then base64 PCM `audio_chunk` events with
  `provider = "elevenlabs_relay"`, and set `commit = true` on the final real
  audio chunk.
- Partial transcript events are subtitle UI only and must not call
  Understanding, Developer B, Developer A, or TTS.
- Final transcript events are committed candidates. Unreal then combines the
  final transcript with the full `dev_c_unreal_turn.v1` JSON and calls
  `POST /api/game/ai/respond`, currently through the JSON `audio.transcript`
  shortcut.
- The current implemented relay is
  `Unreal -> Developer C WebSocket -> ElevenLabs WSS -> Developer C -> Unreal`;
  ElevenLabs API keys stay server-side.

## 2026-06-15 Developer C Alpha Baggage Random Item Follow-up

Developer C implemented the next C-owned Alpha baggage follow-up: random
customs-item context can now travel through the C turn contracts, BAG customs
nodes use customs-officer A-facing NPC context, and deterministic Understanding
fallback recognizes common Alpha Flight/Baggage slot values.

Changed:

- Added `RandomCustomsItemContext` and optional
  `game_state.random_customs_item` to the Unreal turn schema.
- Forwarded `random_customs_item` through `DevBPolicyInput` and
  `DevADialogueInput`.
- Added `random_customs_item` to the Developer A level-design payload so A can
  generate BAG_006 dialogue about the same item Unreal revealed.
- Normalized A-facing BAG NPC context in the C adapter:
  `BAG_001` through `BAG_004` use `BAGGAGE_STAFF /
baggage_service_staff`; `BAG_005` through `BAG_007` use
  `CUSTOMS_OFFICER / customs_officer`.
- Extended deterministic Understanding fallback with slot/value keyword
  coverage for Alpha Flight small talk and Baggage/customs-hold slots. This is
  a rule/mock safety net; the LLM path still uses generic current-node
  `slot_evidence`.
- Added regression tests for natural Alpha fallback phrases and BAG_006 random
  customs-item pass-through.

Verification:

- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_rule_mode_recognizes_alpha_flight_and_baggage_slot_values backend/tests/test_preprototype_flow.py::test_orchestrator_passes_random_customs_item_and_routes_customs_npc_to_developer_a -q`:
  PASS, 2 passed, 1 warning.
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_developer_c_langgraph_orchestrator.py -q`:
  PASS, 47 passed, 1 warning.
- `uv run pytest`: PASS, 240 passed, 1 warning.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 106 source files.

## 2026-06-15 Developer C Beginner Docstring Pass

Developer C added beginner-friendly docstrings to current C-owned non-test
Python source files and recorded the ongoing convention in `AGENTS.md`.

Scope:

- Included Developer C app entrypoint, API, schemas, `agent_c`, `service_c`,
  C middleware, C graph/tools, A/B integration adapters, and the current
  realtime STT smoke script.
- Excluded test files, Developer A implementation paths, Developer B
  implementation paths, generated runtime files, and non-Python data files.

Rule going forward:

- When Developer C creates or substantially edits non-test Python source, add
  beginner-friendly docstrings that explain the file or callable's role in the
  backend flow and its ownership/authority boundary.

## 2026-06-15 Developer C Alpha Speaker Mismatch Diagnostics

Developer C completed the next C-owned item from the consolidated Alpha
follow-up: diagnostics when the requested NPC context and Developer A returned
speaker clearly do not match.

Changed:

- `DevADialogueOutput` now carries additive `diagnostics`.
- `DevANpcDialogueClient` emits `npc_speaker_mismatch` when A's speaker shares
  no useful identity token with the requested `npc_id`.
- `ResponseBuilder` copies Developer A diagnostics into
  `UnrealResponse.debug.diagnostics`.
- C AgentRun summaries now include Developer A diagnostics in the
  `dev_a_client.generate_dialogue` output summary.
- Updated C schema and adapter contracts to document that diagnostics are
  non-blocking warnings and not branch authority.

Verification:

- `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_reports_speaker_mismatch_diagnostic backend/tests/test_final_result_payload.py::test_response_builder_carries_dev_a_diagnostics_into_debug_payload -q`:
  PASS, 2 passed, 1 warning.

## 2026-06-15 Developer C Alpha A-Adapter Non-Immigration Seed Follow-up

Developer C updated the C-owned Developer A dialogue adapter so the A-facing
level-design payload now forwards Developer B's optional `dialogue_seed`
metadata. This lets Developer A consume Alpha role and generation metadata for
Flight and Baggage chapters without C changing Developer A implementation files
or Developer B branch authority.

Ownership check:

- `backend/app/integrations/dev_a_npc_dialogue_client.py` is explicitly listed
  under Developer C owned files in `AGENTS.md`, even though its name references
  Developer A. It is the C-owned integration adapter that calls Developer A's
  contract boundary.
- No current Alpha A-adapter follow-up changes modify Developer A
  implementation paths such as `backend/app/agents/agent_a/`,
  `backend/app/services/service_a/`, `backend/app/tools/tool_a/`,
  `backend/app/middleware/middleware_a/`, or
  `backend/app/prompts/npc_dialogue_prompt.md`.

Changed:

- `backend/app/integrations/dev_a_npc_dialogue_client.py` now includes
  `dialogue_seed` in the payload passed to Developer A's voice output builder.
- `backend/tests/test_preprototype_flow.py` adds regression coverage for
  `FLIGHT_A_001_SEATMATE_SMALLTALK -> FLIGHT_A_002_TRAVEL_PURPOSE` and
  `BAG_001_REPORT_MISSING_AT_DESK -> BAG_002_PROVIDE_CLAIM_TAG` so the A-facing
  payload preserves `npc_id`, `npc_role`, `chapter_id`, next-question seed text,
  and `dialogue_seed` metadata.
- `docs/contracts/developer_c_adapter_contracts.md` documents the forwarded
  `dialogue_seed` field and current Edge audio path naming.
- `pyproject.toml` excludes `backend/runtime/generated` from pytest and mypy
  discovery so generated runtime artifacts do not break full-suite verification.

Verification:

- `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata -q`:
  PASS, 2 passed, 1 warning.

## 2026-06-15 Developer C Realtime STT Smoke Commit Follow-up

Developer C fixed the solo ElevenLabs realtime STT smoke path after live smoke
testing showed partial transcripts arrived, but committed provider finals could
be missed before the local fallback ran.

Ownership check:

- Backend relay, settings, and tests are Developer C owned.
- `scripts/smoke_elevenlabs_realtime_stt_relay.py` is a Developer C realtime
  STT smoke utility by responsibility, but `scripts/` is not yet explicitly
  listed in `AGENTS.md`. Developer C recorded a contract clarification request
  so future agents do not treat this path as ambiguous.

Root cause:

- `scripts/smoke_elevenlabs_realtime_stt_relay.py` committed a separate
  silence-only sentinel chunk instead of committing the final real audio chunk.
- The backend relay reused the short partial-drain timeout for committed final
  transcripts, so ElevenLabs could emit useful partials but miss the final
  before fallback.

Changed:

- `scripts/smoke_elevenlabs_realtime_stt_relay.py` now builds audio chunk
  events with `commit = true` on the final real WAV chunk.
- Added `scripts/__init__.py` so tests and mypy resolve the smoke script under
  one module name.
- `backend/app/services/service_c/elevenlabs_realtime_stt_relay.py` now uses a
  separate commit-final drain timeout and stops draining as soon as a final
  transcript is received.
- Added `ELEVENLABS_REALTIME_COMMIT_TIMEOUT_S`, default `3.0`, to
  `backend/app/services/service_c/settings_service.py` and `.env.example`.
- Updated C-owned schema and adapter contracts to document final-real-chunk
  commit semantics and the commit timeout.
- Added regression tests for the smoke script chunk builder and the longer
  commit-final wait.

Verification:

- `uv run pytest backend/tests/test_elevenlabs_realtime_stt_relay.py backend/tests/test_realtime_stt_websocket.py backend/tests/test_settings_service.py backend/tests/test_smoke_elevenlabs_realtime_stt_relay_script.py -q`:
  PASS, 17 passed, 1 warning.
- Live smoke with `backend/runtime/generated/stt_smoke_tour_16k_mono.wav`:
  PASS. The backend returned `final_transcript` from `provider =
"elevenlabs_relay"` with text `I'm here for tour- tourism.` and
  `target_endpoint = "POST /api/game/ai/respond"`.
- Debug AgentRun append: PASS. The realtime STT record ended with
  `status = "success"`, `final_provider = "elevenlabs_relay"`, token counts
  set to zero, estimated cost from configured per-minute rate, and audio
  metadata for 14 chunks / 107520 bytes.

## 2026-06-13 Developer C Refactor: Remove Deprecated Miller NPC, Update Default NPC to Hale & Apply TTS Slimming Test Updates

Developer C는 기획상 더 이상 사용되지 않는 레거시 입국심사관 NPC인 `miller`를 완전히 제거하고, 실제 챕터 0의 메인 입국심사관 NPC인 `hale`을 기본(Default) NPC로 변경하여 기획과의 정합성을 일치시켰습니다. 또한, Developer A의 로컬 온디바이스 TTS 제거(TTS Slimming) 계획에 따른 Developer C 소유의 통합 테스트 실패 지점을 해결했습니다.

구현 및 수정 내용:

- **로스터 정리**: `npc_roster_service.py`에서 폐기된 `miller` 캐릭터 정보를 삭제하고, `_DEFAULT_NPC_ID`를 `"hale"`로 수정했습니다.
- **하위 호환(Fallback) 기능 구현**: `_normalize_npc_id` 정규화 함수에 레거시 매핑 로직을 보강하여, 이전 규격인 `"miller"` 혹은 `"officer_miller"`를 참조해 통신을 시도해도 자동으로 `"hale"` 프로필로 변환하여 리턴하도록 처리했습니다.
- **음성 매핑 정리**: `voice_profile_service.py`에서 `miller` 음성 설정을 삭제했습니다.
- **유닛 및 통합 테스트 일괄 갱신**: `test_developer_a_npc_roster.py`, `test_developer_a_agent_run_logging.py`, `test_developer_a_npc_dialogue.py`, `test_developer_a_npc_emotion_escalation.py`, `test_developer_c_langgraph_orchestrator.py`, `test_final_result_payload.py`, `test_preprototype_flow.py`, `test_unified_agent_run_log.py` 내의 모든 `officer_miller` 혹은 `OFFICER_MILLER` 참조를 신규 디폴트인 `miller` ➡️ `hale` 및 `MILLER` ➡️ `hale`로 갱신하여 정합성을 맞췄습니다.
- **TTS Slimming 통합 테스트 실패 해결**: `test_preprototype_flow.py`, `test_demo_ai_respond_page.py`, `test_final_result_payload.py` 내의 `audio_url` 경로에서 이전 Kokoro 경로인 `/runtime/audio/kokoro/` 대신 신규 Edge TTS 경로인 `/runtime/audio/edge/`를 검증/모킹하도록 수정하여, 통합 테스트 실패를 완전히 해소했습니다.

검증 결과:

- `uv run pytest`: PASS, 231개 전체 테스트 중 Kokoro 로컬 환경 의존 테스트 1개를 제외한 230개 케이스 성공 통과 (TTS Slimming 변경 사항 및 Miller NPC 제거 작업 검증 완료).

수정된 파일 목록:

- `backend/app/services/service_a/npc_roster_service.py`
- `backend/app/services/service_a/voice_profile_service.py`
- `backend/tests/test_developer_a_npc_roster.py`
- `backend/tests/test_developer_a_agent_run_logging.py`
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/test_developer_a_npc_emotion_escalation.py`
- `backend/tests/test_developer_c_langgraph_orchestrator.py`
- `backend/tests/test_final_result_payload.py`
- `backend/tests/test_preprototype_flow.py`
- `backend/tests/test_demo_ai_respond_page.py`
- `backend/tests/test_unified_agent_run_log.py`
- `docs/contracts/change_requests.md`

## 2026-06-13 Developer A TTS Slimming Refactor Implementation & Testing Complete

Developer A는 Chatterbox, Kokoro 등 사용하지 않는 로컬 온디바이스 TTS 엔진 및 무거운 PyTorch(`torch`, `torchaudio`) 의존성 제거와 `edge-tts`로의 단일화 리팩토링 작업을 완수하고 관련 테스트 코드 수정을 완료했습니다.

구현 및 수정 내용:

- **의존성 정리**: `pyproject.toml`에서 무거운 의존성인 `chatterbox-tts`, `kokoro`, `espeakng-loader`, `torch` 등을 제거하고 `uv sync`를 실행하여 가상환경(Virtual Environment)을 경량화했습니다.
- **서비스 리팩토링**: `tts_provider_service.py`, `tts_service.py`, `voice_output_service.py`, `npc_roster_service.py`, `voice_profile_service.py` 내의 Kokoro 및 Chatterbox 로직을 제거하고, 기본 폴백(Fallback) 엔진 및 오디오 저장 경로 명칭을 `edge`로 일원화했습니다.
- **Developer A 테스트 수정 완료**: `test_developer_a_agent_run_logging.py` 내의 목소리 검증 단언문(Assertion) 중 기존 코코로 음성 ID(`am_michael`)를 기대하던 부분을 새로운 기본 폴백인 엣지 TTS 음성 ID(`en-US-GuyNeural`)로 수정하여, Developer A 소유의 모든 단위 테스트(35개 케이스)가 100% 성공적으로 패스하도록 조치했습니다.
- **Ruff 및 Mypy 검증 완료**: `uv run ruff check .` 및 `uv run mypy .`를 실행하여 린트 오류 및 타입 정적 분석 오류가 발생하지 않음을 교차 검증했습니다.

남은 연동 이슈 (Developer C 작업 대기):

- [change_requests.md](file:///C:/5th_project/pj05_Murphy/docs/contracts/change_requests.md)에 등록된 대로 Developer C 소유의 통합 테스트 파일들([test_preprototype_flow.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_preprototype_flow.py), [test_demo_ai_respond_page.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_demo_ai_respond_page.py), [test_final_result_payload.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_final_result_payload.py))에서 `audio_url` 내 `kokoro` 경로 대신 `edge` 경로를 기대하도록 검증 식을 수정해야 전체 테스트가 정상적으로 완료될 수 있습니다.

## 2026-06-13 Developer A TTS Slimming Refactor Plan & Change Request

Developer A는 시스템 경량화(Slimming)를 위해 사용하지 않는 로컬 온디바이스 TTS 엔진(Chatterbox, Kokoro)과 무거운 PyTorch(`torch`, `torchaudio`) 의존성을 제거하고, ElevenLabs API의 폴백(Fallback) 엔진을 `edge-tts`로 단일화하는 리팩토링 계획을 수립했습니다.

이와 관련하여 Developer C 소유의 통합 테스트 파일들([test_preprototype_flow.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_preprototype_flow.py), [test_demo_ai_respond_page.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_demo_ai_respond_page.py), [test_final_result_payload.py](file:///C:/5th_project/pj05_Murphy/backend/tests/test_final_result_payload.py))에서 `audio_url` 경로로 `kokoro`를 기대하는 단언(Assertion) 및 Mock 데이터가 확인되어, [change_requests.md](file:///C:/5th_project/pj05_Murphy/docs/contracts/change_requests.md)에 테스트 수정을 요청하는 변경 요청(Change Request)을 등록했습니다.

## Current Status

Phase 1 bootstrap is complete, Phase 2 contracts exist, and the AI-only
pre-prototype turn flow is now implemented through merged A/B/C packages. The
repository has a Developer C FastAPI backend package, C-side schemas, real
Developer B deterministic policy wiring, Developer A voice artifact wiring, a
Whisper-large-v3-turbo STT wrapper, an orchestrator, a strengthened validator,
and tests for JSON mock and multipart sample-wav turn flows. The STT contract
is local-first with API fallback. Automated tests keep deterministic STT through
`MURPHY_STT_MODE=mock`. Runtime settings now load from `.env` through
`pydantic-settings`, and the endpoint can enable real Kokoro TTS through
`MURPHY_TTS_MODE=real`. Developer C Understanding Agent now supports
deterministic `rule` mode and optional OpenAI-assisted `llm` mode with rule
fallback.

## 2026-06-12 Developer A LangGraph & ElevenLabs Parameter Refactor

Developer A는 패키지 버전 제약(langchain==1.3.2, langgraph==1.2.2)을 준수하며, NPC 대사 생성 및 ElevenLabs TTS 파라미터 동적 튜닝 흐름을 LangChain 및 LangGraph 기반 상태 기계 구조로 전면 리팩터링 및 마이그레이션 완료했습니다.

구현 내용:

- npc_llm_client.py 리팩터링: BaseChatModel을 상속하는 내부 ChatModel을 구현하여 LCEL 체인(prompt | model) 구조를 정립하고, 외부에서는 래퍼 클래스를 통해 generate 인터페이스 일관성을 유지했습니다.
- npc_dialogue_agent.py LangGraph 상태 기계 구현: NPCDialogueState 기반의 StateGraph를 조립 및 컴파일하여 데이터 초기화(initialize_state), LLM 대사 생성(generate_dialogue_llm), 폴백 매핑(apply_fallback) 노드를 유기적으로 연동하고 조건부 엣지를 통해 예외 처리를 일원화했습니다.
- voice_output_service.py 동적 파라미터 매핑: LLM이 동적으로 산출한 stability, style, speed, similarity_boost 파라미터를 ElevenLabs TTS API 주입 시 환경 변수보다 최우선적으로 적용하도록 연동 보강했습니다.
- 테스트 Mock 코드 보완: test_developer_a_npc_roster.py 및 test_developer_a_npc_dialogue.py 내 NPCProfile 모크 생성 시 누락되었던 필수 속성(persona_instruction, elevenlabs_voice_id)을 채워 정적 검사 오류를 해결했습니다.
- 작업 계획서 업데이트: backend/app/agents/agent_a/npc_implementation_plan.md 내 추후 계획에 머물러 있던 LangChain/LangGraph 마이그레이션 항목을 구현 완료 상태로 개정했습니다.

검증 결과:

- uv run pytest: PASS, Chapter 0 전체 223개 유닛 테스트 케이스 성공 통과.
- uv run ruff check .: PASS, 린트 지적 사항 0건.
- uv run mypy .: PASS, 101개 소스 파일 대상 정적 분석 타입 오류 0건 완료.

수정된 파일 목록:

- backend/app/agents/agent_a/npc_dialogue_agent.py
- backend/app/agents/agent_a/npc_llm_client.py
- backend/app/agents/agent_a/npc_implementation_plan.md
- backend/app/services/service_a/voice_output_service.py
- backend/tests/test_developer_a_npc_roster.py
- backend/tests/test_developer_a_npc_dialogue.py

## 2026-06-12 Developer C Realtime STT Smoke Fix

Developer C investigated a solo ElevenLabs realtime STT smoke-test failure from
`scripts/smoke_elevenlabs_realtime_stt_relay.py`. The backend connected to
ElevenLabs successfully and received `session_started`, but the provider then
returned `input_error` and closed the socket with
`previous_text_on_subsequent_input_audio`.

Root cause:

- `backend/app/services/service_c/elevenlabs_realtime_stt_relay.py` sent
  `previous_text` on every `input_audio_chunk`, even when it was an empty
  string.
- ElevenLabs accepts `previous_text` as optional context for the first audio
  input, but rejects it on subsequent audio chunks.

Fix:

- The relay now omits blank `previous_text`.
- Non-empty `previous_text` is forwarded only on the first audio chunk of a
  realtime relay session.
- Regression tests cover both the blank-value case and repeated-audio-chunk
  case.

Verification:

- `uv run pytest backend/tests/test_elevenlabs_realtime_stt_relay.py -q`: PASS,
  8 passed, 1 pytest cache warning when using the default Windows cache.
- `uv run pytest backend/tests/test_realtime_stt_websocket.py backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q -p no:cacheprovider --basetemp=backend/runtime/generated/pytest-stt-fix-tmp`:
  PASS, 6 passed, 2 warnings.

## Developer C Alpha Plan Notice

2026-06-10 Developer C / Sean Han is moving the prototype toward Alpha in
phases while preserving A/B/C ownership boundaries.

Alpha gameplay direction captured from the latest planning discussion:

- The current prototype is NPC-prompt-first: Unreal sends the fixed current
  NPC question context and player wav, Developer C runs STT and Understanding,
  Developer B evaluates the answer and branch, Developer A returns NPC
  dialogue/TTS, then Developer C assembles AI-to-Unreal JSON.
- Alpha must also support player-initiated interactions where the player walks
  up to an NPC and speaks first.
- NPC interactions must distinguish quest dialogue from ambient daily dialogue.
  Both NPC-first and player-first starts are valid.
- The rough Alpha flow is: start screen, single/multi select, takeoff
  cinematic, name entry on a customs declaration UI, seatmate level-test
  conversation on the plane, JFK arrival objective UI, immigration, baggage
  claim, odd baggage-item explanation, airport exit cinematic, and scoreboard.
- Immigration officer NPCs are fixed-question, NPC-first scenario agents. Desk
  and roaming staff may remain interactable after their main scenario beats.
- Time pressure and failure policy remain gameplay constraints: 30-second
  answers, repeated timeouts or unsatisfactory answers can fail, and dangerous
  words can trigger an immediate bad ending.
- Random baggage item/location keywords should be authored by humans in table
  data for Unreal to consume. AI may generate dialogue around those authored
  keywords but must not invent branch authority.

Developer C Alpha phases:

1. Alpha 0 - Team notice and contract alignment. Document the C-owned plan for
   A/B, keep A/B implementation files read-only, and use
   `docs/contracts/change_requests.md` for any cross-owner behavior changes.
2. Alpha 1 - Request context and timing baseline. Add a C-owned interaction
   context so Unreal can mark NPC-first vs player-first, quest vs ambient, and
   time-limit metadata. Add stage timing to responses/log summaries so STT,
   Understanding, Developer B, Developer A/TTS, response build, and validation
   latency can be measured.
3. Alpha 2 - Understanding Agent generic slot extraction. Replace the current
   per-slot strict schema/repair pattern with a generic slot evidence contract
   that can read `node_context.required_slots`, return allowed slot evidence,
   and keep Developer B as the only branch authority.
4. Alpha 3 - Scenario flow contract. Map Alpha scene ids, quest ids, and
   interactability rules without replacing Developer B's branch authority or
   Developer A's NPC wording authority.
5. Alpha 4 - STT provider benchmark. Compare the current local-first Whisper
   path with an API provider path behind the C-owned STT adapter.
6. Alpha 5 - Realtime voice path. Evaluate WebSocket streaming STT for player
   speech turns if timing data shows batch wav STT is the main latency issue.

No immediate Developer A or Developer B implementation change is required for
Alpha 1, Alpha 2, or Alpha 3A. Developer C added additive request/response
metadata, C-owned Understanding postprocessing, and C-owned runtime adapter
alignment only; any future change requiring A/B logic changes must be filed as a
change request first.

## 2026-06-12 Developer C LangGraph Refactor

Developer C refactored the hardcoded procedural orchestrator into a LangGraph
v1.2.2 workflow while preserving the public `Orchestrator.run_turn()` API and
A/B adapter boundaries.

Implemented:

- Added `backend/app/graphs/graph.py` with `DeveloperCTurnState`,
  `build_initial_developer_c_state()`, and the compiled Developer C turn graph.
- Added C-owned graph tool wrappers under
  `backend/app/tools/tool_c/developer_c_graph_tools.py`.
- Replaced the large procedural `Orchestrator.run_turn()` body with a thin
  LangGraph invocation wrapper.
- Preserved compatibility for C diagnostics/tests that replace orchestrator
  dependencies such as `understanding_agent`.
- Kept Developer A and B implementation files read-only; C still calls A/B
  only through existing adapters.
- Added AgentRun metadata showing `runtime.orchestrator = "langgraph"`,
  graph name, tool style, and graph node order.
- Moved transition handling into graph state so `COMPLETE_CHAPTER` responses
  pass `TransitionContext` to Developer A and the response builder.
- Updated C flow metadata to follow current B transition nodes and events:
  `START_AIRPORT_ARRIVAL_TUTORIAL`, `ENTER_BAGGAGE_CLAIM`, and
  `SHOW_ALPHA_SCOREBOARD`.
- Added sprint tracking at
  `docs/sprints/2026-06-12-langgraph-refactor-sprint.md`.

Verification for this update:

- `uv run pytest backend/tests/test_developer_c_langgraph_orchestrator.py -q`:
  PASS, 2 passed, 1 warning.
- `uv run pytest backend/tests/test_developer_c_langgraph_orchestrator.py backend/tests/test_preprototype_flow.py backend/tests/test_unified_agent_run_log.py -q`:
  PASS, 29 passed, 2 warnings.
- `uv sync`: PASS. It restored the locked environment and removed undeclared
  local package `en-core-web-sm==3.8.0` from the current virtualenv.
- `uv run pytest -q`: PASS, 218 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 101 source files.
- `git diff --check`: PASS with Git's normal CRLF working-copy warnings only.

## 2026-06-15 Developer C StructuredTool Wrapper Update

Developer C wrapped every C-owned LangGraph `*_tool()` step in
LangChain-compatible `StructuredTool` objects while preserving the existing
linear `StateGraph` turn flow and A/B adapter boundaries.

Implemented:

- Added `DeveloperCStructuredToolInput` in
  `backend/app/tools/tool_c/developer_c_graph_tools.py` so each C graph tool
  accepts the current turn `state` through a standard LangChain tool schema.
- Exposed node-name keyed `structured_tools` on `DeveloperCGraphTools`.
- Added `invoke_structured_tool()` and changed each node function in
  `backend/app/graphs/graph.py` to execute via `StructuredTool.invoke(...)`.
- Added `as_tool_node_tools()` to return the ordered tool list for a future
  LangGraph `ToolNode` or subgraph migration. The current C graph still uses
  explicit state nodes because the C turn state is richer than a chat
  message/tool-call loop.
- Updated AgentRun runtime metadata so Developer C records now include
  `tool_style = "langchain_structured_tools"` and the
  `structured_tool_names` list.
- Added regression coverage in
  `backend/tests/test_developer_c_langgraph_orchestrator.py` proving the tools
  are real `StructuredTool` instances and that graph execution passes through
  `invoke_structured_tool()`.

Verification for this update:

- `uv run pytest`: PASS, 238 passed, 1 warning.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 106 source files.
- `uv run python -c "from langgraph.prebuilt import ToolNode; from backend.app.tools.tool_c.developer_c_graph_tools import DeveloperCGraphTools; tools = DeveloperCGraphTools(); node = ToolNode(tools.as_tool_node_tools()); print(type(node).__name__, len(tools.as_tool_node_tools()))"`:
  PASS, printed `ToolNode 11`.

## 2026-06-12 Developer C Alpha 3E Follow-up

Developer C updated the realtime STT path to match the recommended Alpha
runtime: ElevenLabs realtime relay remains the primary subtitle provider, while
the existing local Whisper STT runtime is retained as a batch-on-commit
fallback.

Implemented behavior:

- `/api/game/ai/stt/stream` still streams partial/final subtitle events through
  the C-owned WebSocket.
- When an `audio_chunk` is committed and ElevenLabs fails to send or returns no
  final transcript, Developer C wraps the buffered PCM chunks into a wav file
  and calls the existing local Whisper batch STT boundary.
- Fallback final events use `provider = "local_batch_fallback"` and keep
  `target_endpoint = "POST /api/game/ai/respond"` so Unreal can reuse the
  committed transcript path.
- The local fallback is not partial-streaming STT; it only recovers the final
  transcript at commit time.
- `MURPHY_STT_DEBUG_LOG_MODE=debug` appends standalone
  `realtime_stt_relay` Developer C AgentRun records to the same unified
  JSONL/Markdown files as the existing A/B/C logs.
- Realtime STT debug records include chunk count, total audio bytes, estimated
  duration, primary/fallback provider metadata, final transcript summary, token
  counts fixed at zero, and estimated cost from
  `ELEVENLABS_REALTIME_ESTIMATED_COST_PER_MINUTE_USD`.

Changed:

- Added `local_batch_fallback` to the realtime STT server event provider
  contract.
- Added local batch fallback buffering to
  `backend/app/services/service_c/elevenlabs_realtime_stt_relay.py`.
- Added `backend/app/services/service_c/realtime_stt_debug_log_service.py`.
- Added realtime STT debug settings to
  `backend/app/services/service_c/settings_service.py` and `.env.example`.
- Updated Developer C schema, adapter, dependency, and handoff docs.
- Added focused tests for fallback final recovery and debug AgentRun append.

Verification for this update:

- `uv run pytest backend/tests/test_elevenlabs_realtime_stt_relay.py backend/tests/test_realtime_stt_websocket.py::test_realtime_stt_websocket_appends_debug_agent_run_log_for_stt_session backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q`:
  PASS, 8 passed, 2 warnings.
- `uv sync`: PASS. It restored the locked environment and removed undeclared
  local STT extra packages from the current virtualenv.
- `uv run pytest -q`: PASS, 211 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 96 source files.
- `git diff --check`: PASS with Git's normal CRLF working-copy warnings only.

## 2026-06-12 Developer C Alpha 3D Follow-up

Developer C added a backend relay path for ElevenLabs realtime STT. Unreal can
connect to the existing C-owned WebSocket and start a relay session with:

```json
{
  "contract_version": "dev_c_realtime_stt.v1",
  "event_type": "session_start",
  "provider": "elevenlabs_relay"
}
```

Developer C then opens a server-side WSS connection to:

```text
wss://api.elevenlabs.io/v1/speech-to-text/realtime
```

The ElevenLabs API key stays in backend `.env` as `ELEVENLABS_API_KEY` and is
sent only as the provider `xi-api-key` header. Unreal sends `audio_chunk` events
with base64 PCM audio; Developer C forwards those as ElevenLabs
`input_audio_chunk` messages and maps ElevenLabs `partial_transcript` and
`committed_transcript` messages back into `dev_c_realtime_stt.v1` subtitle
events.

Changed:

- Added `websockets` as a direct runtime dependency.
- Added ElevenLabs realtime settings to
  `backend/app/services/service_c/settings_service.py` and `.env.example`.
- Added `audio_chunk` and `elevenlabs_relay` to the realtime STT schema.
- Added `backend/app/services/service_c/elevenlabs_realtime_stt_relay.py`.
- Updated `/api/game/ai/stt/stream` to open and use the relay when requested.
- Added fake-provider tests for settings, relay mapping, and WebSocket route
  behavior.
- Added `scripts/smoke_elevenlabs_realtime_stt_relay.py` for solo local smoke
  testing with a 16 kHz mono 16-bit PCM wav file.

Manual solo smoke test:

```powershell
Copy-Item .env.example .env
# Fill ELEVENLABS_API_KEY in .env
uv run uvicorn backend.app.main:app --reload
uv run python scripts/smoke_elevenlabs_realtime_stt_relay.py --wav path\to\mono_16k_pcm.wav
```

Still open:

- Unreal must capture microphone PCM chunks and send `audio_chunk` events.
- Direct final WebSocket transcript commit into the C orchestrator is not
  implemented yet; final events still point to `POST /api/game/ai/respond`.
- Short-lived client token mode is intentionally not used because this phase
  chose backend relay.

Verification for this update:

- `uv run pytest backend/tests/test_settings_service.py backend/tests/test_elevenlabs_realtime_stt_relay.py backend/tests/test_realtime_stt_websocket.py -q`:
  PASS, 8 passed, 2 warnings.
- `uv run pytest -q`: PASS, 206 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 95 source files.

## 2026-06-12 Developer C Alpha 3C Follow-up

Developer C added a provider-neutral realtime STT transcript WebSocket for
Unreal subtitle previews:

```text
WebSocket /api/game/ai/stt/stream
```

The new event contract is `dev_c_realtime_stt.v1`. It accepts `session_start`,
`partial_transcript`, `final_transcript`, and `cancel` events from Unreal or a
safe STT bridge. The endpoint returns subtitle-ready server events that Unreal
can render immediately while the player is speaking.

Implemented behavior:

- `session_start` returns `session_started`.
- `partial_transcript` returns a non-committed `subtitle` payload with
  `display_mode=replace`.
- `final_transcript` returns `committed=true` and
  `target_endpoint=POST /api/game/ai/respond`.
- Invalid events return `contract_error` instead of entering orchestration.
- Per-connection `sequence` must increase monotonically.

Important boundary:

- Partial transcripts are UI-only and do not call the Understanding Agent,
  Developer B, Developer A, or TTS.
- Alpha 3C does not yet connect a real provider SDK or short-lived provider
  token flow.
- Alpha 3C does not yet pipe final WebSocket events directly into the
  orchestrator; it points Unreal back to the existing `/respond` committed
  transcript path.

Changed:

- Added realtime STT client/server event schemas in
  `backend/app/schemas/game_turn.py`.
- Added WebSocket handling in `backend/app/api/ai_respond.py`.
- Added realtime STT event validation in
  `backend/app/services/service_c/validator.py`.
- Added focused WebSocket contract tests in
  `backend/tests/test_realtime_stt_websocket.py`.
- Updated Developer C schema, adapter, change-request, and handoff docs.

Verification for this update:

- `uv run pytest backend/tests/test_realtime_stt_websocket.py -q`: PASS, 3
  passed, 2 warnings.
- `uv run pytest backend/tests/test_realtime_stt_websocket.py backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py -q`:
  PASS, 30 passed, 2 warnings.
- `uv run pytest -q`: PASS, 203 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 92 source files.

## 2026-06-12 Developer C Alpha 3B Follow-up

Developer C added additive Unreal flow metadata to `dev_c_unreal_response.v1`.
The new `flow` object uses `dev_c_unreal_flow.v1` and tells Unreal which Alpha
presentation transition should happen after a validated backend turn. It is
presentation metadata only and does not override Developer B's `next_node_id` or
`next_action`.

Implemented flow cues:

- `FLIGHT_005_WRAP_UP -> IMM_001_PASSPORT`: `cutscene` transition
  `flight_to_immigration_arrival`, `to_scene_id=IMMIGRATION_ALPHA`,
  `cinematic_id=CIN_FLIGHT_ARRIVAL_JFK`, `skip_allowed=true`.
- `IMM_007_FINAL_DECISION -> BAG_001_NOTICE_BAG_MISSING`: `scene_transition`
  `immigration_to_baggage_claim`, `to_scene_id=BAGGAGE_MISSING`.
- `ALPHA_999_FINAL_SCOREBOARD -> END_ALPHA_SCENARIO`: `scoreboard` transition
  `alpha_final_scoreboard`, `to_scene_id=ALPHA_SCOREBOARD`,
  `show_scoreboard=true`.

Changed:

- Added `FlowResponse` and `UnrealResponse.flow` to the C schema.
- Updated `ResponseBuilder` to emit flow metadata for the base Alpha route.
- Updated `Validator` to check `dev_c_unreal_flow.v1` and scoreboard flag
  consistency.
- Added integration tests for flight arrival cutscene, baggage scene transition,
  and final scoreboard flow.

Still open:

- Unreal must consume `flow` and actually play/skip cinematics, move scene
  state, and render the scoreboard.
- A-owned dialogue/TTS polish for seatmate and baggage staff voices.
- Dedicated final `out_game_feedback` UI exposure beyond the existing
  `final_result` payload.

Verification for this update:

- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py -q`:
  PASS, 27 passed, 2 warnings.
- `uv run pytest -q`: PASS, 200 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 91 source files.
- `git diff --check`: PASS with Git's normal CRLF working-copy warnings only.

## 2026-06-12 Developer C Alpha 3A Follow-up

Developer C adopted the base Alpha scenario node expansion at the C runtime
boundary without editing B-owned `scenario_nodes.json`. The integrated flow now
treats `IMM_007_FINAL_DECISION` as an immigration-clearance transition into
`BAG_001_NOTICE_BAG_MISSING`, and treats `ALPHA_999_FINAL_SCOREBOARD` as the
only Alpha final-result trigger for attached `report.final_result`.

Changed:

- Updated `DevBPolicyClient` so it attaches B `final_result` only when Developer
  B returns a final branch from `ALPHA_999_FINAL_SCOREBOARD`.
- Removed the `IMM_` prefix gate from the C-to-A adapter's next-node question
  lookup so FLIGHT/BAG/ALPHA nodes can seed Developer A generation through
  OpenKB metadata.
- Added generic rule-mode Understanding fallback that consumes B-authored
  `hint_policy` and allowed slot metadata for non-hardcoded slots such as
  `missing_bag_observation` and `final_recommendation`.
- Opened the C schema/validator to accept
  `scene_normalized_dimension_average` in addition to `simple_average`.
- Added C integration tests for `IMM_007 -> BAG_001`, `BAG_001 -> BAG_002`, and
  `ALPHA_999_FINAL_SCOREBOARD -> END_ALPHA_SCENARIO`.

Still open after Alpha 3A:

- Unreal cutscene/skip state wiring for flight exit, arrival, baggage entry,
  ending cinematic, and scoreboard display. Alpha 3B now exposes backend `flow`
  metadata for the base route, but Unreal still owns execution.
- A-owned dialogue/TTS polish for seatmate and baggage staff voices.
- Dedicated final `out_game_feedback` UI exposure beyond the existing
  `final_result` payload.

Verification for this update:

- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_understanding_agent.py backend/tests/test_understanding_llm_client.py -q`:
  PASS, 41 passed, 2 warnings.
- `uv run pytest -q`: PASS, 197 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 91 source files.
- `git diff --check`: PASS with Git's normal CRLF working-copy warnings only.

## 2026-06-12 Developer C Follow-up

Developer C implemented Alpha 2 generic slot evidence in the C-owned
Understanding layer. The LLM can now return `slot_evidence` entries for the
current node's required, optional, or critical slots. Developer C filters those
entries to the current node, drops unrelated or forbidden slot names such as
`next_node_id` and `npc_text`, and converts accepted evidence into the existing
`extracted_slots` dict before Developer B receives the policy input.

Changed:

- Added `SlotEvidence` and `UnderstandingOutput.slot_evidence` to the C schema.
- Updated the Understanding LLM strict schema and normalization so generic slot
  evidence can fill `extracted_slots` without adding one strict slot key per
  scenario node.
- Added C postprocessing that accepts only current-node slots and keeps
  Developer B as the sole branch/progression authority.
- Kept deterministic `visit_purpose` and `stay_duration` repairs as regression
  guards for the existing prototype nodes.
- Added tests for `stay_location` generic evidence, forbidden slot filtering,
  and strict schema compatibility.

Changed files for this update:

- `backend/app/schemas/game_turn.py`
- `backend/app/agents/agent_c/understanding_llm_client.py`
- `backend/app/agents/agent_c/understanding_agent.py`
- `backend/tests/test_understanding_agent.py`
- `backend/tests/test_understanding_llm_client.py`
- `docs/contracts/developer_c_schema_contract.md`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/handoff.md`

Verification for this update:

- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_understanding_llm_client.py backend/tests/test_preprototype_flow.py -q`:
  PASS, 34 passed, 2 warnings.
- `uv run pytest -q`: PASS, 193 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 91 source files.
- `git diff --check`: PASS with Git's normal CRLF working-copy warnings only.

## 2026-06-11 Developer C Follow-up

Developer C fixed the IMM_003_DURATION progression issue in the C-owned
Understanding layer. The root cause was that rule mode, LLM structured output,
and LLM postprocessing only knew how to fill `visit_purpose`, while the duration
node requires `stay_duration`. C now recognizes duration answers such as
`5 days`, `five days`, `one week`, and `until Friday`, and repairs missing
LLM `stay_duration` slots before calling Developer B. Developer B's
`intent_success and not missing_slots` success policy remains unchanged.

Developer C also documented the Alpha realtime caption transport candidate:
add a C-owned WebSocket STT session for partial and committed transcripts while
keeping the existing multipart wav `/respond` path as the fallback baseline.
Partial transcripts are for Unreal subtitle UI only; committed transcripts enter
the normal C orchestrator path.

Next Alpha priority: refactor the C-owned Understanding Agent around generic
slot evidence before expanding the full Alpha scenario flow. The current
`visit_purpose` and `stay_duration` extractors are acceptable regression guards,
but new scene slots should not require one hardcoded extractor per node.

## Developer A ElevenLabs TTS Provider Update - 2026-06-09

Developer A integrated ElevenLabs as an official selectable TTS provider. The
runtime can now switch providers with:

```text
MURPHY_TTS_PROVIDER=elevenlabs
MURPHY_TTS_PROVIDER=edge
MURPHY_TTS_PROVIDER=kokoro
MURPHY_TTS_PROVIDER=chatterbox
```

Generated ElevenLabs WAV files are stored under:

```text
backend/runtime/generated/audio/elevenlabs/
```

Runtime settings:

```text
MURPHY_ELEVENLABS_API_KEY=
ELEVENLABS_API_KEY=
MURPHY_ELEVENLABS_BASE_URL=https://api.elevenlabs.io/v1
MURPHY_ELEVENLABS_VOICE_ID=CwhRBWXzGAHq8TQ4Fs17
MURPHY_ELEVENLABS_MODEL_ID=eleven_flash_v2_5
MURPHY_ELEVENLABS_API_OUTPUT_FORMAT=mp3_44100_128
MURPHY_ELEVENLABS_OUTPUT_FORMAT=wav
MURPHY_ELEVENLABS_STABILITY=0.52
MURPHY_ELEVENLABS_SIMILARITY_BOOST=0.82
MURPHY_ELEVENLABS_STYLE=0.42
MURPHY_ELEVENLABS_SPEED=0.80
MURPHY_ELEVENLABS_USE_SPEAKER_BOOST=true
MURPHY_ELEVENLABS_TIMEOUT_SECONDS=60
```

Implementation notes:

- The provider uses the existing `httpx` dependency.
- ElevenLabs MP3 responses are converted to 24kHz mono PCM WAV with `ffmpeg`.
- API keys are read from `.env` or process environment but are not returned in
  provider metadata or AgentRun logs.
- AgentRun tool name: `tts_provider_service.elevenlabs.synthesize`.
- Rollback is immediate by setting `MURPHY_TTS_PROVIDER=edge` or
  `MURPHY_TTS_PROVIDER=kokoro`.

Verification:

- Added tests for provider switching, output path, AgentRun logging, and secret
  redaction.
- ElevenLabs provider can be benchmarked through the integrated
  `/api/game/ai/respond` path with `MURPHY_TTS_PROVIDER=elevenlabs`.

## Developer A Chatterbox TTS Provider Update - 2026-06-09

Developer A added a reversible Chatterbox TTS provider path for stronger
emotion and reference-audio voice conditioning experiments. The runtime can now
switch providers with:

```text
MURPHY_TTS_PROVIDER=kokoro
MURPHY_TTS_PROVIDER=edge
MURPHY_TTS_PROVIDER=chatterbox
```

Generated Chatterbox files are stored under:

```text
backend/runtime/generated/audio/chatterbox/
```

Chatterbox runtime parameters are read from `.env`:

```text
MURPHY_CHATTERBOX_VOICE_ID=officer_miller_ref
MURPHY_CHATTERBOX_REFERENCE_AUDIO=backend/app/assets/voices/officer_miller_ref.wav
MURPHY_CHATTERBOX_EXAGGERATION=0.75
MURPHY_CHATTERBOX_CFG_WEIGHT=0.35
MURPHY_CHATTERBOX_TEMPERATURE=0.60
MURPHY_CHATTERBOX_DEVICE=auto
MURPHY_CHATTERBOX_LANGUAGE_ID=en
MURPHY_CHATTERBOX_OUTPUT_FORMAT=wav
```

Dependency note:

- `chatterbox-tts==0.1.7` requires `torch==2.6.0`, so `pyproject.toml` now
  limits Python to `>=3.12,<3.13` and pins torch to `2.6.0`.
- `pyproject.toml` routes `torch` and `torchaudio` to the PyTorch CUDA 12.4
  wheel index on Windows/Linux.
- Local verification currently imports `torch==2.6.0+cu124`,
  `torch.version.cuda==12.4`, and `chatterbox.tts.ChatterboxTTS`.
- `torch.cuda.is_available()` is `True` on the local RTX 4070 Laptop GPU.
- With `MURPHY_CHATTERBOX_DEVICE=auto`, Developer A uses CUDA when available
  and CPU otherwise.
- If `MURPHY_CHATTERBOX_REFERENCE_AUDIO` is missing, Developer A omits
  `audio_prompt_path` and uses the model default voice rather than failing at
  request construction.

Verification:

- `uv run pytest backend/tests/test_developer_a_agent_run_logging.py -q`
  passed: 14 tests, 1 `audioop` deprecation warning.
- Actual Chatterbox model-weight smoke generation completed on CPU without
  reference audio:
  - Output:
    `backend/runtime/generated/audio/chatterbox/chatterbox_smoke_warning_cpu.wav`
  - Text: `Sir. Answer the question directly.`
  - Audio duration: about 1.76 seconds.
  - Generation time: about 29.04 seconds on CPU.
  - Real-time factor: about 16.50.
  - `reference_audio_exists=false`; Officer Miller voice cloning still needs a
    reference wav under `backend/app/assets/voices/`.
- Actual Chatterbox model-weight smoke generation also completed on CUDA
  without reference audio:
  - Output:
    `backend/runtime/generated/audio/chatterbox/chatterbox_smoke_warning_cuda.wav`
  - Text: `Sir. Answer the question directly.`
  - Audio duration: about 2.04 seconds.
  - Generation time: about 18.06 seconds on RTX 4070 Laptop GPU.
  - Real-time factor: about 8.85.
  - `provider_options.device=cuda`.

Rollback is immediate by setting `MURPHY_TTS_PROVIDER=kokoro` or
`MURPHY_TTS_PROVIDER=edge`.

## Developer A Edge TTS Provider Update - 2026-06-09

Developer A added a reversible Edge TTS provider path without removing Kokoro.
The runtime can switch providers with:

```text
MURPHY_TTS_PROVIDER=kokoro
MURPHY_TTS_PROVIDER=edge
```

Edge TTS currently uses the Python `edge-tts` package to generate MP3 and
converts it to PCM WAV with `ffmpeg` when
`MURPHY_EDGE_TTS_OUTPUT_FORMAT=wav`. Generated Edge files are stored under:

```text
backend/runtime/generated/audio/edge/
```

Smoke result on 2026-06-09:

- Audio duration: about 4.656 seconds.
- Total Edge generation plus WAV conversion: about 0.69 seconds.
- WAV conversion time: about 0.04 seconds.

Rollback is immediate by setting `MURPHY_TTS_PROVIDER=kokoro`.

## Last Completed Task

2026-06-05 Developer C updated the `/respond-dialog` tester usage and audio
input workflow.

Changed:

- `/respond-dialog` now shows a CSS stopwatch icon only while the top status is
  `Running`.
- The `Next WAV` area now includes browser microphone recording controls. The
  browser captures PCM audio, encodes a RIFF WAV file client-side, and submits
  it through the existing multipart `audio` field.
- The browser tester tracks request ids sent by the current page and asks
  `session-usage` for only those request ids. This prevents reused session ids
  such as `session_001` from mixing historical or other-person runs into the
  visible token total.
- `GET /api/game/ai/agent-runs/session-usage` now accepts repeated optional
  `request_ids` query params in addition to `session_id`.
- Session usage normalization now accepts canonical unified usage fields and
  OpenAI-compatible aliases such as `prompt_tokens`, `completion_tokens`, and
  `cost_usd`.

Known usage limitation:

- If an upstream A/B/C AgentRun record stores `model_name` but records zero
  token counts and zero cost, Developer C cannot reconstruct the missing
  provider usage after the fact. The updated summary service will display
  costs when token/cost fields are present or when known-model tokens can be
  estimated.

Changed files for this update:

- `backend/app/api/ai_respond.py`
- `backend/app/services/service_c/agent_run_summary_service.py`
- `demo/respond-dialog/index.html`
- `backend/tests/test_demo_ai_respond_page.py`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/handoff.md`

Verification for this update:

- `uv sync`: PASS after approved escalation for uv user-cache access.
- `uv run pytest backend/tests/test_demo_ai_respond_page.py -q`: PASS, 8
  passed, 2 warnings.
- `uv run pytest -q`: PASS, 110 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 87 source files after approved
  escalation for uv user-cache access.

Developer C added a separate multi-turn browser tester at `/respond-dialog`
without changing the existing `/demo/ai-respond` page. The new page starts at
`IMM_002_PURPOSE`, keeps the left-side wav/Turn JSON upload workflow, and
renders the right side as an iMessage-style transcript with user STT text, NPC
text, per-message audio play buttons, and branch dividers. Browser-side state
now advances playable nodes on `ADVANCE`, keeps the current playable node for
`REASK`/`GIVE_HINT`, accumulates `state_delta`, appends
`previous_node_results`, and regenerates `request_id`/`turn_index` per run.
The page also shows per-turn timing metrics (`Total`, `Status`, `STT`,
`Verdict`) above session token/cost usage. A separate `Next WAV` picker and
`Continue` button let testers continue the current auto-updated scenario state
with only a wav file after the first turn.

Developer C also added demo-only helper APIs:

- `GET /api/game/ai/demo/node/{node_id}` for safe Chapter 0 node context used
  by the browser tester.
- `GET /api/game/ai/agent-runs/session-usage?session_id=<optional>` for
  session-level token and estimated USD cost totals from top-level unified
  AgentRun `model` fields.
- `GET /api/game/ai/agent-runs/latest` now includes `model_usage` while keeping
  the previous compact node summary response fields.

Changed files for this update:

- `backend/app/main.py`
- `backend/app/api/ai_respond.py`
- `backend/app/services/service_c/agent_run_summary_service.py`
- `demo/respond-dialog/index.html`
- `backend/tests/test_demo_ai_respond_page.py`
- `backend/tests/test_preprototype_flow.py`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/handoff.md`

Verification for this update:

- `uv sync`: PASS. It completed after approved escalation because sandboxed
  `uv` cache access was denied.
- `uv run pytest backend/tests/test_demo_ai_respond_page.py -q`: PASS, 6
  passed, 2 warnings.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_unified_agent_run_log.py -q`:
  PASS, 15 passed, 2 warnings.
- `uv run pytest -q`: PASS, 106 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 86 source files. The sandboxed run hit a
  `uv` cache access-denied error, so the same command was rerun with approved
  escalation.

Developer A NPC dialogue/voice path is now structured around an NPC roster.
`backend/app/services/service_a/npc_roster_service.py` owns NPC display name,
role, default animation, fallback text, mock voice id, and Kokoro voice
candidates. The current roster contains `officer_miller`; unknown or missing
NPC ids fall back to that profile. Kokoro voice ids are configured per NPC
through `kokoro_voices`, with Korean code comments marking that the values must
come from the installed Kokoro model's supported voice list.

Developer C's `DevANpcDialogueClient` forwards Unreal `npc` context into
Developer A's level-design payload, while final NPC dialogue text and voice
style remain Developer A-owned. Developer A AgentRun metadata now includes
`dialogue_source_trace`, which records the node context, player text preview,
Developer B feedback/directive, branch, NPC profile, and voice profile data
used to shape the next NPC line and TTS selection.
LLM dialogue mode also keeps roster-owned speaker and animation values instead
of trusting model-provided presentation identifiers.

Verification for this update:

- `uv run pytest backend/tests/test_developer_a_npc_roster.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_developer_a_agent_run_logging.py -q`: PASS, 22 passed, 1 warning.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_unified_agent_run_log.py -q`: PASS, 14 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS.
- `git diff --check`: PASS.
- `uv run pytest -q`: PASS, 76 passed, 2 warnings.

Automated tests remain deterministic and do not require real API keys. User-local
manual verification may enable real API-backed LLM/TTS modes through environment
settings when explicitly requested.

Gemma4 vLLM fallback support replaces the previous temporary Gemini provider
path for the GPT key outage case. OpenAI remains the primary provider, and the
academy server is tried only when the fallback flags are enabled:

- `GEMMA4_VLLM_BASE_URL=http://100.95.34.69:8001/v1`
- `GEMMA4_VLLM_MODEL=google/gemma-4-26B-A4B-it`
- `GEMMA4_VLLM_API_KEY=dummy`
- `MURPHY_UNDERSTANDING_LLM_FALLBACK=gemma4_vllm`
- `NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm`

The academy server is a vLLM OpenAI-compatible `/v1/chat/completions` endpoint.
Smoke verification on 2026-06-05 confirmed:

- `GET http://100.95.34.69:8001/v1/models`: PASS, model
  `google/gemma-4-26B-A4B-it`, owned by `vllm`.
- `POST /v1/chat/completions`: PASS, returned `OK`.
- Developer A real path with `NPC_DIALOGUE_LLM_FALLBACK=gemma4_vllm` and
  `use_real_tts=True`: PASS, generated
  `backend\runtime\generated\gemma4_wav_smoke\audio\kokoro\IMM_002_PURPOSE_unknown_slot_success_am_michael_737b8af0.wav`.
- Latest AgentRun log includes TTS speed:
  `generation_seconds=4.129077799996594`,
  `audio_seconds=3.575`,
  `real_time_factor=1.1549867972018444`.

Verification for this update:

- `uv run pytest backend/tests/test_developer_a_npc_llm_client.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/test_understanding_llm_client.py backend/tests/test_settings_service.py -q`: PASS, 19 passed, 1 warning.
- `uv run pytest -q`: PASS, 87 passed, 2 warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS.
- `git diff --check`: PASS.

Removed duplicate Developer A-only runtime logs from the NPC dialogue voice
output path. Developer A now appends NPC dialogue AgentRun records only through
the shared `unified_agent_run.v1` sink:
`backend/runtime/generated/agent_runs/unified_agent_runs.jsonl` and
`backend/runtime/generated/agent_runs/unified_agent_runs.md`. The old
`npc_dialogue_agent_runs.jsonl`, `npc_dialogue_artifacts.jsonl`, and
`backend/runtime/logs/developer_a_events.jsonl` write paths were removed from
runtime behavior.

Enabled the real STT plus real Kokoro TTS endpoint demo path. The C-owned
`DevANpcDialogueClient` now reads `MURPHY_TTS_MODE` and
`MURPHY_NPC_DIALOGUE_MODE` from `AppSettings` and passes `use_real_tts` /
`use_llm_dialogue` into Developer A's `build_voice_output_from_level_design()`
service. Deterministic defaults remain `MURPHY_STT_MODE=mock`,
`MURPHY_TTS_MODE=fake`, and `MURPHY_NPC_DIALOGUE_MODE=rule` for tests. A demo
turn fixture now exists at `demo/input/imm_002_purpose.json`.

Developer C also added real AI mode for the Understanding Agent. Set
`MURPHY_UNDERSTANDING_MODE=llm` with `OPENAI_API_KEY` to call the C-owned
OpenAI Responses API client. Missing API key, request failure, invalid JSON,
schema failure, or forbidden authority fields fall back to deterministic rule
mode. Developer C now appends an orchestration-level unified AgentRun record to
Developer A's shared log sink and includes the Understanding Agent's
LLM/fallback trace inside the orchestrator event timeline. The Understanding
LLM structured output schema now follows OpenAI strict schema requirements, and
rule fallback recognizes family, friend, business, study, transit, and tourism
visit-purpose values.

Developer C also debugged a recurring NPC fallback response:
`Okay. Please continue.`. The cause was a valid Understanding LLM response that
missed `visit_purpose=family_visit` for `I'm here to visit my uncle.`, so B
returned `REASK/clarify` and A intentionally used its safe fallback dialogue.
C now applies a narrow post-processing guard when a valid LLM response leaves a
required `visit_purpose` slot empty but the deterministic allowed-value
classifier can clearly fill it. The guard records
`last_trace.postprocessing.slot_repair_applied=true` and preserves LLM mode
rather than treating it as provider fallback.

## Changed Files

- `.env.example`
- `.gitignore`
- `README.md`
- `demo/input/imm_002_purpose.json`
- `backend/app/services/service_c/settings_service.py`
- `backend/app/services/service_c/stt_service.py`
- `backend/tests/test_settings_service.py`
- `backend/app/integrations/dev_a_npc_dialogue_client.py`
- `backend/app/agents/agent_c/understanding_agent.py`
- `backend/app/agents/agent_c/understanding_llm_client.py`
- `backend/app/agents/agent_c/visit_purpose_classifier.py`
- `backend/app/middleware/middleware_c/developer_c_agent_run_middleware.py`
- `backend/app/integrations/dev_b_level_hint_client.py`
- `backend/app/main.py`
- `backend/app/schemas/game_turn.py`
- `backend/app/services/service_c/openkb_service.py`
- `backend/app/services/service_c/response_builder.py`
- `backend/app/services/service_c/validator.py`
- `backend/tests/test_preprototype_flow.py`
- `backend/tests/test_understanding_agent.py`
- `backend/tests/test_understanding_llm_client.py`
- `docs/contracts/dependency_contract.md`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/contracts/developer_c_schema_contract.md`
- `docs/handoff.md`
- `backend/app/services/shared/__init__.py`
- `backend/app/services/shared/agent_run_log_store.py`
- `backend/app/services/shared/agent_run_markdown_formatter.py`
- `backend/app/services/service_a/npc_dialogue_agent_run_store.py`
- `backend/app/services/service_a/npc_roster_service.py`
- `backend/app/services/service_a/voice_profile_service.py`
- `backend/app/services/service_a/tts_service.py`
- `backend/app/services/service_a/voice_output_service.py`
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/services/service_a/developer_a_runtime_log_service.py` (removed)
- `backend/runtime/logs/developer_a_events.jsonl` (removed)
- `backend/tests/test_developer_a_agent_run_logging.py`
- `backend/tests/test_developer_a_npc_roster.py`
- `backend/tests/test_developer_a_npc_dialogue.py`
- `backend/tests/test_unified_agent_run_log.py`
- `docs/implementation_logs/developer_a_implementation_log_kimyonghee.md`
- `docs/contracts/developer_a_agent_spec.md`
- `docs/contracts/change_requests.md`
- `AGENTS.md`
- `docs/preprototype_status_demo_plan.md`
- `docs/superpowers/plans/2026-06-04-real-understanding-agent-mode.md`
- `docs/superpowers/plans/2026-06-04-real-stt-kokoro-endpoint-demo.md`
- `docs/superpowers/plans/2026-06-04-preprototype-abc-integration.md`

## Commands Run

- `git status --short --branch`
- `Get-Content -Path backend\app\services\stt_service.py`
- `Get-Content -Path .gitignore`
- `Get-Content -Path .env.example`
- `Get-Content -Path backend\tests\test_stt_service.py`
- `Get-Content -Path README.md`
- `Get-Content -Path docs\contracts\dependency_contract.md`
- `Get-Content -Path docs\contracts\developer_c_schema_contract.md`
- `Get-Content -Path docs\preprototype_status_demo_plan.md`
- `Get-Content -Path docs\handoff.md`
- `uv run pytest backend/tests/test_settings_service.py -q` (RED: settings service did not exist)
- `uv run pytest backend/tests/test_settings_service.py -q` (GREEN: 2 passed)
- `rg --files -g ".gitignore" -g ".env*" -g "*.env" -g "pyproject.toml" -g "*.md"`
- `rg -n "MURPHY_STT|OPENAI_API_KEY|\.env|Runtime STT|STT Runtime Setup" README.md docs\contracts\dependency_contract.md docs\contracts\developer_c_schema_contract.md docs\contracts\developer_c_adapter_contracts.md docs\preprototype_status_demo_plan.md docs\handoff.md`
- `git diff --stat`
- `uv sync` (first sandboxed attempt failed on user-level uv cache initialization)
- `uv sync` (rerun with approved escalation: resolved 93 packages, audited 55 packages)
- `uv run pytest` (9 passed, 1 warning)
- `uv run ruff check .` (passed)
- `uv run mypy .` (initially failed on typed `_env_file` constructor usage)
- `uv run mypy .` (passed)
- `git diff --check` (passed)
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (RED: OpenKB only supported `IMM_002_PURPOSE`; B adapter was still mock)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_api_accepts_multipart_turn_json_and_sample_wav -q` (RED: A adapter did not produce next-question dialogue or `npc.audio_url`)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_validator_rejects_developer_b_hint_payload_when_hint_is_not_needed backend/tests/test_preprototype_flow.py::test_validator_requires_npc_audio_url_for_preprototype_response -q` (RED: validator did not enforce these invariants)
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_developer_a_npc_dialogue.py backend/tests/dev_b/test_developer_b_policy_engine.py -q` (20 passed, 2 warnings)
- `uv run pytest` (27 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q` (RED: `AppSettings` had no `murphy_tts_mode`)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_real_tts_and_llm_modes_from_settings -q` (RED: `DevANpcDialogueClient` had no settings or builder injection)
- `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q` (GREEN: 1 passed)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_real_tts_and_llm_modes_from_settings -q` (GREEN: 1 passed, 2 warnings)
- `uv run pytest` (28 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q` (RED: `AppSettings` had no `murphy_understanding_mode`)
- `uv run pytest backend/tests/test_understanding_agent.py -q` (RED: `UnderstandingAgent` had no settings or LLM client injection)
- `uv run pytest backend/tests/test_settings_service.py::test_app_settings_reads_values_from_env_file -q` (GREEN: 1 passed)
- `uv run pytest backend/tests/test_understanding_agent.py -q` (GREEN: 2 passed)
- `uv run pytest backend/tests/test_preprototype_flow.py -q` (GREEN: 9 passed, 2 warnings after deterministic runtime fixture cache clearing)
- `uv run ruff check .` (passed)
- `uv run mypy .` (initially failed on `UnderstandingLLMClient.model` protocol mutability)
- `uv run mypy .` (passed after using a read-only protocol property)
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_settings_service.py -q` (4 passed)
- `uv run pytest` (42 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_unified_agent_run_log.py -q` (RED: `UnderstandingAgent.last_trace` and `Orchestrator(agent_run_root=...)` were not implemented)
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_unified_agent_run_log.py -q` (GREEN: 3 passed, 1 warning)
- `uv run pytest` (52 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_understanding_llm_client.py backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py::test_orchestrator_advances_family_visit_purpose_to_duration_node -q` (RED: strict schema rejected `extracted_slots`, null slots were not normalized, uncle fallback did not fill `family_visit`, and orchestrator stayed on `REASK`)
- `uv run pytest backend/tests/test_understanding_llm_client.py backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py::test_orchestrator_advances_family_visit_purpose_to_duration_node -q` (GREEN: 8 passed, 2 warnings)
- `uv run pytest` (58 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_understanding_llm_client.py::test_extract_structured_json_preserves_llm_usage backend/tests/test_unified_agent_run_log.py::test_orchestrator_unified_agent_run_includes_understanding_llm_tokens_and_cost -q` (RED: Understanding usage was not preserved and C unified record used zero token/cost values)
- `uv run pytest backend/tests/test_understanding_llm_client.py::test_extract_structured_json_preserves_llm_usage backend/tests/test_unified_agent_run_log.py::test_orchestrator_unified_agent_run_includes_understanding_llm_tokens_and_cost -q` (GREEN: 2 passed, 1 warning)
- `uv run pytest` (60 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_repairs_llm_missing_allowed_visit_purpose_slot -q` (RED: valid LLM output left `intent_success=false` and `visit_purpose` missing)
- `uv run pytest backend/tests/test_preprototype_flow.py::test_orchestrator_uses_repaired_llm_visit_purpose_before_developer_a_dialogue -q` (RED: orchestrator returned `REASK`)
- `uv run pytest backend/tests/test_understanding_agent.py::test_understanding_agent_repairs_llm_missing_allowed_visit_purpose_slot backend/tests/test_preprototype_flow.py::test_orchestrator_uses_repaired_llm_visit_purpose_before_developer_a_dialogue -q` (GREEN: 2 passed, 2 warnings)
- `uv run pytest backend/tests/test_understanding_agent.py backend/tests/test_preprototype_flow.py -q` (GREEN: 16 passed, 2 warnings)
- `uv run pytest` (initial rerun found 2 test-isolation/log-order failures unrelated to the slot repair)
- `uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py::test_developer_b_appends_unified_agent_run_for_success_turn backend/tests/test_unified_agent_run_log.py::test_orchestrator_unified_agent_run_includes_understanding_llm_tokens_and_cost -q` (GREEN: 2 passed, 1 warning after deterministic B feedback mode and C-owner record selection test fixes)
- `uv run pytest` (GREEN: 66 passed, 2 warnings)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `git diff --check` (passed with CRLF conversion warnings only)
- `uv sync` (removed stale `en-core-web-sm==3.8.0` from the local environment)
- `uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_writes_only_unified_agent_run_records backend/tests/test_developer_a_agent_run_logging.py::test_agent_run_store_appends_only_unified_agent_run_jsonl -q` (RED: old `npc_dialogue_agent_runs.jsonl` was still created)
- `uv run pytest backend/tests/test_developer_a_agent_run_logging.py::test_voice_output_writes_only_unified_agent_run_records backend/tests/test_developer_a_agent_run_logging.py::test_agent_run_store_appends_only_unified_agent_run_jsonl -q` (GREEN: 2 passed, 1 warning)
- `uv run pytest backend/tests/test_developer_a_agent_run_logging.py -q` (GREEN: 9 passed, 1 warning)
- `uv run pytest backend/tests/test_unified_agent_run_log.py backend/tests/test_developer_a_agent_run_logging.py -q` (GREEN: 10 passed, 1 warning)
- `uv run ruff check .` (passed)
- `uv run mypy .` (passed)
- `uv run pytest -q` (failed once because the current environment made Developer B log `model_name=gpt-4o-mini` instead of the test-expected `rule_based`)
- `DEV_B_FEEDBACK_LLM_MODE=rule uv run pytest -q` (GREEN: 62 passed, 2 warnings)

## Current Architecture

The current implementation exposes `GET /health` and
`POST /api/game/ai/respond`. The pre-prototype endpoint accepts JSON mock input
and multipart `turn` JSON plus wav input.

The target Developer C architecture is a FastAPI backend that receives wav
audio from Unreal, runs STT, retrieves OpenKB context, runs a deterministic
Understanding Agent, calls replaceable Developer B and Developer A adapters,
records validated error-capture markdown, assembles Unreal response JSON, and
validates all responses before returning them.

# Developer B Update - 2026-06-04

Developer B added a first deterministic `dev_b_policy.v1` policy engine without
modifying C-owned adapters, schemas, OpenKB runtime, orchestrator, validator, or
response builder.

Added B-owned runtime files:

- `backend/app/agents/agent_b/english_level_hint_agent.py`
- `backend/app/services/service_b/scenario_state_machine.py`
- `backend/app/services/service_b/level_adaptation_controller.py`
- `backend/app/data/scenario_nodes.json`
- `backend/app/prompts/english_level_hint_prompt.md`

Added B-focused tests under `backend/tests/dev_b/` to cover clear success,
broken English, clarify, retry/hint, warning/bad-end, allowed next-node guards,
empty allowed-node failure, node JSON coverage, and report/feedback fields.

Coordination request:

- `docs/contracts/change_requests.md` now requests that Developer C wire
  `backend/app/integrations/dev_b_level_hint_client.py` to
  `backend.app.agents.agent_b.EnglishLevelHintAgent` and sync
  `backend/app/data/scenario_nodes.json` into the C-owned OpenKB runtime.

Verification note:

- After the lockfile repair, Developer B verification passes:
  `uv run pytest backend/tests/dev_b -q` reports `10 passed`,
  `uv run pytest` reports `23 passed, 2 warnings`, `uv run ruff check .`
  passes, and `uv run mypy .` passes when run outside the sandbox because the
  sandboxed run cannot access the user-level uv cache.

# Developer B OpenKB Runtime Write Update - 2026-06-04

Developer B now owns runtime feedback/error writes under the OpenKB `dev_b`
namespace. The B policy engine writes deterministic JSONL and markdown records
to `backend/runtime/openkb/dev_b/` through
`backend/app/services/service_b/openkb_feedback_writer.py`. Static B OpenKB
content seeds live under `backend/app/kb/dev_b/`.

Added/changed B write behavior:

- `DevBPolicyOutput` now has an optional additive `openkb_write` field with the
  write attempt status, namespace, record id, JSONL path, markdown path, and
  error message.
- `EnglishLevelHintAgent.evaluate_turn()` builds the policy output first, then
  attempts the B OpenKB write. Writer failures do not change branch, verdict, or
  state delta; they are surfaced through `openkb_write.succeeded == false`.
- Runtime record ids are deterministic from request id, node id, turn index, and
  error ids, so repeated evaluation of the same turn does not append duplicate
  JSONL entries.

Coordination request:

- Developer C should update logging to avoid duplicate error markdown records
  when `dev_b_policy.openkb_write.succeeded == true`.
- Developer C validator should validate B write references for namespace and
  local path safety.
- Developer C final report retrieval should consume B-authored records by
  `openkb_write.record_id`.

# Developer B LLM-Assisted Feedback Update - 2026-06-04

Developer B now has an optional LLM-assisted feedback/hint layer on top of the
deterministic policy engine. Branch, next-node, verdict, and state-delta remain
rule-based. The LLM layer may only improve learning feedback text, report text,
Focus-on-Form explanations, and rubric score candidates.

Added B-owned runtime files:

- `backend/app/agents/agent_b/feedback_hint_llm_client.py`
- `backend/app/services/service_b/feedback_hint_generator.py`
- `backend/app/services/service_b/tier_difficulty_controller.py`

Added optional `DevBPolicyOutput` fields:

- `rubric_scores`
- `difficulty_profile`
- `feedback_generation`

Runtime behavior:

- `DEV_B_FEEDBACK_LLM_MODE=rule` is the default and does not call an external
  model.
- `DEV_B_FEEDBACK_LLM_MODE=llm` enables the B feedback LLM path.
- `DEV_B_FEEDBACK_LLM_MODEL` defaults to `gpt-4o-mini`.
- `DEV_B_FEEDBACK_LLM_TIMEOUT_SECONDS` defaults to `10`.
- `OPENAI_API_KEY` is required only when B LLM mode is enabled and no fake
  client is injected.
- Missing API keys, failed LLM calls, or invalid LLM JSON produce
  `feedback_generation.mode == "fallback"` and preserve the deterministic
  branch/verdict/state.

Coordination request:

- Developer C should treat `rubric_scores`, `difficulty_profile`, and
  `feedback_generation` as optional metadata.
- Developer C validator should ensure these optional fields never override
  branch, next-node, state-delta, or verdict authority.
- Final report generation can use B's OpenKB records to distinguish rule, LLM,
  and fallback feedback sources.

# Developer B Unified AgentRun Logger Update - 2026-06-04

Developer B now appends execution-level AgentRun records using the shared
`unified_agent_run.v1` format already used by Developer A and Developer C. The
new B logger is separate from `OpenKBFeedbackWriter`: OpenKB records remain
learning feedback/error artifacts, while AgentRun records explain the B policy
engine's runtime decision path.

Added/changed files:

- `backend/app/services/service_b/developer_b_agent_run_logger.py`
- `backend/app/agents/agent_b/english_level_hint_agent.py`
- `backend/app/services/service_b/__init__.py`
- `backend/app/integrations/dev_b_level_hint_client.py`
- `backend/app/services/service_c/orchestrator.py`
- `backend/tests/dev_b/test_developer_b_agent_run_log.py`
- `backend/tests/test_unified_agent_run_log.py`
- `docs/portfolio_dev_b.md`

Runtime behavior:

- B records append to `backend/runtime/generated/agent_runs/unified_agent_runs.jsonl`
  and `backend/runtime/generated/agent_runs/unified_agent_runs.md`.
- B uses `agent_name=english_level_hint_agent` and `owner=developer_b`.
- The B event timeline records state-machine, level, hint, feedback strategy,
  form issue, rubric/difficulty, feedback generation, and OpenKB write steps.
- B log summaries store `player_text_preview`, not a full `player_text` field.
- Logger append failures are best-effort and must not change B branch, verdict,
  state delta, or OpenKB write behavior.

Verification commands for this update:

- `uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py -q`
  reports `4 passed`.
- `uv run pytest backend/tests/test_unified_agent_run_log.py -q` reports
  `1 passed, 1 warning`.
- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py backend/tests/dev_b/test_developer_b_agent_run_log.py -q`
  reports `26 passed`.
- `uv run ruff check .` passes.
- `uv run mypy .` passes when run outside the sandbox because the sandboxed
  run cannot access the user-level uv cache.
- `uv run pytest -q` reports `62 passed, 2 warnings`.

# Developer B Objective UI Content Update - 2026-06-04

Developer B added `objective_kr` to Chapter 0 scenario node content and the
shared `NodeContext` schema as an optional field. The field is intended for
Korean Unreal UI objective display, for example `방문 목적 말하기` or `체류 기간
말하기`.

Scope:

- `backend/app/data/scenario_nodes.json` now defines `objective_kr` for every
  Chapter 0 immigration node.
- `backend/app/services/service_c/openkb_service.py` maps `objective_kr` into
  `NodeContext`.
- No `retry_question` or `retry_prompt_seed` field was added. Retry/clarify
  behavior continues to use `npc_question`, B feedback candidates, and Developer
  A dialogue generation.
- Developer C still needs to decide whether and where to expose `objective_kr`
  in the final Unreal response UI payload.

---

Current pre-prototype flow:

```text
Mock Unreal JSON or multipart sample wav
  -> Whisper-large-v3-turbo STT boundary (mock mode in tests, local mode in demo)
  -> Developer C Orchestrator
  -> Developer C OpenKB node_context from backend/app/data/scenario_nodes.json
  -> Developer C Understanding Agent
  -> Developer B Policy Adapter calling EnglishLevelHintAgent
  -> Developer A Dialogue/Voice Adapter calling voice output service
     (fake Kokoro by default, real Kokoro with MURPHY_TTS_MODE=real)
  -> Developer C Response Builder
  -> Developer C Validator
  -> Unreal-safe JSON with npc.audio_url
```

Canonical turn flow:

```text
Unreal wav
  -> Developer C local STT, with API fallback
  -> Developer C Orchestrator
  -> Developer C OpenKB node_context
  -> Developer C Understanding Agent
  -> Developer B Policy / Level / Hint / Feedback Adapter
  -> Developer C Orchestrator
  -> Developer A NPC Dialogue Adapter
  -> Developer C Response Builder
  -> Developer C Validator
  -> Unreal
```

## Contracts / Interfaces

Initial Phase 1 team guardrail, Developer C ownership, dependency, and change
request contracts exist under `docs/contracts/`. `AGENTS.md` now explains
Developer A, B, and C ownership boundaries. Developer A and B start prompts now
exist under `docs/prompts/`. Developer A and Developer B implementation packages
now live under their owner-specific `agent_a`/`service_a` and
`agent_b`/`service_b` folders; Developer C adapters remain the integration
boundary.

New Developer C contract docs:

- `docs/preprototype_status_demo_plan.md` summarizes the current phase status,
  AI-only pre-prototype architecture, target demo request/response plan,
  Developer A/B/C demo responsibilities, and demo readiness criteria.
- `docs/contracts/developer_c_schema_contract.md` defines
  `dev_c_unreal_turn.v1`, STT normalized input, OpenKB node context,
  Understanding output, Developer B policy input mapping, internal turn context,
  and `dev_c_unreal_response.v1`.
- `docs/contracts/developer_c_adapter_contracts.md` defines the STT, OpenKB,
  Understanding, Developer B policy, Developer B final feedback, Developer A
  dialogue, logging, response builder, and validator adapter boundaries.

The Developer B adapter now consumes the broader `dev_b_policy.v1` policy
contract, not only level/hint/branch fields.

Implemented C-owned modules:

- `backend/app/schemas/game_turn.py` contains the pre-prototype Pydantic
  schemas for mock Unreal input, STT normalized input, OpenKB node context,
  Understanding output, Developer A/B adapter payloads, and final response.
- `backend/app/services/service_c/stt_service.py` wraps the configured
  `whisper-large-v3-turbo` model name with real local Whisper transcription,
  OpenAI Transcriptions API fallback, and deterministic mock mode for tests.
- `backend/app/services/service_c/settings_service.py` centralizes `.env` and
  process environment configuration for C-owned runtime settings.
- `backend/app/services/service_c/orchestrator.py` wires STT, OpenKB,
  Understanding, Developer B, Developer A, logging, response building,
  validation, and C-owned unified AgentRun logging.
- `backend/app/middleware/middleware_c/developer_c_agent_run_middleware.py`
  builds the C orchestration AgentRun record and appends it through the shared
  `AgentRunLogStore`.
- `backend/app/services/service_c/validator.py` enforces minimal branch and response
  invariants.
- `backend/app/integrations/dev_b_level_hint_client.py` delegates C's
  `DevBPolicyInput` to Developer B's `EnglishLevelHintAgent`.
- `backend/app/integrations/dev_a_npc_dialogue_client.py` maps C turn context
  and validated B policy output into Developer A's level-design voice output
  service, then returns C-safe dialogue fields plus `audio_url`.
- `backend/app/main.py` serves generated demo wav artifacts from
  `/runtime/audio/...`, backed by `backend/runtime/generated/audio`.

## Dependency State

Package management uses `uv`. Python is set to 3.12. Required runtime and dev
dependencies are recorded in `pyproject.toml` and `uv.lock`, including
`langchain==1.3.2` and `langgraph==1.2.2`.

Local STT dependencies are optional:

```powershell
uv sync --extra local-stt
```

Runtime STT settings:

- `.env.example` is the committed settings template.
- `.env` is local-only and ignored by git.
- `MURPHY_STT_MODE=local` runs local Whisper first.
- `MURPHY_STT_MODE=mock` uses deterministic transcription for tests.
- `MURPHY_STT_LOCAL_MODEL=turbo` uses the local Whisper large-v3-turbo alias.
- `MURPHY_STT_API_MODEL=whisper-1` controls API fallback.
- `OPENAI_API_KEY` is required only if API fallback is needed.

Runtime TTS and NPC dialogue settings:

- `MURPHY_TTS_MODE=fake` keeps deterministic fake Kokoro wav output.
- `MURPHY_TTS_MODE=real` runs Developer A's real Kokoro provider and serves the
  generated wav under `/runtime/audio/...`.
- `MURPHY_NPC_DIALOGUE_MODE=rule` keeps deterministic Developer A dialogue.
- `MURPHY_NPC_DIALOGUE_MODE=llm` enables optional OpenAI NPC dialogue before
  Kokoro TTS and requires `OPENAI_API_KEY`.

Runtime Understanding settings:

- `MURPHY_UNDERSTANDING_MODE=rule` keeps deterministic semantic analysis.
- `MURPHY_UNDERSTANDING_MODE=llm` calls Developer C's OpenAI-backed semantic
  analyzer and falls back to rule mode when the LLM path is unavailable or
  unsafe.
- `MURPHY_UNDERSTANDING_LLM_MODEL=gpt-4o-mini` is the default model.
- `MURPHY_UNDERSTANDING_LLM_TIMEOUT_SECONDS=10` is the default timeout.
- Valid LLM responses can still be post-processed by Developer C when they miss
  a required allowed slot that deterministic evidence can safely recover. The
  current guard only repairs missing `visit_purpose` values such as
  `uncle -> family_visit` and writes the decision to
  `UnderstandingAgent.last_trace.postprocessing`.

Unified AgentRun logging:

- Developer C appends one record per orchestrated turn to
  `backend/runtime/generated/agent_runs/unified_agent_runs.jsonl` and
  `backend/runtime/generated/agent_runs/unified_agent_runs.md`.
- The C record uses `agent_name=ai_backend_orchestrator` and
  `owner=developer_c`.
- Timeline events cover STT, OpenKB, Understanding, Developer B, Developer A,
  response builder, validator, and error-capture boundaries.
- If Understanding LLM mode returns provider usage, the C record's `model`
  object now includes `input_tokens`, `output_tokens`, `total_tokens`, and
  `estimated_cost_usd`. The same summary is copied into the Understanding trace
  event. Developer A/B costs remain in their own AgentRun records.
- `metadata.data_flow` summarizes payload movement between services/agents.
  It intentionally stores compact summaries, not wav bytes, API keys, or full
  provider prompts.

## 2026-06-05 Final Result Score Policy Update

Implemented the remaining Developer B/C pre-prototype final score path.

Changed:

- Added B-owned `FinalResultScorePolicy` and B OpenKB final-result record
  reader under `backend/app/services/service_b/`.
- Added typed `FinalResult`, `FinalScoreState`, `QuantitativeScores`, and
  `UnrealResultResponse` schemas in the C-owned schema layer.
- `DevBPolicyClient.evaluate_turn(...)` now attaches B-scored
  `final_result` on final-branch outputs, and
  `DevBPolicyClient.final_result_for_session(session_id)` exposes the same B
  policy for result UI lookups.
- `/api/game/ai/respond` includes final score data under `report.final_result`
  when B returns it.
- Added `GET /api/game/ai/result/{session_id}` returning
  `dev_c_unreal_result.v1`.
- Developer C validator now checks `final_result.final_score_100`,
  `quantitative_scores.overall`, and `scoring_policy`.
- C-owned Developer A adapter normalizes leading `Alright` to `All right` and
  uses the final node's NPC line for final-branch candidate text.

Score policy:

- Per-turn `rubric_scores.total` is converted from 0-12 to 0-100.
- Chapter 0 v1 uses simple unweighted average.
- `IMM_007_FINAL_DECISION` is excluded from the average when prior scored
  records exist.
- feedback/error/focus-on-form records affect `reason_tags` and
  `report_summary`, not a separate numeric penalty.

Verification so far:

- `uv run pytest backend/tests/dev_b/test_final_result_score_policy.py backend/tests/test_final_result_payload.py backend/tests/test_preprototype_flow.py::test_orchestrator_connects_stt_understanding_dev_b_dev_a_and_response backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_final_node_line_for_final_branch -q`
  passed with 9 tests and 2 warnings.
- `uv sync` passed after using the known uv cache escalation workaround.
- `uv run pytest -q` passed with 76 tests and 2 warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 82 source files after using the
  known uv cache escalation workaround.

The sandboxed `uv sync`, `uv lock`, and `uv run ...` attempts can fail while
initializing the user-level uv cache. Rerunning with approved escalation is the
known workaround in this environment.

## Known Issues

The pre-prototype now wires merged Developer A/B packages through C adapters.
The automated path still uses deterministic STT and fake Kokoro TTS so it
passes without local model downloads, real API keys, Unreal Engine runtime, or
remote OpenKB. STT can execute real local Whisper in `local` mode, but the
first real local run needs `uv sync --extra local-stt`, `ffmpeg`, and time to
download/load the Whisper model. Real Kokoro can execute with
`MURPHY_TTS_MODE=real`, but the first run may download/load model assets and
can emit known torch/Kokoro warnings. Developer C Understanding is still a
deterministic prototype analyzer. The final score/result payload is implemented,
and Developer B has a directly tested Focus-on-Form practice-card report
builder, but C still needs to expose that report as optional out-game feedback.
Generated runtime artifacts for the integrated endpoint are written under
`backend/runtime/generated/` and ignored by git.

## Next Recommended Step

Next, run a live endpoint smoke test on the demo machine with
`MURPHY_STT_MODE=local` and `MURPHY_TTS_MODE=real`, then add API-level retry,
clarify, warning, and bad-end demo cases. After that, implement out-game
feedback/final report and prepare the real Unreal multipart bridge.

## 2026-06-08 Developer B IMMIGRATION_ALPHA Tier Policy Update

Developer B extended the current immigration prototype toward the Alpha
`IMMIGRATION_ALPHA` plan without editing Developer A or Developer C
implementation files.

Changed:

- Added a B-owned Gold-only immigration challenge node,
  `IMM_ALPHA_GOLD_BAG_CONTENT_CHECK`, to `backend/app/data/scenario_nodes.json`.
- Updated B-owned scenario policy so Gold players can route from
  `IMM_005_RETURN_TICKET` into the bag-content challenge when the return-ticket
  answer is strong and the node is allowed.
- Kept Bronze on the baseline immigration route and preserved rule-based branch
  authority.
- Added B-owned output self-checks before OpenKB writes for allowed next-node,
  hint payload, feedback payload, error capture, final-report seed, and rubric
  invariants.
- Added immigration-specific Focus-on-Form target names for final-report seeds,
  including `return_ticket_statement` and `bag_content_explanation`.
- Tightened optional LLM feedback handling so forbidden authority keys such as
  `branch`, `state_delta`, or `verdict` force rule fallback instead of being
  accepted as LLM feedback.
- Expanded `backend/tests/dev_b/test_developer_b_policy_engine.py` to cover
  Bronze baseline routing, Gold challenge routing, final-report seed behavior,
  Dev B output self-checks, and forbidden LLM fallback.

Verification so far:

- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q`
  passed with 29 tests.
- `uv run pytest backend/tests/dev_b -q` passed with 37 tests.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q`
  passed with 26 tests and 2 existing warnings.
- `uv run pytest -q` passed with 117 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 87 source files after using the
  known uv cache permission workaround.

## 2026-06-08 Developer B Direct Next Work Update

Developer B completed the next B-owned Alpha/Chapter 0 package without editing
Developer A or Developer C implementation files.

Changed:

- Expanded Chapter 0 policy tests to cover success and retry behavior across
  playable immigration nodes, the Gold challenge node, and new baggage nodes.
- Added `FocusOnFormReportPolicy` as a B-owned out-game report builder under
  `backend/app/services/service_b/`.
- Added static B-owned Focus-on-Form learning cards under
  `backend/app/kb/dev_b/focus_on_form_cards.json`.
- Added additive OpenKB v2 record metadata:
  `record_schema_version=dev_b_openkb_record.v2` and
  `record_kind=policy_turn_feedback`.
- Added B-owned `BAGGAGE_MISSING` node definitions. The current Alpha route
  now uses `BAG_001_REPORT_MISSING_AT_DESK` through
  `BAG_007_CUSTOMS_CLEARANCE`.
- Added baggage Focus-on-Form target mapping for problem statement, bag
  description, flight/tag statement, delivery request, and follow-up question.
- Preserved existing OpenKB record keys for compatibility.
- Added optional LLM usage capture in AgentRun feedback-generator event
  summaries without exposing usage on public `DevBPolicyOutput`.
- Kept forbidden LLM authority keys in fallback-only mode.
- Converted `backend/app/services/service_b/__init__.py` to lazy exports to
  avoid package import cycles while preserving exported service names.

Change requests:

- Added a C-owned request to expose optional Developer B Focus-on-Form report v1
  metadata through the final result response or a result detail endpoint.

Verification:

- `uv run pytest backend/tests/dev_b/test_focus_on_form_report_policy.py -q`
  passed with 5 tests.
- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py -q`
  passed with 63 tests.
- `uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py -q`
  passed with 6 tests.
- `uv run pytest backend/tests/dev_b -q` passed with 78 tests.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/test_final_result_payload.py backend/tests/test_demo_ai_respond_page.py -q`
  passed with 26 tests and 2 existing warnings.
- `uv run pytest -q` passed with 158 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 89 source files after using the
  known uv cache permission workaround.

## 2026-06-09 Developer B Code Review and Remaining Alpha Plan Update

Developer B reviewed the current Dev B implementation and the 2026-06-08 plan
artifacts.

Dev B-owned fixes:

- `FocusOnFormReportPolicy` now treats
  `out_game_feedback_seed.include_in_final_report=false` as an explicit
  exclusion signal, even when legacy `focus_on_form_targets` are present.
- `FinalResultScorePolicy` now applies the same exclusion rule before adding
  `focus_on_form_recorded` reason tags or report-summary targets.
- Added regression tests for both exclusion paths.
- `backend/app/kb/dev_b/focus_on_form_cards.json` now covers every current
  Dev B Focus-on-Form target emitted by immigration, the Gold challenge, and
  baggage policy nodes.
- `backend/tests/dev_b/test_developer_b_policy_engine.py` now pins
  `DEV_B_FEEDBACK_LLM_MODE=rule` during tests so local `.env` values cannot
  accidentally send default policy tests through the external LLM path.

Cross-owner findings:

- Developer C rule-based `UnderstandingAgent` still handles the deterministic
  prototype mostly through visit-purpose classification. Alpha baggage and
  flight nodes need C-owned understanding coverage for their required slots, or
  an approved LLM-mode/runtime contract.
- Developer A/C dialogue integration currently looks up next-node questions
  only for `IMM_` node ids, so `BAG_` follow-up dialogue will not naturally
  advance in the integrated runtime until that adapter path is expanded.
- Developer C response/result surfaces return B `final_result`, but do not yet
  expose B `FocusOnFormReportPolicy.build_report(...)` as optional
  `out_game_feedback`.
- Alpha scene orchestration for
  `FLIGHT_A_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING`,
  cutscene transition, skip eligibility, and silent level carryover is not yet
  implemented in C-owned runtime code.
- Developer A still needs to consume B difficulty metadata for tier-aware NPC
  response speed/strictness and scene-specific roles such as friendly seatmate
  and baggage service staff.

Docs updated:

- `docs/contracts/change_requests.md` now marks older B integration requests as
  resolved or partially resolved and adds an open Alpha scene-flow request for
  A/C.
- `docs/portfolio_dev_b.md` now reflects that the C adapter delegates to the
  real B engine and that remaining work is Alpha scene/runtime exposure.

## 2026-06-09 Alpha Flow Planning Adjustment

Developer B updated the Alpha planning artifacts after the product direction
changed to include final scenario-end `evaluation` and `out_game_feedback`.

Planning changes:

- Final Alpha scoring should use `scene_normalized_dimension_average` rather
  than raw per-turn averaging, with default scene weights of flight 20%,
  immigration 50%, and baggage 30%.
- Flight small talk still produces a deferred `out_game_feedback_seed`, but the
  final report should frame it as a low-pressure calibration sample rather than
  a surprise grading event.
- Gold immigration strictness should prioritize missing facts, contradictions,
  evasive answers, and credibility risk over harmless grammar mistakes.
- Baggage missing should remain a practical service-desk problem-solving scene,
  not another high-pressure interview.
- Optional post-baggage events should be feature-gated, with at most one enabled
  for the first Alpha pass. Seatmate reunion is the recommended first candidate.

Updated docs:

- `docs/superpowers/plans/2026-06-09-dev-b-remaining-alpha-work.md`
- `docs/superpowers/plans/2026-06-08-alpha-flight-seatmate-smalltalk.md`
- `docs/superpowers/plans/2026-06-08-alpha-immigration.md`
- `docs/superpowers/plans/2026-06-08-alpha-baggage-missing.md`
- `docs/contracts/change_requests.md`

## 2026-06-09 Developer B Remaining Alpha Work Implementation

Developer B implemented the B-owned portions of
`docs/superpowers/plans/2026-06-09-dev-b-remaining-alpha-work.md` without
editing Developer A or Developer C runtime code.

Changed:

- Added `FlightSmallTalkDiagnosticPolicy` with minimum-turn, skip-eligibility,
  deferred-feedback, and fallback-question decisions.
- Added `FLIGHT_A_001_SEATMATE_SMALLTALK` to B-owned scenario node data.
- Updated `EnglishLevelHintAgent` so `FLIGHT_` nodes always create a deferred
  `out_game_feedback_seed` with `smalltalk_response_clarity`.
- Added a `smalltalk_response_clarity` static Focus-on-Form card.
- Updated `FinalResultScorePolicy` numeric computation to scene-normalized
  dimension averages with default Alpha weights: flight 20%, immigration 50%,
  and baggage 30%.
- Added `FocusOnFormReportPolicy.build_session_report(session_id)` for
  scenario-end `out_game_feedback` generation from local `dev_b` JSONL records.
- Added optional Alpha event seed documentation for customs declaration problem,
  stolen passport, and seatmate reunion.

Still C-owned:

- C now accepts both `simple_average` and
  `scene_normalized_dimension_average` score policy names, but final UI
  `out_game_feedback` exposure is still separate from the existing
  `final_result` payload.
- C still needs Unreal-facing cutscene/skip state orchestration for
  `FLIGHT_A_001_SEATMATE_SMALLTALK -> IMMIGRATION_ALPHA -> BAGGAGE_MISSING ->
scenario_end`.

## 2026-06-09 NPC Metadata Ownership Follow-Up

Developer B recorded the next contract-cleanup plan and cross-owner handoff for
removing B-authored NPC wording from the A-facing dialogue path.

Decision summary:

- Developer B must not author final NPC dialogue.
- Developer C should stop passing `node_context.npc_question` to Developer A as
  candidate dialogue.
- Developer C should stop deriving `in_game_feedback.npc_recast_line_candidate`
  from next-node `npc_question`.
- Developer B should not send `dialogue_directive.do_not_generate_npc_text` once
  C removes or relaxes the current schema field.
- `npc_speech_speed` and `question_complexity` should become 0-10 numeric
  metadata after C updates the schema.
- `hint_frequency` is cancelled as A-facing NPC-generation metadata and remains
  B-owned feedback policy only.
- `pressure_level` is cancelled as A-facing NPC-generation metadata and should
  be replaced by word-only `emotion_change`: `positive`, `neutral`, or
  `negative`.
- Runtime JSON should not include `_comment_*` keys. Value explanations belong
  in contract/plan tables.

Docs added or updated:

- `docs/superpowers/plans/2026-06-09-dev-b-npc-metadata-contract-cleanup.md`
- `docs/contracts/change_requests.md`

Ownership split:

- B-owned later work: update B difficulty/emotion policy output after C schema
  support is available.
- C-owned work: update schemas, validators, and the C-to-A adapter payload.
- A-owned work: generate final NPC utterances and TTS wording from metadata
  rather than polishing B/C-provided dialogue text.

## 2026-06-11 Developer B Report and Dialogue Seed Contract

Developer B added additive seed metadata for report assembly and A-facing
dialogue generation without expanding or reordering scenario nodes.

Changed implementation:

- Added optional `report_seed_summary` and `dialogue_seed` models to
  `backend/app/schemas/game_turn.py`.
- Updated `EnglishLevelHintAgent` to derive deterministic report seed metadata
  from existing evaluation, report item, error capture, Focus-on-Form targets,
  and level/tier data.
- Updated `EnglishLevelHintAgent` to emit `dialogue_seed` metadata containing
  scene, NPC role cue, goals, assessment targets, slots, difficulty cue,
  feedback focus, tone guidance, follow-up intents, and stop condition.
- Kept existing `dialogue_directive` for backward compatibility.
- Updated the Dev B OpenKB writer to store `report_seed_summary` and
  `dialogue_seed` in B-owned runtime records.
- Tightened LLM feedback guardrails so `npc_utterance`,
  `final_dialogue_line`, `npc_text`, `tts_text`, animation, and authority keys
  force fallback rather than changing policy output.

Contract/docs updated:

- Added `docs/contracts/developer_b_report_and_dialogue_seed_contract.md`.
- Updated `docs/contracts/developer_b_json_key_value_contract_v1.md`.
- Updated `docs/contracts/developer_b_json_final_v1.md`.
- Updated `docs/contracts/developer_c_adapter_contracts.md`.
- Updated `docs/contracts/developer_c_schema_contract.md`.

Tests added:

- Dev B output contains `report_seed_summary` fields for UI/report assembly.
- Dev B output contains `dialogue_seed` fields for Developer A generation.
- Dev B output does not contain final NPC utterance keys.
- OpenKB Dev B records include the new seeds.
- LLM-assisted feedback cannot return dialogue/final NPC text keys without
  falling back to rule output.

Verification:

- `uv sync` completed. It removed undeclared local package
  `en-core-web-sm==3.8.0` from the virtualenv because it is not part of the
  locked project dependency set.
- `uv run pytest` passed: 173 tests, 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

Known issues / coordination:

- This work does not expose `report_seed_summary` or `dialogue_seed` in the
  Unreal response envelope. Dev C or a future final report assembler should
  decide how to aggregate and present these seeds.
- This work does not remove existing legacy feedback candidate fields such as
  `npc_recast_line_candidate`, because doing so would be a breaking contract
  change. The new `dialogue_seed` is the preferred forward path for NPC
  generation metadata.
- Scenario node expansion, Chapter renaming, IMM node-id changes, and Alpha
  node reordering were intentionally not changed.

## 2026-06-11 Alpha Dev B Scenario Node Expansion

Developer B expanded B-owned Alpha scenario policy and node data. Developer A,
Developer C, and Unreal runtime code were not edited.

Changed implementation:

- Replaced the single flight diagnostic node with a five-turn Dev B node route:
  `FLIGHT_A_001_SEATMATE_SMALLTALK -> FLIGHT_A_002_TRAVEL_PURPOSE ->
FLIGHT_A_003_STAY_PLAN -> FLIGHT_A_004_CLARIFY_OR_ASK_BACK ->
FLIGHT_A_005_WRAP_UP`.
- Updated `FlightSmallTalkDiagnosticPolicy` to require 5 player turns and make
  skip eligibility available at 5 turns.
- Flight nodes now advance to the next evidence node even for retry, clarify,
  hint, warning, or bad-end branch candidates so small talk collects diagnostic
  samples instead of blocking progression.
- Added a mandatory baggage/customs route that starts with
  `BAG_001_REPORT_MISSING_AT_DESK` and ends at `BAG_007_CUSTOMS_CLEARANCE`.
- Routed `BAG_007_CUSTOMS_CLEARANCE` to `ALPHA_999_FINAL_SCOREBOARD` through
  `BAG_999_COMPLETE`.
- Updated `ScenarioStateMachine` so `ALPHA_999_FINAL_SCOREBOARD` is the Dev B
  final-branch node. `IMM_007_FINAL_DECISION` now behaves as an
  immigration-clearance transition in B policy.
- Updated `FinalResultScorePolicy` to exclude both
  `IMM_007_FINAL_DECISION` and `ALPHA_999_FINAL_SCOREBOARD` when prior scored
  records exist.
- Flight `dialogue_seed.max_turns` now uses 5 turns.

Docs updated:

- `docs/contracts/developer_b_json_key_value_contract_v1.md`
- `docs/contracts/developer_b_report_and_dialogue_seed_contract.md`
- `docs/contracts/change_requests.md`

Tests added or updated:

- 5-turn flight diagnostic minimum and skip eligibility.
- Five-node flight route coverage.
- Baggage notice node and Alpha final scoreboard route coverage.
- Flight retry still advances to the next evidence node.
- `ALPHA_999_FINAL_SCOREBOARD` is the only Dev B final branch node.
- Alpha final-scoreboard records are excluded from scored averages when prior
  scored records exist.

Verification:

- `uv sync` completed.
- `uv run pytest` passed: 187 tests, 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

Known issues / coordination:

- Developer C-owned `DevBPolicyClient` now uses `ALPHA_999_FINAL_SCOREBOARD` as
  the Alpha final-result trigger. `IMM_007_FINAL_DECISION` is a transition into
  baggage claim.
- Developer A must generate actual NPC dialogue/TTS for the new `FLIGHT_*` and
  current `BAG_001` through `BAG_007` metadata. Dev B still does not author
  final NPC utterances.
- Unreal must connect flight exit, airport arrival, baggage claim, final
  scoreboard, and ending cinematic flow states.
- The baggage-open/random-item concept is now mandatory in the Alpha baggage
  route; Unreal should reveal the random customs item before
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`.

## 2026-06-12 Alpha Chapter Boundary Transition Nodes

Developer B and Developer C adopted Alpha chapter-boundary transition nodes so
`chapter_id` now represents ordered scenario phases inside
`ALPHA_AIRPORT_ARRIVAL`.

Changed implementation:

- Upgraded `backend/app/data/scenario_nodes.json` to
  `dev_b_scenario_nodes.v2` with top-level `scenario_id`, ordered `chapters`,
  node-level `chapter_id`, and explicit `node_type`.
- Added transition nodes `FLIGHT_999_COMPLETE`, `IMM_999_CLEARED`, and
  `BAG_999_COMPLETE`.
- Routed `FLIGHT_A_005_WRAP_UP`, `IMM_007_FINAL_DECISION`, and
  `BAG_007_CUSTOMS_CLEARANCE` success branches to those transition nodes.
- Added `next_action = COMPLETE_CHAPTER` when Developer B policy reaches a
  chapter transition node.
- Kept `ALPHA_999_FINAL_SCOREBOARD` as the final/result node rather than a
  chapter-complete node.
- Updated Developer C `NodeContext`, OpenKB loading, response building,
  orchestration, and validation for optional `transition` metadata.
- Developer C now passes additive `transition` metadata to the Developer A
  adapter on `COMPLETE_CHAPTER` so A can choose a closing tone without
  generating the next chapter's opening question.
- Removed the Developer C compatibility path that treated
  `IMM_007_FINAL_DECISION` as the final-result trigger.
- Demo request helpers now choose the Alpha chapter id from the node prefix.

Docs updated:

- `docs/contracts/change_requests.md`
- `docs/contracts/developer_b_json_key_value_contract_v1.md`
- `docs/contracts/developer_b_json_final_v1.md`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/contracts/developer_c_schema_contract.md`

Tests added or updated:

- OpenKB node-level `chapter_id` loading and wrong-chapter rejection.
- Transition metadata parsing for chapter-complete nodes.
- Developer B `COMPLETE_CHAPTER` behavior for flight, immigration, and baggage
  boundary transitions.
- Orchestrator integration coverage for Unreal transition events:
  `START_AIRPORT_ARRIVAL_TUTORIAL`, `ENTER_BAGGAGE_CLAIM`, and
  `SHOW_ALPHA_SCOREBOARD`.
- Existing secondary-inspection and final-scoreboard behavior remains covered.

Verification:

- `uv sync` completed.
- `uv run pytest` passed: 199 tests, 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

Known issues / coordination:

- Developer A should treat `next_action=COMPLETE_CHAPTER` as closing-dialogue
  context and must not generate the next chapter's first question from
  `transition.entry_node_id`.
- Unreal should stop current NPC voice-turn capture on `COMPLETE_CHAPTER`,
  consume `transition.unreal_event`, then enter
  `transition.next_chapter_id` / `transition.entry_node_id` when applicable.
- Unreal should not submit player speech turns for `node_type=transition`.
- `CH0_02_ARRIVAL_TUTORIAL` remains chapter metadata only for this backend
  change; there is no AI dialogue node for that phase.

## 2026-06-12 Alpha Flight Smalltalk Route Variants

Developer B expanded `CH0_01_FLIGHT_SMALLTALK` from one fixed 5-turn stream to
three 5-turn route candidates.

Changed implementation:

- Kept the existing Friendly Seatmate route as the default:
  `FLIGHT_A_001_SEATMATE_SMALLTALK -> FLIGHT_A_002_TRAVEL_PURPOSE ->
FLIGHT_A_003_STAY_PLAN -> FLIGHT_A_004_CLARIFY_OR_ASK_BACK ->
FLIGHT_A_005_WRAP_UP -> FLIGHT_999_COMPLETE`.
- Renamed the previous unlabeled `FLIGHT_001..005` route to `FLIGHT_A_001..005`
  so all flight variants use the same A/B/C naming scheme.
- Added Curious Seatmate route:
  `FLIGHT_B_001_DESTINATION_CHAT -> FLIGHT_B_002_COMPANION_OR_VISIT ->
FLIGHT_B_003_STAY_PLACE -> FLIGHT_B_004_TRIP_PLANS ->
FLIGHT_B_005_LANDING_CLOSE -> FLIGHT_999_COMPLETE`.
- Added Travel Form Help route:
  `FLIGHT_C_001_FORM_HELP_REQUEST -> FLIGHT_C_002_FIRST_TIME_ENTRY ->
FLIGHT_C_003_ADDRESS_HELP -> FLIGHT_C_004_HOTEL_HOSTEL_REPAIR ->
FLIGHT_C_005_FORM_CLOSE -> FLIGHT_999_COMPLETE`.
- Added `entry_node_ids` to the flight chapter metadata while preserving
  `entry_node_id = FLIGHT_A_001_SEATMATE_SMALLTALK` as the default.
- Updated B contract docs and change requests for the additive route metadata.

Tests added or updated:

- Scenario node coverage now verifies the three flight route starts and all
  15 dialogue nodes.
- Flight route coverage now verifies that each route has exactly five turns and
  ends at the shared `FLIGHT_999_COMPLETE` transition node.
- Route A coverage verifies that legacy unlabeled `FLIGHT_001..005` node IDs
  are no longer present in scenario node data.

Verification:

- `uv sync` completed.
- `uv run pytest` passed: 200 tests, 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

Known issues / coordination:

- Developer A should add dialogue/TTS coverage for the `FLIGHT_A_*`,
  `FLIGHT_B_*`, and `FLIGHT_C_*` node metadata.
- Unreal can keep using the default `entry_node_id`; when ready, it may select
  one start from `entry_node_ids` and should not mix nodes across routes.

## 2026-06-12 Respond Dialog Flight Start Payload

Developer C demo support was updated so `/respond-dialog` starts from the Alpha
flight first dialogue node instead of the old immigration purpose node.

Changed implementation:

- `demo/respond-dialog/index.html` now uses
  `FLIGHT_A_001_SEATMATE_SMALLTALK` as `firstNodeId`.
- The default turn payload now uses `CH0_01_FLIGHT_SMALLTALK`,
  `SEATMATE_A_01`, and `npc_role = seatmate`.
- The default allowed next node is `FLIGHT_A_002_TRAVEL_PURPOSE`.
- The demo's next-turn updater now auto-loads `FLIGHT_`, `IMM_`, and `BAG_`
  dialogue nodes on `ADVANCE`.

Tests updated:

- `backend/tests/test_demo_ai_respond_page.py` verifies the flight start
  defaults and `FLIGHT_` auto-load support.

## 2026-06-12 Respond Dialog Chapter Start Buttons

Developer C demo support was updated so `/respond-dialog` no longer requires a
Turn JSON upload to start a test turn.

Changed implementation:

- Added chapter start buttons for Flight, Immigration, Baggage, and Result.
- The default selected chapter is Flight:
  `CH0_01_FLIGHT_SMALLTALK` / `FLIGHT_A_001_SEATMATE_SMALLTALK`.
- Clicking a chapter button now regenerates the current turn payload from that
  chapter's configured start node and refreshes the visible NPC first line.
- The generated payload is read-only and kept behind a details panel for
  inspection.
- WAV upload and in-browser recording can submit the current first turn, so
  the first player response no longer needs a preloaded JSON file.

Tests and browser verification:

- `backend/tests/test_demo_ai_respond_page.py` verifies chapter buttons, removed
  `turnFile` upload, generated payload defaults, and recording submission path.
- Browser verification against `http://127.0.0.1:8017/respond-dialog` confirmed
  Flight, Immigration, Baggage, and Result buttons update
  `session.chapter_id`, `session.current_node_id`, active button state, NPC id,
  scene id, and the first visible NPC line.
- Microphone permission was not accepted during automated verification; the
  recording controls and recorded-WAV submission path were verified without
  starting capture.

Verification:

- `uv sync` completed.
- `uv run pytest` passed: 200 tests, 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

## 2026-06-12 Respond Dialog Flight NPC Fallback Diagnosis

Integrated `/respond-dialog` testing exposed an A/C integration gap after the
new Flight chapter start buttons were added.

Observed test turn:

- First NPC line: `Seatmate: Could I borrow your pen for this arrival form?`
- Player STT: `Okay, okay.`
- Returned NPC line: `Officer Miller: Okay. Please continue.`

Runtime diagnosis:

- Developer C received the correct Flight request:
  `CH0_01_FLIGHT_SMALLTALK` /
  `FLIGHT_A_001_SEATMATE_SMALLTALK`.
- STT returned `Okay, okay.`
- Understanding and Developer B treated the turn as successful.
- Developer B returned
  `SUCCESS -> FLIGHT_A_002_TRAVEL_PURPOSE`.
- Developer A returned `speaker = Officer Miller` and
  `text = Okay. Please continue.`

Root cause:

- C's A adapter currently seeds next questions only when the next node id starts
  with `IMM_`, so the Flight next node question was not passed to A.
- A's roster currently falls unknown NPC ids back to `officer_miller`, so
  `SEATMATE_A_01` resolves to Officer Miller.
- A's fallback text is Officer Miller-specific.

Change request added:

- `docs/contracts/change_requests.md`
  `Align Developer A/C NPC Routing for Alpha Non-Immigration Nodes`.

Developer C follow-up:

- Allow `backend/app/integrations/dev_a_npc_dialogue_client.py` to resolve
  next-question seeds for supported Alpha dialogue prefixes beyond `IMM_`,
  including `FLIGHT_` and `BAG_`.
- Preserve and validate A-facing `npc_id`, `npc_role`, and chapter/node context.
- Add diagnostics or validation when requested NPC and returned speaker clearly
  mismatch.
- Add regression coverage for the first Flight success turn verifying the A
  candidate line comes from `FLIGHT_A_002_TRAVEL_PURPOSE`.

Developer A follow-up:

- Add roster profiles for `SEATMATE_A_01`, `SEATMATE_B_01`,
  `SEATMATE_C_01`, and `BAGGAGE_STAFF_01`.
- Derive fallback text, display name, default animation, and voice profile from
  the resolved NPC profile instead of Officer Miller-only defaults.
- Add natural dialogue/TTS behavior for `FLIGHT_A_*`, `FLIGHT_B_*`,
  `FLIGHT_C_*`, and `BAG_*` nodes.
- Keep `COMPLETE_CHAPTER` as a closing-line context.

Current testing caveat:

- `/respond-dialog` can test STT, Understanding, B branching, generated
  payloads, and transition behavior.
- Flight/Baggage NPC speaker and text quality still require A/C follow-up before
  they are reliable integrated test signals.

## 2026-06-12 Baggage Customs Hold Required Flow

Developer B replaced the old missing-bag service route with the mandatory
customs-hold route requested for Alpha baggage claim.

Changed implementation:

- `CH0_04_BAGGAGE_CLAIM` now starts at
  `BAG_001_REPORT_MISSING_AT_DESK`.
- `IMM_999_CLEARED.transition.entry_node_id` now points to
  `BAG_001_REPORT_MISSING_AT_DESK`.
- The baggage route is now:
  `BAG_001_REPORT_MISSING_AT_DESK -> BAG_002_PROVIDE_CLAIM_TAG ->
BAG_003_CONFIRM_SEARCHED_CAROUSEL ->
BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD ->
BAG_005_CUSTOMS_HOLD_EXPLANATION ->
BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM -> BAG_007_CUSTOMS_CLEARANCE ->
BAG_999_COMPLETE`.
- The random customs item explanation is required. Unreal should run the
  unlock/open-suitcase interaction and reveal the random item between
  `BAG_005_CUSTOMS_HOLD_EXPLANATION` and
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`.
- Added Focus-on-Form target `customs_item_explanation`.
- `/respond-dialog` Baggage button now starts from
  `BAG_001_REPORT_MISSING_AT_DESK`.

Developer A follow-up:

- Add or update NPC dialogue/TTS behavior for baggage service staff and customs
  officer roles in the new `BAG_*` route.
- Avoid Officer Miller fallback for baggage/customs NPCs.

Developer C follow-up:

- Ensure Understanding supports the new baggage intents and slots.
- Route the correct NPC context into A for baggage service desk nodes versus
  customs officer nodes.
- Preserve `BAG_999_COMPLETE` transition behavior into
  `ALPHA_999_FINAL_SCOREBOARD`.

Unreal follow-up:

- Implement the mandatory non-dialogue interaction after
  `BAG_005_CUSTOMS_HOLD_EXPLANATION`: show locked suitcase, unlock it, add it
  to inventory, open suitcase UI, reveal random customs item, then start
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`.
- Use `BAG_999_COMPLETE.transition.unreal_event = SHOW_ALPHA_SCOREBOARD` to
  enter the final scoreboard.

Verification:

- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py::test_baggage_route_requires_customs_hold_item_explanation_and_alpha_scoreboard backend/tests/dev_b/test_developer_b_policy_engine.py::test_flight_immigration_baggage_transition_nodes_are_complete_chapter_boundaries backend/tests/dev_b/test_developer_b_policy_engine.py::test_success_branch_advances_to_configured_success_node backend/tests/dev_b/test_developer_b_policy_engine.py::test_retry_branch_returns_same_node_with_retry_action backend/tests/dev_b/test_developer_b_policy_engine.py::test_bronze_broken_english_still_advances_with_feedback_candidate backend/tests/dev_b/test_developer_b_policy_engine.py::test_gold_missing_required_detail_requests_hint_and_focus_form_seed -q`
  passed with 39 tests.
- `uv run pytest backend/tests/test_preprototype_flow.py backend/tests/dev_b/test_focus_on_form_report_policy.py backend/tests/dev_b/test_final_result_score_policy.py backend/tests/test_demo_ai_respond_page.py -q`
  passed with 45 tests and 2 existing warnings.
- `uv sync` completed.
- `uv run pytest` passed with 200 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

## 2026-06-12 Consolidated Alpha A/C/Unreal Handoff

This entry consolidates the current Alpha scenario-node/runtime contract after
the recent chapter-boundary, flight-route, `/respond-dialog`, and baggage
customs-hold changes.

Current implemented state:

- `backend/app/data/scenario_nodes.json` now uses
  `contract_version = dev_b_scenario_nodes.v2` and
  `scenario_id = ALPHA_AIRPORT_ARRIVAL`.
- `chapter_id` is now the ordered Alpha phase, not a whole-scenario namespace:
  `CH0_01_FLIGHT_SMALLTALK`,
  `CH0_02_ARRIVAL_TUTORIAL`,
  `CH0_03_IMMIGRATION_CHECK`,
  `CH0_04_BAGGAGE_CLAIM`,
  `CH0_05_RESULT`.
- Chapter boundary nodes are explicit transition nodes:
  `FLIGHT_999_COMPLETE`,
  `IMM_999_CLEARED`,
  `BAG_999_COMPLETE`.
- Transition branches return `next_action = COMPLETE_CHAPTER` and include
  optional `transition` metadata for Unreal.
- Flight has three 5-turn diagnostic route starts:
  `FLIGHT_A_001_SEATMATE_SMALLTALK`,
  `FLIGHT_B_001_DESTINATION_CHAT`,
  `FLIGHT_C_001_FORM_HELP_REQUEST`.
- Baggage claim now starts at `BAG_001_REPORT_MISSING_AT_DESK` and follows the
  required customs-hold route:
  `BAG_001_REPORT_MISSING_AT_DESK -> BAG_002_PROVIDE_CLAIM_TAG ->
BAG_003_CONFIRM_SEARCHED_CAROUSEL ->
BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD ->
BAG_005_CUSTOMS_HOLD_EXPLANATION ->
BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM -> BAG_007_CUSTOMS_CLEARANCE ->
BAG_999_COMPLETE`.
- `/respond-dialog` can start Flight, Immigration, Baggage, or Result from
  buttons, defaults to Flight, and supports first-turn WAV upload/browser
  recording without JSON upload.

Developer A follow-up:

- Add or map NPC roster/voice profiles for seatmate route A/B/C, baggage
  service staff, and customs officer.
- Stop falling non-immigration NPCs back to Officer Miller.
- Generate natural dialogue/TTS for `FLIGHT_A_*`, `FLIGHT_B_*`,
  `FLIGHT_C_*`, service-desk `BAG_001` through `BAG_004`, and customs-officer
  `BAG_005` through `BAG_007`.
- Treat `COMPLETE_CHAPTER` as a closing-line context only.

Developer C follow-up:

- Extend the Developer A adapter's next-question seed lookup for `FLIGHT_` and
  `BAG_` nodes, not only `IMM_`.
- Preserve and validate A-facing `npc_id`, `npc_role`, `chapter_id`, and
  `node_id` for all Alpha chapters.
- Add diagnostics when requested NPC role and A returned speaker mismatch.
- Add Understanding coverage for the new flight route slots and the new baggage
  customs-hold slots.
- Route BAG NPC context by phase: service staff for `BAG_001` through
  `BAG_004`, customs officer for `BAG_005` through `BAG_007`.
- Pass Unreal-provided random item context into
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` when available.

Unreal follow-up:

- Use chapter metadata to select a Flight route start. The default start is
  `FLIGHT_A_001_SEATMATE_SMALLTALK`.
- Do not submit speech turns for `node_type = transition`.
- On `next_action = COMPLETE_CHAPTER`, stop voice capture and consume
  `transition.unreal_event`, `transition.next_chapter_id`, and
  `transition.entry_node_id`.
- Handle transition events:
  `START_AIRPORT_ARRIVAL_TUTORIAL`,
  `ENTER_BAGGAGE_CLAIM`,
  `SHOW_ALPHA_SCOREBOARD`.
- After `BAG_005_CUSTOMS_HOLD_EXPLANATION`, run the non-dialogue suitcase flow:
  locked suitcase, unlock interaction, add suitcase to inventory, open suitcase
  UI, reveal random customs item, then start
  `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`.

Docs updated:

- `docs/contracts/change_requests.md`
  `Consolidated Alpha Follow-up for Developer A, Developer C, and Unreal`.

Latest verification:

- `uv sync` completed.
- `uv run pytest` passed with 201 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

## 2026-06-12 Developer B NPC Emotion Enum Propagation

Developer B now sends a turn-level NPC emotion cue to Developer C.

Changed implementation:

- Added `NpcEmotion` enum and `DevBPolicyOutput.npc_emotion` to
  `backend/app/schemas/game_turn.py`.
- Developer B sets `npc_emotion` in
  `backend/app/agents/agent_b/english_level_hint_agent.py`.
- Current rule mapping:
  normal success -> `Nomal`, clarify/retry/hint -> `Confusion`,
  warning/bad-end/critical risk -> `Suspicion`.
- Developer C passes the value to Developer A as A-facing `npc.emotion` in
  `backend/app/integrations/dev_a_npc_dialogue_client.py`.
- Developer C returns the same value to Unreal as response `npc.emotion` from
  `backend/app/services/service_c/response_builder.py`.

Allowed emotion values:

```text
Nomal
Joy
Anger
Sadness
Panic
Suspicion
Disgust
Fear
Smirk
Surprise
Pain
Confusion
Boredom
```

Developer A follow-up:

- Use `npc.emotion` as the preferred enum cue for facial expression, TTS style,
  animation tone, and fallback behavior.

Unreal follow-up:

- Consume response `npc.emotion` for NPC expression/animation mapping.

Docs updated:

- `docs/contracts/change_requests.md`
  `Propagate Developer B NPC Emotion Enum`.
- `docs/contracts/developer_b_json_final_v1.md`
- `docs/contracts/developer_c_adapter_contracts.md`
- `docs/contracts/developer_c_schema_contract.md`

Verification:

- `uv sync` completed.
- `uv run pytest` passed with 201 tests and 2 existing warnings.
- `uv run ruff check .` passed.
- `uv run mypy .` passed with no issues in 91 source files.

## 2026-06-12 Developer B LangGraph Policy Wrapper

Developer B refactored the internal `EnglishLevelHintAgent.evaluate_turn()`
flow into a B-owned LangGraph policy graph while preserving the public
`DevBPolicyClient.evaluate_turn(payload) -> DevBPolicyOutput` adapter contract.

Changed implementation:

- Added `backend/app/agents/agent_b/policy_graph.py`.
- Added B-owned graph tool wrappers under `backend/app/tools/tool_b/`.
- Kept `ScenarioStateMachine` as the rule-based branch authority.
- Kept LLM-assisted feedback limited to hint, report, feedback, and rubric
  candidate enrichment.
- Added Developer B AgentRun runtime metadata showing
  `policy_engine = langgraph`, graph name, tool style, and graph node order.
- Updated B `dialogue_seed.npc_role` so BAG service-desk nodes
  `BAG_001` through `BAG_004` use `baggage_service_agent`, while customs-hold
  nodes `BAG_005` through `BAG_007` use `customs_officer`.
- Kept legacy `dialogue_directive.do_not_generate_npc_text` for C adapter
  compatibility. New integration should prefer `dialogue_seed`.

Docs updated:

- `docs/contracts/developer_b_report_and_dialogue_seed_contract.md`

Verification:

- `uv run pytest backend/tests/dev_b -q`: PASS, 109 passed.
- `uv run pytest backend/tests/dev_b/test_developer_b_agent_run_log.py backend/tests/dev_b/test_developer_b_policy_engine.py -q`:
  PASS, 98 passed.
- `uv run pytest backend/tests/test_developer_c_langgraph_orchestrator.py backend/tests/test_preprototype_flow.py backend/tests/dev_b -q`:
  PASS, 144 passed, 2 existing warnings.
- `uv sync`: PASS.
- `uv run pytest`: PASS, 226 passed, 2 existing warnings.
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues in 104 source files.
- `git diff --check`: PASS with Git's normal CRLF working-copy warnings only.
- `rg -n "^<<<<<<<|^=======|^>>>>>>>" .`: PASS, no conflict markers.

Known coordination:

- Developer A/C still own final NPC text, TTS, A-facing adapter payload cleanup,
  and non-immigration NPC roster/voice handling.
- Developer B has not removed the legacy `dialogue_directive` field; retiring
  that field should wait for explicit C adapter confirmation.

## Resume Instructions

Run `uv sync` from the repository root, then run `uv run pytest`,
`uv run ruff check .`, and `uv run mypy .`. Continue from the integrated
pre-prototype flow unless a newer handoff entry supersedes this one.

## 2026-06-12 Developer A Animation Data Update

Developer A updated the NPC default animation and dialogue generation policy to use the temporary "move" data, keeping the `animation` field contract intact for Developer C's Unreal serialization.

Changed:

- Updated `default_animation` value for all roster profiles (including `officer_miller`) to `"move"` in `backend/app/services/service_a/npc_roster_service.py`.
- Updated deterministic, retry, and fallback animation outputs to `"move"` in `backend/app/agents/agent_a/npc_dialogue_agent.py`.
- Updated fallback services (`build_text_fallback` and `voice_output_service` fallbacks) to return `"move"` for `animation` in `backend/app/services/service_a/developer_a_fallback_service.py` and `backend/app/services/service_a/voice_output_service.py`.
- Corrected the `_developer_instructions` prompt in `backend/app/agents/agent_a/npc_llm_client.py` to instruct the LLM to always generate `"move"` for the required `animation` schema field, fixing a prior inconsistency where it referred to a missing `fallback_candidate.animation` input.
- Added a `[tool.ruff]` section in `pyproject.toml` to exclude the `.tmp` directory from global formatting checks, resolving linting issues for un-formatted scratch scripts.
- Updated `docs/contracts/developer_a_agent_spec.md` contract documentation to reflect `"move"` as the example output value for `animation`.
- Updated Developer A tests (`test_developer_a_npc_dialogue.py`, `test_developer_a_npc_roster.py`, `test_developer_a_agent_run_logging.py`, `test_developer_a_npc_llm_client.py`) to verify animation values evaluate to `"move"` instead of specific action codes.

Verification:

- `uv sync`: PASS.
- `uv run pytest`: PASS, 198 passed, 1 warning (deprecation warning for `audioop`).
- `uv run ruff check .`: PASS.
- `uv run mypy .`: PASS, no issues found in 91 source files.

## 2026-06-12 Developer A Plan & Contract Refinements for Dynamic Audio Parameters

Developer A updated the implementation plan and submitted a new Change Request to introduce a unified, single agent design for dynamic emotion and TTS parameter tuning.

Changed:

- Updated `backend/app/agents/agent_a/npc_implementation_plan.md` to design a unified single agent flow where the LLM dynamically calculates ElevenLabs TTS parameters (stability, style, speed, similarity_boost) based on dialogue context and 13 official level design emotion inputs (`joy`, `panic`, `sad`, `suspicion`, `disgust`, `fear`, `smirk`, `normal`, `anger`, `surprise`, `pain`, `confusion`, `boredom`).
- Added dynamic persona resolution to the plan, where Roster profile's `persona_instruction` is resolved by `npc_id` and injected into the LLM system prompt.
- Added a detailed LangChain/LangGraph migration section to the plan under Pinned AI framework versions (`langchain==1.3.2`, `langgraph==1.2.2`). This includes mapping internal helpers/loggers to LangChain standard `BaseTool`/`BaseCallbackHandler` and wrapping `npc_dialogue_agent.py` as a Single Node / Subgraph to plug into Developer C's main orchestrator graph (`developer_c_graph.py`).
- Added a new Change Request to `docs/contracts/change_requests.md` proposing schema and adapter extensions to accept the new audio parameters and 13-type input emotion strings from Level Design.

Coordination:

- Developer C is currently refactoring the backend orchestrator using LangChain/LangGraph. Developer A's updated plan ensures the Dialogue Agent will expose itself as a single node/subgraph rather than trying to own the overall orchestration, avoiding graph and term conflicts.

## 2026-06-16 Developer B Slot Value Validation Plan and Cross-Team Requests

플레이어가 "Um,"(단순 망설임)으로 답했을 때 SUCCESS(ADVANCE)로 오판정되어
잘못된 NPC 대사가 생성되는 버그를 분석했다. 원인은 세 영역에 걸쳐 있으며,
소유권에 따라 작업을 분리했다.

Developer B 소유 작업 (계획 수립 완료, `docs/workplan-dev-b.md`):

- `ScenarioStateMachine`(`backend/app/services/service_b/scenario_state_machine.py`)
  의 `_is_success`가 `intent_success`와 `missing_slots`만 검사하고, 슬롯에
  채워진 값이 `node_context.allowed_slot_values`에 실재하는 후보인지
  검증하지 않는 문제를 확인.
- 계획: `_has_invalid_required_slot_value` 헬퍼를 추가하고 `_is_success`와
  `_is_unclear`에 반영하여, 허용 후보로 매핑되지 않는 슬롯 값을 SUCCESS가
  아닌 clarify(REASK)로 라우팅. 분기 제어는 규칙 기반을 유지(가드레일 준수).
- 회귀/신규 테스트를 `backend/tests/dev_b/test_developer_b_policy_engine.py`에
  추가 예정. 추가 스키마/계약 변경 없음.
- 이 수정이 적용되면 잘못된 SUCCESS가 Developer A로 전달되지 않으므로 Dev A
  측 환각/다음 질문 누락의 발현 조건이 차단된다.

Cross-team change requests (`docs/contracts/change_requests.md`, 2026-06-16):

- Developer C: Understanding Agent가 슬롯 값을 `allowed_slot_values` 후보로
  정규화하고, 매핑 실패/망설임 발화는 임의 자유 텍스트를 채우지 말고
  `intent_success=False` 또는 `needs_clarification=True`로 반환하도록 요청.
  또한 통합 어댑터의 `npc_recast_line_candidate` 강제 None 필터링이 다음 질문
  후보까지 제거하는지 점검 요청.
- Developer A: Dialogue Agent의 화자 역할 혼동/환각 방지 및
  `dialogue_seed.surface_goal` 기반 다음 질문 작문 결합 보강 요청.

Known issue / 제외:

- 남자 목소리(en-US-GuyNeural) 재생 문제는 env(`MURPHY_EDGE_TTS_VOICE`,
  `MURPHY_TTS_PROVIDER`) 수작업 및 Developer A 소유 `voice_output_service.py`
  영역이므로 본 Developer B 작업 범위에서 제외한다.

Next recommended step: `docs/workplan-dev-b.md`의 작업 1~3과 테스트를 구현한 뒤
`uv run pytest` / `uv run ruff check .` / `uv run mypy .`로 검증.

## 2026-06-16 Developer B Slot Value Validation Verified — Root Cause Confirmed in Developer C

Developer B의 슬롯 값 검증 작업을 구현·검증 완료했고, `/respond-dialog`
런타임 재현을 통해 잔여 증상의 책임 소재를 확정했다.

Developer B 작업 검증 결과 (정상 완료):

- `scenario_state_machine.py`에 `_has_invalid_required_slot_value` 헬퍼 추가
  및 `_is_success` / `_is_unclear` 반영 완료.
- `uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py`
  결과 94 passed. 코드·로직·테스트 모두 계획대로 반영됨.

런타임 재현 (책임 소재 확정):

- `FLIGHT_A_001_SEATMATE_SMALLTALK`에서 off-topic 관용구
  `"Okay, you're on."` 입력 시, Understanding Agent가
  `intent_success=true`, `confidence=0.98`, `answer_relevance="on_topic"`,
  `extracted_slots={"polite_response": "short_acknowledgement"}`(유효 정규값),
  `missing_slots=[]`을 반환함.
- 슬롯 값이 허용 후보군에 실재하는 정규값이므로 Developer B의 멤버십 검증은
  이 케이스를 원천적으로 잡을 수 없음(값이 유효하여 통과가 정상 동작).
  상태 머신의 모든 규칙 기반 신호가 SUCCESS를 가리킴 → 이 오판정은
  Understanding Agent(Developer C) 단계에서만 차단 가능.
- 따라서 Developer C 대상 change request(2026-06-16, Understanding Agent
  Slot Value Normalization)에 "Verified Runtime Reproduction" 및
  "Strengthened Request"(정확도 보강)를 추가하고 우선순위를 긴급으로
  상향함.

분기 vs 대사 구분 (중요):

- 로그상 상태 머신은 `FLIGHT_A_001 -> FLIGHT_A_002 | ADVANCE`로 정상
  전진함. "다음 질문으로 넘어가지 않는다"는 증상은 분기(노드) 문제가
  아니라, NPC가 말하는 대사 텍스트가 다음 질문 대신
  `"Sure, here you are. Thanks!"`로 잘못 생성된 Developer A Dialogue Agent
  품질 문제임.

Known issue / 제외 (Developer B 범위 밖, 변동 없음):

- 남자 목소리 재생: env(`MURPHY_EDGE_TTS_VOICE`, `MURPHY_TTS_PROVIDER`
  kokoro→edge 폴백) 수작업 + Developer A `voice_output_service.py` 영역.

Next recommended step: Developer C가 Understanding Agent 분류/정규화 정확도
보강(1차 차단)을 우선 착수. Developer A는 Dialogue Agent 화자 역할/다음 질문
작문 보강. Developer B 추가 작업 없음.

## 2026-06-16 Developer C B-to-A Payload Boundary Cleanup

Developer B's open handoff/change-request items for B-authored NPC wording were
applied in the Developer C adapter boundary.

Changed files:

- `backend/app/integrations/dev_a_npc_dialogue_client.py`
- `backend/tests/test_preprototype_flow.py`
- `docs/contracts/change_requests.md`
- `docs/handoff.md`

Decision:

- Developer A should not receive B-authored model answers or fixed node
  questions as live NPC-generation input.
- Removing `recommended_expression` and `npc_question_goal` from the A-facing
  payload does not block current A generation because A still receives
  `dialogue_seed.surface_goal`, `dialogue_seed.allowed_followup_intents`,
  required slot metadata, branch metadata, the NPC identity, and evaluation
  summary.
- `recommended_expression` remains available for Unreal UI/out-game feedback
  through Developer C response assembly; only the internal B-to-A adapter
  payload is reduced.

Adapter behavior:

- Removed from A-facing `node_context`: `npc_question`, `npc_question_goal`,
  `recommended_expression`.
- Removed from A-facing `in_game_feedback`: `npc_recast_line_candidate`,
  `recommended_expression`.
- Removed from A-facing `level_hint`: `recommended_expression`.
- Removed from A-facing `dialogue_directive`: `do_not_generate_npc_text`,
  `hint_frequency`, `pressure_level`.
- Kept `dialogue_seed.surface_goal` and `allowed_followup_intents` so A can use
  them as topic/intent hints rather than receiving B's final wording.

Verification:

- `uv run pytest backend/tests/test_preprototype_flow.py::test_dev_a_adapter_uses_next_question_seed_without_generic_recast_in_llm_mode backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_npc_context_to_voice_builder backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_flight_seed_and_dialogue_metadata backend/tests/test_preprototype_flow.py::test_dev_a_adapter_forwards_baggage_seed_and_dialogue_metadata -q`
  passed.

## 2026-06-17 Developer C Structured Failure Logging

Developer C investigated a runtime case where Developer A's NPC dialogue
AgentRun showed `fallback_used=true` and `llm.reason="ValueError"` without the
actual exception message. The observable root cause was inside A's LLM dialogue
generation path, but the precise A-owned failure condition could not be
confirmed because the AgentRun stored only the exception type.

Changed C-owned files:

- `backend/app/middleware/middleware_c/developer_c_agent_run_middleware.py`
- `backend/app/tools/tool_c/developer_c_graph_tools.py`
- `backend/app/agents/agent_c/understanding_agent.py`
- `backend/tests/test_developer_c_langgraph_orchestrator.py`
- `backend/tests/test_understanding_agent.py`
- `docs/contracts/change_requests.md`
- `docs/handoff.md`

Behavior added:

- Failed Developer C LangGraph runs now write a structured `error_details`
  block on the failed AgentRun event and in `summary.output.error_details`.
- Understanding Agent LLM fallback traces now include `error_details` with
  `error_type`, `error_message`, `phase`, and `tool_name`.
- The extra details are sanitized and do not include API keys, raw audio, or
  full payload dumps.

Cross-team request:

- Added `docs/contracts/change_requests.md` request asking Developer A and
  Developer B to record structured `error_details` whenever their own tools,
  LLM calls, validators, or fallback paths fail.
- Developer A's highest-priority follow-up is to expand the current
  `llm.reason="ValueError"` output with the exact sanitized exception message
  from the NPC dialogue LLM path.
- The same change request now restates the `candidate_text` boundary:
  `candidate_text` is deprecated A-side normalized input from B's old
  `npc_recast_line_candidate`; A should not consume it as live dialogue, B
  should not rely on it for NPC wording, and C continues stripping
  B-authored dialogue candidates before the A-facing payload.

Verification:

- `uv run pytest backend/tests/test_developer_c_langgraph_orchestrator.py::test_developer_c_failed_agent_run_records_structured_error_details backend/tests/test_understanding_agent.py::test_understanding_agent_falls_back_to_rule_mode_when_llm_output_is_forbidden -q`
  passed.
- `uv run pytest -q` passed: 279 passed, 1 warning.
- `uv run ruff check .` passed.
- `uv run mypy .` passed: no issues found in 118 source files.
