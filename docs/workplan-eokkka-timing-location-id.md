# 억까 배정 타이밍 통일 + 장소 ID 드리븐 작업계획서

> 작성일: 2026-06-29
> 작성자: wd14177 (level_agent)
> 소스: Unreal 팀 요청(억까 장소/물건 배정 타이밍·식별자 불일치)
> 범위: 억까(장소/물건) **배정 시점**과 **장소 식별자(ID)** 전송 경로에 한정. 억까 테이블 내용·난이도 매핑·NPC 대사 로직은 변경하지 않음.
> 영향: `tools/tool_c/developer_c_graph_tools.py`, `schemas/game_turn.py`(`GameState`/`ChallengeContext`), `api/ai_respond.py`(데모 엔드포인트), 관련 테스트, `docs/contracts/*`(계약 갱신)

---

## 0. 요약 & 목표

Unreal 팀 보고 2건:

1. **타이밍 불일치** — 억까 **장소**는 비행기씬 종료(`FLIGHT_999_COMPLETE`)에, 억까 **물건**은 입국심사 종료(`IMM_999_CLEARED`)에 배정/전송됨. 둘 다 비행기씬 종료 시점에 와야 Unreal이 이후 씬 UI를 미리 세팅할 수 있음.
2. **장소 데이터 드리븐 불가** — 물건은 `item_id`(`ITEM_*`)로 보내 드리븐 가능하나, 장소는 영어 이름(`name_en`)으로 보내 드리븐 불가. `LocationEntry.location_id`(`LOC_*`)가 이미 존재하나 전송 경로에 실리지 않음.

**목표**: 장소·물건 억까를 **모두 `FLIGHT_999_COMPLETE`에서 배정**하고, 장소를 **ID(`LOC_*`)로 전송**한다(물건의 `item_id`와 동일 패턴). 기존 영어/한글 이름 필드는 표시·NPC 대사용으로 유지(하위 호환).

---

## 1. 현재 구조 (참조)

### 배정 로직 — [developer_c_graph_tools.py:454](../backend/app/tools/tool_c/developer_c_graph_tools.py#L454) `validate_dev_b_policy_tool`
```python
if next_node_id == "FLIGHT_999_COMPLETE" and not game_state.assigned_visit_location:
    loc = pick_location(current_tsl)
    game_state.assigned_visit_location = loc.name_en          # 영어 '이름'만 저장
    game_state.assigned_visit_location_ko = loc.name_ko
    game_state.visit_location_difficulty = loc.difficulty
    game_state.visit_location_suspicion_reason = loc.suspicion_reason
elif next_node_id == "IMM_999_CLEARED" and game_state.random_customs_item is None:
    item = pick_customs_item(current_tsl)                     # 입국심사 종료에 배정
    game_state.random_customs_item = to_random_customs_item_context(item)
```

