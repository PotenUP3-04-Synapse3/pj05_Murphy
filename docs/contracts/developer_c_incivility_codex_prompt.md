# Developer C 인계 프롬프트 — Incivility 신호 산출 & A 어댑터 Forward

> 발행: Developer A / kimyonghee · 2026-06-16
> 대상: Developer C / Sean Han (Understanding Agent + 통합 어댑터)
> 관련 CR: `CR-A1` (Understanding 분류), `CR-A3` (어댑터 forward)
> 본 문서는 Codex/AI 에이전트가 그대로 받아 작업을 수행할 수 있는 self-contained 프롬프트입니다.

---

## 컨텍스트 (필독)

Developer A 측은 NPC 발화의 격앙/욕설 미러링(`MURPHY_NPC_PROFANITY_MIRROR_MODE`) 모드 구현을 완료했습니다. 그러나 신호 산출과 어댑터 전달이 비어 있어 `"fuck you"` 같은 T3 욕설도 평상 응답으로 처리됩니다.

검증:
```bash
$ grep -rn "incivility" backend/app/services/service_c backend/app/agents/agent_c \
                       backend/app/integrations backend/app/schemas
# (no matches)  ← Developer C 영역 전체에 incivility 신호 부재
```

A 측 수신부(이미 준비됨):
- `backend/app/agents/agent_a/npc_dialogue_agent.py:218` — `payload.get("incivility") or {}`
- `backend/app/services/service_a/profanity_response_policy.py` — `get_profanity_fallback_response(npc_id, tier, mode)`
- `backend/app/services/service_a/voice_output_service.py:389` — `_apply_incivility_bias(...)`

가드레일: 분류 신호는 산출만 하고, **분기/페널티는 Developer B 가 결정**합니다. C는 신호 생산자 + 어댑터 전달 책임만.

---

## 작업 1 — CR-A1: Understanding Agent 에 `incivility` 신호 추가

### 1-1. 스키마 추가

`backend/app/schemas/game_turn.py` (또는 동등 위치) 의 Understanding 출력 스키마에 다음 필드 추가:

```python
class IncivilityClassification(BaseModel):
    tier: int = Field(0, ge=0, le=3, description="0=정상, 1=무례, 2=인격모독, 3=욕설/혐오/위협")
    detected_terms: list[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    category: Literal["rudeness", "insult", "profanity", "slur", "threat", "none"] = "none"
    source: Literal["rule", "llm", "none"] = "none"

class UnderstandingOutput(BaseModel):
    ...
    incivility: IncivilityClassification | None = None  # additive, optional
```

### 1-2. Rule-mode 분류기 (필수, 최소 구현)

`backend/app/services/service_c/incivility_classifier.py` 신설.

- 키워드 사전 기반. tier 별 어휘 목록:
  - **T1 무례:** `shut up`, `stupid`, `dumb`, `loser`, `pathetic`
  - **T2 모욕:** `you idiot`, `you're useless`, `moron`, `asshole`
  - **T3 욕설/위협:** `fuck`, `fuck you`, `shit`, `bitch`, `kill yourself`, `die`, 한국어 욕설 일부 (`씨발`, `개새끼`, `좆`)
- 우회 표기도 일부 매칭: `f*ck`, `f**k`, `fck`, `phuck` (정규식 또는 lookup table).
- 슬러/혐오발언: tier=3, category=slur 로 분류. 본 문서에는 어휘 미게재 (별도 ALWAYS_BLOCKED 사전 참고).

호출 예:
```python
def classify_incivility_rule(player_text: str) -> IncivilityClassification:
    """player_text 의 키워드 매칭만으로 tier 산출.
    confidence 는 매칭 강도(다중 매칭이면 ↑), category 는 최고 tier 카테고리.
    """
```

### 1-3. LLM-mode 분류 (선택, 정확도 보강)

- 옵션 A: `understanding_agent.py` 의 기존 LLM 호출 응답 스키마에 `_incivility` 필드 추가 (같은 호출에서 함께 추출 → 비용 0 추가).
- 옵션 B: 별도 LLM 호출 (정확도 우월, 지연 +)
- 환경변수: `MURPHY_INCIVILITY_CLASSIFIER_MODE=rule|llm|hybrid` (기본 `rule`).
- `hybrid`: rule이 tier ≥ 1 이면 LLM 로 확정 검증.

### 1-4. Understanding Agent 통합

`backend/app/agents/agent_c/understanding_agent.py` 의 `evaluate_turn` 종료 직전:

```python
mode = settings.murphy_incivility_classifier_mode  # rule|llm|hybrid
if mode == "rule":
    result.incivility = classify_incivility_rule(payload.player_text)
elif mode == "llm":
    result.incivility = classify_incivility_llm(payload.player_text)
elif mode == "hybrid":
    rule_res = classify_incivility_rule(payload.player_text)
    result.incivility = (
        classify_incivility_llm(payload.player_text) if rule_res.tier >= 1 else rule_res
    )
```

