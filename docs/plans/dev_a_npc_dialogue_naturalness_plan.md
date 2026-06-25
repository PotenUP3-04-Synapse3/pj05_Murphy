# NPC 대화 자연스러움·정합성 개선 통합 계획 (dev_a)

작성일: 2026-06-25
배경: 실제 플레이 세션에서 발견된 두 갈래 문제를 한 문서로 통합.

- **Part A — 추임새 자연스러움(페르소나):** Arabella가 매 턴 "Haha"로 시작하는 등, 특정 추임새가 시그니처로 강제되어 부자연스럽고 TTS 발음도 어색함.
- **Part B — BAG_003 무한 루프 & "You mentioned X" 기계적 콜백(시나리오/정책):** 가방을 정확히 설명해도 영구 `REASK|UNCLEAR` 루프, 그리고 "You mentioned yup —" 같은 무의미한 콜백 반복.

도메인이 다르므로(Part A=페르소나 로스터, Part B=정책 시드/시나리오 노드/Understanding 채점) 작업·검증을 분리하되, 둘 다 "대화가 실제 대화처럼 자연스럽고 정합적인가"라는 동일 목표를 공유.

우선순위: **Part B-① (루프) → Part A/B 나머지.** 루프는 플레이어가 진행 불가 상태에 빠지는 치명 버그이므로 최우선.

---

# Part A. 추임새 자연스러움

대상: `arabella`, `brielle`, `hale`, `dan` + 공통 프롬프트 가드.
범위 밖: `novak`(이미 `occasional`로 완화·단어 적절), `harris`(`Mm-hmm.`/`Indeed.` 구어로 자연스러움).

## A1. 문제

```
Arabella: Haha, thanks. So, do you travel a lot?
Arabella: Aww, nice. New York with family sounds fun, haha. ...
Arabella: Haha, I mean, yeah. ...
Arabella: Haha, nice. I'm headed to New York for a friend's wedding.
```

판정: 부자연스러움. "haha"는 본질적으로 *문자/채팅* 토큰이라 실제 발화 시 진짜로 웃지 "하하"라고 말하지 않으며, TTS가 그대로 읽으면 로봇음이 난다. 친근한 화자라도 거의 모든 턴을 "Haha,"로 시작하지 않는다.

| NPC | 심각도 | 문제 유형 |
|-----|--------|-----------|
| arabella | 심각 | 채팅 토큰("haha") + 추임새 강제 명명 + 나쁜 예시 |
| brielle | 중간 | 추임새 강제 명명(단어 자체는 자연스러움) |
| hale | 중간 | TTS 발음 부자연 의성어(`Tsk.`/`Hmph.`) |
| dan | 경미 | 명령어를 비구어 팔레트에 오분류(`Halt.`/`Now...`) |

## A2. 근본 원인

1. **Tone & Speech가 특정 추임새를 시그니처로 못박음** → 매 턴 적용.
   - arabella `npc_roster_service.py:56-58`: `"...light humor and 'Haha' / 'Aww' interjections."`
   - brielle `npc_roster_service.py:251-253`: `"...Uses 'Oh!' / 'Let's see...' interjections."`
2. **non_verbal_palette에 부적절한 토큰**
   - arabella `:84`: `["Haha!","Aww.","Hmm...",break]` (채팅 토큰)
   - hale `:163`: `["Hmph.","Tsk.",break]` (TTS가 문자 그대로 읽음)
   - dan `:237`: `["Halt.","Now...",break]` (추임새 아닌 명령어)
   - 중복 정의: `non_verbal_palette.py` 에도 동일 값 → 동기화 필요.
3. **In-Character 예시도 'Haha'로 시작** — arabella `:73`.
4. **턴 단위 빈도 억제 부재** — 프롬프트 `npc_dialogue_prompt.md:117`는 *문장당* 개수만 제한, 매 턴 추임새가 붙는 것을 못 막음.

## A3. 설계 원칙

- 기준은 "문자에서 쓰는가"가 아니라 "입으로 말할 때 실제로 나오고 TTS가 자연스럽게 발음하는가".
- 특정 추임새를 시그니처로 강제하지 않음(따뜻함/위압감은 단어·문장 길이·포즈로).
- 빈도가 핵심 — 자연스러운 단어라도 매 턴이면 어색. 대부분 턴은 추임새 없음이 기본.
- 팔레트는 진짜 비구어(의성어·짧은 반응·break)만. 명령어·완전한 문장은 본문 생성.

