# Developer A 작업계획서 (Gemini 인계용) — CR-B-CONV-A 트집 게이팅·히스토리 소비·대사 변주

> 발행: 2026-06-18
> 대상 owner: Developer A
> 관련 CR: `[CR-B-CONV-A] 트집 게이팅·히스토리 소비·대사 변주` (docs/contracts/change_requests.md)
> 본 문서는 Gemini CLI 가 그대로 읽고 실행할 수 있는 self-contained 작업계획서입니다.

---

## ⚠ Gemini 안전 작업 규칙 (반드시 준수)

직전 세션에서 batch write 도중 응답이 잘려 11개 파일이 동시에 truncate 된 사고가 있었습니다.

1. **한 번에 한 파일만 수정**. 여러 파일 동시 write 금지.
2. **모든 파일 write 직후 즉시 `python -m py_compile <편집한 파일>` 실행** 으로 자가 검증.
3. **응답 잘림 감지 시 그대로 채택하지 말고 재시도** — 응답 끝에 `<truncated>` / `... to be continued` / 미완성 코드 블록이 있으면 파일에 기록하지 말고 사용자에게 보고.
4. **편집 후 마지막 60자 확인** — 파일이 자연스럽게 종결되는지(`}`, `return`, 닫힌 docstring 등) 확인.
5. **`git commit --no-verify` 사용 금지**.
6. **본 계획에 명시된 6개 파일 외 절대 수정 금지**.
7. **B/C 영역 0 수정** (`agent_b/`, `agent_c/`, `service_b/`, `service_c/`, `tool_b/`, `tool_c/`, `integrations/`, `schemas/`, `api/`, `graphs/`, `data/`).
8. **Edit 도구로 line-by-line 수정**. Write 전체 덮어쓰기 금지.

---

## 컨텍스트

### 문제 현황 (CR-B-CONV-A Reason 발췌)
CR-B-EOKKKA 로 도입된 SUSPICION MODE 블록(`prompts/npc_dialogue_prompt.md:80` Rule 3 verbatim 강제)이 **할당만 되면 모든 입국심사 노드에서 활성**됩니다. 그래서:
- 방문 목적 노드(`IMM_002_PURPOSE`)인데 "Downtown Luxury Hotel" 이 박힘
- 플레이어가 답하기도 전에 트집
- 메인 시나리오에 히스토리 미전달 → 이미 답한 질문 반복
- stern/retry 대사가 무변주 동일 문장 반복

**트집은 핵심 재미** 이므로 제거가 아니라 **게이팅**이 필요합니다.

### B/C 가 이미 보내는 신호 (소비만 하면 됨)
| 신호 | 발행자 | 위치 | 의미 |
|---|---|---|---|
| `DialogueSeed.suspicion_scope` | B (06-18) | `Literal["location","declaration","none"]` | 트집 모드 활성 범위 |
| `DialogueSeed.dialogue_history` | C (06-18) | `list[TurnHistoryEntry]` (player/NPC previews + filled_slots) | 단기 대화 메모리 (현재 턴 제외) |
| `_sync_challenge_context_to_dialogue_seed` | C (06-18) | scope=`location` → location 만 / `declaration` → item 만 / `none` → 모두 clear | A 가 받기 전 게이팅 |

→ A 측은 **이미 도착한 신호를 읽어서 프롬프트/페이로드 게이팅만 추가**하면 됩니다.

### A 측 4 작업 (CR-B-CONV-A Proposed Contract Change)

1. **트집 게이팅**: SUSPICION MODE 활성 조건을 `assigned_visit_location` 존재 → `suspicion_scope` 신호로 변경.
2. **답변 후 발동 + verbatim 완화**: 선제 블러팅 금지, Rule 3 verbatim 강제 완화.
3. **히스토리 소비(전 노드)**: `llm_payload` 에 `dialogue_history` 주입, "답변된 질문 반복 금지" 가이드 smalltalk 전용 제약 해제 → 모든 purpose 적용.
4. **대사 변주**: stern/retry 반복 시 동일 문장 반복 방지, `recommended_expression` 모범답안 힌트 1회 제시.

---

## 작업 ① — Input service 에서 새 신호 normalize (10분)

### 목적
B/C 가 보낸 `suspicion_scope` + `dialogue_history` 를 A normalize 단계에서 안전 추출.

### 대상 파일
- `backend/app/services/service_a/developer_a_input_service.py`

