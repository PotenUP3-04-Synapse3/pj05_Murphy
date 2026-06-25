# 작업계획서: 방문목적 판정 불일치(#1) — 프롬프트 완화

## Context (배경)

CH0_03 입국심사 노드 `IMM_002_PURPOSE`에서 학습자가 **더 풍부하게 답할수록 불리해지는** 판정 불일치가 발생한다.

| 학습자 답변 | 실제 판정 |
|---|---|
| "I'm here to see my friend, **and go somewhere around, like Disney Land**" | ❌ FAIL → REASK |
| "I'm here to see my friend, sir" (정보 더 적음) | ✅ SUCCESS → ADVANCE |

첫 답변은 `friend_visit`(required slot `visit_purpose`의 allowed value)을 이미 충족하고, Disney Land = optional slot(`activity`/`destination`)까지 채운 **더 완전한 답변**이다. 그런데도 FAIL → 학습자가 "더 잘 대답했는데 왜 틀렸지?"라고 느끼는 직접적 UX 손상.

### 근본 원인 (LLM 모드 전용)

- LLM 지침([understanding_llm_client.py:205-212](backend/app/agents/agent_c/understanding_llm_client.py))이 "목적이 loose/모호하면 `intent_satisfied=false`"로 유도. "go somewhere around" 같은 부가설명·복수목적을 모호함으로 보고 `intent_satisfied=false` 반환.
- [scenario_state_machine.py:268-281](backend/app/services/service_b/scenario_state_machine.py)의 `_is_success`는 open slot(`visit_purpose`)에서 `intent_satisfied`를 성공 게이트로 사용 → false면 REASK.
- 단순 답변은 LLM이 `intent_satisfied=true`로 보므로 통과 → **불일치**.
- (참고: rule 모드에선 키워드 첫 매치로 둘 다 통과하므로 불일치 없음. 이 버그는 LLM 모드에서만 재현됨.)

### 의도한 결과

required slot이 **유효한 allowed value로 채워지면**, 부가설명이나 복수의 정당한 목적이 함께 있어도 SUCCESS로 통과시킨다. 단, 순수 회피성 답변(유효 목적 없음)과 위험/critical 목적은 **기존대로 FAIL/차단 유지**.

## 결정 사항

- **범위: #1만** (되물음 무시/금괴 플래그/물음표 누락은 이번 범위 제외)
- **전략: 프롬프트만 완화** (코드 로직·state machine 미변경, 비결정적이므로 eval로 검증)

## 변경 대상

프롬프트는 두 곳에 분산되어 있고 [understanding_prompt.md:5-6](backend/app/prompts/understanding_prompt.md)가 "런타임 지침과 동기화 유지"를 명시하므로 **둘 다** 수정한다.

### 1. 런타임 지침 (active) — [understanding_llm_client.py](backend/app/agents/agent_c/understanding_llm_client.py) `_developer_instructions()` (line 205-219)

"Required Intent First" 단락(205-212)에 완화 규칙을 추가:

- 현재 문구 유지: 유효한 목적이 **전혀 없는** loose/회피 답변("I just want to walk around" 등)은 `intent_success=false`, `intent_satisfied=false`, slot은 missing 유지.
- **추가**: player_text가 `allowed_slot_values`의 유효 값을 **하나라도** 충족하면, 추가 설명이나 **둘 이상의 정당한 목적**(예: 친구 방문 + 관광)이 함께 있어도 그것만으로 `intent_satisfied=false`로 만들지 말 것. 답변이 필요 정보보다 풍부하거나 복수의 유효 항목을 말한다는 이유만으로 불충족 처리 금지.
- **예외 유지**: 위험/critical 신호(불법취업·초과체류 등)가 섞이면 risk 신호는 그대로 기록 (이 완화는 risk 판정을 건드리지 않음 — risk_delta/risk_tags 경로는 무관).

### 2. 동기화 문서 — [understanding_prompt.md](backend/app/prompts/understanding_prompt.md) "Required Intent First" (line 20-33)