## A4. 공통 변경 (프롬프트 빈도 가드)

`npc_dialogue_prompt.md` NON-VERBAL EXPRESSION 섹션(`:117` 인근)에 1줄 추가:
```
- Frequency: most turns use NO interjection. Never open consecutive turns
  with an interjection, and never reuse the same one twice in a row.
```
`npc_dialogue_prompt.short.md` 팔레트 안내 라인에도 동일 취지 압축 반영.

## A5. NPC별 변경

### A5.1 arabella — 단어 교체 + 강제 해제
대체: `Oh` / `Aw`(Aww→Aw) / `Wow`. `Haha` 제거.
- **Tone** `:55-58` → `Warm, patient, socially easygoing. Short casual sentences; humor comes from word choice, not catchphrases. May occasionally open with a natural spoken reaction (e.g. 'Oh', 'Aw', 'Wow'). Never written-chat laughter like 'haha'/'lol'. Avoids long lectures or formal phrasing.`
- **In-Character 예시** `:73` → `'What? Aw, you're funny. I'm just heading to New York like you.'`
- **팔레트** `:84` → `["Oh!", "Aw.", "Wow.", "<break time='0.5s'/>"]`

### A5.2 brielle — 강제 해제만 (단어 유지)
- **Tone** `:251-253` → `Helpful, bright, polite, service-oriented. Medium-length friendly sentences. May occasionally use a brief service-desk reaction (e.g. 'Oh', 'Let's see'), but does not lead every turn with one.`
- 팔레트 `:275` 유지.

### A5.3 hale — TTS-나쁜 의성어 제거
- **팔레트** `:163` → `["<break time='0.4s'/>"]` (어휘 추임새 제거, 포즈만). 발성 토큰을 꼭 남기려면 `"Hm."` 단일형으로 TTS 검증 후 채택.

### A5.4 dan — 명령어 오분류 정리
- **팔레트** `:237` → `["<break time='0.5s'/>"]`. 위압감은 기존 Tone/Behavioral Rules로 표현.

### A5.5 팔레트 중복 파일 동기화
`non_verbal_palette.py` 의 arabella/hale/dan 항목을 위와 일치. (실주입은 로스터 인라인이지만 어긋나면 혼동 유발. 장기적으로 단일 출처 통합은 범위 밖.)

---

# Part B. BAG_003 무한 루프 & 기계적 콜백

대상: `dialogue_policy_service.py`(정책 시드/콜백), `scenario_nodes.json`(노드, dev_b 도메인 협의 필요), Understanding 채점(연동 확인).

## B1. 현상

```
You: Yeah, it is black and a big bag, maybe it's 24 inches, and the maker is Hermes.
Brielle: Oh. You mentioned yeah — Let me search the carousel. Can you describe your bag?
... (정확히 설명해도 매 턴 REASK|UNCLEAR 루프, "You mentioned {첫단어}" 만 바뀜)
BAG_003_CONFIRM_SEARCHED_CAROUSEL -> BAG_003_CLARIFY_CONFIRM_SEARCHED_CAROUSEL | REASK | UNCLEAR
```

## B2. 버그 ① 무한 루프 — 질문과 채점 슬롯 모순 (핵심)

노드 BAG_003 (`scenario_nodes.json:701-734`):
- `npc_question`: **"Did you check the carousel carefully?"**
- `required_slots`: `["carousel_search_confirmation"]`, `recommended_expression`: `"Yes, I checked carefully, but it wasn't there."`

그러나 surface-goal 시드 (`dialogue_policy_service.py:123`):
```python
"confirm_carousel_search": "Let me search the carousel. Can you describe your bag?",
```
→ NPC는 "가방을 설명"하라고 묻는데 채점기는 "벨트 확인 여부"를 기대. 플레이어가 시키는 대로 설명해도 `carousel_search_confirmation` 기준 채점 → 영구 `UNCLEAR` → CLARIFY 루프. 빠져나올 경로가 없음.