### 작업 단계

1. **현재 dialogue_seed 추출 위치 확인:**
   ```powershell
   Select-String -Path backend\app\services\service_a\developer_a_input_service.py -Pattern "dialogue_seed" -Context 0,3
   ```

2. **기존 `assigned_visit_location` 등 추출 직후에 추가** (existing dialogue_seed 객체 활용):
   ```python
   # 기존 normalize 블록 안, dialogue_seed = payload.get("dialogue_seed") or {} 직후
   normalized["suspicion_scope"] = (
       dialogue_seed.get("suspicion_scope")
       or "none"
   )
   normalized["dialogue_history"] = list(dialogue_seed.get("dialogue_history") or [])
   ```

3. **자가 검증:**
   ```powershell
   python -m py_compile backend\app\services\service_a\developer_a_input_service.py
   Get-Content backend\app\services\service_a\developer_a_input_service.py -Tail 5
   Select-String -Path backend\app\services\service_a\developer_a_input_service.py -Pattern "suspicion_scope|dialogue_history" -SimpleMatch
   ```

### 수용 기준
- [ ] `normalized["suspicion_scope"]` 기본값 `"none"` 으로 안전 폴백
- [ ] `normalized["dialogue_history"]` 빈 리스트 안전 폴백
- [ ] py_compile 통과 + 마지막 60자 자연 종결

---

## 작업 ② — `llm_payload` 에 두 필드 주입 (10분)

### 대상 파일
- `backend/app/agents/agent_a/npc_dialogue_agent.py`

### 작업 단계

1. **현재 llm_payload 생성 위치 확인:**
   ```powershell
   Select-String -Path backend\app\agents\agent_a\npc_dialogue_agent.py -Pattern "llm_payload\s*=|llm_payload\[" -Context 0,3
   ```

2. **모든 purpose 에서 두 필드 주입** (smalltalk_diagnostic 전용 제약 해제):
   ```python
   # llm_payload 생성/보강 부분에 추가
   llm_payload["suspicion_scope"] = normalized.get("suspicion_scope", "none")
   llm_payload["dialogue_history"] = normalized.get("dialogue_history", [])
   ```

3. **기존 smalltalk 전용 `discussed_topics` / `past_player_utterances` 분기 확인:**
   ```powershell
   Select-String -Path backend\app\agents\agent_a\npc_dialogue_agent.py -Pattern "discussed_topics|past_player_utterances" -Context 0,3
   ```
   - 이 두 필드의 주입이 `is_smalltalk_diagnostic` 조건 안에 있으면 **조건을 풀어 모든 purpose 에서 dialogue_history 기반으로 채워지도록** 변경. 단 smalltalk 전용 OpenKB 로딩 로직은 그대로 유지하고, immigration/baggage 등에서는 `normalized["dialogue_history"]` 의 player/npc preview 를 그대로 활용:
     ```python
     # before (smalltalk 전용)
     if is_smalltalk_diagnostic:
         llm_payload["discussed_topics"] = ...
         llm_payload["past_player_utterances"] = ...

     # after (모든 purpose, C dialogue_history 가 있으면 그것 우선)
     history = normalized.get("dialogue_history", [])
     llm_payload["past_player_utterances"] = [
         h.get("player_text_preview", "") for h in history if h.get("player_text_preview")
     ]
     llm_payload["discussed_topics"] = [
         h.get("npc_text_preview", "") for h in history if h.get("npc_text_preview")
     ]
     if is_smalltalk_diagnostic:
         # 기존 OpenKB 로딩 로직 유지 (smalltalk 전용 보강)
         ...
     ```
   ⚠ smalltalk 전용 OpenKB 로딩 로직 자체는 보존. C 가 보낸 dialogue_history 가 우선이지만 smalltalk 에서는 더 풍부한 OpenKB 이력도 보충.

4. **자가 검증:**
   ```powershell
   python -m py_compile backend\app\agents\agent_a\npc_dialogue_agent.py
   Get-Content backend\app\agents\agent_a\npc_dialogue_agent.py -Tail 5
   ```

### 수용 기준
- [ ] suspicion_scope, dialogue_history 가 모든 purpose 에서 llm_payload 에 주입
- [ ] smalltalk 전용 OpenKB 보강은 보존
- [ ] immigration/baggage 노드에서도 dialogue_history 가 전달됨

---

