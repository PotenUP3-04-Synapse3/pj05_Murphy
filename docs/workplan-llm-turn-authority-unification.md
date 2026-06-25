# 턴 결정 권한 통합 작업계획서 — 판단→해결→발화 (A안)

> 작성일: 2026-06-25
> 작성자: wd14177 (level_agent)
> 소스: Brielle 수하물 루프(CH0_04) 진단 + `.env` 런타임 설정 확인 + C→A 경계 코드/커밋 이력(24379e7) 분석
> 관련: `docs/workplan-llm-acceptance-restructure.md`(개념 선행), `docs/workplan-llm-acceptance-remediation.md`, 메모리 `runtime-llm-config`·`enum-gate-architecture`·`dialogue-awkwardness-diagnosis`
> 영향: `agent_c`(이해/판정), `service_b`(상태기계=거부권), `agent_a`+`dev_a_npc_dialogue_client`(발화), `schemas/game_turn.py`, `service_c`(오케스트레이션/그래프)

---

## 0. 배경 — 진짜 문제는 rule/llm이 아니라 "권한 구조"

런타임 `.env`는 이미 전부 LLM이다(`MURPHY_UNDERSTANDING_MODE=llm`, `MURPHY_NPC_DIALOGUE_MODE=llm`, `DEV_B_FEEDBACK_LLM_MODE=llm`, 모델 `gpt-5.4-mini`). 그럼에도 Brielle 수하물에서 무한 REASK 루프가 발생했다. 즉 **"LLM을 안 켜서"가 아니다.** LLM이 이미 판단하는데도 매번 테스트→발견→패치가 반복되는 건 **구조** 때문이다.

### 0.1 두더지잡기의 구조적 원인 2가지

**① 한 턴의 진실이 세 곳으로 쪼개짐 (split authority).**
- "충족했나?" → C(LLM)가 `intent_satisfied`를 내지만 **B(룰)가 `_is_success`/`_is_unclear`로 재판정**(`confidence<0.5`, `missing_slots`, `answer_relevance` 임계값). LLM 판정이 1급이 아니라 룰의 검토 대상이다.
- "다음 노드는?" → B 단독.
- "뭐라고 말하지?" → A(LLM)가 **B와 병렬로** 자유 생성.
- 세 권한이 병렬이라 접합부마다 불일치 → 버그 → 패치.

**② A를 현재 목표에 묶는 결합이 "블랙리스트 패치"다.**
- C→A 경계에서 `npc_question`/`npc_question_goal`/`recommended_expression`을 **함께** 제거(`_A_BLOCKED_NODE_CONTEXT_FIELDS`, `dev_a_npc_dialogue_client.py` L27). A는 노드의 질문을 못 보고 `dialogue_seed`로 **재작문**한다.
- LLM-A는 자유 작문 중 "다음에 물을 법한 것"으로 표류(BAG_001에 묶여있는데 BAG_002의 claim-tag 질문 누출).
- 이를 막는 장치가 `npc_dialogue_agent.py` L163 `_is_immigration_turn` — **입국 전용 금지문구 매처**. 새 NPC/표현마다 새 패턴 → 본질적 두더지잡기. Brielle(BAG_)은 무방비.

### 0.2 회귀 추적 — "왜 A가 따로 놀게 됐나"

커밋 `24379e7`(2026-06-19, "LLM-driven NPC dialogue")에서 A를 LLM 생성기로 전환하며, **모범답안(`recommended_expression`)을 NPC가 입으로 부르는 것**(학습 설계 붕괴)을 막으려고 같은 커밋에서 경계 격리(`public_node_context` L79, `_A_BLOCKED_NODE_CONTEXT_FIELDS`)를 넣었다.

문제는 A에 성격이 다른 결합이 **두 개**였다는 점:

| 결합 | 떼야 하나 | 이유 |
|---|---|---|
| A ↔ `recommended_expression` (모범답안) | **뗀다** | NPC가 정답을 말하면 안 됨 (학습 설계) |
| A ↔ 현재 노드 objective/질문 (지금 뭘 묻나) | **유지** | A가 엉뚱한 걸 물으면 안 됨 |

