# Developer A 작업계획서 — 프롬프트 고도화 + 비-텍스트 표현 (Flash v2.5) + Profanity Mirror 모드

> 작성일: 2026-06-16
> 작성자: Developer A / kimyonghee
> 소유 영역: `backend/app/agents/agent_a/`, `backend/app/services/service_a/`, `backend/app/tools/tool_a/`, `backend/app/prompts/`
> 대상 TTS 모델: **ElevenLabs `eleven_flash_v2_5`** (현재 `.env` 기본값 유지)
> 참고: `workplan-dev-a.md` 의 P0(Dialogue 품질) 작업과 직접 연계

---

## 0. 요약

본 계획서는 세 가지 축을 묶어 진행합니다.

1. **프롬프트 계층화 고도화** — 현재 `_developer_instructions()` 의 평탄한 산문 프롬프트를 `Role / Hard Constraints / Speaker Discipline / Dialogue Structure / Persona / Difficulty / Emotion / Few-Shot / Output` 9 계층으로 재구성하고 외부 파일(`prompts/npc_dialogue_prompt.md`)로 분리.
2. **Flash v2.5 한도 내 비-텍스트 표현** — Eleven v3 의 audio tag(`[sigh]`, `[laughs]` 등)는 Flash v2.5 에서 미지원이므로 **SSML `<break time="…">`**, **줄임표·세미콜론·줄바꿈**, **의성어 카탈로그**, **stability/style/speed 미세 조정**을 결합해 인간적 호흡감을 확보. Eleven v3 도입은 본 계획 범위 밖(별도 RFC).
3. **Profanity Mirror Mode** — 플레이어가 욕설/모독/위협 발화 시 NPC도 동급의 거친 응답을 자연스럽게 반환하는 모드 추가. 기본은 OFF, `MURPHY_NPC_PROFANITY_MIRROR_MODE=mirror` 로 옵트인. 단순 on/off 가 아니라 **Severity Tier(T0~T3)** + **Response Style(`firm` / `mirror`)** 두 축으로 구성해 운영 정책과 게임 등급에 맞춰 조정 가능하도록 한다.

가드레일(`AGENTS.md`): Developer A는 대사 텍스트·페르소나·TTS 파라미터·로스터만 다룬다. **모욕성/욕설 입력의 분류·분기·점수 처리는 Developer B(분기) / Developer C(Understanding)** 영역이므로 본 계획서는 **계약 변경 요청(Change Request)** 형식으로 분류 신호 추출만 위임하고, A는 **수신한 신호를 어떻게 발화로 표현할지**만 책임진다.

---

## 1. 인벤토리 — 현재 상태 vs 목표 상태

### 1-1. 프롬프트

| 항목 | 현재 | 목표 |
|---|---|---|
| 정의 위치 | `npc_llm_client.py` 의 함수 내 인라인 산문 | `prompts/npc_dialogue_prompt.md` 외부 파일 + Jinja 템플릿 |
| 구조 | 한 덩어리 문장 | 9 계층 (Role/Hard Constraints/Speaker Discipline/...) |
| 페르소나 주입 | `persona_instruction` 한 줄 | persona + role별 어휘·어조 규칙 표 |
| few-shot | 0개 | 3개 (SUCCESS / RETRY / COMPLETE_CHAPTER), 가능하면 role별 |
| Speaker 가드 | 없음 (P0 결함 원인) | "player_text는 PLAYER 발화" 명시 |
| 다음 질문 작문 의무 | 없음 (P0 결함 원인) | dialogue_seed.surface_goal이 있으면 다음 질문 필수 |
| 비-텍스트 표현 가이드 | "use brief pauses like '...'" 한 줄 | SSML `<break>` + 의성어 카탈로그 + 호흡 가이드 |
| Profanity 응답 정책 | 없음 | T0~T3 tier별 응답 규칙 |

### 1-2. 비-텍스트 표현 (Flash v2.5 한정)

