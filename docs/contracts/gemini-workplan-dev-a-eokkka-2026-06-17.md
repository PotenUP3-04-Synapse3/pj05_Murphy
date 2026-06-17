# Developer A 작업계획서 (Gemini 인계용) — CR-B-EOKKKA NPC 트집 대사 구현

> 발행: 2026-06-17
> 대상 owner: Developer A
> 관련 CR: `[CR-B-EOKKKA] 억까 장소·수화물 레벨별 배정` (docs/contracts/change_requests.md)
> 본 문서는 Gemini CLI 가 그대로 읽고 실행할 수 있는 self-contained 작업계획서입니다.

---

## ⚠ Gemini 안전 작업 규칙 (반드시 준수)

직전 세션에서 batch write 도중 응답이 잘려 11개 파일이 동시에 truncate 된 사고가 있었습니다. 본 작업 진행 시 다음 규칙을 의무적으로 지켜주세요.

1. **한 번에 한 파일만 수정**. 여러 파일 동시 write 금지.
2. **모든 파일 write 직후 즉시 `python -m py_compile <편집한 파일>` 실행** 으로 자가 검증.
3. **응답 잘림 감지 시 그대로 채택하지 말고 재시도** — 응답 끝에 `<truncated>`, `... to be continued`, 미완성 코드 블록이 있으면 파일에 기록하지 말고 사용자에게 보고.
4. **편집 후 마지막 60자 확인** — 파일이 자연스럽게 종결되는지(`}`, `return`, 닫힌 docstring 등) 확인.
5. **`git commit --no-verify` 사용 금지**.
6. **본 계획에 명시된 5개 파일 외 절대 수정 금지**.
7. **B/C 영역 (`agent_b/`, `agent_c/`, `service_b/`, `service_c/`, `tool_b/`, `tool_c/`, `middleware_b/`, `middleware_c/`, `integrations/`, `schemas/`, `api/`, `graphs/`, `data/`) 0 수정**.

---

## 컨텍스트

CR-B-EOKKKA 는 **플레이어의 진단 레벨(TSL)에 따라 입국심사 "억까 장소"와 세관 "억까 수화물"을 난이도 구간별로 랜덤 배정**해 NPC 가 트집을 잡도록 하는 기능입니다.

**B/C 측은 이미 구현 완료**:
- B: `challenge_tables.py` (장소 17종 · 수화물 18종, 난이도 1-12 + suspicion_reason 태깅), `challenge_assignment_service.py` (`pick_location`, `pick_customs_item`)
- C: `RandomCustomsItemContext` + `difficulty/suspicion_reason` 필드, `GameState` + `assigned_visit_location/ko/difficulty/suspicion_reason`, `DialogueSeed` 에 메타 forward, `validate_dev_b_policy_tool` 에서 전환 노드에서 픽 호출 + GameState 영속화

**A 측은 미구현**. 본 작업이 그 마지막 조각입니다.

**A 가 할 일 (handoff 2026-06-17 entry 발췌):**
> Dev A: `suspicion_reason` 의도대로 NPC 트집 대사 생성(고정 질문 모방 금지), 입국신고서 장소와 동일 지칭 유지.

핵심:
- `dialogue_seed` 의 새 필드(`assigned_visit_location`, `assigned_visit_location_ko`, `visit_location_difficulty`, `visit_location_suspicion_reason`, `random_customs_item.*`) 를 LLM 프롬프트에 주입
- **B 가 작성한 고정 질문은 어댑터 경계(`_A_BLOCKED_*`)에서 차단**되므로 A 가 메타데이터만 보고 트집 대사 생성
- 입국신고서 UI 에 적힌 장소명과 NPC 발화의 장소명이 정확히 일치해야 함 (Unreal 측에서도 같은 `assigned_visit_location` 사용)

예시:
- `assigned_visit_location = "MGM Grand Las Vegas"`, `difficulty=10`, `suspicion_reason="luxury_hotel_at_business_trip"` 으로 오면
- NPC 가 "MGM Grand in Las Vegas? That's pretty upscale for a business trip. Who's paying?" 같은 트집 대사를 만들어야 함

