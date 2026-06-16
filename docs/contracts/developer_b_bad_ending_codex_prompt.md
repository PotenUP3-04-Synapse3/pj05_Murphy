# Developer B 인계 프롬프트 — Bad Ending 분기 정책 & 시나리오 노드

> 발행: Developer A / kimyonghee · 2026-06-16
> 대상: Developer B (Policy Engine + Scenario Data)
> 관련 CR: `CR-A2` (분기 정책), `CR-A4` (시나리오 노드)
> 본 문서는 Codex/AI 에이전트가 그대로 받아 작업을 수행할 수 있는 self-contained 프롬프트입니다.

---

## 컨텍스트 (필독)

Developer A 측은 NPC 발화의 격앙/욕설 미러링 모드(`MURPHY_NPC_PROFANITY_MIRROR_MODE`)를 구현 완료했습니다. Developer C 는 별도 인계서(`developer_c_incivility_codex_prompt.md`) 에 따라 Understanding Agent 에 `incivility` 신호를 추가합니다.

그러나 Alpha 디자인 노트의 핵심 정책 **"dangerous words can trigger an immediate bad ending"** 이 분기 정책으로 구현되지 않았습니다. `incivility.tier == 3` (욕설·혐오·위협) 발화가 들어와도 게임은 정상 분기로 진행됩니다.

가드레일: 본 작업은 **Developer B 분기 권한** 안에서만 수행합니다. A의 NPC 발화 표현이나 C의 Understanding 분류 로직은 변경하지 않습니다.

---

## 작업 1 — CR-A2: Bad Ending 분기 정책

### 1-1. Policy Engine 분기 결정 추가

`backend/app/agents/agent_b/english_level_hint_agent.py` (또는 분기 결정 진입점) 의 `evaluate_turn` 흐름에:

1. **선행 검사 (분기 결정 최상단):** Understanding 결과의 `incivility.tier` 를 먼저 평가.
   ```python
   incivility = payload.understanding.incivility  # CR-A1 의 신호 (없으면 None)
   if incivility is not None and incivility.tier >= 3:
       return _build_bad_ending_output(payload, reason="verbal_abuse_t3")
   if incivility is not None and incivility.tier == 2:
       _accumulate_incivility_warning(session_state)  # 2턴 연속이면 동일 분기
       if session_state.incivility_t2_streak >= 2:
           return _build_bad_ending_output(payload, reason="verbal_abuse_t2_repeated")
   ```

2. **`_build_bad_ending_output(payload, reason)` 신설** — `backend/app/services/service_b/bad_ending_policy.py` 신설 권장:
   ```python
   def _build_bad_ending_output(payload, reason: str) -> DevBPolicyOutput:
       chapter_id = payload.current_node.chapter_id
       bad_end_node_id = _bad_end_node_id_for_chapter(chapter_id)  # CR-A4 노드
       return DevBPolicyOutput(
           branch=Branch(
               branch_type="fail",  # 또는 신규 "bad_end" (enum 확장 가능 시)
               next_node_id=bad_end_node_id,
               next_action="COMPLETE_CHAPTER",
           ),
           dialogue_directive=DialogueDirective(
               do_not_generate_npc_text=False,
               reason=reason,  # "verbal_abuse_t3" / "verbal_abuse_t2_repeated"
           ),
           state_delta=StateDelta(
               score_penalty=-2,  # 정책에 따라 조정
               verbal_abuse_flag=True,
           ),
           evaluation=Evaluation(
               verdict="fail",
               feedback_note="Player ended interaction due to verbal abuse.",
               feedback_tags=["verbal_abuse", "bad_ending"],
           ),
           out_game_feedback=OutGameFeedback(
               reason="verbal_abuse",
               learning_card_id="verbal_conduct_card",
           ),
           npc_emotion="anger",  # CR 2026-06-12 NPC Emotion Enum 과 정합
       )

   _BAD_END_BY_CHAPTER = {
       "CH0_01_FLIGHT_SMALLTALK": "FLIGHT_BAD_END_VERBAL_ABUSE",
       "CH0_03_IMMIGRATION_CHECK": "IMM_BAD_END_VERBAL_ABUSE",
       "CH0_04_BAGGAGE_CLAIM":    "BAG_BAD_END_VERBAL_ABUSE",
   }
   def _bad_end_node_id_for_chapter(chapter_id: str) -> str:
       return _BAD_END_BY_CHAPTER.get(chapter_id, "IMM_BAD_END_VERBAL_ABUSE")
   ```

### 1-2. `branch_type` enum 확장 결정

- **권장(작은 변경):** 기존 `"fail"` 재사용 + `dialogue_directive.reason="verbal_abuse_t3"` 로 식별. schema 무변경.
- **선택(명시적):** `branch_type` enum 에 `"bad_end"` 추가. 이 경우 C 어댑터·검증기·로깅도 동시 정렬 필요 → 별도 sub-PR 권장.

본 인계서는 **권장안(fail 재사용)** 기준으로 작성. enum 확장 채택 시 본 문서 후속 RFC.