| 기능 | Flash v2.5 지원 여부 | 본 계획에서의 사용 |
|---|---|---|
| SSML `<break time="0.6s"/>` | ✅ (최대 3초) | 호흡·뜸들임 표현 |
| 줄임표 `...` | ✅ | 망설임·말끝 흐림 |
| 쉼표/세미콜론/줄바꿈 | ✅ | 자연 호흡 보조 |
| SSML `<phoneme>` | ✅ | 고유명사·외래어 발음 보정용 (선택) |
| Audio tags `[sigh]`, `[laughs]`, `[whispers]` | ❌ | **미사용** (v3 도입 시 RFC) |
| 인라인 사운드 이펙트 `[gunshot]` | ❌ | **미사용** |
| 의성어 텍스트화 (`"Ugh."`, `"Hmph."`, `"Tsk."`) | ✅ (모델이 발화) | 본 계획에서 적극 활용 |
| stability/style/speed 동적 조정 | ✅ | 한숨 흉내·격앙 톤 흉내 |

### 1-3. Profanity Mirror

| 항목 | 현재 | 목표 |
|---|---|---|
| 모욕성 입력 처리 | 일반 응답과 동일 | T0~T3 분류 후 차별화 |
| 욕설 응답 | 절대 안 함 | `mode=mirror` 일 때 T2~T3 에서 mild profanity 허용 |
| 게임 등급 고려 | 미명시 | env 토글 + 등급 영향 명문화 |
| bad ending 트리거 연동 | 미연동 | T3 발화는 Developer B 의 bad ending 정책에 신호 송출 |
| 욕설 사전 | 없음 | A 소유 `profanity_lexicon.py` 화이트리스트/블랙리스트 |

---

## 2. 아키텍처 변경 개요

```
[Developer C] Understanding Agent
   └─ player_text 분석 시 incivility_tier (0~3) 신호 추가      ◀── Change Request §5
                                                                     (Developer C가 구현)

[Developer B] Policy Engine
   └─ tier ≥ 2 일 때 분기·페널티·bad ending 트리거 결정          ◀── Change Request §5
                                                                     (Developer B가 구현)

[Developer A] Dialogue Agent  (본 계획서 범위)
   ├─ payload.incivility.tier (0~3) 수신
   ├─ payload.incivility.detected_terms (list[str])  ─ 안전 로그용
   ├─ MURPHY_NPC_PROFANITY_MIRROR_MODE=off|firm|mirror  토글 로드
   ├─ 룰베이스 시드: tier × mode 매트릭스로 응답 템플릿 선택
   ├─ LLM 프롬프트: tier × mode 컨텍스트 주입 + 출력 후처리
   ├─ TTS 파라미터: tier 상승 시 stability↓ style↑ speed↑
   └─ 출력 후 검증: profanity_lexicon 화이트리스트 외 단어 차단
```

---

## 3. 작업 계획 (Phased)

### Phase A — 프롬프트 외부화 + 9계층 재구성 (1.5d)

**대상 파일:**
- 신설: `backend/app/prompts/npc_dialogue_prompt.md` (시스템 프롬프트 본문)
- 신설: `backend/app/prompts/npc_dialogue_few_shots.md` (예시 모음)
- 수정: `backend/app/agents/agent_a/npc_llm_client.py` (`_developer_instructions` → 외부 파일 렌더링)

**작업:**
1. `_developer_instructions(persona_instruction)` 의 현재 내용을 9 계층으로 분해해 `npc_dialogue_prompt.md` 로 이전. Jinja 변수: `{{ persona_instruction }}`, `{{ npc_role }}`, `{{ english_level }}`, `{{ incivility_tier }}`, `{{ profanity_mode }}`, `{{ surface_goal }}`, `{{ allowed_emotions }}`.
2. 9 계층 구성:
   ```
   [1] ROLE — 영어 학습 게임 NPC 에이전트
   [2] HARD CONSTRAINTS — JSON 스키마, ASCII only, branch 손대지 않음 …
   [3] SPEAKER DISCIPLINE — PLAYER vs NPC 명확 분리 (P0 가드)
   [4] DIALOGUE STRUCTURE — (a) 리액션 + (b) 다음 질문 (surface_goal 있을 때 필수)
   [5] PERSONA — {{ persona_instruction }} + role별 어휘·어조 표
   [6] DIFFICULTY ADAPTATION — english_level 별 문장·어휘 가이드
   [7] EMOTION & TTS PARAMS — npc.emotion 13종 우선
   [8] NON-VERBAL EXPRESSION (Flash v2.5) — SSML <break>, …, 의성어 카탈로그
   [9] PROFANITY HANDLING — incivility_tier × profanity_mode 매트릭스 (§4 표)
   [10] OUTPUT FORMAT — JSON only, no fence, no comment
   ```