---

## 작업 ① — `dialogue_seed` 새 필드 normalize (10분)

### 목적
A 측 페이로드 정규화에서 dialogue_seed 의 새 필드를 안전하게 추출해 후속 단계(프롬프트 변수, 룰베이스 폴백)에서 일관되게 사용 가능하도록 한다.

### 대상 파일
- `backend/app/services/service_a/developer_a_input_service.py`

### 작업 단계

1. **현재 normalize 코드 확인:**
   ```powershell
   Select-String -Path backend\app\services\service_a\developer_a_input_service.py -Pattern "dialogue_seed|random_customs_item" -Context 0,2
   ```

2. **`dialogue_seed` 객체 안에 새 필드가 안전히 통과하는지 확인.** 이미 `payload.get("dialogue_seed") or {}` 로 dict 통째로 받고 있으면 추가 코드 불필요. 다만 normalize 단계에서 다음 편의 키를 추가해 후속 활용을 쉽게:
   ```python
   dialogue_seed = payload.get("dialogue_seed") or {}
   game_state = payload.get("game_state") or {}
   normalized["assigned_visit_location"] = (
       dialogue_seed.get("assigned_visit_location")
       or game_state.get("assigned_visit_location")
       or ""
   )
   normalized["assigned_visit_location_ko"] = (
       dialogue_seed.get("assigned_visit_location_ko")
       or game_state.get("assigned_visit_location_ko")
       or ""
   )
   normalized["visit_location_difficulty"] = (
       dialogue_seed.get("visit_location_difficulty")
       or game_state.get("visit_location_difficulty")
       or 0
   )
   normalized["visit_location_suspicion_reason"] = (
       dialogue_seed.get("visit_location_suspicion_reason")
       or game_state.get("visit_location_suspicion_reason")
       or ""
   )
   ```
   (`random_customs_item` 은 이미 normalize 됨 — handoff 확인.)

3. **자가 검증:**
   ```powershell
   python -m py_compile backend\app\services\service_a\developer_a_input_service.py
   Get-Content backend\app\services\service_a\developer_a_input_service.py -Tail 5
   ```

### 수용 기준
- [ ] py_compile 통과
- [ ] 마지막 60자 자연 종결 확인
- [ ] B/C 영역 0 수정

---

## 작업 ② — LLM 페이로드에 트집 컨텍스트 주입 (15분)

### 목적
`node_generate_dialogue_llm` 또는 동등 위치에서 LLM 호출 직전 새 필드를 시스템 프롬프트 변수로 주입.

### 대상 파일
- `backend/app/agents/agent_a/npc_dialogue_agent.py`

### 작업 단계

1. **현재 llm_payload 생성 코드 확인:**
   ```powershell
   Select-String -Path backend\app\agents\agent_a\npc_dialogue_agent.py -Pattern "llm_payload\s*=" -Context 0,15
   ```

2. **`llm_payload` 에 다음 키 추가** (이미 `normalized` 가 통째로 들어가면 추가 불필요. 확인 후 누락 시 명시적 키로 추가):
   ```python
   llm_payload["assigned_visit_location"] = normalized.get("assigned_visit_location", "")
   llm_payload["assigned_visit_location_ko"] = normalized.get("assigned_visit_location_ko", "")
   llm_payload["visit_location_difficulty"] = normalized.get("visit_location_difficulty", 0)
   llm_payload["visit_location_suspicion_reason"] = normalized.get("visit_location_suspicion_reason", "")
   llm_payload["random_customs_item"] = normalized.get("random_customs_item") or ""
   # random_customs_item 의 difficulty/suspicion_reason 도 있다면 함께
   ```

3. **자가 검증:**
   ```powershell
   python -m py_compile backend\app\agents\agent_a\npc_dialogue_agent.py
   Get-Content backend\app\agents\agent_a\npc_dialogue_agent.py -Tail 5
   ```

### 수용 기준
- [ ] py_compile 통과
- [ ] 마지막 60자 자연 종결 확인
- [ ] 새 키가 LLM 입력으로 전달됨

---

## 작업 ③ — 시스템 프롬프트에 트집 모드 가이드 추가 (20분)