### 데이터 모델
- `LocationEntry`([challenge_tables.py:47](../backend/app/data/challenge_tables.py#L47)): `location_id`(`LOC_*`), `name_en`, `name_ko`, `difficulty`, `suspicion_reason`.
- `RandomCustomsItemContext`([game_turn.py:98](../backend/app/schemas/game_turn.py#L98)): `item_id` 포함 → 물건은 이미 ID 드리븐.
- `GameState`([game_turn.py:171](../backend/app/schemas/game_turn.py#L171)): `assigned_visit_location`(영어 이름), `assigned_visit_location_ko`, `visit_location_difficulty`, `visit_location_suspicion_reason` — **ID 필드 없음**.
- `ChallengeContext`([game_turn.py:150](../backend/app/schemas/game_turn.py#L150)): A에게 넘기는 메타데이터 — 마찬가지로 장소 ID 없음.

### 전송 경로
- `UnrealResponse.game_state`([game_turn.py:1135](../backend/app/schemas/game_turn.py#L1135))로 `GameState` 전체가 그대로 round-trip → **`GameState`에 ID 필드 추가만으로 Unreal까지 자동 전달**.
- `_sync_challenge_context_to_dialogue_seed`([developer_c_graph_tools.py:867](../backend/app/tools/tool_c/developer_c_graph_tools.py#L867)): `game_state` 억까값 → A용 `DialogueSeed.challenge_context` 동기화.

---

## 2. 작업 항목

### P1 — 배정 타이밍 통일 (물건도 `FLIGHT_999_COMPLETE`에서 배정)
[developer_c_graph_tools.py:454](../backend/app/tools/tool_c/developer_c_graph_tools.py#L454) `if/elif`를 합쳐 비행기씬 종료 시 장소·물건을 함께 배정:

```python
if next_node_id == "FLIGHT_999_COMPLETE":
    if not game_state.assigned_visit_location:
        loc = pick_location(current_tsl)
        game_state.assigned_visit_location_id = loc.location_id     # P2
        game_state.assigned_visit_location = loc.name_en
        game_state.assigned_visit_location_ko = loc.name_ko
        game_state.visit_location_difficulty = loc.difficulty
        game_state.visit_location_suspicion_reason = loc.suspicion_reason
    if game_state.random_customs_item is None:
        item = pick_customs_item(current_tsl)
        game_state.random_customs_item = to_random_customs_item_context(item)
```

- **`IMM_999_CLEARED` 분기는 방어용 fallback으로 유지**(`is None` 가드). 비행기씬에서 이미 배정됐으면 재배정 안 됨. 비행 챕터 skip 등 엣지 흐름에서 입국심사 전 물건 누락 방지.
- **결과**: 물건은 `FLIGHT_999_COMPLETE` 응답부터 `game_state.random_customs_item`에 실려 round-trip → 이후 모든 턴에서 노출.

### P2 — 장소 ID 전송 (물건의 `item_id`와 동일 패턴)
ID 필드를 추가하되 기존 영어/한글 이름은 표시·NPC 대사용으로 유지.

1. **`GameState`** ([game_turn.py:180](../backend/app/schemas/game_turn.py#L180)) 필드 추가:
   ```python
   assigned_visit_location_id: str | None = None
   ```
2. **`ChallengeContext`** ([game_turn.py:160](../backend/app/schemas/game_turn.py#L160)) 필드 추가(A도 ID 인지):
   ```python
   assigned_visit_location_id: str | None = None
   ```
3. **배정부**(P1 코드): `game_state.assigned_visit_location_id = loc.location_id` (위 P1에 포함).
4. **동기화**: `_sync_challenge_context_to_dialogue_seed`([developer_c_graph_tools.py:897](../backend/app/tools/tool_c/developer_c_graph_tools.py#L897)) location 분기에서 `assigned_visit_location_id=game_state.assigned_visit_location_id` 전달.
5. **데모 엔드포인트**: `/demo/eokkka/assign`([ai_respond.py:422](../backend/app/api/ai_respond.py#L422)) 반환에 `"assigned_visit_location_id": loc.location_id` 추가(일관성).

> 참고: `DialogueSeed` flat 필드([game_turn.py:677](../backend/app/schemas/game_turn.py#L677))에도 `assigned_visit_location_id`를 추가할지 여부는 A 어댑터가 ID를 필요로 하는지에 따라 결정(현재 A는 대사 생성에 이름·사유만 사용 → 선택). §4 확인 필요.

### P3 — 테스트 보강
- `tests/dev_b/test_challenge_assignment.py`: 장소 배정 결과에 `location_id` 포함 검증.
- `tests/test_preprototype_flow.py`: `FLIGHT_999_COMPLETE` 턴 응답의 `game_state`에 **장소 + 물건이 모두** 채워지고, `assigned_visit_location_id`가 `LOC_*` 형식인지 검증. `IMM_999_CLEARED` 도달 시 물건이 비행 시점 값 그대로 유지(재배정 없음)인지 확인.
- `tests/test_developer_a_npc_dialogue.py`: location scope에서 `challenge_context.assigned_visit_location_id` 전달 확인.

### P4 — 계약 문서 갱신
- `docs/contracts/scenario_nodes_guide_unreal.md` 및 `docs/contracts/developer_b_json_*`: `game_state.assigned_visit_location_id` 신규 필드 명시 + 배정 시점이 `FLIGHT_999_COMPLETE`로 통일됨을 기록.
- Unreal 팀 전달: 장소 드리븐 키는 `assigned_visit_location_id`(`LOC_*`). 24개 ID 목록은 [challenge_tables.py:47](../backend/app/data/challenge_tables.py#L47) `LOCATIONS` 참조.

---

## 3. 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `tools/tool_c/developer_c_graph_tools.py` | `if/elif` 병합(P1), 장소 ID 저장(P2-3), challenge_context 동기화(P2-4) |
| `schemas/game_turn.py` | `GameState`/`ChallengeContext`에 `assigned_visit_location_id` 추가(P2-1,2) |
| `api/ai_respond.py` | 데모 엔드포인트 반환에 ID 추가(P2-5) |
| `tests/...` | 배정 타이밍·ID 검증 보강(P3) |
| `docs/contracts/...` | 계약 갱신(P4) |

---

## 4. 확인 필요 (결정 대기)

1. **물건 난이도 기준 TSL 변경**: 물건을 비행기씬 종료에 뽑으면 난이도가 입국심사 챕터가 아니라 **비행 챕터의 레벨 추정값** 기준이 된다. 장소는 이미 동일하게 동작하므로 둘이 일관되나, 의도한 동작인지 확인 필요. (관련: [[flight-smalltalk-redesign]]의 레벨추정 교체)
2. **`IMM_999_CLEARED` fallback 유지 vs 제거**: 권장은 방어용 유지(엣지 흐름 안전). 단일 진실 공급원을 더 엄격히 두려면 제거 가능 — 단, 비행 skip 시 물건 누락 위험.
3. **`DialogueSeed` flat 필드에 `assigned_visit_location_id` 추가 여부**: A가 ID를 사용하지 않으면 생략. (현재 A는 이름·사유 기반 대사 생성)

---

## 5. 작업 순서 (제안)
1. P2-1,2 스키마 필드 추가 → 2. P1+P2-3,4 배정/동기화 로직 → 3. P2-5 데모 → 4. P3 테스트 → 5. P4 계약 문서. (§4는 1 착수 전 합의)