위 런타임 변경과 동일 취지의 문장을 추가해 동기화. "유효 값이 하나라도 있으면 부가설명/복수 정당 목적은 충족으로 본다"는 규칙과, 반례로 기존 evasion 케이스("walk around"만 = 불충족)를 함께 명시.

## 검증

프롬프트 변경은 비결정적이므로 실제 LLM 호출 기반으로 확인한다.

1. **수동 재현 (필수)** — 앱/데모를 LLM 모드(`murphy_understanding_mode="llm"`)로 실행하고 IMM_002_PURPOSE에서 다음 입력:
   - "I'm here to see my friend, and go somewhere around, like Disney Land" → **SUCCESS → IMM_003_DURATION** 기대 (수정 후 통과해야 함)
   - 회귀 확인: "I just want to walk around." → 여전히 **RETRY** ([immigration_hale.yaml:42-54](backend/tests/eval_harness/scenarios/immigration_hale.yaml)의 `immigration_hale_purpose_evasion` 취지)
   - 회귀 확인: "I'm here to see my friend, sir" → 여전히 **SUCCESS**

2. **eval harness** — `immigration_hale.yaml`에 멀티목적 성공 케이스(`immigration_hale_purpose_multi`) 1건 추가(branch_type=success, next=IMM_003_DURATION)하고 실 LLM eval 실행. 기존 `purpose_tourism`/`purpose_evasion` 케이스가 회귀 없이 통과하는지 확인.

3. **다운스트림 계약 회귀 (선택)** — [test_llm_acceptance.py](backend/tests/test_llm_acceptance.py)에 "LLM이 멀티목적에 intent_satisfied=True를 반환했을 때" FakeUnderstandingLLMClient 응답으로 ScenarioStateMachine가 SUCCESS를 내는지 확인하는 결정적 테스트 추가(프롬프트 자체가 아니라 state machine 계약 보증용).

## 참고: 손대지 않는 것

- `_is_success`/`slot_policy`/`visit_purpose_classifier` 등 코드 로직 — 전략상 미변경.
- risk/critical 판정 경로([scenario_state_machine.py:318-336](backend/app/services/service_b/scenario_state_machine.py)) — 불법취업 등은 그대로 차단되어야 하므로 건드리지 않음.
  
  ---
  
# 작업계획서: 입국심사·수화물 판정 false-negative 개선

## Context (배경)

두 챕터에서 **유효한 답변을 했는데도 학습자가 막히거나 부당하게 실패하는** 판정 문제가 관측됨. 세 건을 함께 처리한다.

### #1 — 입국심사 방문목적 판정 불일치 (CH0_03 `IMM_002_PURPOSE`)

| 학습자 답변 | 실제 판정 |
|---|---|
| "I'm here to see my friend, **and go somewhere around, like Disney Land**" | ❌ FAIL → REASK |
| "I'm here to see my friend, sir" (정보 더 적음) | ✅ SUCCESS → ADVANCE |

첫 답변은 `friend_visit`(required slot `visit_purpose`의 allowed value)을 이미 충족하고 Disney Land = optional slot까지 채운 **더 완전한 답변**인데 FAIL. "더 잘 답했는데 왜 틀리지?"라는 직접적 UX 손상.

**근본 원인 (LLM 모드 전용):** LLM 지침([understanding_llm_client.py:205-212](backend/app/agents/agent_c/understanding_llm_client.py))이 "목적이 loose/모호하면 `intent_satisfied=false`"로 유도 → 부가설명·복수목적을 모호함으로 보고 `intent_satisfied=false` 반환. [scenario_state_machine.py:268-281](backend/app/services/service_b/scenario_state_machine.py)의 `_is_success`가 open slot에서 `intent_satisfied`를 성공 게이트로 써서 REASK. 단순 답변은 `intent_satisfied=true`라 통과 → 불일치. (rule 모드에선 둘 다 통과하므로 LLM 모드에서만 재현)