### 목적
LLM 이 "고정 질문 모방 금지 + 메타 의도대로 트집 질문 생성 + 입국신고서 장소명과 동일 지칭" 규칙을 따르도록 프롬프트에 명시.

### 대상 파일
- `backend/app/prompts/npc_dialogue_prompt.md`

### 작업 단계

1. **현재 프롬프트 구조 확인:**
   ```powershell
   Get-Content backend\app\prompts\npc_dialogue_prompt.md
   ```

2. **Jinja2 조건 블록으로 트집 모드 섹션 추가** (기존 진단 모드 블록 형식과 동일 패턴 유지):
   ```markdown
   {% if assigned_visit_location or random_customs_item %}
   ## SUSPICION MODE (Immigration Eokkka / Customs Item Challenge)

   The player has been assigned a context the NPC is supposed to **challenge** (트집).
   You are an immigration/customs officer probing the player's answer.

   ### Assigned Context
   {% if assigned_visit_location %}
   - **Visit location** (must match the player's arrival form exactly):
     - English: `{{ assigned_visit_location }}`
     - Korean: `{{ assigned_visit_location_ko }}`
     - Difficulty: {{ visit_location_difficulty }} / 12
     - Suspicion reason: `{{ visit_location_suspicion_reason }}`
   {% endif %}
   {% if random_customs_item %}
   - **Customs item**: `{{ random_customs_item }}`
     {% if random_customs_item_difficulty %}- Difficulty: {{ random_customs_item_difficulty }} / 12{% endif %}
     {% if random_customs_item_suspicion_reason %}- Suspicion reason: `{{ random_customs_item_suspicion_reason }}`{% endif %}
   {% endif %}

   ### Hard Rules
   1. **DO NOT** invent a different visit location or customs item. Always reference
      the exact `assigned_visit_location` or `random_customs_item` above.
   2. **DO NOT** copy any fixed question that B might have authored. Build your
      own challenge dialogue from the suspicion_reason intent.
   3. The visit_location string must appear **verbatim** in your dialogue
      (e.g. "MGM Grand Las Vegas", not "a hotel in Las Vegas").
   4. Higher difficulty → more pointed, more skeptical, more specific suspicion.
      Lower difficulty → softer probing, give the player a chance.
   5. The line must still be a single short utterance (1–2 sentences max).
      No multi-paragraph interrogations.

   ### Examples (do NOT copy verbatim; vary phrasing)
   - location="MGM Grand Las Vegas", suspicion_reason="luxury_hotel_at_business_trip":
     "MGM Grand in Las Vegas? That's pretty upscale for a business trip. Who's covering the bill?"
   - customs_item="red ginseng box", suspicion_reason="bulk_quantity":
     "That's a lot of red ginseng for personal use. Who is it for?"
   {% endif %}
   ```

3. **`npc_dialogue_prompt.short.md` 에도 압축된 버전 추가** (vLLM 폴백용):
   ```markdown
   {% if assigned_visit_location or random_customs_item %}
   SUSPICION MODE: probe the assigned context as an officer.
   Visit location: {{ assigned_visit_location }} (must appear verbatim)
   Customs item: {{ random_customs_item }}
   Suspicion: {{ visit_location_suspicion_reason }}{{ random_customs_item_suspicion_reason }}
   Rules: never invent another location/item; never copy a fixed question; one short line.
   {% endif %}
   ```

4. **자가 검증:**
   ```powershell
   Get-Content backend\app\prompts\npc_dialogue_prompt.md -Tail 5
   Get-Content backend\app\prompts\npc_dialogue_prompt.short.md -Tail 5
   # 프롬프트 파일은 py_compile 대상 아님 — 단순 마크다운 텍스트
   ```