3. few-shot 3개 작성:
   - SUCCESS (FLIGHT_A_001 → FLIGHT_A_002, tier=0)
   - RETRY (IMM_002_PURPOSE, tier=0)
   - PROFANITY MIRROR (IMM_002_PURPOSE 에서 player_text="fuck you", tier=2, mode=mirror)
4. `npc_llm_client.py` 에 `_render_developer_instructions(context: dict) -> str` 헬퍼 추가 — 외부 파일 읽고 변수 치환.
5. 모델별 분기: gpt-4o-mini는 full 프롬프트, vLLM fallback(gemma)은 축약본 — `npc_dialogue_prompt.md` 와 `npc_dialogue_prompt.short.md` 두 벌.

**수용 기준:**
- `_developer_instructions()` 코드 라인 50줄 이상 → 외부 파일 1회 로드 + 템플릿 렌더링 5줄로 축소.
- 기존 모든 회귀 그린.

### Phase B — Flash v2.5 비-텍스트 표현 인프라 (1.0d)

**대상 파일:**
- 수정: `backend/app/services/service_a/tts_text_polisher_service.py`
- 신설: `backend/app/services/service_a/non_verbal_palette.py`
- 수정: `backend/app/services/service_a/npc_roster_service.py` (NPCProfile에 `non_verbal_palette` 추가)
- 수정: `backend/app/agents/agent_a/schemas.py` (`tts_text` max_length 220 → 256)

**작업:**
1. **NPCProfile 확장:** `non_verbal_palette: list[str]` 추가. 예시:
   ```python
   "hale":     ["Hmph.", "Tsk.", "<break time='0.4s'/>"],
   "arabella": ["Haha!", "Aww.", "Hmm...", "<break time='0.5s'/>"],
   "brielle":  ["Oh!", "Mm-hmm.", "Let's see..."],
   ```
2. **시스템 프롬프트 §8 NON-VERBAL EXPRESSION 가이드:**
   ```
   You may use these natural-speech devices in `tts_text` (NOT in `npc_text`):
     - SSML pauses: <break time="0.4s"/> (max 3.0s)
     - Trailing hesitation: "..."
     - Punctuation breaths: comma, semicolon
     - Interjections from this NPC's palette ONLY: {{ non_verbal_palette }}
   Use sparingly — at most ONE non-verbal element per sentence.
   Examples:
     npc_text: "Okay. Where will you stay?"
     tts_text: "Okay. <break time='0.4s'/> Where will you stay?"

     npc_text: "Hmm. I see. Let me check that."
     tts_text: "Hmm... <break time='0.5s'/> I see. Let me check that."
   ```
3. **`tts_text_polisher_service.polish_tts_text` 보강:**
   - 룰베이스 경로에서도 emotion 별로 1개 정도의 `<break>` 또는 의성어 자동 삽입.
   - LLM 경로에서는 LLM 출력의 SSML 유효성만 검증(잘못된 시간 단위 보정, 3초 초과 클램프).
4. **`schemas.py`:** `tts_text` 의 `max_length` 220 → 256 (SSML 태그가 글자 수를 잡아먹는 점 반영). `pattern` 으로 위험한 태그(예: `<script>`) 차단.
5. **`audio_quality_service.analyze_wav_quality`:** SSML break 가 너무 많아 침묵 비율이 높아지는지 검출. 임계치 초과 시 폴백.

**수용 기준:**
- 6개 NPC 각각의 `tts_text` 샘플에서 SSML break/의성어가 페르소나에 맞게 삽입됨.
- `<break time="X"/>` 가 0.0~3.0s 범위 밖이면 자동 클램프.
- `npc_text` (UI 표시용)에는 SSML 태그가 들어가지 않음(LLM 가드).

### Phase C — Profanity Mirror 모드 (2.0d)

#### C-1 — 운영 토글 및 입력 신호 계약 (0.5d)

**대상 파일:**
- 수정: `.env.example`
- 수정: `backend/app/services/service_c/settings_service.py` (Developer C 영역이라 본 PR 범위 밖, 별도 change request)
- **신규 등록:** `docs/contracts/change_requests.md` — "Add `incivility_tier` to Understanding output + B branch policy"

