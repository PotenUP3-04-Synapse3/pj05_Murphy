:loudspeaker: *Developer A 작업 머지 사전 공유 (2026-06-19)*
브랜치 `npc_dialogue_agent` → `main` 머지 예정. 본 작업의 결과로 B/C 영역에 알려드릴 사항과 요청사항 정리합니다.

*[A 영역에서 한 일 — 입출력 계약 변경 없음]*
• NPC 단기 메모리 도입: LangGraph `InMemorySaver`로 `(session_id, npc_id)` 격리, N=20 슬라이딩
• 세션 컨텍스트 카드 신설: `confirmed_facts` / `open_hooks` / `forbidden_repeat_questions` / `last_npc_intent` / `recent_turns_compact`를 프롬프트에 노출
• 신규 IMM 9 슬롯·surface_goal 매핑 추가 (B/C의 27 노드 대응)
• SUSPICION MODE 게이팅을 `dialogue_seed.suspicion_scope` 기준으로 정리 (CR-B-CONV-A)
• SPEAKER DISCIPLINE 강화 + `speaker_role_confusion` 후처리 가드
• fallback 분기 우선순위 재구성, fail-fast 도입 (silently 폴백 금지)
• 꼬리물기 가드 `repeats_confirmed_fact` / `weak_followup_no_hook`
• NPC 페르소나 7종에 Pending-request / Topic-discipline 행동 방침 추가
• *평가 하네스 신설*: `backend/tests/eval_harness/` 30개 시나리오 + scorer + pytest smoke

*[B/C에 등록한 Change Request — 처리 부탁]*
:one: *CR-A-E2E-TEST-SYNC* (C) — `test_preprototype_flow.py:863` 단언 한 줄 수정
   ```
   - assert response.npc.text == "Okay. Please continue."
   + assert response.npc.text == "How long will you stay in the United States?"
   ```
   A의 폴백 라인 자연스럽게 개선 → 기존 단언이 깨짐

:two: *CR-A-SESSION-ID-REQUIRED* (C) — `turn.session.session_id` required 명시 + C 어댑터에서 빈 값 사전 검증(4xx)
   A는 `(session_id, npc_id)`로 메모리 격리. 빈 값이면 `ValueError` fail-fast

:three: *CR-A-HISTORY-DEPRECATION* (C) — `_sync_dialogue_history_to_dialogue_seed` 점진 폐지 검토
   A가 자체 NPC 메모리 보유 후 dialogue_history는 cold-start fallback 외 미사용. 페이로드 절감

*[B/C에 알리는 변경 — 코드 작업은 없음]*
• 트집(SUSPICION) 발동 조건이 `suspicion_scope`만 봅니다. B는 `none` / `location` / `declaration` 정확히 emit 부탁
• 신규 surface_goal/슬롯 추가 시 A 매핑 동기화 필요 → *매핑 누락 시 `KeyError`로 즉시 실패*(silently 동작 안 함)
• 평가 하네스가 회귀 검증함. B/C 정책 변경 시 일부 시나리오 깨질 수 있음 → 알려주시면 시나리오 갱신

*[검증]* `uv run pytest`, `ruff check`, `mypy` 모두 그린. 다른 개발자 파일 수정 없음.

*[문서]* 상세본: `docs/handoff_summary_dev_a_2026-06-19.md`
정본 계획서: `docs/plans/dev_a_unified_memory_plan.md`

머지는 직접 진행하겠습니다. 질문/이슈 있으면 스레드에 부탁드려요. :pray:
