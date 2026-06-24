# 최종 결과(Final Result / Scoreboard) 페이로드 잔여 작업 계획서

> 작성일: 2026-06-24
> 작성자: wd14177 (level_agent)
> 소스: Unreal 결과 화면 요구사항(최종 티어 / 총점 / 6항목 점수 / 최종 피드백) 대조 진단
> 범위: `ALPHA_999_FINAL_SCOREBOARD` 및 `GET /result/{session_id}`로 나가는 최종 결과 페이로드. 점수 산출 **알고리즘 자체는 유지**(이미 씬 가중 적용됨), 계약/전달 경로/라벨 정합성에 한정.
> 영향: `schemas/game_turn.py`, `service_b/final_result_score_policy.py`, `service_c/response_builder.py`, `integrations/dev_b_level_hint_client.py`, `service_c/validator.py`, `docs/contracts/developer_c_schema_contract.md`

---

## 0. 요약 & 배경

Unreal이 결과 화면에 필요로 하는 4가지를 현재 구현과 대조한 결과:

| Unreal 요구 | 현재 상태 | 비고 |
|---|---|---|
| ① 최종 티어 (gold/silver/bronze) | ✅ **이번 세션에 구현됨**(§1 참조) | `final_result.tier` 신설 |
| ② 최종 총점 (100점) | ✅ 있음 | `final_result.final_score_100` |
| ③ 6항목별 점수 (각 100점) | ✅ 있음 | `final_result.quantitative_scores` |
| ④ 최종 피드백 (focus_on_form + 의사소통) | ⚠️ 부분 / 채널 분리 | P2·P3 |

본 계획은 ②③을 제외한 **잔여 정합성 작업(P1)**, **전달 경로 정리(P2)**, **피드백 보강(P3)**을 다룬다.

---

## 1. 이미 처리된 항목 (참고 — 별도 작업 불요)

> ⚠️ 이 항목은 직전 세션에서 **계획 합의 전에 선구현**되었음. 계획 단계로 되돌리고 싶으면 revert 가능(아래 커밋/변경 파일 기준).

- `final_result.tier: Literal["Gold","Silver","Bronze","Iron"]` 신설.
  - `rank`(UI 표시 문구)은 유지, `tier`는 게임 로직용 4단계.
  - 매핑: 합격 3단계 → Gold/Silver/Bronze, 비합격(`Secondary Review`/`Comic Fail`/`Unranked`) → **Iron**.
  - 변경: [game_turn.py](backend/app/schemas/game_turn.py) `FinalResult`, [final_result_score_policy.py](backend/app/services/service_b/final_result_score_policy.py) `_RANK_TO_TIER`/`build_result`/`_unranked_result`, 계약 문서 규칙 19, 테스트 픽스처/검증.
- **결정 필요**: 이 선구현을 (a) 유지, (b) revert 후 본 계획에 P0로 재편입 — 둘 중 택1. (§4-D0)

---

## 2. 작업 항목

### P1 — `scoring_policy` 라벨 정합성 (버그성, 낮은 리스크)

**문제:** 실제 점수 산출은 씬 가중(flight 20 / immigration 50 / baggage 30)을 적용하는 **scene-normalized** 방식인데, 응답에 나가는 라벨은 `scoring_policy="simple_average"`로 하드코딩되어 있다. 같은 객체의 `reason_tags`에는 `"scene_normalized_dimension_average_policy"`가 찍혀 **자기 모순**. 스키마 `Literal`에는 두 값이 모두 허용되어 있어 검증은 통과하지만, Unreal/리포트가 이 라벨을 신뢰하면 실제 정책과 어긋난다.

**근거:**
- `_quantitative_scores()`: 차원별 씬 가중평균 → `overall`은 6차원 단순평균. 반환 시 `scoring_policy="simple_average"`.
- `_unranked_result()`도 동일하게 `"simple_average"`.
- `_recommendation()`: `reason_tags`에 `"scene_normalized_dimension_average_policy"` 추가.
- 검증/테스트: `test_validator_accepts_alpha_scene_normalized_score_policy`, `test_final_score_uses_scene_normalized_dimension_averages_not_turn_counts`가 이미 scene-normalized 의미를 전제.

**작업:**
1. `_quantitative_scores()`와 `_unranked_result()`의 `scoring_policy` 리터럴을 `"scene_normalized_dimension_average"`로 교체. (단, `_unranked_result`는 점수 0/레코드 0이므로 가중 의미가 없음 → 라벨을 어떻게 둘지 §4-D1.)
2. 기존 테스트 중 `scoring_policy == "simple_average"`를 단언하는 케이스(`test_final_score_excludes_final_node_when_prior_scores_exist` 등) 갱신.
3. 계약 예시 JSON은 이미 `scene_normalized_dimension_average`로 표기됨 → 코드만 맞추면 일치.

**리스크:** 낮음. 산출 알고리즘 불변, 라벨 문자열만 변경. Unreal이 이 필드로 분기하지 않으면 무해.

---

### P2 — bad-end 경로 결과 비대칭 + 결과 페이로드 단일화