5. **렌더링 smoke 테스트** (Jinja 변수 누락 시 KeyError 방지):
   ```powershell
   uv run python -c @"
   from backend.app.agents.agent_a.npc_llm_client import _developer_instructions
   ctx = {
       'persona_instruction': 'stern immigration officer',
       'npc_role': 'immigration_officer',
       'english_level': 'A2',
       'incivility_tier': 0,
       'profanity_mode': 'mirror',
       'assigned_visit_location': 'MGM Grand Las Vegas',
       'assigned_visit_location_ko': 'MGM 그랜드 라스베가스',
       'visit_location_difficulty': 10,
       'visit_location_suspicion_reason': 'luxury_hotel_at_business_trip',
       'random_customs_item': '',
       'random_customs_item_difficulty': 0,
       'random_customs_item_suspicion_reason': '',
       'dialogue_purpose': 'default',
       'length_target': 12,
       'topic_switch': False,
       'discussed_topics': [],
       'past_player_utterances': [],
       'allowed_mild': [],
       'allowed_strong': [],
       'non_verbal_palette': [],
       'surface_goal': '',
   }
   out = _developer_instructions(ctx)
   assert 'MGM Grand Las Vegas' in out
   print('OK — suspicion mode prompt rendered')
   print(out[-500:])
   "@
   ```
   ⚠ `_developer_instructions` 시그니처가 다르면 그에 맞게 호출 조정. 핵심은 새 변수가 KeyError 없이 렌더링되는지.

### 수용 기준
- [ ] 두 프롬프트 파일에 SUSPICION MODE 블록 추가
- [ ] 마지막 60자 자연 종결
- [ ] Jinja 렌더링 smoke 테스트 "OK" 출력

---

## 작업 ④ — 룰베이스 폴백 보강 (10분)

### 목적
LLM 실패 시 generic 폴백("Okay. Please continue.") 으로 떨어지지 않고, assigned_visit_location/customs_item 을 활용한 트집 폴백 사용.

### 대상 파일
- `backend/app/services/service_a/developer_a_fallback_service.py`

### 작업 단계

1. **현재 `build_text_fallback` 분기 확인:**
   ```powershell
   Select-String -Path backend\app\services\service_a\developer_a_fallback_service.py -Pattern "def build_text_fallback|surface_goal|random_customs_item" -Context 0,3
   ```

2. **새 분기 추가** (기존 `explain_random_customs_item` 분기와 같은 위치, generic else 직전):
   ```python
   # CR-B-EOKKKA 트집 모드 폴백
   assigned_visit_location = normalized.get("assigned_visit_location", "").strip()
   if assigned_visit_location:
       text = f"{assigned_visit_location}? Tell me more about that."
       reason = "suspicion_visit_location_seeded"
   elif random_item:   # 기존 변수
       text = f"{random_item}? What is this for?"
       reason = "suspicion_customs_item_seeded"
   else:
       text = "Okay. Please continue."
       reason = "default_text_fallback"
   ```
   (기존 fallback reason 명칭 정리 작업이 미수행 상태면 `reason` 변수 도입은 선택 — 일단 본 작업은 텍스트만 분기.)

3. **자가 검증:**
   ```powershell
   python -m py_compile backend\app\services\service_a\developer_a_fallback_service.py
   Get-Content backend\app\services\service_a\developer_a_fallback_service.py -Tail 5
   ```

### 수용 기준
- [ ] py_compile 통과
- [ ] LLM 실패 시 폴백 응답이 assigned_visit_location 을 포함 (예: `"MGM Grand Las Vegas? Tell me more..."`)
- [ ] random_customs_item 만 있을 때 그쪽으로 폴백

---

## 작업 ⑤ — 회귀 테스트 추가 (15분)

### 목적
정상 경로 + 폴백 경로 + 입국신고서 장소 동일 지칭 유지가 회귀에서 보호됨.

### 대상 파일
- `backend/tests/test_developer_a_npc_dialogue.py`

### 작업 단계

1. **기존 테스트 패턴 확인:**
   ```powershell
   Get-Content backend\tests\test_developer_a_npc_dialogue.py | Select-Object -First 50
   ```