### 수정 방향 (권장: 시드를 슬롯에 맞춤)
- `dialogue_policy_service.py:123`
  - before: `"confirm_carousel_search": "Let me search the carousel. Can you describe your bag?"`
  - after:  `"confirm_carousel_search": "Did you check the carousel carefully before coming to the desk?"`
- "Can you describe your bag?"는 다른 비트(가방 설명 단계)의 텍스트가 잘못 매핑된 것으로 추정 → 해당 노드가 따로 존재하는지 확인.
- **clarify/retry 일관성**: `RETRY_PARAPHRASES`의 `confirm_carousel_search` 및 `BAG_003_CLARIFY`/`BAG_003_RETRY` 노드 시드도 "벨트 확인" 계열로 통일(describe bag 금지).
- 비권장 대안: 노드 `required_slot`을 "가방 설명"으로 변경 → `objective_kr`/`recommended_expression`/노드명까지 전부 바꿔야 해 설계 뒤집기. 시드 수정이 최소 변경.

## B3. 버그 ② "You mentioned X —" 기계적 콜백

`dialogue_policy_service.py:163-169`:
```python
if open_hooks and len(open_hooks) > 0:
    first_hook = open_hooks[0]
    if first_hook.isascii() and first_hook.isalpha():
        prefix = f"You mentioned {first_hook} — "
```
`open_hooks`는 직전 발화에서 3글자 이상 단어를 등장 순서로 추출(`session_context_card_service.py:163-170`) → `open_hooks[0]`은 항상 첫 단어("yup","yeah","what","black","hermes"). 필러 필터·관련성 검증 없음 → 무의미한 콜백.

### 수정 방향 (3가지 병행)
1. **re-ask(clarify/retry/warning) 분기에선 prefix 비활성화.** "You mentioned X —"는 앞으로 나아가며 방금 말을 받아주는 success 턴에서만 자연스러움 → `synthesize_fallback_next_question`에 `branch_type` 전달, success/neutral일 때만 prefix 합성. (루프 중 반복은 이걸로 즉시 사라짐.)
2. **필러·기능어 스토플리스트 추가** (yes/no/인사/대명사/의문사 등) — extraction 또는 prefix 단계에서 제외.
3. **첫 단어 대신 내용어(명사) 우선 선택** — `open_hooks[0]` 맹목 사용 지양(1번 적용 시 보조).

## B4. Part B 우선순위
①을 먼저. ②를 고쳐도 루프 원인(정답 불가)은 ①이라 그대로 남음. ①로 정답 경로를 열고 ②로 콜백 자연화.

---

# 통합 작업 순서

1. **B-① 루프 시드 수정** (`dialogue_policy_service.py:123` + clarify/retry 일관성) — 최우선, 진행 불가 해소.
2. **B-② 콜백 게이팅/필터** (`dialogue_policy_service.py:163-169`, `session_context_card_service.py`).
3. **A-4 프롬프트 빈도 가드** — 추임새 공통 효과.
4. **A-5 페르소나/팔레트** (arabella→brielle→hale→dan + `non_verbal_palette.py` 동기화).

# 검증

- **B-①**: BAG_003에서 "Yes, I checked carefully but it wasn't there." → `SUCCESS`로 BAG_004 진행. 가방 설명을 해도 더이상 정답 강요되지 않는지(시드가 올바른 질문을 하는지).
- **B-②**: 되묻는 턴에 "You mentioned ..." prefix 미부착. success 턴에서 prefix가 붙을 땐 필러가 아닌 내용어인지.
- **A**: arabella 5~6턴 → "haha" 0회, 연속 턴 동일 추임새 미시작, 추임새 없는 턴 과반. hale/dan 의성어·명령어 prefix 미부착 및 TTS 자연성. brielle 매 턴 'Oh!' 미시작.
- 회귀 테스트: `test_developer_a_npc_roster.py`, `test_developer_a_npc_dialogue.py`, 정책/시나리오 관련 테스트.

# 도메인/협의

- Part A, B-②: dev_a(`service_a`, 프롬프트) 단독 가능.
- B-①: 시드는 dev_a(`dialogue_policy_service.py`)이나, `scenario_nodes.json` 측 의도(가방 설명 비트 존재 여부)는 dev_b와 확인 필요.