### 1-3. T2 누적 카운터

`ScenarioStateMachine` (또는 session state) 에 `incivility_t2_streak: int` 필드 추가. T0/T1 답변이 들어오면 리셋, T2가 들어오면 +1.

### 1-4. `final_result` 연동

세션 종료 시 `final_result` 빌더에서 `verbal_abuse_flag` 또는 `out_game_feedback.reason=="verbal_abuse"` 가 true 이면 학습 리포트에 별도 카드/사유 표시.

### 1-5. 테스트 (필수)

신설: `backend/tests/test_dev_b_bad_ending_branch.py`

- Understanding `incivility.tier=3` → `branch.next_node_id == "IMM_BAD_END_VERBAL_ABUSE"` (immigration 시나리오 기준)
- Understanding `incivility.tier=2` 1회 → 정상 진행 + streak=1
- Understanding `incivility.tier=2` 2회 연속 → bad ending 라우팅
- Understanding `incivility.tier=2` + 정상 답변 → streak 리셋
- Understanding `incivility=None` → 기존 분기 회귀 무영향

---

## 작업 2 — CR-A4: 시나리오 노드 신설

### 2-1. `backend/app/data/scenario_nodes.json` 추가

다음 3개 노드를 `nodes` 객체에 append:

```json
"FLIGHT_BAD_END_VERBAL_ABUSE": {
  "node_id": "FLIGHT_BAD_END_VERBAL_ABUSE",
  "chapter_id": "CH0_01_FLIGHT_SMALLTALK",
  "node_type": "ending",
  "npc_question": "Yeah... I'm done talking to you.",
  "npc_question_goal": "closing_eviction",
  "objective_kr": "강제 종료 — 무례한 발언으로 인한 대화 중단",
  "required_intents": [],
  "required_slots": [],
  "optional_slots": [],
  "critical_slots": [],
  "allowed_slot_values": {},
  "risk_keywords": [],
  "recommended_expression": "",
  "base_hint_kr": "",
  "hint_policy": { "max_hints": 0, "hint_style": "none" },
  "branch_candidates": {
    "success": "FLIGHT_BAD_END_VERBAL_ABUSE",
    "retry":   "FLIGHT_BAD_END_VERBAL_ABUSE",
    "clarify": "FLIGHT_BAD_END_VERBAL_ABUSE",
    "hint":    "FLIGHT_BAD_END_VERBAL_ABUSE",
    "warning": "FLIGHT_BAD_END_VERBAL_ABUSE"
  },
  "allowed_next_nodes": ["ALPHA_999_FINAL_SCOREBOARD"],
  "transition": {
    "status": "complete_chapter",
    "completed_chapter_id": "CH0_01_FLIGHT_SMALLTALK",
    "next_chapter_id": "CH0_05_RESULT",
    "entry_node_id": "ALPHA_999_FINAL_SCOREBOARD",
    "unreal_event": "SHOW_BAD_END_SCOREBOARD",
    "requires_player_input": false
  }
},
"IMM_BAD_END_VERBAL_ABUSE": {
  "node_id": "IMM_BAD_END_VERBAL_ABUSE",
  "chapter_id": "CH0_03_IMMIGRATION_CHECK",
  "node_type": "ending",
  "npc_question": "That's enough. This interview is over.",
  "npc_question_goal": "closing_eviction",
  "objective_kr": "강제 종료 — 입국심사관에 대한 무례한 발언",
  "required_intents": [], "required_slots": [], "optional_slots": [],
  "critical_slots": [], "allowed_slot_values": {}, "risk_keywords": [],
  "recommended_expression": "", "base_hint_kr": "",
  "hint_policy": { "max_hints": 0, "hint_style": "none" },
  "branch_candidates": {
    "success": "IMM_BAD_END_VERBAL_ABUSE",
    "retry":   "IMM_BAD_END_VERBAL_ABUSE",
    "clarify": "IMM_BAD_END_VERBAL_ABUSE",
    "hint":    "IMM_BAD_END_VERBAL_ABUSE",
    "warning": "IMM_BAD_END_VERBAL_ABUSE"
  },
  "allowed_next_nodes": ["ALPHA_999_FINAL_SCOREBOARD"],
  "transition": {
    "status": "complete_chapter",
    "completed_chapter_id": "CH0_03_IMMIGRATION_CHECK",
    "next_chapter_id": "CH0_05_RESULT",
    "entry_node_id": "ALPHA_999_FINAL_SCOREBOARD",
    "unreal_event": "SHOW_BAD_END_SCOREBOARD",
    "requires_player_input": false
  }
},
"BAG_BAD_END_VERBAL_ABUSE": {
  "node_id": "BAG_BAD_END_VERBAL_ABUSE",
  "chapter_id": "CH0_04_BAGGAGE_CLAIM",
  "node_type": "ending",
  "npc_question": "Sir, that's it. Security will escort you out.",
  "npc_question_goal": "closing_eviction",
  "objective_kr": "강제 종료 — 세관 직원에 대한 무례한 발언",
  "required_intents": [], "required_slots": [], "optional_slots": [],
  "critical_slots": [], "allowed_slot_values": {}, "risk_keywords": [],
  "recommended_expression": "", "base_hint_kr": "",
  "hint_policy": { "max_hints": 0, "hint_style": "none" },
  "branch_candidates": {
    "success": "BAG_BAD_END_VERBAL_ABUSE",
    "retry":   "BAG_BAD_END_VERBAL_ABUSE",
    "clarify": "BAG_BAD_END_VERBAL_ABUSE",
    "hint":    "BAG_BAD_END_VERBAL_ABUSE",
    "warning": "BAG_BAD_END_VERBAL_ABUSE"
  },
  "allowed_next_nodes": ["ALPHA_999_FINAL_SCOREBOARD"],
  "transition": {
    "status": "complete_chapter",
    "completed_chapter_id": "CH0_04_BAGGAGE_CLAIM",
    "next_chapter_id": "CH0_05_RESULT",
    "entry_node_id": "ALPHA_999_FINAL_SCOREBOARD",
    "unreal_event": "SHOW_BAD_END_SCOREBOARD",
    "requires_player_input": false
  }
}
```

