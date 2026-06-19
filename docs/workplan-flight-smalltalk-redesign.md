# Flight 스몰토크 챕터 재설계 작업계획서

> 작성일: 2026-06-19
> 작성자: wd14177 (level_agent)
> 소스: flight 챕터 "정형화" 진단 + 팀 방향 결정
> 범위: **dialogue_history/컨텍스트 요약 전략은 제외**(Dev A에서 히스토리 개선 완료). 본 계획은 노드/턴 구조, 토픽 선정, 레벨 추정, 종료 분기에 한정.
> 영향: `service_b/flight_smalltalk_diagnostic_policy.py`, `data/flight_smalltalk_probes.json`, `data/scenario_nodes.json`, `agent_c`(진단 출력), `service_b/bad_ending_policy.py`, 턴 요청 스키마(skip 신호)

---

## 0. 요약 & 목표

현재 flight 챕터는 단일 self-loop 노드(`FLIGHT_A_001_SEATMATE_SMALLTALK`)에서 probe 14개를 **결정적(첫 번째)으로** 소비해(`coherent_probes[0]`) 매 세션 동일 토픽 순서를 따라가며, 레벨 추정은 **턴 수 누적 휴리스틱**이다 → 사용자가 "정형화"를 체감.

**목표**: 사용자가 NPC와 *자유롭게 대화한다*고 느끼게 하되, 그 아래에서 **레벨 진단**을 정확히 수행하고, **게임 NPC로서 완성도**를 유지한다. 세 목적을 모두 충족하기 위한 핵심 원칙:

- **표면은 자유 대화, 속은 목표지향**: 꼬리물기 대화로 자연스럽게 흐르되, 진단 목표(아직 측정 못 한 능력)를 **숨은 조종 목표**로 둔다.
- **레벨은 발화의 언어 능력으로 측정**(턴 수 아님).
- **종료는 사용자 주도(skip)**, 단 최소 신호 확보 전엔 안전장치, 30턴은 자동종료 상한.
- **부적절 언행은 bad end**.

---

## 1. 현재 구조 (참조)
- 노드: `FLIGHT_A_001_SEATMATE_SMALLTALK`(self-loop), `FLIGHT_999_COMPLETE`(→IMM), `FLIGHT_BAD_END_VERBAL_ABUSE`(→scoreboard).
- 정책: [flight_smalltalk_diagnostic_policy.py](backend/app/services/service_b/flight_smalltalk_diagnostic_policy.py) `decide_conversational`.
  - 상수: `MIN_TURNS=3`, `MAX_TURNS=7`, `CONFIDENCE_THRESHOLD=0.7`, `STEERING=0.4`(dead), `SKIP_ELIGIBLE_PLAYER_TURNS=3`.
  - probe 선택(L147-168): 항상 `[0]` → 결정적.
  - confidence(L111-133): self-report base + verdict별 턴 증분 → 턴 수 누적.
- probe 데이터: [flight_smalltalk_probes.json](backend/app/data/flight_smalltalk_probes.json) 14개, 각 `probe_id`/`target_competency`/`topic_tag`/`coherent_topics`.

---

## 2. 작업 항목

### P1 — 턴/종료 구조: 30턴 상한 + 자동종료 + skip + 조기skip 폴백
- 상수 변경: `MAX_TURNS = 30`. `MIN_TURNS`(최소 신호)는 유지(3) — skip/저신뢰 처리에 사용.
- **자동 종료(상한)**: `turns >= MAX_TURNS`면 `FLIGHT_999_COMPLETE` / `COMPLETE_CHAPTER`(기존 분기 재사용, 상한만 30으로).
- **skip 종료(사용자 주도)**: 신규. `skip` 신호가 들어온 턴은 진단 진행과 무관하게 NPC가 **마무리 대사** 후 `FLIGHT_999_COMPLETE`로 전이.
  - 신호 경로: 턴 요청 스키마(`UnrealTurnRequest`/`PrePrototypeRequest`)에 `intent="skip"`(또는 `skip_requested: bool`) 추가 → 오케스트레이터가 flight 경로에서 분기. (현 `FlowResponse.skip_allowed`는 cinematic용이라 별개.)
  - 마무리 대사: A가 `next_action=COMPLETE_CHAPTER` 컨텍스트에서 종료 대사를 생성(기존 complete_chapter 처리 재사용).
- **조기 skip 폴백**: `player_turn_count < MIN_TURNS`에서 skip 시 →
  - (택1, 권장) skip 버튼을 MIN_TURNS 전까지 **비활성화**, 또는
  - (택2) 종료는 허용하되 **부분/기본 레벨 추정 + `low_confidence` 플래그**로 결과 기록.
  - → UX 결정 필요(§4).
- **성공 종료 의미**: "진단 완료"는 내부 상태(레벨 추정 안정)로 표시하되, 물리적 종료는 skip/상한. 진단이 충분해지면 NPC가 자연스레 **마무리 신호**(랜딩/폼 완료 톤)를 주도록 A에 힌트 전달(선택).

### P2 — 토픽 선정: 숨은-목표 기반 (정형화 제거의 핵심)
결정적 `probe[0]` 소비를 폐기하고, **꼬리물기 + 미커버 competency 우선 + 확률적 변주**로 교체.
- **선정 로직(`decide_conversational` 내 probe 선택부 교체)**:
  1. 진단 state(P3)에서 **아직 측정 안 된/약하게 측정된 competency**를 우선 후보로.
  2. 직전 발화와 **coherent한 토픽**(꼬리물기) 가중.
  3. `STEERING`을 **실제 확률 노브로 배선**: 확률 `STEERING`로 "현재 토픽 심화", `1-STEERING`로 "미커버 competency 탐색". 후보 중 **결정적 [0] 금지 → 가중 랜덤**.
