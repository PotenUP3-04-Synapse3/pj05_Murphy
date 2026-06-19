# Developer A — 평가 하네스 + 페르소나/스몰토크 프롬프트 보강 작업계획서

작성일: 2026-06-19
대상 실행 에이전트: **Gemini (Developer A 페르소나)**
선행 문서:
- `docs/plans/dev_a_unified_memory_plan.md` (정본)
- `docs/plans/dev_a_speaker_role_guard_plan.md` (잔여 S-4, S-5 흡수)

본 계획은 사후 봉합형 룰 가드 누적을 끝내고, A 자체 회귀 검증 인프라
(평가 하네스)와 LLM 자유 대화 품질(페르소나/스몰토크 프롬프트)을 동시에
확보한다. B/C 영역 변경이 필요한 항목은 본 계획서 범위 밖이다.

---

## 0. 작업 가드레일

### 0.1 수정 가능 파일 (Developer A 소유 한정)
- `backend/app/agents/agent_a/npc_dialogue_agent.py`
- `backend/app/agents/agent_a/npc_llm_client.py`
- `backend/app/services/service_a/npc_roster_service.py`
- `backend/app/services/service_a/*.py`
- `backend/app/prompts/npc_dialogue_prompt.md`
- `backend/app/prompts/npc_dialogue_prompt.short.md`
- `backend/app/prompts/npc_dialogue_few_shots.md`
- **신규 디렉토리**: `backend/tests/eval_harness/**`
- `backend/tests/test_developer_a_npc_dialogue.py`
- 본 계획서

### 0.2 절대 수정 금지 파일 (Developer B/C 소유)
- `backend/app/agents/agent_b/**`, `backend/app/services/service_b/**`
- `backend/app/agents/agent_c/**`, `backend/app/services/service_c/**`
- `backend/app/api/**`, `backend/app/main.py`, `backend/app/graphs/**`
- `backend/app/schemas/**`, `backend/app/integrations/**`
- `backend/app/tools/tool_b/**`, `backend/app/tools/tool_c/**`
- `backend/app/middleware/middleware_c/**`
- `backend/app/data/scenario_nodes.json`
- `backend/app/kb/**`, `backend/runtime/openkb/**`
- 위 영역에 속하는 모든 테스트

### 0.3 의존성
- `langchain==1.3.2`, `langgraph==1.2.2` 고정. 추가 패키지는 평가 하네스용
  YAML 파서가 필요할 경우에 한해 `uv add pyyaml`만 허용. 그 외 금지.
- 테스트는 실제 OpenAI 키 없이도 결정형 채점은 통과해야 한다. LLM-as-judge는
  키가 있을 때만 동작하는 옵션 모드.

### 0.4 핵심 원칙
1. **새 가드 추가 금지.** 본 계획은 평가 하네스 + 페르소나/프롬프트 보강만
   다룬다. 발견된 결함은 가드로 막지 말고 하네스 케이스로 등록.
2. **Fail-fast 유지.** 기존 가드(`speaker_role_confusion` 등)는 그대로 둔다.
   계약 위반은 계속 명시적 예외.
3. **B/C 영역은 건드리지 않는다.** 본 계획서에 B/C 작업은 포함하지 않는다.

---

## 1. 문제 정의

### 1.1 현재 검증 구조의 한계
- 결함이 사용자/QA에 도달한 후에야 발견됨.
- 가드 추가 → 새 결함 발견 → 또 가드 추가의 무한 루프.
- 가드/프롬프트/모델 변경의 효과를 객관적으로 측정할 수 없음.