2. **신규 테스트 4개 추가** (기존 fixture 패턴 따라 작성):

   ```python
   def test_dialogue_agent_includes_assigned_visit_location_in_prompt(monkeypatch):
       """CR-B-EOKKKA: dialogue_seed 의 assigned_visit_location 이 LLM 페이로드에 그대로 전달됨."""
       payload = _eokkka_payload(
           assigned_visit_location="MGM Grand Las Vegas",
           visit_location_suspicion_reason="luxury_hotel_at_business_trip",
           visit_location_difficulty=10,
       )
       captured = {}
       monkeypatch.setattr(
           "backend.app.agents.agent_a.npc_dialogue_agent.build_npc_dialogue_llm_client_from_environment",
           lambda: _CapturingLLMClient(captured),
       )
       generate_npc_dialogue_from_level_design(payload, use_llm=True)
       assert "MGM Grand Las Vegas" in str(captured.get("payload", {}))

   def test_dialogue_agent_fallback_seeds_assigned_visit_location():
       """LLM 실패 시 폴백이 generic 이 아닌 assigned_visit_location 시드 응답."""
       payload = _eokkka_payload(assigned_visit_location="MGM Grand Las Vegas")
       result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
       # 룰베이스 시드 시점에 MGM Grand Las Vegas 가 텍스트에 포함되어야 함
       assert "MGM Grand Las Vegas" in result["npc_text"]

   def test_dialogue_agent_fallback_seeds_customs_item():
       """customs item 시드 폴백."""
       payload = _eokkka_payload(random_customs_item="red ginseng box")
       result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
       assert "red ginseng" in result["npc_text"].lower()

   def test_dialogue_agent_no_suspicion_meta_uses_default_fallback():
       """assigned_visit_location 도 customs_item 도 없으면 기존 default 폴백 유지."""
       payload = _eokkka_payload()
       result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
       assert result["npc_text"]  # 기존 동작 회귀 보호
   ```

3. **헬퍼 `_eokkka_payload` + `_CapturingLLMClient` 는 동일 파일 상단에 추가** (기존 헬퍼 패턴과 동일 스타일).

4. **자가 검증:**
   ```powershell
   python -m py_compile backend\tests\test_developer_a_npc_dialogue.py
   uv run pytest backend\tests\test_developer_a_npc_dialogue.py -q
   ```

### 수용 기준
- [ ] 4개 신규 테스트 모두 그린
- [ ] 기존 테스트 회귀 무영향

---

## 머지 전 종합 체크리스트

- [ ] `uv run pytest backend\tests -q` 그린 (302+ 통과 기준)
- [ ] `uv run ruff check .` 0 errors
- [ ] `uv run mypy .` 0 errors
- [ ] Jinja 렌더링 smoke 통과
- [ ] `/respond-dialog` 수동 회귀:
  - Flight 진행 → `FLIGHT_999_COMPLETE` 통과 → IMM 진입 시 assigned_visit_location 이 NPC 첫 질문에 verbatim 포함됨
  - Immigration 진행 → `IMM_999_CLEARED` 통과 → Baggage 진입 시 random_customs_item 이 NPC 질문에 포함됨
- [ ] `git diff --stat` 결과가 다음 5개 파일 외 0:
  - `backend/app/services/service_a/developer_a_input_service.py`
  - `backend/app/agents/agent_a/npc_dialogue_agent.py`
  - `backend/app/prompts/npc_dialogue_prompt.md`
  - `backend/app/prompts/npc_dialogue_prompt.short.md`
  - `backend/app/services/service_a/developer_a_fallback_service.py`
  - `backend/tests/test_developer_a_npc_dialogue.py`
- [ ] B/C 영역 0 수정 (`git diff --stat | grep -E "(agent_b|agent_c|service_b|service_c|tool_b|tool_c|middleware_b|middleware_c|integrations|graphs|api|schemas|data)"` 결과 0)

---

## handoff entry 초안

```markdown
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
```

---

## 참고

- 본 계획서 가정 main 상태: `git log --oneline -1` → `0761086 Merge pull request #49 from PotenUP3-04-Synapse3/level_agent`
- 작업 분량: 총 ~70~80분
- 우선순위: ① → ② → ③ → ④ → ⑤ 순서
- 도구 사용 권장: Edit (line-by-line), Read (확인용)
- **Write (전체 덮어쓰기) 금지** — 한 줄씩 정확히 수정. truncation 사고 방지.