**문제 A (비대칭):** 정상 완주는 `ALPHA_999_FINAL_SCOREBOARD` 턴에서 `final_result`가 응답에 실린다. 그러나 욕설/입국 강제반려 등 **bad-end 경로**(`FLIGHT_BAD_END_VERBAL_ABUSE`, `END_SECONDARY_INSPECTION`, `BAG_BAD_END_*`)는 `unreal_event=SHOW_BAD_END_SCOREBOARD`로 결과 화면을 열지만, 그 턴의 `current_node_id`가 `ALPHA_999_FINAL_SCOREBOARD`가 아니므로 [dev_b_level_hint_client.py `evaluate_turn`](backend/app/integrations/dev_b_level_hint_client.py) 조건에 안 걸려 **`final_result`가 응답에 안 붙는다**. 결과 화면을 그리려면 Unreal이 `GET /result/{session_id}`를 별도 호출해야 한다.

**문제 B (focus_on_form 채널 분리):** focus_on_form 상세 피드백(`out_game_feedback`)은 `/respond` 응답엔 전혀 없고 `GET /result/{session_id}`(`UnrealResultResponse`)에만 존재. 즉 결과 화면 완성에 **항상 2회 호출**(scoreboard 턴 + /result)이 필요.

**작업(택1 — §4-D2):**
- **옵션 A (권장): 결과 조회 단일화.** scoreboard/bad-end 도달 시 Unreal은 결과를 **항상 `GET /result/{session_id}` 한 곳에서만** 받도록 규약 고정. `/respond`의 per-turn `final_result`는 디버그/하위호환용으로만 두고 결과 화면은 `/result` 의존. → 비대칭이 자연 해소(둘 다 `/result`). 작업량 최소, 계약 문서에 "결과 화면은 /result 사용" 명시.
- **옵션 B: scoreboard 응답에 통합.** bad-end 턴에도 `final_result` + `out_game_feedback`를 실어 `/respond` 한 번으로 끝내기. `_transition_for_branch`/`build_unreal_response` 경로에서 bad-end ending 노드 도달 시 `final_result_for_session` + `out_game_feedback_for_session`를 호출해 `report`에 병합. → 1회 호출로 끝나지만 `UnrealResponse.report` 스키마 확장 필요.

**리스크:** 옵션 A 낮음(주로 규약/문서), 옵션 B 중간(`UnrealResponse` 계약 확장 + 응답 시간에 final 집계 추가).

---

### P3 — 의사소통 서술형 피드백 필드 (선택 / 설계 필요)

**문제:** "의사소통 관련 피드백"이 정량 점수(`quantitative_scores.interaction_problem_solving`) 외에 **서술형 텍스트**로 필요하면, 현재는 `report_summary.main_improvement` / `report_item.improvement` 같은 범용 필드에 섞여 나올 뿐 전용 필드가 없다. focus_on_form은 어휘·문법·표현 교정 중심이라 "의사소통 전략" 피드백과 결이 다름.

**작업:**
1. Unreal이 원하는 게 ⓐ 기존 범용 필드 재사용으로 충분한지, ⓑ `report_summary`에 `communication_feedback_kr` 등 전용 필드 신설인지 먼저 확정(§4-D3).
2. ⓑ면 Dev B가 산출하는 보고서(`_report_summary` / focus_on_form 정책)에 의사소통 항목 생성 로직 추가 — LLM/룰 어느 쪽으로 생성할지 결정 필요.

**리스크:** 중간~높음. 새 콘텐츠 생성 로직이라 Dev B 보고서 파이프라인 변경 동반.

---

## 3. 권장 순서

1. **P1**(라벨 정합성) — 독립적·저리스크, 즉시 가능.
2. **P2**(결과 경로 단일화) — 옵션 A로 가면 주로 규약 확정. Unreal 호출 패턴 합의가 핵심.
3. **P3**(의사소통 피드백) — 요구 구체화 후 착수. 가장 불확실.

---

## 4. 결정 필요 (Decisions)

- **D0 — tier 선구현 처리:** (a) 유지 / (b) revert 후 P0로 재계획. *(현재 코드·테스트·계약 모두 반영된 상태)*
- **D1 — `_unranked_result`의 scoring_policy:** 레코드 0건일 때 라벨을 `scene_normalized_dimension_average`로 통일할지, 별도(`unranked`/공백) 둘지.
- **D2 — 결과 전달 경로:** P2 옵션 A(단일 `/result` 의존) vs 옵션 B(`/respond` 통합).
- **D3 — 의사소통 피드백:** 범용 필드 재사용(ⓐ) vs 전용 필드 신설(ⓑ). ⓑ면 생성 방식(LLM/룰).

---

## 5. 검증 계획

- P1: `test_final_result_score_policy.py`의 scoring_policy 단언 갱신 + scene-normalized 산출 회귀 테스트 유지.
- P2: bad-end 분기 도달 시 결과 페이로드 존재 검증 — 옵션 A면 `/result` 응답 테스트(`test_result_endpoint_returns_unreal_result_payload`) 확장, 옵션 B면 `response_builder` bad-end 경로에 `final_result`/`out_game_feedback` 병합 테스트 신규.
- P3: 신설 필드 스키마 검증 + 생성 로직 단위 테스트.
- 공통: `uv run pytest backend/tests/dev_b/ backend/tests/test_final_result_payload.py` 그린 유지.