## 작업 ③ — SUSPICION MODE 게이팅 변경 + 답변 후 발동 + verbatim 완화 (20분)

### 대상 파일
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`

### 작업 단계

1. **현재 SUSPICION MODE 블록 위치 확인** (md L80 부근):
   ```powershell
   Select-String -Path backend\app\prompts\npc_dialogue_prompt.md -Pattern "SUSPICION MODE|assigned_visit_location|random_customs_item" -Context 0,5
   ```

2. **Jinja2 게이팅 조건 교체** — 기존:
   ```jinja
   {% if assigned_visit_location or random_customs_item %}
   ## SUSPICION MODE ...
   ```

   변경:
   ```jinja
   {% if suspicion_scope and suspicion_scope != "none" %}
   ## SUSPICION MODE (Immigration Eokkka / Customs Item Challenge)

   The player has been assigned a context the NPC may **challenge** (트집).
   You are an immigration/customs officer probing the player's answer — but only
   when the relevant slot has been answered. Do NOT challenge preemptively.

   ### Suspicion Scope
   - Current scope: `{{ suspicion_scope }}`
     - `location` — challenge the visit location only (relevant on visit-purpose / stay-location turns).
     - `declaration` — challenge the customs item / declaration only (relevant on declaration / customs turns).
     - `none` — this block is hidden; do not challenge.

   ### Assigned Context (only the in-scope half)
   {% if suspicion_scope == "location" and assigned_visit_location %}
   - **Visit location** (must match the player's arrival form exactly):
     - English: `{{ assigned_visit_location }}`
     - Korean: `{{ assigned_visit_location_ko }}`
     - Difficulty: {{ visit_location_difficulty }} / 12
     - Suspicion reason: `{{ visit_location_suspicion_reason }}`
   {% endif %}
   {% if suspicion_scope == "declaration" and random_customs_item %}
   - **Customs item**: `{{ random_customs_item }}`
     {% if random_customs_item_difficulty %}- Difficulty: {{ random_customs_item_difficulty }} / 12{% endif %}
     {% if random_customs_item_suspicion_reason %}- Suspicion reason: `{{ random_customs_item_suspicion_reason }}`{% endif %}
   {% endif %}

   ### Hard Rules
   1. **Answer-first**: Do NOT challenge the location/item BEFORE the player has answered
      the relevant slot in this turn or a previous turn. Inspect `dialogue_history` —
      challenge only when `player_text_preview` or `filled_slots` shows the player
      has already provided the slot. Otherwise just probe the question normally.
   2. **No invented context**: Never invent a different visit location or customs
      item than the one above. Cross-turn callbacks ("출장이라며? 근데 고급 호텔?")
      may reference the player's earlier statements from `dialogue_history`.
   3. **Natural reference (no forced verbatim)**: When the location/item is
      *contextually relevant* to the current question, reference it by name
      naturally. **Do NOT force the location/item name into unrelated turns**
      (e.g., a polite-greeting turn must not mention the hotel). If the current
      question is not about the slot, suspicion stays silent for this turn.
   4. **Officer-style suspicion**: Higher difficulty → more pointed / more specific
      doubt. Lower difficulty → softer probing. Still 1–2 sentences max.
   5. **No fixed-question mimicry**: Do not copy any B-authored fixed question.
      Build your own challenge dialogue from the suspicion_reason intent.

   ### Examples (do NOT copy verbatim; vary phrasing)
   - scope="location", player already answered "business trip", location="MGM Grand Las Vegas":
     "MGM Grand in Las Vegas for a business trip? That's a pretty upscale stay. Who's covering it?"
   - scope="declaration", player declared "red ginseng box" with bulk quantity:
     "That's quite a lot of red ginseng for personal use. Who is it for?"
   - scope="location" but turn is the polite-greeting opener (slot NOT answered):
     "Welcome. What's the purpose of your visit?"  (← no location reference yet)
   {% endif %}
   ```

3. **`npc_dialogue_prompt.short.md` 도 동일 게이팅** (vLLM 폴백용 압축):
   ```jinja
   {% if suspicion_scope and suspicion_scope != "none" %}
   SUSPICION MODE: probe assigned context as officer, only after slot is answered.
   Scope: {{ suspicion_scope }}
   {% if suspicion_scope == "location" %}Visit location: {{ assigned_visit_location }} (reference by name only when contextually relevant){% endif %}
   {% if suspicion_scope == "declaration" %}Customs item: {{ random_customs_item }}{% endif %}
   Rules: answer-first (check dialogue_history); no forced verbatim in unrelated turns; one short line; never copy a fixed question.
   {% endif %}
   ```

4. **Jinja 렌더링 smoke 테스트:**
   ```powershell
   uv run python -c @"
   from backend.app.agents.agent_a.npc_llm_client import _developer_instructions

   def render(ctx):
       base = {
           'persona_instruction': 'stern officer', 'npc_role': 'immigration_officer',
           'english_level': 'A2', 'incivility_tier': 0, 'profanity_mode': 'off',
           'assigned_visit_location': 'MGM Grand Las Vegas',
           'assigned_visit_location_ko': 'MGM 그랜드',
           'visit_location_difficulty': 10,
           'visit_location_suspicion_reason': 'luxury_hotel_at_business_trip',
           'random_customs_item': '', 'random_customs_item_difficulty': 0,
           'random_customs_item_suspicion_reason': '',
           'dialogue_purpose': 'default', 'length_target': 12, 'topic_switch': False,
           'discussed_topics': [], 'past_player_utterances': [],
           'allowed_mild': [], 'allowed_strong': [], 'non_verbal_palette': [], 'surface_goal': '',
           'dialogue_history': [],
       }
       base.update(ctx)
       return _developer_instructions(base)

   # scope=location 일 때만 location 노출
   o = render({'suspicion_scope': 'location'})
   assert 'SUSPICION MODE' in o and 'MGM Grand' in o, 'location scope failed'

   # scope=declaration 일 때 location 숨김
   o = render({'suspicion_scope': 'declaration', 'random_customs_item': 'red ginseng'})
   assert 'SUSPICION MODE' in o and 'MGM Grand' not in o and 'red ginseng' in o, 'declaration scope leak'

   # scope=none 일 때 SUSPICION MODE 자체 숨김
   o = render({'suspicion_scope': 'none'})
   assert 'SUSPICION MODE' not in o, 'none scope leak'

   print('OK — suspicion_scope gating works')
   "@
   ```

### 수용 기준
- [ ] scope=`location` → location 만 노출, item 숨김
- [ ] scope=`declaration` → item 만 노출, location 숨김
- [ ] scope=`none` → 블록 자체 숨김
- [ ] Hard Rules 에 answer-first(Rule 1), 자연스러운 reference(Rule 3 완화) 포함
- [ ] short.md 도 동일 게이팅 + 압축 가이드

---

## 작업 ④ — 히스토리 소비 가이드 확대 (smalltalk 전용 제약 해제, 10분)

### 대상 파일
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`

### 작업 단계

1. **현재 smalltalk 전용 가이드 위치 확인:**
   ```powershell
   Select-String -Path backend\app\prompts\npc_dialogue_prompt.md -Pattern "discussed_topics|past_player_utterances|smalltalk_diagnostic" -Context 0,3
   ```

2. **기존 smalltalk_diagnostic 분기 안에 있는 히스토리 가이드를 분기 밖으로 끌어내거나, 별도 블록으로 추가:**

   ```jinja
   ## DIALOGUE HISTORY (전 노드 적용)

   {% if dialogue_history and dialogue_history|length > 0 %}
   Recent turns in this session (most recent last):
   {% for h in dialogue_history %}
   - Turn {{ h.turn_index | default(loop.index0) }}: player="{{ h.player_text_preview | default('') }}" → npc="{{ h.npc_text_preview | default('') }}" → filled: {{ h.filled_slots | default({}) }}
   {% endfor %}

   ### Rules using history
   1. **Do NOT repeat a question that has already been answered.** Cross-check
      `filled_slots` and `player_text_preview` before re-asking.
   2. **Acknowledge before progressing.** Show a brief reaction to the player's last
      answer (`{{ dialogue_history[-1].player_text_preview }}`) before moving on.
   3. **Cross-turn callbacks are encouraged.** When natural, reference an earlier
      statement ("You mentioned you're here for business — ...").
   {% endif %}
   ```

3. **smalltalk_diagnostic 블록 안의 `discussed_topics`/`past_player_utterances` 관련 중복 가이드는 그대로 두되, 위 새 블록과 동작 일치하도록 정리.** (충돌 없으면 추가만 하고 종료.)

4. **short.md 에 압축 가이드 추가:**
   ```jinja
   {% if dialogue_history and dialogue_history|length > 0 %}
   History: {{ dialogue_history|length }} prior turns. Do not re-ask answered questions; acknowledge last player utterance before progressing; cross-turn callbacks OK.
   {% endif %}
   ```

5. **렌더링 smoke 테스트:**
   ```powershell
   uv run python -c @"
   from backend.app.agents.agent_a.npc_llm_client import _developer_instructions
   ctx = {
       'dialogue_history': [
           {'turn_index': 1, 'player_text_preview': 'business trip',
            'npc_text_preview': 'For how long?',
            'filled_slots': {'visit_purpose': 'business'}},
           {'turn_index': 2, 'player_text_preview': 'two weeks',
            'npc_text_preview': 'Where will you stay?',
            'filled_slots': {'stay_duration': '14_days'}},
       ],
       'dialogue_purpose': 'default', 'suspicion_scope': 'none',
       'assigned_visit_location': '', 'random_customs_item': '',
       # ... 나머지 필수 필드 (위 작업 ③ smoke 와 동일)
       'persona_instruction': 's', 'npc_role': 'immigration_officer',
       'english_level': 'A2', 'incivility_tier': 0, 'profanity_mode': 'off',
       'length_target': 12, 'topic_switch': False,
       'discussed_topics': [], 'past_player_utterances': [],
       'allowed_mild': [], 'allowed_strong': [], 'non_verbal_palette': [], 'surface_goal': '',
       'assigned_visit_location_ko': '', 'visit_location_difficulty': 0,
       'visit_location_suspicion_reason': '', 'random_customs_item_difficulty': 0,
       'random_customs_item_suspicion_reason': '',
   }
   o = _developer_instructions(ctx)
   assert 'business trip' in o and 'two weeks' in o, 'history not rendered'
   assert 'already been answered' in o or 'Do NOT repeat' in o, 'no-repeat rule missing'
   print('OK — dialogue_history gating works for non-smalltalk purpose')
   "@
   ```

### 수용 기준
- [ ] dialogue_history 가 모든 purpose 에서 프롬프트에 노출
- [ ] "Do NOT repeat answered questions" 가이드 존재
- [ ] 직전 턴 acknowledge 가이드 존재
- [ ] smalltalk_diagnostic 의 기존 기능 회귀 없음

---

## 작업 ⑤ — 대사 변주 (stern/retry 동일 문장 반복 방지, 15분)

### 대상 파일
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/services/service_a/dialogue_policy_service.py` (선택, 폴백 변주 보강 시)

### 작업 단계

1. **프롬프트에 stern/retry 변주 가이드 추가** (DIALOGUE HISTORY 블록 하단에 이어서):
   ```jinja
   ## RETRY / STERN VARIATION

   {% if branch_type == "retry" or branch_type == "clarify" %}
   The previous turn was a retry/clarify and the player has tried again.
   - Do NOT repeat the same sentence you used last turn. Inspect
     `dialogue_history[-1].npc_text_preview` and vary your phrasing.
   - Use synonyms, sentence-structure shifts, or split into a shorter rephrasing.
   - You MAY offer the recommended_expression as a hint paraphrase (e.g.,
     "Try saying it like ..."), but do NOT echo it verbatim.
   {% endif %}
   ```

2. **`dialogue_policy_service.py` 의 stern/retry 폴백 변주 보강** (선택, LLM 실패 시 룰베이스 변주):
   ```powershell
   Select-String -Path backend\app\services\service_a\dialogue_policy_service.py -Pattern "stern|retry|clarify" -Context 0,3
   ```

   `SURFACE_GOAL_QUESTIONS` 같은 고정 큐가 있다면, retry 폴백 시 **여러 후보 중 직전과 다른 것을 랜덤 선택** 하도록 보강:
   ```python
   RETRY_PARAPHRASES = {
       "ask_visit_purpose": [
           "What is the purpose of your visit?",
           "Could you tell me why you're here?",
           "What brings you to the United States?",
       ],
       # 다른 surface_goal 도 동일 패턴
   }

   def pick_retry_paraphrase(surface_goal: str, recent_npc_lines: list[str]) -> str:
       options = RETRY_PARAPHRASES.get(surface_goal, [])
       fresh = [o for o in options if o not in recent_npc_lines]
       return random.choice(fresh or options) if options else ""
   ```

   (단순화: 본 단계는 프롬프트 가이드만 추가하고 service 보강은 후속 PR 로 분리해도 됨.)

3. **자가 검증:**
   ```powershell
   python -m py_compile backend\app\services\service_a\dialogue_policy_service.py
   Get-Content backend\app\prompts\npc_dialogue_prompt.md -Tail 5
   ```

### 수용 기준
- [ ] retry/clarify 시 동일 문장 반복 금지 가이드 노출
- [ ] recommended_expression 패러프레이즈 힌트 허용 (verbatim 에코 금지)
- [ ] (선택) 룰베이스 retry 폴백이 직전 문장 회피

---

## 작업 ⑥ — 회귀 테스트 (15분)

### 대상 파일
- `backend/tests/test_developer_a_npc_dialogue.py`

### 작업 단계

기존 테스트 패턴 따라 신규 5종 추가:

```python
def test_suspicion_mode_active_only_when_scope_location():
    """scope=location 일 때만 location 정보가 프롬프트에 노출."""
    payload = _payload(suspicion_scope="location", assigned_visit_location="MGM Grand Las Vegas")
    captured = _capture_llm_payload(payload)
    assert captured["suspicion_scope"] == "location"
    assert "MGM Grand Las Vegas" in str(captured)

def test_suspicion_mode_hidden_when_scope_none():
    """scope=none 일 때 SUSPICION MODE 가 렌더링되지 않음."""
    payload = _payload(suspicion_scope="none", assigned_visit_location="MGM Grand Las Vegas")
    captured = _capture_llm_payload(payload)
    # location 정보가 페이로드엔 있어도 프롬프트 렌더링 결과엔 없어야 함
    rendered = _render_system_prompt(captured)
    assert "SUSPICION MODE" not in rendered

def test_dialogue_history_passed_in_all_purposes():
    """dialogue_history 가 smalltalk 외 purpose 에서도 llm_payload 에 전달됨."""
    history = [
        {"turn_index": 1, "player_text_preview": "business",
         "npc_text_preview": "How long?", "filled_slots": {"visit_purpose": "business"}}
    ]
    payload = _payload(dialogue_purpose="default", dialogue_history=history)
    captured = _capture_llm_payload(payload)
    assert captured["dialogue_history"] == history
    assert "business" in captured["past_player_utterances"][0]

def test_retry_paraphrase_varies_from_previous():
    """retry 분기에서 직전 NPC 라인과 다른 표현이 폴백으로 선택됨."""
    payload = _payload(
        branch_type="retry",
        dialogue_history=[{"player_text_preview": "I dunno",
                           "npc_text_preview": "What is the purpose of your visit?"}],
        surface_goal="ask_visit_purpose",
    )
    result = generate_npc_dialogue_from_level_design(payload, use_llm=False)
    # 룰베이스 폴백 텍스트가 직전 NPC 라인을 그대로 반복하지 않음
    assert result["npc_text"] != "What is the purpose of your visit?"

def test_suspicion_not_blurted_before_answer():
    """scope=location 이지만 dialogue_history 에서 visit_purpose 슬롯 미응답이면
    프롬프트에 'do NOT challenge preemptively' 가이드 적용 검증."""
    payload = _payload(
        suspicion_scope="location",
        assigned_visit_location="MGM Grand Las Vegas",
        dialogue_history=[],  # 이전 턴 없음 = 답변 전
    )
    captured = _capture_llm_payload(payload)
    rendered = _render_system_prompt(captured)
    assert "answer" in rendered.lower() and "preemptive" in rendered.lower() or "Answer-first" in rendered
```

기존 `_payload`, `_capture_llm_payload`, `_render_system_prompt` 헬퍼가 없으면 동일 파일 상단의 기존 패턴 따라 작성. 헬퍼 시그니처는 기존 테스트에서 차용.

### 자가 검증
```powershell
python -m py_compile backend\tests\test_developer_a_npc_dialogue.py
uv run pytest backend\tests\test_developer_a_npc_dialogue.py -q
```

### 수용 기준
- [ ] 5개 신규 테스트 모두 그린
- [ ] 기존 EOKKKA 테스트 회귀 무영향

---

## 머지 전 종합 체크리스트

- [ ] `uv run pytest backend\tests -q` 그린 (321+ 통과 기준)
- [ ] `uv run ruff check .` 0 errors
- [ ] `uv run mypy .` 0 errors
- [ ] Jinja 렌더링 smoke 3종 통과 (작업 ③, ④)
- [ ] `/respond-dialog` 수동 회귀:
  - IMM_002 (방문 목적 노드) + scope=`location` + 첫 턴(답변 전): NPC 가 location verbatim 으로 트집하지 않음 ✅
  - IMM_002 답변 후 다음 턴: NPC 가 dialogue_history 의 player_text 보고 location 트집 발동 ✅
  - IMM_006 (declaration 노드) + scope=`declaration`: location 안 박히고 customs_item 만 박힘 ✅
  - 같은 retry 2회: NPC 응답이 매번 다른 표현 ✅
  - 이미 답변된 슬롯 재질문 없음 ✅
- [ ] `git diff --stat` 결과 다음 6개 파일 외 0:
  - `backend/app/services/service_a/developer_a_input_service.py`
  - `backend/app/agents/agent_a/npc_dialogue_agent.py`
  - `backend/app/prompts/npc_dialogue_prompt.md`
  - `backend/app/prompts/npc_dialogue_prompt.short.md`
  - `backend/app/services/service_a/dialogue_policy_service.py` (선택)
  - `backend/tests/test_developer_a_npc_dialogue.py`
- [ ] B/C 영역 0 수정

---

## handoff entry 초안

```markdown
## 2026-06-18 Developer A: CR-B-CONV-A 트집 게이팅·히스토리 소비·대사 변주 구현 완료

Developer A 는 CR-B-CONV-A 의 A 측 4가지 항목을 완료했습니다. B 가 2026-06-18 에 emit 한 `dialogue_seed.suspicion_scope` 및 C 가 동일 날짜에 attach 한 `dialogue_seed.dialogue_history` 를 모두 소비합니다.

Changed:

- `developer_a_input_service.py`: normalize 단계에서 `suspicion_scope` (기본 "none"), `dialogue_history` 안전 추출.
- `npc_dialogue_agent.py`: `llm_payload` 에 두 필드를 모든 purpose 에서 주입. smalltalk 전용 OpenKB 보강은 그대로 두되 dialogue_history 가 우선 활용되도록 `past_player_utterances` / `discussed_topics` 채움 로직 일반화.
- `prompts/npc_dialogue_prompt.md`, `prompts/npc_dialogue_prompt.short.md`:
  - SUSPICION MODE 활성 조건을 `assigned_visit_location 존재` → `suspicion_scope != "none"` 로 변경.
  - scope=`location` 일 때 location 만 / `declaration` 일 때 item 만 노출.
  - Hard Rule 1 (answer-first): dialogue_history 확인 후 슬롯 답변 전까지 선제 블러팅 금지.
  - Hard Rule 3 verbatim 완화: 맥락상 관련 턴에서만 자연스럽게 지칭.
  - DIALOGUE HISTORY 블록 신설 (모든 purpose 적용): 답변된 질문 반복 금지 + 직전 턴 acknowledge + cross-turn callback 허용.
  - RETRY/STERN VARIATION 블록 신설: 직전 NPC 라인 회피 + recommended_expression 패러프레이즈 힌트 허용.
- `dialogue_policy_service.py` (선택): retry 폴백 paraphrase 사전 + 직전 라인 회피 헬퍼.
- `test_developer_a_npc_dialogue.py`: 회귀 5종 (suspicion scope 게이팅 3종, dialogue_history 모든 purpose, retry 변주, answer-first).

Verification:

- `uv run pytest backend/tests`: PASS
- `uv run ruff check .`: PASS
- `uv run mypy .`: PASS
- `/respond-dialog` 수동 회귀: IMM_002 첫 턴 선제 블러팅 없음 / scope 분리 동작 / retry 변주 / 이미 답변된 슬롯 재질문 없음 확인.

B/C 영역 0 수정. CR-B-CONV-A 의 Dev A 측 항목 완료.
```

---

## 참고

- 본 계획서 가정 main: 2026-06-18 B/C 머지 직후 (`DialogueSeed.suspicion_scope`, `DialogueSeed.dialogue_history`, `_sync_challenge_context_to_dialogue_seed` 모두 적용된 상태)
- 작업 분량: 총 ~80분
- 우선순위: ① → ② → ③ → ④ → ⑤ → ⑥ 순서
- 도구 사용 권장: Edit (line-by-line), Read (확인용)
- **Write (전체 덮어쓰기) 금지** — 한 줄씩 정확히 수정. truncation 사고 방지.
