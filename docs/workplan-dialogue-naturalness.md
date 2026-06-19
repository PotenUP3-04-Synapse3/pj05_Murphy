# 입국심사 대화 자연스러움 개선 작업계획서

> 작성일: 2026-06-19
> 작성자: wd14177 (level_agent)
> 소스: 실제 플레이 transcript(CH0_03 Officer Hale) 코드 레벨 진단
> 관련 메모리: `dialogue-awkwardness-diagnosis`
> 영향 영역: `agent_a`(대사 텍스트), `agent_c`(이해), `service_c`(오케스트레이션/어댑터), `service_b`(힌트 소유), `schemas/game_turn.py`

---

## 0. 요약

CH0_03 입국심사 실제 대화에서 "문법은 맞지만 어색한" 결함 5건을 코드 레벨로 진단했다. 어색함의 뿌리는 영어 문장 품질이 아니라 **"판정 결과 ↔ 응답 톤 ↔ 노드 의미 ↔ 학습용 데이터 경계"가 서로 어긋나 도는 것**이다.

| # | 증상 | 진짜 원인 | 영역 | 상태 |
|---|---|---|---|---|
| ③ | "Thank you, officer." 깨진 대사(화자 혼동) | `recommended_expression`(학습용 모범답안)이 A로 흘러 LLM이 그대로 echo | A | **부분완료**(echo 탐지 강화). 본 계획서 §2에서 **구조적 격리**로 마무리 |
| ④ | 시나리오에 없는 "음식 신고" 질문 + 김치 거절 | declaration suspicion 모드가 비-신고 노드(IMM_007=입국허가)를 침범, hard rule #3 미준수 | A(+B 데이터) | 미착수 |
| ② | "i said hotel" 통과 / "Grand Hyatt" 거절 | stay_location이 literal "hotel" substring만 매칭, 브랜드 어휘 부재 + 메타발화 가드 없음 | C | 미착수 |
| ① | "Good" 후 거절(톤 모순) | 톤이 branch_type/transition.status에 안 묶임 | A | 미착수 |
| ⑤ | (참고) closed-list 직업 — carpenter 거절 | 설계 의도(허용값 제한). 버그 아님 | B 데이터 | 보류 |

**핵심 설계 결정(§2):** `recommended_expression`은 **학습자용 모범답안**이며 유일한 정당 소유자는 **Developer B(힌트/피드백)**다. **A(NPC 인격 대사)와 C(이해)는 이 값을 절대 받지 않도록 경계에서 구조적으로 차단**한다. 이것이 ③의 근본 해결이자 ②의 literal-matching 의존을 줄이는 토대다.

가드레일(`AGENTS.md`): A는 대사/음성/페르소나, B는 분기/검증/점수/힌트, C는 오케스트레이터/스키마/이해/응답 어셈블러. 본 계획서는 §2에서 schema(`game_turn.py`)와 C 어댑터를 건드리므로 해당 변경은 C 소유 영역에서 수행하고, A·B 내부 변경은 각 영역에서 분리 PR로 처리한다.

---

## 1. 전체 작업 범위와 우선순위

P0부터 머지 단위로 잘게 쪼개고, 각 PR마다 회귀 테스트가 그린이도록 게이트를 둔다.

- **P0 — ③ recommended_expression 구조적 격리 (본 계획서 §2)**
  근본 원인이자 다른 항목의 토대. echo 탐지(이미 적용)는 방어선으로 유지하되, 값 자체가 A·C에 도달하지 않게 만든다.
- **P1 — ④ suspicion 침범 차단**
  declaration/location suspicion이 해당 슬롯 노드에서만 발화하도록 주입 조건 강화 + 비-신고 노드에서 세관 질문 생성 금지. 노드 데이터 정합성(선언 노드 부재) 점검 동반.
- **P2 — ① 거절 시 톤 분기**
  REASK/retry/clarify에서 긍정 리액션("Good") 금지. 톤을 branch_type/transition.status에 바인딩.
- **P3 — ② stay_location 판정 정밀화**
  호텔 브랜드 어휘 추가 + 자유형 호텔명 인정 + "i said hotel" 류 메타발화 가드. 단, P0 이후 C가 모범답안에 의존하지 않게 된 상태에서 진행.
- **P4(보류) — ⑤ 직업 closed-list**
  설계 의도이므로 UX 결정 후 별도 처리(예: 자유 입력 허용 시 B 데이터/판정 변경).

---

## 2. recommended_expression 격리 설계 (P0)

### 2.1 현재 데이터 흐름

```
scenario_nodes.json (recommended_expression 보유)
        │
        ▼
openkb_service.get_node_context()  →  단일 NodeContext (recommended_expression 포함)
        │
        ├──────────────► understanding_agent (C)   ← 받으면 안 됨
        │                     · _matched_generic_evidence_text 후보로 사용 (agent_c L542)
        │
        ├──────────────► DevBPolicyInput.node_context (B)  ← 정당 사용 (힌트 생성)
        │                     · english_level_hint_agent, feedback_hint_generator, bad_ending_policy ...
        │
        └──────────────► DevANpcDialogueClient (A)  ← 받으면 안 됨
                              · 어댑터가 dict에서 제거(_sanitize_a_facing_*)하지만,
                                A 내부 normalize_level_design_payload가 node_context/level_hint/
                                in_game_feedback 3곳에서 다시 읽음 (service_a/developer_a_input_service L20-25)
                              · 데모/직접 API 경로(ai_respond.py L264)는 어댑터를 우회 → 누출 발생 지점
```

**문제 본질:** B만 써야 할 값이 B·C·A 공유 `NodeContext` 한 곳에 실려 fan-out된다. 어댑터에서 그때그때 지우는 방식은 경로가 하나라도 빠지면(데모 API) 새는, 검증된 취약 구조다.

### 2.2 설계 원칙

1. **단일 소유권**: `recommended_expression`은 B-private. A·C 코드 경로에는 존재 자체가 없어야 한다.
2. **구조적 차단 > 규칙 차단**: "LLM아 echo하지 마" 프롬프트 규칙이나 출력 echo 탐지(사후)보다, **입력에서 값이 없게** 만든다(사전). echo 탐지는 defense-in-depth로 잔류.
3. **B 무중단**: B의 힌트 생성은 `recommended_expression`이 그대로 필요하므로 B 경로는 변경하지 않는다.

### 2.3 채택안 — 경계 분리(Boundary split) + 소비처 제거

스키마 대수술(Design B, §2.6) 대신, **C 오케스트레이션 경계에서 컨텍스트를 분기**하고 **A·C 소비처에서 읽기를 제거**한다. 위험 대비 효과가 가장 좋다.

#### (A) A-side — 단일 choke point 차단
- `service_a/developer_a_input_service.normalize_level_design_payload`
  - `recommended_expression` 추출/방출 제거(L19-25, L60). normalized 결과에서 키 자체를 없앤다.
  - 효과: **어떤 입력 경로든(오케스트레이터/데모/테스트) A 내부는 값을 보유하지 않음** → LLM에 보내는 JSON에 포함 불가 → echo 원천 차단.
- `agent_a/npc_dialogue_agent`
  - `_success_feedback`/`_retry_feedback`/`_level_design_feedback`: `recommended_expression` 인자 제거, 모범답안 미포함 버전으로 단순화(이미 빈 문자열 분기 존재 → "좋아요. 짧고 분명하게 전달했어요."). **학습자용 모범답안은 B 힌트가 담당**(중복 책임 제거).
  - echo 검사(L507-515): rec_exp가 항상 "" → 사실상 no-op. **방어선으로 유지**(주석으로 "isolation 이후 잔류 안전망" 명시). 향후 어떤 필드가 새도 잡는다.