이 둘을 **한 경계에서 같이 잘랐다.** 모범답안을 떼려다 "지금 뭘 묻는가"라는 닻까지 버렸고, A는 자유를 얻고 기준점을 잃었다. 과거 "너무 묶임"의 해법이 "다 풂"으로 과잉교정된 것.

### 0.3 설계 원칙 (본 계획서의 1번 원칙)

> **올바른 결합만 묶는다.** 떼야 할 결합(모범답안)과 유지할 결합(현재 objective)을 분리한다.
> - LLM = **의미 판단**("이 발화가 현재 노드 목표를 충족하나?") + 그 결과에 맞는 **발화**.
> - rule/상태기계 = **불변식 거부권만**(합법 전이, 안전 escalation, 수치 한도, 챕터 완료). **의미 재판정 권한은 삭제.**
> - 그래프 토폴로지 = **데이터(`branch_candidates`)가 소유.** LLM은 노드 ID를 자유선택하지 않는다.

---

## 1. 목표 아키텍처 — 판단 → 해결 → 발화 (단일 진실 사슬)

```
지금 (병렬 권한):
   C판단 ─┐
          ├─ B(재판정 + 전이)      A(자유발화, B와 무관) ← 누출/표류
   A발화 ─┘

A안 (직렬 사슬):
   ① C(LLM)   "현재 노드 목표 충족?" → satisfied + branch_hint + risk_evidence
        ↓ (소비)
   ② B(룰)    거부권 체크(안전/수치/멤버십) → branch_candidates로 next_node 해결
              → patience/suspicion/retry 부기
        ↓ (소비)
   ③ A(LLM)   ②가 확정한 next_node의 objective로만 발화 (모범답안은 여전히 격리)
```

핵심 차이: 지금은 ①·③이 **병렬**, A안은 ③이 ②의 출력을 **소비**한다. A는 "B가 실제로 착지한 노드"에 대해서만 말하므로 **앞 노드 질문을 흘릴 구조적 경로가 없다.** 거부권으로 막힌 턴이면 A는 막힌 결과를 말하지, 통과한 척 못 한다.

### 1.1 C(이해) — 의미 판정의 단독 1급 권한

`UnderstandingOutput`이 내는 의미 결론을 **B가 재계산하지 않고 그대로 신뢰**한다.

```jsonc
{
  "satisfied": true,                 // 현재 노드 목표 충족 여부 (1급, B가 안 뒤집음)
  "branch_hint": "success",          // success | retry | clarify  (의미 결론; 노드 ID 아님)
  "judgment_reason_kr": "가방이 안 나왔다고 분실 신고함",
  "confidence": 0.86,
  "risk_evidence": { "tags": [], "delta": 0 },   // B 거부권 입력 (안전 신호)
  "slot_evidence": [ ... ]           // 리포트/표시·디버그용. 수용 게이트 아님
}
```

- `branch_hint`는 **의미 결론**일 뿐 노드 ID가 아니다 → LLM은 그래프 토폴로지를 몰라도 된다.
- `satisfied=false`일 때 `branch_hint`로 retry(재시도) vs clarify(되묻기)를 구분.
- **numeric 슬롯**(stay_duration, cash_amount)은 LLM에 위임하지 않고 **텍스트 룰 파서를 병행**해 `risk_evidence`/수치 필드에 주입(LLM과 OR; §5).

### 1.2 B(상태기계) — 심판에서 문지기로

B는 의미를 **다시 판단하지 않는다.** `satisfied`를 신뢰하고, 아래 **거부권(veto)만** 행사한다.

거부권 불변식 목록(이것만 룰):
1. **그래프 멤버십** — 해결된 `next_node ∈ allowed_next_nodes` 아니면 거부.
2. **치명 위험** — `_is_critical_risk`(critical_tags / `risk_delta`≥20 / risk_total / 미신고 고가품 / 여권제출 거부) → critical_fail/warning으로 **덮어씀** (`scenario_state_machine.py` L330).
3. **수치 한도** — cash $10k, stay ≥14일 등 파서 기반 게이트/라우팅(`_stay_duration_days` L33, GATED_ROUTES L90).
4. **한도/부기** — `MAX_HARD_FAIL_RETRIES`, patience floor, retry/hint/suspicion delta, 챕터 완료 노드 집합.