**환경 변수:**
```bash
# off    : 기존 동작. tier 신호가 와도 평이한 응답.
# firm   : tier 1+에서 정색·경고. 욕설은 절대 미러링 안 함. 기본 권장.
# mirror : tier 2+에서 mild profanity 미러링 허용. 게임 등급 영향 있음.
MURPHY_NPC_PROFANITY_MIRROR_MODE=off

# mirror 모드에서 허용할 최대 강도. mild / strong.
# mild  : damn, hell, screw, crap, shut up 등.
# strong: shit, ass, bullshit 등. 슬러/혐오발언은 모드 무관 항상 금지.
MURPHY_NPC_PROFANITY_MIRROR_MAX_INTENSITY=mild
```

**Change Request 등록 항목 (Developer C/B 측 작업 위임):**
- Understanding Agent 가 `player_text` 분석 시 `incivility` 객체 추가:
  ```json
  "incivility": {
    "tier": 0,           // 0=정상, 1=무례, 2=인격모독, 3=욕설/혐오/위협
    "detected_terms": ["stupid", "shut up"],
    "confidence": 0.87,
    "category": "rudeness|insult|profanity|slur|threat"
  }
  ```
- B Policy 가 tier ≥ 2 일 때 분기·페널티 결정 (현재 "dangerous words trigger immediate bad ending" 정책과 정합).
- C 어댑터 `dev_a_npc_dialogue_client.py` 가 `incivility` 를 A-facing payload 에 전달.

#### C-2 — A 측 룰베이스 시드 + 응답 매트릭스 (0.5d)

**대상 파일:**
- 신설: `backend/app/services/service_a/profanity_response_policy.py`
- 신설: `backend/app/services/service_a/profanity_lexicon.py`
- 수정: `backend/app/agents/agent_a/npc_dialogue_agent.py` (`node_initialize_state` 에서 tier × mode 분기)

**`profanity_response_policy.py` 핵심 매트릭스:**

| tier | mode=off | mode=firm | mode=mirror | TTS 보정 |
|---|---|---|---|---|
| T0 정상 | 평상 응답 | 평상 응답 | 평상 응답 | 기존 |
| T1 무례 ("shut up", "stupid") | 평상 응답 | 정색 + 톤 경고 ("Watch your tone, please.") | 정색 + 톤 경고 (동일) | stability ↓0.1, style ↑0.1 |
| T2 인격 모독 ("you idiot", "you're useless") | 평상 응답 | 단호한 제지 ("That's enough. One more remark and this stops.") | mild profanity 한 마디 ("Watch your damn mouth.") | stability ↓0.2, style ↑0.2, speed ↑0.05 |
| T3 욕설/혐오/위협 ("fuck you", "kill yourself") | bad ending 정책에 위임 | 절차 종료 ("This interview is over.") | mild/strong 미러링 + 절차 종료 ("Get the hell out of my line.") | stability ↓0.3, style ↑0.3, speed ↑0.1, emotion=anger+suspicion |

**`profanity_lexicon.py`:**
- `MIRROR_ALLOWED_MILD = {"damn", "hell", "screw", "crap", "shut up", "freaking"}`
- `MIRROR_ALLOWED_STRONG = MIRROR_ALLOWED_MILD | {"shit", "ass", "bullshit", "piss"}`
- `ALWAYS_BLOCKED = { /* 슬러/혐오/위협/성차별 어휘 */ }` — 모드 무관, 출력에서 발견 시 폴백
- 함수: `allowed_for(mode: str, intensity: str) -> set[str]`, `contains_blocked(text: str) -> list[str]`

**룰베이스 폴백 문구 사전 (페르소나×tier):**
- `hale`(immigration_officer) T2 mirror: `"Watch your damn mouth. Last warning."`
- `hale` T3 mirror: `"Get the hell out of my line. We're done."`
- `arabella`(seatmate) T2 mirror: `"Whoa, what the hell is your problem?"`
- `brielle`(baggage_staff) T2 firm: `"Sir, I'm trying to help. Please keep it civil."`

LLM 실패 시에도 이 폴백이 페르소나·tier·mode 에 부합하도록 보장.

#### C-3 — LLM 프롬프트 §9 PROFANITY HANDLING (0.5d)