- `agent_a/npc_llm_client._developer_instructions`
  - "Recommended expression ... never insert" 문장(L411) 유지 가능(무해). 단, prompt가 더 이상 값을 주입하지 않음을 주석화.
- `integrations/dev_a_npc_dialogue_client`
  - `_A_BLOCKED_*` 제거 로직 유지. `_candidate_text`(L160-179)의 `feedback.recommended_expression or policy.level_hint.recommended_expression` 참조 제거(사용처 없으면 함께 정리).

#### (B) C-side — 이해 단계가 값을 안 받고 안 쓰게
- `agent_c/understanding_agent._matched_generic_evidence_text`(L534-548)
  - 후보 리스트에서 `node_context.recommended_expression` 제거(L542). 남는 후보(`hint_policy.keyword`, `sentence_pattern`)로 충분.
  - 효과: C가 **모범답안 문구를 player_text 매칭 근거로 쓰지 않음**. (모범답안과 우연히 겹쳐 통과/거절되는 잡음 제거 → ② 정밀화의 토대)
- `tool_c/developer_c_graph_tools.understand_player_text_tool`(L312-322)
  - understanding 호출 시 **recommended_expression을 비운 NodeContext**를 전달(아래 헬퍼). "받지 않도록"을 데이터 레벨로 보장.
- `service_c/dev_a_npc_dialogue_client`로 가는 node_context도 동일 헬퍼로 blank 처리(어댑터 dict 제거와 이중화).

#### (C) 경계 헬퍼 (C 소유)
`service_c`에 `public_node_context(node_context: NodeContext) -> NodeContext` 추가:
```python
def public_node_context(node_context: NodeContext) -> NodeContext:
    """A·C에 넘길, 학습용 모범답안을 제거한 NodeContext 사본을 만든다."""
    return node_context.model_copy(update={"recommended_expression": ""})
```
- understanding 호출과 A 어댑터 입력에 이 사본을 사용. **B(DevBPolicyInput)에는 원본 그대로** 전달.
- `NodeContext.recommended_expression`은 required `str`(game_turn.py L260)이므로 ""로 유지(스키마 무변경, 위험 최소).

#### (D) 데모/직접 API
- `api/ai_respond.py`(L255-264): node_context를 A 페이로드에 실을 때 `public_node_context`를 거치도록 수정. (A normalizer가 이미 안 읽으므로 이중 안전.)

### 2.4 변경 파일 목록 (P0)

| 파일 | 변경 |
|---|---|
| `service_a/developer_a_input_service.py` | recommended_expression 추출/방출 제거 |
| `agent_a/npc_dialogue_agent.py` | feedback 헬퍼에서 모범답안 제거, echo 검사는 방어선으로 주석화 |
| `agent_a/npc_llm_client.py` | 주석 정리(동작 무변경) |
| `integrations/dev_a_npc_dialogue_client.py` | `_candidate_text`의 rec_exp 참조 제거, public_node_context 적용 |
| `agent_c/understanding_agent.py` | `_matched_generic_evidence_text` 후보에서 제거 |
| `tool_c/developer_c_graph_tools.py` | understanding 호출에 public_node_context 적용 |
| `service_c/openkb_service.py` 또는 신규 `service_c/node_context_view.py` | `public_node_context` 헬퍼 추가 |
| `api/ai_respond.py` | 데모 경로에 public_node_context 적용 |
| **무변경(중요)** | `agent_b/*`, `service_b/*`, `tool_b/*` — B는 원본 NodeContext 유지 |

### 2.5 테스트 계획 (P0)
- **신규**: `developer_a_input_service`가 어떤 입력 위치에 recommended_expression이 있어도 normalized 결과에 키가 없음을 단언.
- **신규**: `public_node_context(ctx).recommended_expression == ""`, 원본 불변.
- **신규**: understanding이 recommended_expression에 의존하지 않음(해당 값만으로는 슬롯이 채워지지 않음) 회귀.
- **유지/강화**: 기존 echo 테스트(`test_developer_a_npc_dialogue.py`) — isolation 후에도 그린.
- **B 회귀**: `dev_b` 힌트 테스트가 모두 그린(원본 컨텍스트 유지 확인).
- 전 스위트: `pytest backend/tests -q`.