> NPC 종결 대사(`npc_question`)는 A 측 풀백 시드일 뿐. A는 페르소나·incivility_tier 기반으로 자체 종결 대사를 생성합니다. 노드의 `npc_question` 그대로 출력되지 않을 수 있음.

### 2-2. 시나리오 검증

```bash
uv run python -c "
import json
from backend.app.services.service_c.openkb_service import OpenKBService
svc = OpenKBService()
for n in ['FLIGHT_BAD_END_VERBAL_ABUSE', 'IMM_BAD_END_VERBAL_ABUSE', 'BAG_BAD_END_VERBAL_ABUSE']:
    ch = json.loads(open('backend/app/data/scenario_nodes.json', encoding='utf-8').read())['nodes'][n]['chapter_id']
    node = svc.get_node_context(ch, n)
    print(n, '→', node.chapter_id, node.node_type, node.transition['unreal_event'])
"
```

### 2-3. 테스트

`backend/tests/test_scenario_nodes_bad_ending.py`:
- 3개 노드 존재 + `node_type == "ending"`
- `transition.unreal_event == "SHOW_BAD_END_SCOREBOARD"`
- `branch_candidates` 가 모두 같은 노드 ID (종착)

---

## 가드레일 체크리스트 (PR 머지 전)

- [ ] Developer A 영역 0 수정. `git diff --stat | grep -E "(agent_a|service_a|tool_a|middleware_a|npc_dialogue)"` → 0 lines.
- [ ] Developer C 영역(`backend/app/services/service_c`, `backend/app/agents/agent_c`, `backend/app/integrations`) 0 수정.
- [ ] `branch_type` enum 미확장 시 schema 변경 0. 확장 시 별도 RFC.
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run mypy .` 그린.
- [ ] 기존 immigration/baggage/flight 회귀 무영향.
- [ ] `final_result` 페이로드에 `verbal_abuse_flag` 또는 `out_game_feedback.reason` 정상 노출.
- [ ] `docs/handoff.md` 에 B 작업 완료 기록 + CR-A2/A4 Status 갱신.

---

## 검증 시나리오 (end-to-end, Developer C 작업 완료 후)

```bash
$env:MURPHY_NPC_PROFANITY_MIRROR_MODE = "mirror"
uv run uvicorn backend.app.main:app --reload

# /respond-dialog 에서:
# 1. 정상 답변 → 평상 진행
# 2. "fuck you" → A 측 mirror 응답 ("Get the hell out of my line.")
#    + branch.next_node_id == "IMM_BAD_END_VERBAL_ABUSE"
#    + flow.unreal_event == "SHOW_BAD_END_SCOREBOARD"
#    + final_result.out_game_feedback.reason == "verbal_abuse"
# 3. "you idiot" 2턴 연속 → 동일 bad ending
```

---

## 우선순위 / 의존

- **CR-A2 와 CR-A4 는 동시 머지 필수** (분기가 라우팅할 노드 데이터 없으면 분기 실패).
- CR-A1 (Developer C 의 incivility 신호 산출) 이 선행되어야 본 분기가 실제로 발동.
- Developer C 의 CR-A3 (어댑터 forward) 는 본 작업과 독립이지만 A 측 mirror 응답의 자연스러운 톤을 위해 함께 머지 권장.

---

## 참고 파일

- 본 요청 정식 CR: `docs/contracts/change_requests.md` 의 `CR-A2`, `CR-A4` 섹션
- A 측 구현 참고: `backend/app/services/service_a/profanity_response_policy.py`
- C 측 작업 가이드: `docs/contracts/developer_c_incivility_codex_prompt.md`
- Alpha 디자인 원문: `docs/handoff.md` "Developer C Alpha Plan Notice" (Time pressure and failure policy)
