# 작업계획서: 억까 세관 물품 "압박 판정" 일반화 수정

## Context (배경)

진단([customs_pressure_diagnostic_plan.md](customs_pressure_diagnostic_plan.md) / 보고서)에서
`BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`의 구조적 구멍이 확정됨:

- **rule 모드 95.8%, llm 모드 68.1% 누출**. 24종 중 23종이 generic 답변("선물이에요"
  등)으로 통과. 유일하게 막힌 `ITEM_GOLD_BAR`도 하드코딩(`_is_gold_bar_violation`) 덕분.
- **근본 원인**: 물품의 `difficulty / item_category / suspicion_reason`가 판정 파이프라인
  (understanding → decide)에 **전혀 전달되지 않음**. 판정은 `customs_item_explanation`
  슬롯이 채워졌는지만 보고, 난이도와 무관하게 generic 답변을 수용.

### 의도한 결과

억까 물품에 대한 **불충분한 설명은 난이도에 비례해 더 압박(REASK/clarify)** 하고, 물품의
구체적 의심 사유를 다룬 설명만 통과시킨다. 금괴 하드코딩을 **데이터 기반 일반 규칙**으로
흡수한다. 저난이도 물품의 generic 통과는 정상 동작으로 유지(과잉 압박 금지).

## 설계 (3계층)

### Part 1 — 물품 컨텍스트를 판정기로 배선 (양 모드 공통 전제)

판정기가 "어떤 물품인지"를 알아야 함. LLM payload는 `node_context.model_dump()`로
직렬화되고([understanding_agent.py:342](../../backend/app/agents/agent_c/understanding_agent.py)),
`public_node_context`는 `recommended_expression`만 제거([openkb_service.py:79](../../backend/app/services/service_c/openkb_service.py))하므로 NodeContext에 필드를 추가하면 LLM까지 전달된다.

1. **스키마**: [game_turn.py](../../backend/app/schemas/game_turn.py)에 작은 모델
   `CustomsItemJudgeContext`(item_name, item_category, difficulty, suspicion_reason) 추가하고
   `NodeContext`에 `customs_item_context: CustomsItemJudgeContext | None = None` 필드 추가.
2. **주입**: [graph_tools.py `understand_player_text_tool`:317-328](../../backend/app/tools/tool_c/developer_c_graph_tools.py)에서
   `game_state.random_customs_item`이 있고 현재 노드가 BAG_005/BAG_006일 때, node_context에
   해당 컨텍스트를 채워 `analyze_player_text`에 전달. (declared 동기화는 기존 로직 재사용)
3. `public_node_context` 통과 확인(필드 보존). 다른 노드는 `None`이라 영향 없음.

### Part 2 — LLM 판정 (production 주 경로, 프롬프트)

[understanding_llm_client.py `_developer_instructions()`](../../backend/app/agents/agent_c/understanding_llm_client.py)
및 동기화 문서 [understanding_prompt.md](../../backend/app/prompts/understanding_prompt.md)에
"Customs item sufficiency" 규칙 추가:

- `node_context.customs_item_context`가 있으면, 플레이어 설명이 **그 물품의 구체적
  suspicion_reason을 합리적으로 해소하는지** 판단할 것.
- 고난이도/고위험 물품에 대해 의심 사유(수량/검역/신고/재판매 등)를 다루지 않는
  generic "gift/souvenir/personal item"은 **불충족**: `intent_satisfied=false`,
  `needs_clarification=true`, 필수 슬롯 missing 유지 → state machine이 REASK(압박).
- 저난이도 물품은 generic 설명도 충족으로 인정(과잉 압박 방지).

### Part 3 — rule 모드 게이트 + 위험 일반화 (state machine)

rule 모드는 의미적 구체성 판단이 불가하므로 결정적 게이트로 보완하고, 금괴 하드코딩을
일반화한다. [scenario_state_machine.py](../../backend/app/services/service_b/scenario_state_machine.py):

1. **난이도 게이트(압박)**: `customs_item_context.difficulty >= THRESHOLD`인 BAG_006에서
   설명이 generic(아이템 고유 토큰/신고 표현 없음)이면 성공으로 보지 않고 clarify/retry로
   라우팅하는 헬퍼 `_customs_explanation_insufficient(payload)` 추가, `decide()`/`_is_success`
   경로에 반영. 룰 모드 키워드 매핑([understanding_agent.py:132-138](../../backend/app/agents/agent_c/understanding_agent.py))의 free-pass를 차단.
2. **위험 일반화(critical)**: `_is_gold_bar_violation`을 `_is_undeclared_high_value_violation`로
   교체 — `declared`가 거짓이고 `item_category in {"valuable", "luxury"}`이며 BAG_005/006일 때
   critical bad_end. 금괴(valuable)·파텍시계(luxury)를 데이터 기반으로 흡수. 그 외 물품은
   instant bad_end가 아니라 Part 2/3-1의 **압박 메커니즘**으로 처리(점진 실패는 기존
   patience/retry escalation이 담당).

### 결정 필요 (권장값 명시)

| 항목 | 권장 | 비고 |
|---|---|---|
| 압박 난이도 임계치 THRESHOLD | **7** (TSL 3+) | 4-6 functional은 generic 허용, 7 이상부터 구체성 요구 |
| critical(즉시 bad_end) 범위 | **category {valuable, luxury} 미신고** | 금괴 하드코딩을 정확히 대체. 나머지는 압박 |
| rule 모드 투자 | **경량 게이트 도입** | LLM이 production이지만 fallback/오프라인 누출 차단 |

## 검증

1. **probe 하네스 확장 + 재실행** ([customs_pressure_probe.py](../../backend/tests/eval_harness/customs_pressure_probe.py)):
   - positive control 추가: 물품별 **구체적·충분한 설명**은 통과(PASS)해야 함.
   - 재실행 기대치: 고난이도(>=7) generic 답변 누출 → **0(압박됨)**, 저난이도 generic → 통과 유지,
     valuable/luxury 미신고 → critical.
2. **단위 테스트**:
   - critical 일반화: 금괴 여전히 bad_end, 파텍시계 신규 bad_end, 저가 물품은 아님,
     신고된 valuable은 통과 ([test_scenario_state_machine_loop_exit.py](../../backend/tests/dev_b/test_scenario_state_machine_loop_exit.py)).
   - rule 난이도 게이트: 고난이도 generic → REASK, 저난이도 generic → success.
   - LLM 계약: FakeUnderstandingLLMClient가 고위험 generic에 `intent_satisfied=false` 반환 시
     decide()가 REASK ([test_llm_acceptance.py](../../backend/tests/test_llm_acceptance.py)).
3. **회귀/품질**: 전체 suite + `ruff` + `mypy`(venv: `.venv/Scripts/python.exe`).

## 범위 밖 / 주의

- Part 2는 비결정적(LLM)이므로 probe 재실행으로 경향 확인하되, CI 게이트는 결정적 단위
  테스트(Part 3)에 둔다.
- 저난이도 물품 과잉 압박 금지(THRESHOLD 미만 generic 통과는 의도된 정상 동작).
- BAG_005(검사 동의) 노드의 설명 충분성은 이번 범위 밖(BAG_006 물품 설명에 집중).