### 2.6 대안 — 스키마 분리(향후 강화, 비채택)
`PublicNodeContext`(recommended_expression 없음)를 신설해 A·C 시그니처를 타입 레벨로 강제. 가장 견고하나 스키마·전 소비처·테스트를 광범위하게 건드려 위험/비용이 큼. P0는 §2.3(blank 사본)으로 가고, 안정화 후 타입 분리를 별도 과제로 승격.

### 2.7 마이그레이션/롤백
- 단계별 분리 PR(A-side → C-side → 경계 헬퍼/데모). 각 PR 독립 그린.
- 롤백: 헬퍼 호출만 되돌리면 원복(스키마 무변경이라 안전).

---

## 3. P1 — ④ suspicion 침범 차단 (요지)
- `npc_dialogue_prompt.md` SUSPICION MODE: hard rule #3을 입력 게이트로 승격 — `suspicion_scope`와 현재 노드의 `required_slots`가 매칭될 때만 suspicion 블록을 렌더(jinja 조건).
- A 입력 빌드에서 비-신고 노드면 `random_customs_item`/declaration 컨텍스트를 주입하지 않음.
- 데이터 점검: 선언/세관 노드가 시나리오에 실제로 필요한지 B와 합의(현재 CH0_03엔 declaration 노드 부재). 필요 시 노드 추가는 B 영역.
- 테스트: IMM_007(clearance)에서 세관 질문이 생성되지 않음을 단언.

## 4. P2 — ① 거절 시 톤 분기 (요지)
- `npc_dialogue_prompt.md`: branch_type ∈ {retry, clarify} 또는 transition status가 REASK/UNCLEAR일 때 **긍정 리액션 금지** 규칙 추가.
- `npc_dialogue_agent`: 결정적 경로 톤은 이미 retry=formal_firm. LLM 경로 결과의 tone/feedback을 분기와 정합되게 후처리 가드.
- 테스트: REASK 입력 시 npc_text가 "Good/Thank you" 등 긍정 접두로 시작하지 않음.

## 5. P3 — ② stay_location 판정 (요지)
- `agent_c/understanding_agent` ALPHA_SLOT_VALUE_KEYWORDS["stay_location"]: 호텔 브랜드 어휘 보강(hyatt, hilton, marriott, sheraton, ...) + 고유명사형 호텔명 휴리스틱.
- "i said hotel" 류 메타발화 가드: stay_location에도 off-topic/메타 표현 가드 추가(`_has_slot_intent_mismatch` 확장).
- P0 완료로 C가 모범답안에 의존하지 않는 상태에서 진행해 회귀 표면 축소.
- 테스트: "Grand Hyatt in Manhattan" 통과, "i said hotel" 비통과, "725 5th Avenue" 통과(현 코드 재현 확인 포함).

---

## 6. 수용 기준(전체)
- ③: A·C 어떤 경로에서도 `recommended_expression`을 보유/echo하지 않음(테스트로 보장). B 힌트는 정상.
- ④: clearance/비-신고 노드에서 세관 질문 미생성.
- ①: REASK에서 긍정 리액션 미발생.
- ②: 실호텔명 통과·메타발화 차단.
- 전 스위트 그린, 데모 `/respond-dialog`·`/ai-respond` 시나리오 정상.

## 7. 리스크
- A의 feedback_kr에서 모범답안이 빠지면 학습 UX가 B 힌트에 의존 → B 힌트가 최종 응답에 노출되는지(`UiResponse.recommended_expression`, response_builder) 확인 필요. (B→client 경로는 유지되므로 사용자에게는 그대로 노출됨.)
- C 매칭 후보 축소로 일부 엣지 입력의 판정이 달라질 수 있음 → 회귀 테스트로 포착.
