# 작업계획서: 억까 세관 물품 "압박 판정" 진단 루프

## Context (배경)

현재 세관 검사 노드 `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`은 물품을 설명하라고 요구하지만,
**물품의 위험도가 판정에 전혀 반영되지 않는다.**

- 판정 기준은 `required_slots: ["customs_item_explanation"]`이고 allowed values는
  `personal_item / souvenir / gift / medicine / food_for_personal_use`
  ([scenario_nodes.json:884-948](../../backend/app/data/scenario_nodes.json)).
- 룰 모드 키워드 맵([understanding_agent.py:132-138](../../backend/app/agents/agent_c/understanding_agent.py))이
  "선물/기념품/개인물건"을 곧장 allowed value로 매핑 → **무조건 SUCCESS**.
- LLM 모드도 understanding 프롬프트/노드 컨텍스트에 **어떤 물품인지(item_name·difficulty·
  category·suspicion_reason)가 전달되지 않는다** → "10개 파텍 시계"든 "금괴"든 "선물이에요"
  한마디로 통과.
- 유일한 예외가 `ITEM_GOLD_BAR` 미신고 하드코딩([scenario_state_machine.py `_is_gold_bar_violation`](../../backend/app/services/service_b/scenario_state_machine.py))인데,
  이는 24종 중 1종만 막는 땜질이다.

### 문제의식

억까 물품(난이도 3~12, 24종)에 대해 generic·불충분한 답변을 했을 때 난이도와 무관하게
"그냥 넘어가는지"를 **하나씩이 아니라 전수로** 확인하고, 그 로그를 근거로 일반화 수정
계획을 세운다. (개별 물품을 케이스별로 잡는 건 끝이 없음.)

## Goal (목표)

24종 × 불충분 답변 N종 조합을 판정 파이프라인에 통과시켜 **통과/제지 여부를 표로 산출**하고,
난이도·카테고리별로 "구멍"의 분포를 드러낸다. 이는 수정이 아니라 **진단**이다(다음 계획의 입력).

## 구현 (이미 초안 작성됨)

[backend/tests/eval_harness/customs_pressure_probe.py](../../backend/tests/eval_harness/customs_pressure_probe.py)

- `CUSTOMS_ITEMS`(24종) × `INSUFFICIENT_ANSWERS`(generic 3종) 루프.
- 각 조합: `UnderstandingAgent.analyze_player_text` → `DevBPolicyInput`(해당 물품을
  `random_customs_item`으로 주입) → `ScenarioStateMachine.decide()`.
- `branch_type == "success"`를 "그냥 넘어감(PASS/leak)"으로 집계.
- 물품 단위 요약: 한 물품에 불충분 답변이 하나라도 통과하면 leaking으로 카운트.

### 불충분 답변(의도적 generic, 의심 사유 미해결)
1. "It's a gift for my friend."
2. "It's just a personal item."
3. "I bought it as a souvenir."

### 실행
```
.venv/Scripts/python.exe -m backend.tests.eval_harness.customs_pressure_probe            # rule
.venv/Scripts/python.exe -m backend.tests.eval_harness.customs_pressure_probe --mode llm # llm
```

## 측정·로깅 항목

| 항목 | 의미 |
|---|---|
| item_id / difficulty / category | 물품 식별 및 난이도 구간 |
| verdict / branch_type / next_action | 판정 결과 |
| pass? (branch=success) | "그냥 넘어감" 여부 |
| TOTAL leak 비율 | 전체 조합 중 통과 비율 |
| ITEMS leaking | 24종 중 한 번이라도 통과한 물품 수 |

## 가설 / 예상 결과

- **rule 모드**: generic 답변이 키워드 매핑으로 전부 슬롯을 채워 **24/24 전 물품 통과**가 예상됨.
  (구조적 구멍의 결정적 증거)
- **llm 모드**: 판단 근거(물품 정보)가 프롬프트에 없으므로 역시 대부분 통과. 다만 LLM이
  "explain" intent를 충족으로 보는지에 따라 일부 변동 가능 → 변동 자체가 비결정성 증거.

## 진단 후 다음 단계 (이 계획의 산출물 → 별도 수정 계획)

로그가 가설을 확인하면, 후속 수정 계획에서 다룰 후보:
1. **물품 컨텍스트를 판정에 주입**: `random_customs_item`의 difficulty·category·suspicion_reason을
   understanding 노드 컨텍스트/프롬프트에 전달 → 난이도 높은 물품은 generic 설명을 불충족으로
   판정하고 압박(REASK/clarify)하도록.
2. **난이도 기반 임계치**: difficulty 구간별로 요구하는 설명 구체성(수량/용도/신고 여부 등)
   상향. 금괴 하드코딩을 이 일반 규칙으로 흡수.
3. **신고서 연계**: 고위험 카테고리(valuable/luxury/weapon_replica 등)는 `declared` 여부를
   판정에 반영(금괴 외 물품으로 확장).

## 범위 밖 / 주의

- 이 작업은 **진단만** 한다. 판정 로직·프롬프트·노드 데이터는 이 단계에서 변경하지 않는다.
- 진단 스크립트는 pass/fail을 단정하는 단위 테스트가 아니라 **로그 산출용 하네스**다.
  (CI 게이트로 쓰지 않음)
- #3 금괴 하드코딩은 진단 결과가 나오기 전까지 유지(회귀 방지).