### B-1 — 수화물 캐러셀 확인 답변이 REASK됨 (CH0_04 `BAG_003_CONFIRM_SEARCHED_CAROUSEL`)

```
Q: "Did you check the carousel carefully?"
A: "Yeah, only my bag didn't come yet, the others came already"  → UNCLEAR/REASK ❌
A: "yes"                                                          → UNCLEAR/REASK ❌
```

"다른 가방은 다 나왔고 내 것만 안 나왔다"는 캐러셀을 끝까지 확인했다는 강력한 정황이고, yes/no 확인 질문에 "yes"면 충족이어야 함.

**근본 원인 (#1과 다른 메커니즘):** `carousel_search_confirmation`의 allowed_slot_values가 `searched_carefully / waited_until_stopped / checked_twice`로 **확인 "방식"까지 특정**([scenario_nodes.json:722-728](backend/app/data/scenario_nodes.json)). yes/no 확인 질문인데 단순 긍정이 이 manner enum으로 매핑되지 못해 **슬롯이 빔(missing_slot)** → `_is_success`의 `not missing_slots`에서 탈락. #1은 슬롯이 채워졌지만 막힌 경우, B-1은 슬롯 자체가 비는 경우.

### B-2 — 부당한 FAIL 종료 + 힌트 미노출 (B-1의 2차 피해)

유효 답변이 계속 거부되며 retry마다 patience −8([scenario_state_machine.py:425](backend/app/services/service_b/scenario_state_machine.py))씩 깎여 `patience<=0` force_bad_end([scenario_state_machine.py:162-168](backend/app/services/service_b/scenario_state_machine.py)) → `END_BAGGAGE_REPORT_INCOMPLETE`. 게다가 BAG_003의 `hint` 분기가 retry 노드와 **동일**(둘 다 `BAG_003_RETRY_CONFIRM_SEARCHED_CAROUSEL`, [scenario_nodes.json:746-753](backend/app/data/scenario_nodes.json))이라 GIVE_HINT가 떠도 학습자에겐 REASK와 구분 안 됨 → 한국어 힌트(`base_hint_kr`/`hint_policy`)가 사실상 노출되지 않은 채 실패.

### 의도한 결과

required 정보가 의미상 충족되면(목적 명시 / 확인 긍정) 부가설명·복수목적·manner 미명시여도 SUCCESS. 순수 회피("just want to walk around")·위험/critical 신호는 기존대로 차단. 막히더라도 실패 전에 한국어 힌트가 반드시 한 번 노출.

## 결정 사항

- 범위: **#1 + B-1 + B-2** (입국심사 되물음/금괴/물음표 누락은 제외)
- #1·B-1: **프롬프트만 완화** (판정 코드 로직 미변경, 비결정적이라 eval 검증)
- B-2: **힌트 우선 노출** escalation/노드 라우팅 점검

## 변경 대상

### A. 프롬프트 완화 (#1, B-1)

프롬프트는 두 곳에 분산 + [understanding_prompt.md:5-6](backend/app/prompts/understanding_prompt.md)이 동기화 유지를 명시하므로 **둘 다** 수정.

**A-1. 런타임 지침** — [understanding_llm_client.py](backend/app/agents/agent_c/understanding_llm_client.py) `_developer_instructions()` "Required Intent First" 단락(205-219):

- 유지: 유효 값이 **전혀 없는** loose/회피 답변은 `intent_success/intent_satisfied=false`, slot missing.
- 추가 (#1): player_text가 `allowed_slot_values` 유효 값을 **하나라도** 충족하면 부가설명·**복수의 정당한 목적**이 함께 있어도 그것만으로 `intent_satisfied=false` 처리 금지. 풍부하거나 항목이 여러 개라는 이유만으로 불충족 처리 금지.
- 추가 (B-1): required_intent가 **확인형(`confirm_*`)** 일 때 player가 긍정(yes/정황상 확인)하면, manner를 명시하지 않아도 **가장 적절한 allowed value를 canonical로 채우고** 그 긍정 발화를 evidence_text로 둘 것. 확인 질문에 manner 미명시라는 이유만으로 slot missing 처리 금지.
- 예외 유지: 위험/critical 신호는 그대로 기록 (risk_delta/risk_tags 경로 무관, 미변경).

**A-2. 동기화 문서** — [understanding_prompt.md](backend/app/prompts/understanding_prompt.md) "Required Intent First"(20-33)에 위 두 규칙을 같은 취지로 추가. 반례로 evasion("walk around"만 = 불충족) 명시.

### B. 힌트 우선 노출 (B-2)

목표: B-1 수정 후에도 막히는 경우, **bad_end 전에 한국어 힌트가 실제로 노출**되도록.

- **B-1차: hint 라우팅 분리** — BAG_003의 `branch_candidates.hint`가 retry와 동일 노드를 가리키는 문제. hint 분기가 `base_hint_kr`/`hint_policy`를 실제 렌더하는 경로로 가도록 노드 데이터/렌더 확인. (GIVE_HINT 액션이 한국어 힌트를 표면화하는지 [scenario_state_machine.py:397-412](backend/app/services/service_b/scenario_state_machine.py) `_hint` 및 다운스트림 NPC 렌더 경로 점검)
- **B-2차: escalation 순서** — [decide() 162-168](backend/app/services/service_b/scenario_state_machine.py)에서 `patience<=0`/retry 한도 도달 시 force_bad_end가 step 5(힌트)보다 먼저 실행됨. **아직 힌트를 한 번도 안 준 경우(hint_count==0) 강제 종료 직전에 힌트를 1회 보장**하도록 가드 추가. (단, B-1이 고쳐지면 정상 답변은 통과하므로 이 경로는 안전망)

## 검증

프롬프트 변경은 비결정적이므로 실제 LLM 호출 기반으로 확인.

1. **수동 재현 (필수)** — LLM 모드(`murphy_understanding_mode="llm"`)로 실행:
   - `IMM_002_PURPOSE`: "see my friend, and go somewhere around, like Disney Land" → **SUCCESS → IMM_003_DURATION**
   - `BAG_003`: "Yeah, only my bag didn't come, the others came already" → **SUCCESS → BAG_004**; "yes" → **SUCCESS**
   - 회귀: `IMM_002_PURPOSE` "I just want to walk around." → 여전히 **RETRY**; `BAG_003` "I didn't really check" → 여전히 **RETRY/FAIL**
   - B-2: 일부러 계속 모호하게 답해 실패 유도 시 **bad_end 전에 한국어 힌트가 1회 노출**되는지 확인

2. **eval harness** — [immigration_hale.yaml](backend/tests/eval_harness/scenarios/immigration_hale.yaml)에 멀티목적 성공 케이스, 수화물 시나리오(예: customs_dan.yaml 또는 신규)에 "yes/정황 확인 → success" 케이스 추가 후 실 LLM eval. 기존 `purpose_tourism`/`purpose_evasion` 회귀 없음 확인.

3. **다운스트림 계약 회귀 (결정적)** — [test_llm_acceptance.py](backend/tests/test_llm_acceptance.py)에 FakeUnderstandingLLMClient로:
   - #1: 멀티목적 intent_satisfied=True → ScenarioStateMachine SUCCESS
   - B-1: carousel_search_confirmation 채워짐 → SUCCESS
   - B-2: hint_count==0 + patience<=0 상태 → 강제 종료가 아니라 GIVE_HINT가 먼저 나오는지

## 참고: 손대지 않는 것

- #1·B-1의 판정 코드(`_is_success`/`slot_policy`/`visit_purpose_classifier`) — 프롬프트 전략이므로 미변경.
- risk/critical 판정 경로([scenario_state_machine.py:318-336](backend/app/services/service_b/scenario_state_machine.py)) — 불법취업 등 차단 유지.
- 입국심사 #2(되물음 무시)·#3(금괴 플래그)·#4(물음표 누락) — 이번 범위 외.