### 1.2 페르소나/프롬프트 부족
- `npc_roster_service.py`의 persona_instruction은 톤만 정의(예: "warm,
  patient"). 대화 행동 방침(토픽 전환 처리, 미해결 요청 유지, 본론 복귀)이
  없음.
- 스몰토크 모드 프롬프트는 `[Reaction]+[Transition]+[Followup]` 형식만 강제.
  자유 대화에서 자연스럽게 토픽 변경을 받되 본론으로 돌아오는 기술 부재.
- 결과: 플레이어가 토픽을 바꾸면 NPC가 본론(예: 펜 부탁)을 silently 버리고
  generic smalltalk 풀로 떨어지는 사고 (실제 테스트 케이스에서 관찰).

### 1.3 잔여 작업
`docs/plans/dev_a_speaker_role_guard_plan.md` 중 S-4 (few-shot Example 7)와
S-5 (가드 회귀 테스트 2종)이 누락된 상태로 본 계획에 흡수.

---

## 2. 목표 (Definition of Done)

1. 평가 하네스가 `backend/tests/eval_harness/` 아래에 구축되어 결정형
   채점만으로도 pytest에서 실행 가능.
2. 최소 골든 시나리오 30개 (NPC별/노드별 균등 분포)로 시작.
3. LLM-as-judge 모드는 환경변수 `MURPHY_EVAL_USE_LLM_JUDGE=1`일 때만
   동작. CI 기본 동작은 결정형.
4. NPC 페르소나 7종이 톤 + 행동 방침 형태로 보강.
5. 스몰토크 모드 프롬프트에 토픽 관리 가이드 추가.
6. 잔여 S-4 few-shot Example 7과 S-5 테스트 2종 완료.
7. `dev_a_npc_dialogue_client.py`가 보는 입출력 키 구조 변경 없음.
8. `uv run pytest`, `ruff check`, `mypy` 통과.

---

## 3. 작업 항목

### E. 평가 하네스 구축

#### E-1. 디렉토리 구조 신설
**경로 (신규):** `backend/tests/eval_harness/`

```
backend/tests/eval_harness/
├── __init__.py
├── scenarios/
│   ├── flight_a_arabella.yaml
│   ├── flight_a_novak.yaml
│   ├── flight_a_emily.yaml
│   ├── immigration_hale.yaml
│   ├── immigration_harris.yaml
│   ├── baggage_brielle.yaml
│   └── customs_dan.yaml
├── runner.py              # 시나리오 로더 + invoke + 결과 수집
├── scorers/
│   ├── __init__.py
│   ├── deterministic.py   # 키워드/슬롯/분기/금지 표현 매칭
│   └── llm_judge.py       # LLM-as-judge (옵션)
├── reporter.py            # JSON 리포트 + 콘솔 요약
└── README.md              # 사용법 한국어 1페이지
```

#### E-2. 시나리오 YAML 스키마

한 시나리오 한 항목 예시:

```yaml
- id: flight_a001_pen_unclear_response
  npc_id: arabella
  node_id: FLIGHT_A_001_SEATMATE_SMALLTALK
  description: "펜 부탁에 모호한 답변. NPC는 화자 역할 유지 + 재요청해야 한다."
  payload_overrides:
    dialogue_directive:
      purpose: smalltalk_diagnostic
  player_inputs:
    - "Hello?"
  expected:
    npc_role_must_not_be_giver: true        # 결정형
    must_include_any: ["pen", "borrow"]     # 결정형
    must_not_include_any: ["here you are", "here you go", "of course, take"]
    branch_type_in: ["retry", "clarify"]    # 결정형
    rubric_for_judge: |                     # LLM-as-judge용
      "Does the NPC re-ask for the pen instead of acting as the giver?
      Tone should match Arabella (warm, patient)."
```

규칙:
- `payload_overrides`는 베이스 페이로드 위에 deep-merge.
- `player_inputs`는 1개 이상의 턴 시퀀스. 각 턴마다 invoke → 결과 수집.
- `expected` 는 결정형 키와 `rubric_for_judge` 두 종류 혼합 가능.

#### E-3. 베이스 페이로드 생성 헬퍼
**파일:** `backend/tests/eval_harness/runner.py`

`def build_base_payload(npc_id: str, node_id: str) -> dict[str, Any]`:
- npc_id, node_id로 최소 유효 페이로드를 합성.
- session_id는 시나리오 ID 기반 deterministic (예:
  `eval:{scenario_id}`)로 fail-fast 통과.
- `scenario_nodes.json`을 읽어 npc_question 등 노드 메타를 채움.
- payload_overrides를 deep-merge.

#### E-4. Runner
**파일:** `backend/tests/eval_harness/runner.py`

```python
def run_scenario(scenario: dict, *, use_llm: bool) -> ScenarioResult:
    payload = build_base_payload(scenario["npc_id"], scenario["node_id"])
    payload = deep_merge(payload, scenario.get("payload_overrides", {}))
    turns: list[dict] = []
    for player_text in scenario["player_inputs"]:
        payload["player_text"] = player_text
        result = generate_npc_dialogue_from_level_design(
            payload, use_llm=use_llm
        )
        turns.append({"player_text": player_text, "result": result})
    return ScenarioResult(scenario_id=scenario["id"], turns=turns)
```

#### E-5. Deterministic Scorer
**파일:** `backend/tests/eval_harness/scorers/deterministic.py`

각 expected 키별 채점 함수:
- `score_npc_role_must_not_be_giver(turn, marker_list) -> bool`
- `score_must_include_any(turn, patterns) -> bool`
- `score_must_not_include_any(turn, patterns) -> bool`
- `score_branch_type_in(turn, allowed) -> bool`

반환: `{"key": "must_include_any", "passed": bool, "details": str}`.

#### E-6. LLM-as-Judge Scorer (옵션)
**파일:** `backend/tests/eval_harness/scorers/llm_judge.py`

```python
def judge(rubric: str, turn: dict) -> dict:
    """환경변수 MURPHY_EVAL_USE_LLM_JUDGE=1일 때만 동작."""
    if not os.getenv("MURPHY_EVAL_USE_LLM_JUDGE"):
        return {"passed": None, "skipped": True}
    # 가벼운 모델로 호출 (예: gpt-5.4-mini)
    # 출력은 strict JSON {"passed": bool, "reason": str}
```

비용 통제: LLM-as-judge는 PR 자동 실행에서 빠짐. 로컬/스케줄 전용.

#### E-7. Reporter
**파일:** `backend/tests/eval_harness/reporter.py`

- 콘솔: `scenario_id | passed/total | failed keys`
- JSON: `backend/tests/eval_harness/reports/{timestamp}.json`
- 실패 임계: `--threshold 0.8` 옵션. 통과율이 80% 미만이면 비-zero exit.

#### E-8. pytest 통합 (smoke)
**파일:** `backend/tests/test_eval_harness_smoke.py`

```python
def test_eval_harness_deterministic_smoke():
    """결정형 채점만 사용해 전 시나리오를 runner로 돌리고 통과율 >=0.8 확인.
    LLM-as-judge는 사용하지 않음 (CI는 OpenAI 키 없음 가정).
    """
    summary = run_all(use_llm=False, scorer="deterministic")
    assert summary.pass_rate >= 0.8
```

이 테스트가 PR마다 자동 실행. 결정형만으로도 화자 혼동/금지 표현/분기
같은 명시적 결함은 잡힘.

#### E-9. 초기 시나리오 30개 작성
**파일:** `backend/tests/eval_harness/scenarios/*.yaml`

분포 권장:
- Arabella (seatmate): 6개
  - 펜 부탁 + 정상 응답 / 모호 응답 / 토픽 전환 / 거절 / 토픽 복귀
- Novak (quiet seatmate): 4개
- Emily (form helper): 4개
- Hale (immigration officer): 8개
  - 통상 질문 / 압박 질문 / 재질문 / 트집 / cross-turn callback / 욕설 응대
- Harris (meticulous officer): 4개
- Brielle (baggage agent): 2개
- Dan (security officer): 2개

각 시나리오는 §E-2 스키마 준수. ASCII-only, 영어 텍스트.

#### E-10. 사용법 README
**파일:** `backend/tests/eval_harness/README.md`

한국어 1페이지로 다음 내용 포함:
- 실행 명령: `uv run pytest backend/tests/test_eval_harness_smoke.py`
- 시나리오 추가 방법
- LLM-judge 활성화 방법 (`MURPHY_EVAL_USE_LLM_JUDGE=1`)
- 리포트 위치
- 임계값 변경 방법

---

### P. 페르소나/스몰토크 프롬프트 보강

#### P-1. NPC 페르소나에 행동 방침 추가
**파일:** `backend/app/services/service_a/npc_roster_service.py`

7개 NPC의 `persona_instruction`을 톤+행동 방침 형태로 확장. 예시:

```python
"arabella": NPCProfile(
    ...
    persona_instruction=(
        "Very friendly, warm, patient, socially easygoing seatmate. "
        "Enjoys small talk and gracefully follows the player's topic shifts. "
        "Pending-request rule: if you previously asked for something (e.g., "
        "a pen) and the player changes the subject, briefly acknowledge "
        "their new topic in 1 sentence, then return to your pending request "
        "within the same turn. Never silently drop your own request."
    ),
    ...
),
"hale": NPCProfile(
    ...
    persona_instruction=(
        "Stern, direct, and authoritative immigration officer. "
        "Speaks in short clipped sentences. Does not soften with "
        "'please' or 'could you' during pressure probes. "
        "Pending-request rule: re-ask once if the player evades. "
        "Topic-discipline: never follows the player into off-topic chat."
    ),
    ...
),
```

7개 NPC 모두 동일 방식으로 보강. 핵심 행동 방침:
- pending-request 처리 규칙
- topic-discipline (자유 따라가기 vs 본론 유지) — NPC별로 다름
- 응답 길이 가이드

ASCII-only, 영문, 페르소나 일관성 유지.

#### P-2. 스몰토크 모드 프롬프트에 토픽 관리 가이드
**파일:** `backend/app/prompts/npc_dialogue_prompt.md`,
`backend/app/prompts/npc_dialogue_prompt.short.md`

기존 `# DIALOGUE STRUCTURE` 의 smalltalk_diagnostic 블록 아래에 추가:

```
{% if purpose == 'smalltalk_diagnostic' %}
- Topic management:
  * If the player changes topic while your previous request is still
    unresolved, follow these steps in ONE turn:
    (a) briefly react to the player's new topic (1 short sentence),
    (b) return to your own pending request (the topic you originally raised),
    (c) do not drop your request silently.
  * Real conversation drifts. You MAY accept short topic detours, but
    always circle back to your goal within 1-2 turns.
  * If the player gives a non-answer (e.g., "Hello?", "What?"), assume
    they did not understand. Re-ask your request in a friendly way.
{% endif %}
```

short 프롬프트에도 한 단락으로 압축 추가.

#### P-3. 본론 복귀 few-shot 예시 1개
**파일:** `backend/app/prompts/npc_dialogue_few_shots.md`

Example 8로 추가 (S-4의 Example 7 다음):

```
### Example 8: Topic detour + return to pending request (Smalltalk)
- Input payload (요점):
  npc_question: "Could I borrow your pen for this arrival form?"
  player_text: "What's your name?"
  surface_goal: "estimate_user_travel_speaking_level"
  branch_type: "retry"
  purpose: "smalltalk_diagnostic"
- Expected NPC output:
  npc_text: "I'm Arabella, by the way. So — that pen? I just need it for a minute."
  tts_text: "I'm Arabella, by the way. <break time='0.4s'/> So — that pen? I just need it for a minute."
  feedback_kr: "Good."
  tone: "formal_neutral"
  animation: "move"
  npc_emotion: "normal"
  llm_reason: "[COHERENT] Player off-topic; brief reaction then circle back to pen request per Arabella's persona."
```

---

### S. 잔여 흡수 (speaker_role_guard plan의 S-4, S-5)

#### S-4. few-shot Example 7 추가
**파일:** `backend/app/prompts/npc_dialogue_few_shots.md`

`dev_a_speaker_role_guard_plan.md` §S-4의 본문 그대로:
펜 부탁 + `"Hello?"` → NPC가 응답자 역할 하지 않고 re-ask하는 예시.

번호는 Example 7로. (P-3의 Example 8과 함께 추가.)

#### S-5. 가드 회귀 테스트 2종
**파일:** `backend/tests/test_developer_a_npc_dialogue.py`

`dev_a_speaker_role_guard_plan.md` §S-5의 두 테스트:
1. `test_speaker_role_confusion_guard_blocks_giver_phrase`
2. `test_speaker_role_confusion_guard_allows_legitimate_response`

내용은 해당 계획서 본문 참조.

---

## 4. 실행 순서 권장

1. P-1 (페르소나 행동 방침 보강) — 7개 NPC 일괄
2. P-2 (스몰토크 토픽 관리 가이드 프롬프트) + P-3 (few-shot Example 8)
3. S-4 (few-shot Example 7)
4. S-5 (가드 회귀 테스트 2종)
5. E-1 ~ E-2 (디렉토리/스키마)
6. E-3 ~ E-7 (러너/채점기/리포터)
7. E-8 (pytest smoke)
8. E-9 (시나리오 30개 작성) ← 가장 시간 큼
9. E-10 (README)

각 단계 후 `uv run pytest -k developer_a` 회귀, 마지막에 전체 + ruff + mypy.

---

## 5. 검증 체크리스트

- [ ] `uv sync` 성공 (필요 시 `uv add pyyaml`).
- [ ] `uv run pytest backend/tests/test_eval_harness_smoke.py` 통과
      (결정형 모드, pass_rate >= 0.8).
- [ ] `uv run pytest` 전체 그린.
- [ ] `uv run ruff check .` 그린.
- [ ] `uv run mypy .` 그린.
- [ ] `git diff --name-only` 결과가 §0.1 화이트리스트 내부만.
- [ ] 7개 NPC `persona_instruction`이 톤 + 행동 방침 형태로 갱신.
- [ ] 펜 부탁 + `"Hello?"` 시나리오를 하네스로 돌리면 결정형 채점 통과.
- [ ] 펜 부탁 + `"What's your name?"` 시나리오에서 NPC가 펜으로 복귀하는지
      결정형 채점 통과 (must_include "pen").
- [ ] `dev_a_npc_dialogue_client.py`가 보는 입출력 키 구조 변경 없음.

---

## 6. 본 계획서 범위 밖

다음은 B/C 영역이므로 본 계획서에서 코드 변경 없이 제외한다. 사용자가
별도 채널로 처리한다.

- `max_turns=5` 정책 완화 (B 영역)
- `MAX_HARD_FAIL_RETRIES=5` 완화 (B 영역)
- `polite_response` 슬롯 strictness (C 영역)
- 분기-응답 일치 가드 (B/C 영역)

본 계획서 실행 후, A 측 페르소나/프롬프트만으로 잡히는 부분과 B/C 영역
변경이 필요한 부분이 평가 하네스 점수로 분리되어 보일 것이다. 그 결과를
근거로 B/C 변경 요청 여부를 결정한다.

---

## 7. 본 작업의 가치 (Why)

1. **사후 봉합 종료**: 새 결함마다 가드를 추가하는 패턴이 평가 하네스의
   시나리오 추가로 대체된다. 코드 본체는 더 두꺼워지지 않는다.
2. **객관적 측정**: 페르소나/프롬프트/모델 변경의 효과가 점수로 보인다.
   "체감상 좋아진 것 같다"가 아니라 "스몰토크 통과율 47% → 72%".
3. **NPC 확장 비용 감소**: 신규 NPC 추가 시 시나리오 파일에 항목을 더하면
   회귀가 자동 보장된다.
4. **자유 대화 품질**: 페르소나의 pending-request 규칙 + 스몰토크 토픽 관리
   가이드로 LLM이 토픽 전환을 자연스럽게 받되 본론으로 복귀한다.