**시스템 프롬프트 §9 본문 (예시):**
```
The player's last utterance has incivility_tier={{ incivility_tier }} (0=normal, 3=severe profanity).
The current profanity_mode is "{{ profanity_mode }}".

Rules:
- mode=off:    Always respond politely regardless of tier.
- mode=firm:   If tier>=1, lower your patience but DO NOT use any profanity.
               If tier>=2, deliver a stern procedural warning.
               If tier>=3, end the interaction coldly ("This interview is over.").
               NEVER use profanity yourself.
- mode=mirror: If tier<=1, respond as in firm mode.
               If tier==2, you MAY use ONE mild profanity word from this allowlist: {{ allowed_mild }}.
                           Stay in character. Do NOT escalate beyond one word.
               If tier==3, you MAY use one mild/strong profanity from: {{ allowed_strong }},
                           then end the interaction.
               NEVER use slurs, hate speech, threats of violence, sexual content, or any
               word outside the allowlist regardless of player provocation.

Character voice still rules. Officer Hale would say "Get the hell out of my line."
Brielle (baggage staff) would say "What the heck is wrong with you?" (softer).
Seatmate Arabella would say "Whoa, what the hell is your problem?"

Output the dialogue in {{ npc_text }} and {{ tts_text }} as usual.
Set npc_emotion to one of: anger, suspicion, disgust.
Set tone to formal_warning or formal_stern.
```

#### C-4 — 출력 후처리 검증 (0.5d)

**대상 파일:** `backend/app/agents/agent_a/npc_dialogue_agent.py` (`node_generate_dialogue_llm` 후처리부)

1. LLM 출력의 `npc_text` / `tts_text` 에 대해 `profanity_lexicon.contains_blocked(text)` 호출.
2. 차단어 발견 시:
   - `error="profanity_lexicon_violation"` 로 폴백 노드 라우팅.
   - 차단어를 로그에 기록 (개수만, 단어 자체는 마스킹).
3. `mode=off` 인데 mild 이상의 미러링 어휘가 등장한 경우도 폴백.
4. `mode=mirror` + tier 매트릭스 외 어휘 사용 시 폴백.
5. 모든 폴백은 C-2 의 룰베이스 폴백 사전으로 떨어짐 — 시스템이 침묵하지 않음.

---

### Phase D — TTS 파라미터 incivility 연동 (0.5d)

**대상 파일:** `backend/app/services/service_a/voice_output_service.py`

1. `_build_provider_request` (ElevenLabs 분기) 에 `incivility_tier` 컨텍스트 추가.
2. 기존 `EMOTION_TTS_PARAMETERS` 보정에 더해 tier별 추가 보정 함수:
   ```python
   def _apply_incivility_bias(params, tier):
       if tier == 0: return params
       stability      = max(0.0, params.stability - 0.1 * tier)
       style          = min(1.0, params.style + 0.1 * tier)
       speed          = min(2.0, params.speed + 0.05 * tier)
       similarity     = params.similarity_boost
       return TTSParams(stability, style, speed, similarity)
   ```
3. LLM이 산출한 stability/style/speed 가 있으면 LLM 우선(현재 동작 유지) + 없을 때만 tier 기반 보정.

---

### Phase E — 테스트 (1.5d)

**신설 테스트:**
- `backend/tests/test_developer_a_prompt_rendering.py`
  - 외부 파일 로드 + Jinja 변수 치환 검증
  - 9 계층이 모두 포함되는지
- `backend/tests/test_developer_a_non_verbal_expression.py`
  - SSML `<break>` 시간 클램프
  - `npc_text` 에 SSML 태그 미포함 보장
  - 의성어 카탈로그 외 어휘 등장 시 폴백
- `backend/tests/test_developer_a_profanity_mirror.py`
  - tier × mode 매트릭스 12 케이스 (3 mode × 4 tier)
  - `profanity_lexicon.contains_blocked` 차단어 검출
  - `mode=mirror` + T3 인데 `ALWAYS_BLOCKED` 어휘 출력 → 폴백
  - 룰베이스 폴백이 페르소나에 맞게 선택됨

**기존 테스트 영향 점검:**
- `test_developer_a_npc_dialogue.py` — incivility 미주입(T0) 케이스가 기존과 동일 동작.
- `test_developer_a_npc_llm_client.py` — 외부 프롬프트 로드 mocking.

**수동 회귀:**
- `/respond-dialog` 에서 (a) 정상 답변 (b) 무례 답변 (c) 욕설 답변 각 1회씩 mode 토글하며 NPC 응답·voice 변화 청취.