- **토픽 불확실 시 LLM 자율 선정**: 적합 probe가 없거나 자유 흐름이 더 자연스러우면, LLM이 **가볍고 보편적인 주제**를 직접 고르게 한다(현재 surface_goal을 LLM이 질문으로 변환하는 경로 활용).
- **민감주제 결정적 필터**: 정치·종교·성·건강·민감한 개인사 등은 **프롬프트 지시 + 결정적 차단 목록** 이중으로 배제(LLM 지시만 신뢰 금지). 누구나 가볍게 답할 주제만 허용.
- probe 파일(`flight_smalltalk_probes.json`)은 **competency 라벨/예시 힌트로 유지**하되, "순서 스크립트"로는 쓰지 않는다(추가/삭제로 정형화가 풀리지 않음을 명시).

### P3 — 레벨 추정 모델 교체: 턴 수 누적 → 발화 언어 능력 평가
- **구조화 진단 state 도입**(대화 히스토리와 별개):
  - `covered_competencies`, competency별 관측치, 누적 루브릭(문법 범위·어휘 폭·유창성·오류율·문장 복잡도), 현재 레벨 추정(CEFR/TSL) + confidence.
  - 턴마다 **결정적으로 누적**(산문 요약에서 재구성하지 않음).
- **레벨 산출**: confidence를 "성공 턴 수"가 아니라 **발화의 언어 능력 신호**로 계산. 가능하면 기존 per-turn 루브릭(`Evaluation.Scores`의 grammar/vocabulary 등)을 진단용으로 집계하거나, 진단 전용 LLM 루브릭 평가를 1회/턴 산출.
- **종료 신뢰 조건**: `turns >= MIN_TURNS` AND (핵심 competency 커버 + 추정 안정/`confidence >= CONFIDENCE_THRESHOLD`) → "진단 완료"로 표시(물리 종료는 skip/상한).
- C 출력 정합: [understanding_agent.py](backend/app/agents/agent_c/understanding_agent.py)의 `_flight_smalltalk_diagnostic_output`/`_normalize_flight_smalltalk_diagnostic_output`가 진단 state 갱신에 필요한 신호(능력 관측)를 일관되게 제공하는지 점검.

### P4 — 실패 종료: bad-end 임계값 정의
- 빌더는 이미 존재: [bad_ending_policy.py](backend/app/services/service_b/bad_ending_policy.py) `build_bad_ending_output`, `CH0_01_FLIGHT_SMALLTALK → FLIGHT_BAD_END_VERBAL_ABUSE`.
- **임계값(신규 정의)**: incivility tier 기반 — 예) tier≥2(모욕) 즉시 bad-end, tier1(무례) 누적/반복 시 경고→bad-end. 위험 표현(risk_tags)도 기존 `_is_critical_risk` 경로 유지.
- `decide_conversational` 진입부에서 critical risk/incivility를 먼저 체크(현재 critical risk 위임 구조 확장).

---

## 3. 테스트 전략
- **P1**: skip 신호 → `FLIGHT_999_COMPLETE`/`COMPLETE_CHAPTER` 전이; 30턴 도달 자동종료; MIN_TURNS 미만 skip → 폴백(비활성 or low_confidence) 분기 단언.
- **P2**: 동일 입력 반복 시 토픽 시퀀스가 **결정적이지 않음**(가중 랜덤) 단언; 미커버 competency 우선 선택; 민감주제 후보가 결정적 필터로 제거됨.
- **P3**: mock 신호로 진단 state 누적/레벨 추정이 **턴 수가 아니라 능력 신호**로 변함; 종료 신뢰 조건 충족/미충족 분기.
- **P4**: incivility tier≥임계 → bad-end 노드; tier 미만 → 정상 진행.
- 전 스위트 `pytest backend/tests -q` 그린 유지.

## 4. 결정 필요 / 리스크
- **조기 skip 정책**: 버튼 비활성(권장) vs 저신뢰 종료 허용 — 택1.
- **skip 신호 스키마 위치**: 턴 요청에 `skip_requested` 추가(클라이언트 계약 변경 → Unreal 측 합의 필요).
- **비결정성 vs 측정 안정성**: P2 가중 랜덤이 진단 커버리지를 해치지 않도록, "미커버 competency 우선"을 변주보다 상위 가중으로.
- **비용/레이턴시**: 최대 30 LLM턴(5턴 대비 6배). 진단이 일찍 끝나면 NPC가 마무리 신호를 주어 skip을 유도.
- **영역 경계(AGENTS.md)**: 정책/진단/종료는 B, 진단 신호는 C, 대사는 A. skip 스키마는 C 계약.

## 5. 수용 기준
- 세션마다 토픽 순서·조합이 달라지고(정형화 해소), 꼬리물기가 자연스럽다.
- 레벨 추정이 발화 능력 기반이며 조기 종료 시 신뢰도 플래그가 붙는다.
- skip로 즉시 마무리 대사 후 다음 챕터 전이, 30턴 자동종료 동작.
- 부적절 언행 시 bad-end 전이.
- 민감주제가 결정적으로 배제된다.
- 전 스위트 그린.