### 1-5. 테스트 (필수)

신설: `backend/tests/test_understanding_incivility_classifier.py`

- T0~T3 각 tier별 입력 → tier 정확히 일치
- `"fuck you"` → tier=3, category=profanity, confidence ≥ 0.9
- 우회 표기 `"f*ck you"` → tier=3 (LLM 모드)
- 한국어 욕설 → tier=3
- 정상 발화 → tier=0

### 1-6. 환경변수

`.env.example` 추가:
```bash
# Understanding Agent 의 incivility 분류 모드.
# rule  : 키워드 사전만 (기본, 비용 0)
# llm   : LLM 분류 (정확도 우월, 비용/지연 ↑)
# hybrid: rule이 tier>=1 이면 LLM로 검증
MURPHY_INCIVILITY_CLASSIFIER_MODE=rule
```

---

## 작업 2 — CR-A3: A 어댑터 `incivility` Forward

### 2-1. 어댑터 수정

`backend/app/integrations/dev_a_npc_dialogue_client.py` 의 `_build_level_design_payload` 에 추가:

```python
return {
    "node_id": payload.current_node_id,
    "player_text": payload.player_text,
    "npc": npc,
    "node_context": node_context,
    "understanding": payload.understanding.model_dump(),
    "transition": payload.transition.model_dump() if payload.transition else None,
    # ✨ 신규: incivility 신호를 A-facing payload 최상위에 forward
    "incivility": (
        payload.understanding.incivility.model_dump()
        if payload.understanding.incivility is not None
        else {"tier": 0, "source": "none"}
    ),
    "evaluation_summary": {...},
    ...
}
```

### 2-2. AgentRun 로깅

`response_builder.py` 또는 `agent_run_summary_service.py` 에서 응답 로그에 `incivility.tier`, `incivility.source` 를 evidence_summary 에 포함하여 추적 가능하도록.

### 2-3. 테스트

신설: `backend/tests/test_dev_a_adapter_incivility_forward.py`

- Understanding 결과의 `incivility.tier=3` → A-facing payload 최상위에 `incivility` 키 존재, tier=3
- Understanding 결과의 `incivility=None` → A-facing payload 의 `incivility = {"tier": 0, "source": "none"}` (안전 폴백)

---

## 가드레일 체크리스트 (PR 머지 전)

- [ ] Developer A 영역(`backend/app/agents/agent_a`, `backend/app/services/service_a`, `backend/app/tools/tool_a`, `backend/app/middleware/middleware_a`, `backend/app/prompts/npc_dialogue_*.md`) 0 수정. `git diff --stat | grep -E "(agent_a|service_a|tool_a|middleware_a|npc_dialogue)"` → 0 lines.
- [ ] Developer B 영역(`backend/app/agents/agent_b`, `backend/app/services/service_b`, `backend/app/data/scenario_nodes.json`) 0 수정.
- [ ] 분기 결정/페널티/bad ending 트리거 로직을 C 측에 작성하지 않음. C는 신호만 산출 + 전달.
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run mypy .` 그린.
- [ ] `/respond-dialog` 에서 (a) 정상 답변 → tier=0, (b) `"shut up"` → tier=1, (c) `"fuck you"` → tier=3 신호가 AgentRun 로그에 정확히 찍힘.
- [ ] `docs/handoff.md` 에 C 작업 완료 기록 + CR-A1/A3 Status 갱신.

---

## 검증 시나리오 (수동)

```bash
$env:MURPHY_NPC_PROFANITY_MIRROR_MODE = "mirror"
uv run uvicorn backend.app.main:app --reload

# /respond-dialog 에서:
# 1. 정상 답변 → 평상 응답
# 2. "shut up" → NPC 정색 경고 ("Watch your tone.")
# 3. "fuck you" → A 측 mirror 응답 ("Get the hell out of my line.") + AgentRun 에 tier=3 기록
#    (단, bad ending 분기는 B 측 CR-A2 머지 후 동작)
```

---

## 우선순위 / 의존

- **CR-A1 → CR-A3 순서로 진행** (분류 산출 후 어댑터 forward).
- CR-A2/A4 (B 측)는 본 C 작업과 독립 진행 가능.
- 본 C 작업 완료 후 A 측은 mirror 응답을 즉시 청취 가능 (bad ending 제외).

---

## 참고 파일

- 본 요청 정식 CR: `docs/contracts/change_requests.md` 의 `CR-A1`, `CR-A3` 섹션
- A 측 구현: `backend/app/services/service_a/profanity_response_policy.py`, `profanity_lexicon.py`
- B 측 작업 가이드: `docs/contracts/developer_b_bad_ending_codex_prompt.md`