---

### Phase F — 정리/문서화 (0.5d)

1. `docs/handoff.md` 에 본 PR 결과 기재.
2. `docs/agent_a_structure.md` 의 service_a 섹션에 `profanity_response_policy.py`, `profanity_lexicon.py`, `non_verbal_palette.py` 추가.
3. `docs/contracts/change_requests.md` 에:
   - "Add `incivility` signal to Understanding Agent output" (Affected: Developer C)
   - "Use `incivility.tier ≥ 2` in branch/bad-ending policy" (Affected: Developer B)
   - "Forward `incivility` from C adapter to A payload" (Affected: Developer C)
4. `.env.example` 에 새 토글 + 사용 가이드 주석 추가.
5. README 또는 운영 노트에 **게임 등급 영향** 명시:
   > `MURPHY_NPC_PROFANITY_MIRROR_MODE=mirror` 활성화 시 출시 등급이 T(13+) 이상으로 격상될 수 있음. 배포 전 등급 심사 정책 확인 필수.

---

## 4. Profanity Mirror — 핵심 매트릭스 한 장 요약

| tier | 입력 카테고리 | mode=off | mode=firm (기본 권장) | mode=mirror |
|---|---|---|---|---|
| **T0** | 정상 | 평상 응답 | 평상 응답 | 평상 응답 |
| **T1** | 무례 (`"shut up"`, `"stupid"`) | 평상 응답 | 정색 + 톤 경고, 욕설 X | 정색 + 톤 경고, 욕설 X |
| **T2** | 인격 모독 (`"you idiot"`, `"loser"`) | 평상 응답 | 단호한 절차 경고, 욕설 X | mild profanity 1단어 (`"damn"`, `"hell"`) 허용 |
| **T3** | 욕설·혐오·위협 (`"fuck you"`, `"kill yourself"`) | bad ending 위임 | 절차 종료 ("This interview is over.") | mild/strong 미러링 + 절차 종료 |

**불변 가드 (mode 무관, 모든 tier):**
- 슬러(인종/성별/성적지향/장애 비하), 혐오 표현, 폭력 위협, 성적 묘사 → **항상 금지**. 출력에 등장 시 폴백.
- 미성년 보호 관련 표현 → 항상 금지.
- 출력의 모든 어휘는 `profanity_lexicon.allowed_for(mode, intensity)` 화이트리스트 안에서만.
- 욕설은 NPC 페르소나 일관성 안에서만 (immigration_officer 는 "damn/hell" 수준, seatmate 는 "what the heck" 수준 등).

---

## 5. 신규 Change Request 초안 (Developer C/B 영역)

본 계획 머지 전에 등록 필요. **A 단독으로 분류 신호를 추측해 분기 흉내내는 것은 가드레일 위반**.

### CR-1 (Affected: Developer C) — Understanding Agent `incivility` Signal

- Understanding Agent 출력에 `incivility: {tier, detected_terms, confidence, category}` 추가.
- 분류는 룰베이스(키워드 사전)와 LLM 모드 모두에서 산출.
- 가드: 분류 자체는 신호이며 분기 권한은 Developer B 유지.

### CR-2 (Affected: Developer B) — Bad Ending / Penalty Policy on `incivility.tier ≥ 2`

- B Policy 가 tier ≥ 2 인 경우 분기·페널티·bad ending 트리거 결정 권한 보유.
- A 는 결정된 분기 결과(`branch_type`)와 함께 `incivility` 정보를 받아 발화 표현만 담당.

### CR-3 (Affected: Developer C) — Forward `incivility` to A Payload

- `dev_a_npc_dialogue_client.py` 의 `_build_level_design_payload` 가 `incivility` 를 A-facing payload 에 포함.

---

## 6. 일정 / 의존성

| Phase | 의존성 | 공수 |
|---|---|---|
| A. 프롬프트 외부화 + 9 계층 | 없음 | 1.5d |
| B. Flash v2.5 비-텍스트 인프라 | A 머지 | 1.0d |
| C-1. 토글/계약 | CR-1, CR-2, CR-3 등록 | 0.5d |
| C-2. 룰베이스 응답 매트릭스 | A, B | 0.5d |
| C-3. 프롬프트 §9 | A, C-2 | 0.5d |
| C-4. 후처리 검증 | C-2 | 0.5d |
| D. TTS 파라미터 연동 | C-2 | 0.5d |
| E. 테스트 | 전부 | 1.5d |
| F. 정리/문서 | 전부 | 0.5d |
| **합계** | | **~7.0d** |