해결 절차: `branch_hint` → 현재 노드 `branch_candidates[branch_hint]` → `next_node_id`. (데이터가 토폴로지 소유)

### 1.3 A(발화) — 해결된 노드의 objective로만 말함

- 입력에 **B가 확정한 `resolved_node`의 objective/질문 의미**를 명시적으로 넣는다(모범답안 `recommended_expression`은 계속 제외).
- 발화는 그 objective를 다뤄야 하며, **다음 노드 look-ahead 금지**가 블랙리스트가 아니라 **입력 계약 + 순서**로 보장된다.
- 톤은 `branch_type`/`next_action`에 바인딩(성공=진행 톤, retry/clarify=재요청 톤, 실패 시 긍정 리액션 금지).

---

## 2. 단계별 작업 (P0 ~ P5)

### P0 — 턴 결정 계약/스키마 (기반)
- `UnderstandingOutput`(또는 신설 `TurnDecision`)에 `satisfied`/`branch_hint`/`judgment_reason`/`risk_evidence`를 1급 필드로 정착(`schemas/game_turn.py`). 기존 `intent_satisfied`/`intent_success`와의 의미 충돌 제거.
- A-facing 입력에 `resolved_node_objective`(또는 동등) 필드 추가, `recommended_expression` 격리는 유지.
- 테스트: 스키마 직렬화/계약, 필드 불변식(`satisfied=true`면 `branch_hint∈{success}` 류 정합성).

### P1 — C: 의미 판정 단독화
- LLM `satisfied`/`branch_hint`를 보존하고, **open 슬롯에서 enum/grounding 후처리 재계산 제거**(`understanding_agent.py` L286 `_apply_generic_slot_evidence`, L304 `has_open_required` 정렬 로직 정리).
- numeric 슬롯 파서·risk_tags 분류는 유지.
- 테스트: 패러프레이즈("My suitcase didn't come out"·"carpenter") 통과, 모순답 포착, stay_duration/cash 파싱 회귀.

### P2 — B: 재판정 제거, 거부권만 유지
- `_is_success`/`_is_unclear`/`_has_invalid_required_slot_value`에서 **의미 재판정(confidence 임계·missing_slots·enum 멤버십) 제거**(`scenario_state_machine.py` L254/L306/L203). `satisfied`/`branch_hint`를 직접 소비.
- `_is_critical_risk`·GATED_ROUTES·수치·patience/retry·`allowed_next_nodes` 강제는 **불변**.
- 해결기: `branch_hint`→`branch_candidates`→`next_node` + 멤버십 검증.
- 테스트: open SUCCESS가 enum 무관 결정 / illegal_work_intent·미신고 고가품·여권거부 → 여전히 critical / $10k·≥14일 라우팅 회귀 / retry·patience 한도 유지.

### P3 — A: 해결 노드 바인딩 + 블랙리스트 제거
- A 입력에 `resolved_node` objective 주입(`dev_a_npc_dialogue_client.py` 페이로드 빌드 L115-200). 발화는 그 objective 대상.
- immigration 전용 누출/표면목표 가드(`npc_dialogue_agent.py` L144-211 `_immigration_dialogue_violation` 계열)를 **전역 계약 검증**(발화가 resolved objective를 다루는가/다음노드 키워드를 흘리는가)으로 대체. 순서(②→③)가 1차 방어, 의미 검증이 2차 방어.
- 톤을 branch_type에 바인딩(실패 분기 긍정 리액션 금지).
- 테스트: BAG_001 retry에서 claim-tag(BAG_002) 질문 누출 없음 / 성공 시 resolved 노드 질문 / 실패 발화가 "Oh I see"류로 시작 안 함 / IMM 회귀 동등.

### P4 — eval/골든 하네스 (비결정성·안전 관리)
- 판정 LLM을 mock/녹화(golden)하는 결정적 회귀 레이어(`tests/eval_harness` 확장). 핵심 시나리오 transcript를 golden으로 고정.
- 안전 eval: 미신고 고가품/불법취업/여권거부/현금·체류 한도가 LLM 판정과 무관하게 **항상 거부**되는지 시나리오 배터리.
- baggage 풀플로우(`baggage_brielle_full_flow.yaml`)를 llm 모드 회귀로.

### P5 — 마이그레이션/롤아웃
- 기능 플래그(예: `MURPHY_TURN_AUTHORITY=legacy|unified`)로 신·구 경로 병행, 챕터 단위 점진 전환(수하물→입국→기내→세관).
- 병행 기간 동안 두 경로 출력 비교 로깅(shadow). 안정 후 legacy 제거.

---

## 3. 삭제 / 유지 / 신설 요약

**삭제(두더지 소굴):**
- B `_is_unclear`의 `confidence<0.5`/`answer_relevance`/`needs_clarification` **임계 재판정**, open `_is_success`의 `missing_slots`/grounding 연언, `_has_invalid_required_slot_value`의 open 분기.
- A의 immigration 전용 블랙리스트 가드(`_is_immigration_turn`·`_has_retry_hook_leak`·`_has_immigration_surface_goal_mismatch`).
- C의 open 슬롯 enum/grounding 후처리 재계산.

**유지(거부권 = 의미 무관 불변식):**
- `_is_critical_risk` 안전 경로, GATED_ROUTES·`_stay_duration_days` 수치, `allowed_next_nodes` 멤버십, patience/retry/챕터완료 부기.
- `recommended_expression` 격리(`public_node_context`).

**신설:**
- 턴 결정 계약(`satisfied`/`branch_hint`/`risk_evidence`), `branch_hint→branch_candidates` 해결기, A-facing `resolved_node_objective` 주입, eval/golden 하네스, 기능 플래그.

---

## 4. 현재 문제 → 해결 매핑

| 문제 | 원인 | 해결 |
|---|---|---|
| Brielle 무한 REASK(가방 신고를 했는데도) | A가 BAG_002 질문 누출 → 학습자가 엉뚱한 답 → C가 BAG_001로 채점 | P3(해결노드 바인딩·순서) |
| LLM이 "충족"이라 해도 룰이 UNCLEAR로 뒤집음 | B 의미 재판정 | P2(재판정 제거) |
| 새 NPC마다 누출 가드 재작성 | immigration 블랙리스트 | P3(전역 계약) |
| carpenter/패러프레이즈 거절 | open enum/grounding | P1 |
| 안전 회귀 우려 | 판정 LLM화 | P4(안전 eval) + §1.2 거부권 |

---

## 5. 리스크 & 가드

- **안전 회귀(최대 리스크)**: 의미 판정을 LLM에 넘기므로 "충족"이라 우기면 전진. → §1.2 거부권 불변식 + P4 안전 eval 배터리 필수. risk 경로는 절대 약화 금지.
- **수치 신뢰성**: cash/stay는 LLM 단독 신뢰 금지. **텍스트 룰 파서 병행(OR)** 으로 한도 판정.
- **거부권 입력 의존성**: B 거부권이 LLM이 준 `risk_evidence`에 의존하면, LLM이 위험 태그를 놓칠 때 거부권도 헛돈다 → 진짜 치명적인 것(현금/체류/여권거부)은 **룰 파서/슬롯 기반으로도 독립 판정**.
- **비결정성/테스트**: 판정이 LLM이라 단위테스트가 흔들림 → P4 mock/golden 레이어로 결정적 회귀 고정.
- **영역 경계(AGENTS.md)**: C 변경은 C, B는 B, A는 A, 스키마는 C 소유 — 분리 PR. 기능 플래그로 단계 머지.

## 6. 수용 기준

- Brielle 수하물 전 플로우가 llm 모드에서 누출/루프 없이 완주(golden 회귀).
- LLM `satisfied`가 B에 의해 의미적으로 뒤집히지 않음(거부권 사유 외).
- 미신고 고가품/불법취업/여권거부/현금 $10k/체류 ≥14일 전부 LLM 판정과 무관하게 거부(안전 eval 그린).
- 신규 NPC 추가 시 누출 가드를 **새로 안 짜도** 됨(전역 계약으로 커버).
- 그래프/수치/patience/챕터 분기 전 회귀 그린.
- immigration 기존 동작 동등(회귀 그린).