CR-1/2/3 가 Developer B/C 측에서 구현 완료될 때까지 **A 측은 tier 신호를 "주입 없음(T0)" 으로 가정한 룰베이스/LLM 분기까지만 머지**하고, payload 에 `incivility` 가 도착하면 자동 활성되도록 설계.

---

## 7. 위험 요소 및 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| OpenAI 콘텐츠 정책으로 mild profanity 도 거부될 수 있음 | mirror 모드에서 빈번한 LLM 폴백 | C-2 룰베이스 폴백 사전이 항상 침묵 없이 응답. 운영 모니터링으로 거부율 추적 후 strong intensity 토글 조정 |
| ESRB/플랫폼 등급 격상 | 출시 일정/유통 채널 영향 | 기본은 `off`. `mirror` 는 명시적 옵트인. README/운영 노트에 명문화. 등급 심사 전 미리 비활성화 |
| Speaker discipline 가드(P0) 와 §9 가 충돌 가능 | 화자 혼동 재발 | few-shot 의 PROFANITY MIRROR 예시에 "player_text 와 동일 문구를 NPC 가 따라 말하지 않음" 강조 |
| `<break time="3s"/>` 남용으로 응답이 지나치게 길어짐 | 게임 템포 저하 | `audio_quality_service` 침묵 비율 검출로 임계치 초과 시 폴백 |
| 슬러/혐오 어휘가 LLM 출력에 우연히 포함 | 심각한 운영 사고 | `ALWAYS_BLOCKED` 사전이 모드 무관 항상 적용. 차단 시 로그 알람 |
| `incivility` 신호가 늦게 도착하거나 누락 | A 가 정상 응답으로 처리 → 욕설에 평이하게 답함 | T0 기본값으로 안전 동작. 신호 없을 때 폴백 동작이 회귀 그린이도록 보장 |
| 토글이 운영 중 잘못 바뀜 | 사용자 경험 급변 | `MURPHY_NPC_PROFANITY_MIRROR_MODE` 변경 시 시작 로그에 명시. AgentRun 로그에 mode 기록 |

---

## 8. PR 머지 체크리스트

- [ ] `backend/app/prompts/npc_dialogue_prompt.md` 외부 파일 로드 정상 (테스트 그린)
- [ ] `npc_text` 출력에 SSML 태그 없음 (회귀 그린)
- [ ] `tts_text` 의 `<break time>` 0.0~3.0s 클램프 동작
- [ ] `MURPHY_NPC_PROFANITY_MIRROR_MODE=off` 인 환경에서 모든 기존 회귀 그린
- [ ] `MURPHY_NPC_PROFANITY_MIRROR_MODE=mirror` 환경에서 tier 매트릭스 12 케이스 그린
- [ ] `ALWAYS_BLOCKED` 사전이 모드 무관 작동
- [ ] CR-1/2/3 가 `change_requests.md` 에 등록되고 Affected Owner 명시됨
- [ ] `docs/handoff.md`, `docs/agent_a_structure.md`, `.env.example` 갱신
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run mypy .` 그린
- [ ] B/C 영역 파일 0 변경 (가드레일)

---

## 9. 후속 (별도 RFC)

1. **Eleven v3 도입** — audio tag(`[sigh]`, `[laughs]`, `[whispers]`, `[hesitates]`) 정식 사용. NPC 페르소나·tier 별 tag 팔레트 매핑. 모델 라우팅(주요 NPC = v3, 일반 발화 = flash v2.5)으로 비용/지연 최적화.
2. **`incivility` 분류 LLM 모드** — Understanding Agent 의 분류 정확도를 LLM 기반으로 강화. 룰베이스 사전만으로는 우회 발화(예: `"f*ck"`, leet speak) 탐지에 한계.
3. **Player-side Coaching** — `mode=firm` 에서 NPC 가 정색한 후 게임 UI 가 "이런 표현은 …" 같은 학습 피드백을 표시(Developer B/C 영역).
4. **bad ending 시나리오 분기 노드** — T3 발화 시 진입할 `BAD_END_VERBAL_ABUSE` 노드를 Developer B 시나리오 데이터에 신설.
