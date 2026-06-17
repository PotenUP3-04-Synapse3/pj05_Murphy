# Developer B 작업계획서 — 억까(트집) 장소·수화물 레벨별 배정 적용

- 작성일: 2026-06-17
- 작성자: Developer B
- 대상 기능: 입국심사 "억까 장소 리스트"와 세관 "억까 수화물 리스트"를
  플레이어의 진단 레벨(TSL)에 맞춰 난이도 구간별로 배정한다. 잘할수록 더
  황당하고 설명하기 어려운 상황을 부여해 난이도를 유지하는 것이 목적.
  - 장소: 기내 스몰토크 진단으로 레벨 확정 → **입국심사 전** 입국신고서에
    표기될 방문지(`visit_location`)를 난이도 구간 내 랜덤 배정. 입국심사 NPC는
    각 장소의 **설계 이유(억까 사유)** 의도대로 트집 질문을 한다.
  - 수화물: 입국심사로 **조정된 레벨**에 따라, 입국심사 종료 후 세관 단계에서
    수화물을 난이도 구간 내 랜덤 배정. 플레이어는
    `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM` 노드에서 자신의 억까 물품을 확인하고
    돌발 상황을 설명한다.
- 방향(확정): **1번 안 — 픽 규칙은 B, 실행·영속화는 C, 대사는 A**
  - **B**: 난이도→레벨 픽 규칙(순수함수) + 데이터 테이블 + scenario 노드 설계.
    밸런스의 단일 소스이며 B가 단위 테스트로 닫는다.
  - **C**: 스키마 확장 + 전환 노드에서 B 픽 함수 호출 + GameState 영속화 +
    Unreal(입국신고서·BAG_006 reveal) 전달.
  - **A**: `dialogue_seed`의 억까 사유(suspicion 의도)만 보고 NPC 트집 대사를
    LLM 생성. B의 고정 질문은 `_A_BLOCKED_*` 경계에서 차단되므로 seed 메타로만
    전달한다.

## 0. 왜 1번 안인가 (대안 대비)

배정은 두 책임으로 쪼개진다 — **(가) 픽 규칙**("TSL_3이면 난이도 7~9 풀에서
랜덤"이라는 밸런스 로직)과 **(나) 픽 실행 + 영속화**(실제 선택·GameState 기록·
다음 턴 유지·Unreal 전달).

| 안 | (가) 픽 규칙 | (나) 실행·영속화 | 문제 |
|---|---|---|---|
| **1 (채택)** | **B 코드** | **C 런타임** | 충돌 없음 |
| 2 | 문서/CSV | C/Unreal | 밸런스 규칙이 B·C 두 곳에 중복돼 어긋남, B가 검증 불가 |
| 3 | B | B(정책출력) | 전환-노드 타이밍과 불일치, 영속화는 어차피 C라 이득 없음 |

- 난이도→레벨 경계는 이미 B 소유다(`tier_difficulty_controller.
  travel_speaking_level_for_total`). 픽 규칙을 코드 밖(2번)으로 빼면 TSL 경계를
  한 번 바꿀 때 두 곳을 고쳐야 하고, "레벨 7인데 난이도 11 청심환" 같은 붕괴가
  조용히 발생한다. 1번은 픽 규칙을 B 코드에 두어 **밸런스 단일 소스 + 유닛
  테스트 가능**.
- 3번은 배정 시점(전환 노드)이 B 정책 파이프라인(발화 평가 턴)과 안 맞고,
  영속화는 결국 C라 B 관여만 늘고 이득이 없다.

## 1. 배경 및 목표

`RandomCustomsItemContext`(`game_turn.py:85`)는 이미 `item_name`/`item_category`/
`visit_location` 필드를 갖고 있고, 주석에 *"chosen by Unreal or a local CSV
table"* 로 **소유자가 모호**한 상태다. `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`
노드(`scenario_nodes.json:1084`)도 이미 존재한다. 그러나:

| 부족한 것 | 현황 |
|---|---|
| 난이도→레벨 매핑 | 없음. 어떤 레벨에 어떤 장소/수화물을 줄지 규칙 부재 |
| 데이터 테이블 | 두 리스트가 Obsidian MD에만 존재, 코드 자산 아님 |
| 픽 로직 | 없음. 구간 내 랜덤 선택 함수 부재 |
| 억까 사유 → NPC | `suspicion_reason`을 A에 전달할 경로 없음 |

### 이 작업이 중요한 이유

난이도 1~12는 이미 **TSL 루브릭 total(0~12)과 동일 척도**로 재배치되어 있어
(사용자가 12점 만점에 맞춰 재배치 완료) **추가 변환 없이 직접 매핑**된다. 픽
규칙을 B가 소유하면 기존 TSL 경계를 그대로 재사용해 밸런스 일관성을 보장한다.

## 2. 핵심 설계 (1번 안)

### 2.1 난이도 ↔ 레벨 직접 매핑

루브릭 total(`tier_difficulty_controller.travel_speaking_level_for_total`)의
TSL 경계를 그대로 억까 난이도 구간으로 재사용한다.

| TSL | 루브릭 total | 억까 난이도 구간 | 의도 |
|---|---|---|---|
| TSL_1_SURVIVAL | 0~3 | **1~3** | 약한 학습자 → 쉬운 억까 |
| TSL_2_FUNCTIONAL | 4~6 | **4~6** | |
| TSL_3_INDEPENDENT | 7~9 | **7~9** | |
| TSL_4_STRATEGIC | 10~12 | **10~12** | 강한 학습자 → 황당한 억까 |

> 경계는 **단일 상수 맵** `TSL_TO_DIFFICULTY_RANGE`로 노출해, TSL 경계가 바뀌면
> 한 곳만 고치면 되도록 한다.

### 2.2 데이터 테이블 (신규, Dev B 자산)

신규 `backend/app/data/challenge_tables.py`(또는 동급 JSON + 로더). 두 MD를
구조화한다. **B 내부 dataclass**로 두어 C 스키마(`game_turn.py`)와 디커플링 —
B는 C 스키마 확장을 기다리지 않고 테이블·픽을 완성·테스트할 수 있다.

```python
@dataclass(frozen=True)
class LocationEntry:
    location_id: str        # e.g. "LOC_FRIENDS_HOUSE"
    name_en: str            # 입국신고서/대사 표기용
    name_ko: str
    difficulty: int         # 1~12
    suspicion_reason: str   # 억까 사유 → A seed로 전달

@dataclass(frozen=True)
class CustomsItemEntry:
    item_id: str            # e.g. "ITEM_CHEONGSIMHWAN"
    name_en: str
    name_ko: str
    item_category: str      # medicine/food/electronics/luxury/...
    difficulty: int         # 1~12
    suspicion_reason: str
```

- 장소 17종(난이도 12·12·11·11·10·9·9·8·8·7·7·6·6·5·4·2·1), 수화물 18종
  (난이도 1~12 전 구간 분포).
- **데이터 갭 주의**: 장소 리스트에 **난이도 3이 없다.** TSL_1 구간(1~3) 장소
  풀은 난이도 1·2만으로 구성된다. 픽 함수는 빈 풀/희소 풀을 안전 처리하고(§2.3),
  테이블 로드시 "각 TSL 구간에 최소 1개"를 보장하는 검증을 둔다.

### 2.3 픽 서비스 (신규, Dev B 순수함수)

신규 `backend/app/services/service_b/challenge_assignment_service.py`.

```python
TSL_TO_DIFFICULTY_RANGE = {
    "TSL_1_SURVIVAL": (1, 3),
    "TSL_2_FUNCTIONAL": (4, 6),
    "TSL_3_INDEPENDENT": (7, 9),
    "TSL_4_STRATEGIC": (10, 12),
}

def pick_location(tsl: str, *, rng: random.Random | None = None) -> LocationEntry: ...
def pick_customs_item(tsl: str, *, rng: random.Random | None = None) -> CustomsItemEntry: ...
```

- 구간 내 후보를 필터 → 랜덤 1개. **풀이 비면** 인접 구간으로 폴백(예: TSL_1
  장소 풀에 난이도 3이 없어도 1~2에서 픽). 폴백 규칙을 명시적으로 둔다.
- `rng` 주입 가능 → 테스트에서 결정적 시드로 검증.
- C 경계 변환은 B가 **헬퍼만 제공**(예: `to_random_customs_item_context(entry)`)
  하고, 실제 호출·주입은 C가 한다(§2.4, §9).

### 2.4 배정 타이밍·배선 (C가 B 픽 함수 호출)

배선 지점은 **전환(transition) 노드** 두 곳이다. 호출 주체는 C 런타임.

| 배정 | 전환 노드 | Unreal 이벤트 | 시점 | 사용 레벨 |
|---|---|---|---|---|
| 장소(`visit_location`) | `FLIGHT_999_COMPLETE`(CH0_01→CH0_02) | (기내 종료) | 입국심사 **전** | 기내 진단 확정 TSL |
| 수화물(`random_customs_item`) | `IMM_999_CLEARED`(CH0_03→CH0_04, `ENTER_BAGGAGE_CLAIM`) | 세관 진입 | BAG_006 **전** | 입국심사로 **조정된** TSL |

- 장소는 입국심사(CH0_03)에서 입국신고서로 노출되므로 반드시 그 **이전**
  전환에서 확정돼야 한다.
- 수화물은 BAG_006에서 reveal되므로 입국심사 종료 전환에서 확정. 입국심사
  결과로 레벨이 조정됐다면 그 조정 TSL을 입력으로 쓴다.

### 2.5 노드 보강 + 억까 사유 seed 전달

- `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`(이미 존재) — `required_slots`
  (`customs_item_explanation`), `hint_policy`는 유지. 배정된 품목 메타가
  seed로 흘러가 A가 같은 물건을 지칭하도록 한다.
- 입국심사 노드(`IMM_*`)의 `npc_question_goal`은 유지하되, 배정된 장소의
  `suspicion_reason`을 `dialogue_seed`에 실어 A가 "그 장소"의 억까 사유대로
  압박 질문을 생성하게 한다.
- **A 경계 준수**: B의 고정 질문/정답 예문은 A에 넘기지 않는다
  (`dev_a_npc_dialogue_client._A_BLOCKED_*`). 전달은 `dialogue_seed`의 의도
  메타(`suspicion_reason`, `difficulty`, 품목/장소 식별자)로 한정.

## 3. 범위

### 포함 (Dev B 소유, 단독 진행 가능)

- `backend/app/data/challenge_tables.py` (신규 — 장소·수화물 테이블 + 로더 +
  구간 커버리지 검증)
- `backend/app/services/service_b/challenge_assignment_service.py` (신규 —
  `TSL_TO_DIFFICULTY_RANGE`, `pick_location`, `pick_customs_item`, 빈 풀 폴백,
  C 경계 변환 헬퍼)
- `backend/app/data/scenario_nodes.json` (BAG_006 메타 확인/보강, 입국심사
  노드에 억까 사유 연결 지점 정리 — 단일 진단 노드 정책과 충돌 없게)
- B→A seed emit 지점(`tool_b` 정책 그래프 도구): 배정된 장소/품목의
  `suspicion_reason`을 `dialogue_seed`에 실어보내는 경로
- `backend/tests/dev_b/test_challenge_assignment.py` (신규),
  `test_developer_b_policy_engine.py` 회귀

### 제외 (타 팀 → §9 변경 요청)

- **Dev C**: `game_turn.py` 스키마 확장(`RandomCustomsItemContext`에 `difficulty`/
  `suspicion_reason`, `GameState`에 `assigned_visit_location`/`_ko`/
  `visit_location_difficulty`/`visit_location_suspicion_reason`, `DialogueSeed`에
  억까 컨텍스트 필드), 전환 노드에서 B 픽 함수 호출, GameState 영속화(턴 간
  유지), Unreal로 장소·품목 전달.
- **Dev A**: 배정된 장소/품목의 `suspicion_reason` 의도대로 NPC 트집 대사
  LLM 생성(고정 질문 모방 금지), 입국신고서 표기 장소와 동일 지칭 유지.
- **Unreal**: 입국신고서 UI에 `visit_location` 표시, BAG_006 수화물 시각 reveal.
- env 수정, TTS/음성 출력.

## 4. 현재 코드 분석

- `tier_difficulty_controller.travel_speaking_level_for_total`(`:163`): total
  0-3/4-6/7-9/10+ → TSL_1~4. **억까 난이도 구간과 동일 경계** → 그대로 재사용.
- `RandomCustomsItemContext`(`game_turn.py:85`): `item_name` 필수,
  `visit_location`/`item_category` 등 옵셔널 존재. **`difficulty`/
  `suspicion_reason` 없음** → Dev C 추가 필요(§9).
- `GameState`(`game_turn.py:105`): `random_customs_item`은 있으나 **장소 배정
  필드 없음** → Dev C 추가 필요.
- `DialogueSeed`(`game_turn.py:333`): `surface_goal`/`difficulty_profile` 등
  존재. **억까 사유 전용 필드 없음** → Dev C 추가 또는 기존 필드 재활용 합의.
- `dev_a_npc_dialogue_client._A_BLOCKED_*`(`:26-46`): B의 `npc_question`/
  `recommended_expression` 등이 A로 못 넘어감 → 억까 사유는 **seed 메타로만**
  전달해야 함(고정 질문 경로 불가).
- 전환 노드: `FLIGHT_999_COMPLETE`(`:94`), `IMM_999_CLEARED`(`:728`) — C가
  픽을 호출할 배선 지점.

## 5. 작업 항목 (Dev B 소유)

### 작업 1 — 데이터 테이블 신설

- 두 MD를 `challenge_tables.py`로 이관(난이도·en/ko·category·suspicion_reason
  태깅). 로드시 각 TSL 구간 커버리지 검증(빈 구간이면 명시적 폴백 규칙 적용).

### 작업 2 — 픽 서비스 신설

- `TSL_TO_DIFFICULTY_RANGE` + `pick_location`/`pick_customs_item`(rng 주입,
  빈 풀 인접 구간 폴백) + `to_random_customs_item_context` 경계 변환 헬퍼.

### 작업 3 — seed emit 경로

- `tool_b` 정책 그래프에서 배정된 장소/품목의 `suspicion_reason`·식별자를
  `dialogue_seed`에 실어보내는 경로 추가(고정 질문은 emit 금지, A 경계 준수).

### 작업 4 — 노드 메타 확인/보강

- `BAG_006`·입국심사 노드가 배정 메타와 정합하는지 확인. 단일 진단 노드 정책
  (직전 워크플랜)과 충돌 없게 조정.

## 6. 계약/주의

- **난이도 척도 = TSL 척도**(둘 다 0/1~12). 별도 변환표를 만들지 말고
  `TSL_TO_DIFFICULTY_RANGE` 단일 맵만 둔다.
- **억까 사유는 seed 메타로만** A에 전달(고정 질문 경로 `_A_BLOCKED_*`로 차단됨).
- **장소 난이도 3 부재** 등 풀 갭은 픽 폴백으로 흡수하되, 데이터 보강이
  바람직하면 별도 데이터 과제로 분리.
- B는 C 스키마 확장 전에도 **자체 dataclass로 테이블·픽을 완성·테스트**할 수
  있다(디커플링). C 경계 변환 헬퍼만 스키마 확정 후 연결.

## 7. 테스트 계획

`backend/tests/dev_b/test_challenge_assignment.py`(신규):

- `test_pick_location_respects_tsl_range`: 각 TSL에서 배정 장소의 `difficulty`가
  해당 구간 내(폴백 포함)인지.
- `test_pick_customs_item_respects_tsl_range`: 수화물 동일.
- `test_higher_level_gets_harder_challenge`: TSL_4 풀 최소 난이도 > TSL_1 풀
  최대 난이도(역전 없음) 보장.
- `test_pick_is_deterministic_with_seeded_rng`: 동일 시드 → 동일 결과.
- `test_empty_pool_falls_back_to_adjacent`: 장소 난이도 3 부재 같은 갭에서
  TSL_1이 빈 결과 없이 인접(1~2)에서 픽.
- `test_table_covers_all_tiers`: 테이블 로드시 4개 TSL 구간 모두 픽 가능.
- `test_to_context_helper_maps_fields`: 경계 변환 헬퍼가 name/category/
  difficulty/suspicion_reason를 올바르게 매핑.
- 회귀: `IMM_*`/`BAG_*` 기존 분기·채점 영향 없음.

## 8. 검증 명령

```powershell
uv run pytest backend/tests/dev_b/test_challenge_assignment.py
uv run pytest backend/tests/dev_b/test_developer_b_policy_engine.py
uv run pytest
uv run ruff check .
uv run mypy .
```

## 9. 타 팀 의존 작업 (변경 요청)

배정의 실행·영속화·표시·대사는 타 팀 소유다. 상세는
`docs/contracts/change_requests.md`(**Change Request - 2026-06-17 -
[CR-B-EOKKKA] 억까 장소·수화물 레벨별 배정**) 및 `docs/handoff.md`에 동기화한다.

- **Dev C**:
  1. `game_turn.py` 스키마 확장 — `RandomCustomsItemContext`에 `difficulty: int |
     None`, `suspicion_reason: str | None`; `GameState`에 `assigned_visit_location`/
     `assigned_visit_location_ko`/`visit_location_difficulty`/
     `visit_location_suspicion_reason`; `DialogueSeed`에 억까 컨텍스트 전달 필드
     (또는 기존 필드 재활용 합의).
  2. **픽 실행 주체** — 전환 노드 처리에서 B의 `pick_location`(`FLIGHT_999_COMPLETE`)·
     `pick_customs_item`(`IMM_999_CLEARED`)을 호출해 GameState에 기록.
  3. **영속화** — 배정값을 다음 턴까지 유지, 입국신고서·BAG_006로 Unreal 전달.
- **Dev A**: 배정된 장소/품목의 `suspicion_reason` 의도대로 NPC 트집 대사
  생성(고정 질문 모방 금지), 입국신고서 장소와 동일 지칭 유지.
- **Unreal**: 입국신고서 UI 장소 표시, BAG_006 수화물 시각 reveal.

---

## 10. 산출물·문서 틀 (작업계획서가 교체되어도 유지)

> 이 절은 **이 계획서가 다른 건으로 교체되더라도 유지한다.** Dev B 작업이
> 타 오너(Dev A / Dev C / Unreal)에 의존하면 **handoff 와 change_request 문서를
> 반드시 남긴다.** 본 건의 실제 항목은 §9 와 아래 2건에 작성되어 있다.

### 10.1 절차 (매 작업계획서 작성/교체 시)

1. §3 "제외(타 팀 소유)"와 §9 "타 팀 의존 작업"에 적힌 항목을 오너별
   change request 로 구체화한다(파일·함수 단위, 정확한 입출력/동작).
2. `docs/contracts/change_requests.md` **끝에** 아래 Change Request 틀로 추가한다.
3. `docs/handoff.md` **상단**(`# Handoff` 바로 아래)에 아래 Handoff 틀로 추가한다.
4. §9 에서 추가한 change request 의 제목/날짜를 역참조해 양방향으로 연결한다.
5. 타 팀 의존이 전혀 없으면 change request 는 생략하되, **handoff 는 항상 남긴다**
   (무엇을 왜 바꿨는지 + 검증 결과).

### 10.2 Change Request 틀

```markdown
## Change Request - YYYY-MM-DD - <짧은 제목>

Status: Open.

### Requested By

Developer B

### Affected Owner

Developer A and/or Developer C / Sean Han (필요 시 Unreal)

### Reason

왜 필요한가 — 증상 + 확정 방향 + "Dev B가 한 일 / 타 팀이 해야 할 일"의 경계.

### Proposed Contract Change

오너별로 머리표(`Dev A:`, `Dev C:`)를 달고, 정확한 입출력·동작 변경을
파일·함수 단위로 명시.

### Compatibility Impact

스키마/계약 파급, 회귀 가드(영향받지 않아야 할 씬·테스트).

### Temporary Workaround

타 팀 반영 전까지의 임시 동작.
```

### 10.3 Handoff 틀

```markdown
## YYYY-MM-DD Developer B <한 줄 제목>

Developer B는 <무엇을 / 왜> 했다.

- 변경/산출물: <작업계획서 교체, 신설 정책/메서드, 배선 지점 등>
- 교차 의존: Dev A/Dev C 변경 요청을
  `docs/contracts/change_requests.md`(<change request 제목>)로 전달.
- 검증/후속: <테스트·검증 명령 결과 또는 다음 단계>
```

---

## 11. Dev C 연동 및 respond-dialog 테스트 페이지 개선 완료 (2026-06-17)

Developer C(Sean Han)는 Developer B의 본 작업계획서에 의존된 **[CR-B-EOKKKA]** 관련 백엔드 연동 작업 및 테스트 페이지(`/respond-dialog`) 개선을 완료했습니다.

### Dev C 반영 내역:
1. **스키마 확장 & 영속화**:
   - `game_turn.py` 스키마에 `assigned_visit_location` 계열 필드 및 `random_customs_item` 확장 필드 반영 완료.
   - `DeveloperCGraphTools.validate_dev_b_policy_tool()` 전환 노드 시점에서 B의 `pick_location` 및 `pick_customs_item`을 호출하여 `GameState`에 자동 배정 및 영속화 완료.
2. **테스트 페이지 (`respond-dialog`) 개선**:
   - English Level (0~12) 입력 필드 및 "Auto-Fill", "Apply" 연동 기능을 추가하여 `/api/game/ai/demo/eokkka/assign` 및 `/options` 엔드포인트를 통해 레벨별 결정적/랜덤 억까 정보의 인계 검증을 지원하도록 구현 완료.
   - Flight 및 Result 챕터 선택 시 억까 패널 자동 숨김 및 상태 초기화 보장.
3. **비용 추정 및 로그 개선**:
   - `gpt-5.4-mini`, `fake-understanding-model`, `unknown` 모델의 비용 단가 매핑 및 fallback 단가(`gpt-4o-mini`) 적용으로 $0.000000 비용 오류 해결.
   - 세션 통계에 사용된 모델 목록(`models`) 노출 완료.
4. **검증 통과**:
   - `uv run pytest` 전체 314개 테스트 통과 완료.
   - `ruff` 및 `mypy` 검사 오류 없이 통과 완료.

---

## 12. Developer B 누적 작업 포트폴리오 (git 이력 기반, 2026-06-04 ~ 06-17)

> §11이 직전 억까/테스트 페이지 연동만 다루므로, 그동안 포트폴리오에 정리되지
> 않았던 Developer B의 전체 기여를 git 이력 기준으로 누적 정리한다. 각 항목은
> 실제 커밋·모듈에 근거한다.

### 12.0 역할 한 줄 요약

Developer B는 **결정론적(rule-based) 정책 엔진**을 소유한다. 지저분한 여행 영어·
한국식 영어·짧은 비문 발화를 받아 **평가(verdict)·레벨/힌트·분기·상태 델타·
피드백·최종 점수**를 산출한다. NPC 대사(A)·오케스트레이션/검증(C)·TTS·Unreal
명령은 소유하지 않으며, 모든 출력은 C와의 JSON 계약(`dev_b_policy.v1`)을 엄격히 따른다.

### 12.1 정책 엔진 코어 — 상태 머신 & 난이도 컨트롤러

| 모듈 | 책임 |
|---|---|
| `service_b/scenario_state_machine.py` | 턴별 verdict(SUCCESS/PARTIAL/UNCLEAR/FAIL/CRITICAL_FAIL)와 분기(retry/clarify/hint/advance/bad_end) 결정 |
| `service_b/tier_difficulty_controller.py` | 6개 루브릭 영역(이해·유창·문법·어휘·명확·상호작용) × 0~2점 = **총점 0~12** → `travel_speaking_level_for_total()`로 TSL_1~4 판정, 티어 보정으로 NPC 말속도·질문 복잡도·힌트 빈도·압박 강도 산출 |
| `agent_b/policy_graph.py`, `tool_b/developer_b_policy_graph_tools.py` | LangGraph 기반 정책 파이프라인 배선 |

- 관련 커밋: `fb92130`(상태 머신 + 테스트 스위트, 06-16), `70b0f4a`(정책 엔진 통합, 06-16), `bed85e4`(진단 서비스·상태 머신·응답 오케스트레이션, 06-12).
- 회귀 가드: `test_developer_b_policy_engine.py`.

### 12.2 Chapter 0 시나리오 노드 설계 (`scenario_nodes.json`)

- 입국심사 라우트 `IMM_001_PASSPORT` ~ `IMM_007_FINAL_DECISION`: 각 노드에
  allowed-next-nodes와 retry/clarify/hint/warning/bad-end 분기 후보, `objective_kr`
  (한국어 UI 목표) 포함.
- 5턴 **기내 스몰토크 진단 라우트**, **수화물 분실 문제해결 라우트**
  (`BAG_001_*` ~ `BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM`), `ALPHA_999_FINAL_SCOREBOARD`
  최종 분기 노드.
- 관련 커밋: `9a9da1a`(입국심사 정책·노드 정의, 06-10), `e6b50b5`(한국어 objective, 06-04).

### 12.3 기내 스몰토크 진단 정책 (`flight_smalltalk_diagnostic_policy.py`)

- 게임 도입부 5턴 대화로 플레이어의 초기 TSL을 **숨은 진단**
  (`estimate_user_travel_speaking_level`)으로 추정. 슬롯 중립화로 진단 누설 방지.
- 관련 커밋: `08fa014`(기내 스몰토크 개선, 06-16), `fd10aeb`(진단·리포팅 계약, 06-11),
  `f1ca214`(smalltalk slot safety, 06-17).
- 회귀 가드: `test_flight_smalltalk_diagnostic_policy.py`.

### 12.4 레벨·힌트·피드백 생성 계층

| 모듈 | 책임 |
|---|---|
| `agent_b/english_level_hint_agent.py`, `agent_b/feedback_hint_llm_client.py` | 레벨별 힌트 산출. **결정론 정책이 verdict/분기/다음 노드/상태 델타의 단일 권위**, LLM은 한국어 힌트·피드백 문구·리포트 표현·Focus-on-Form 설명·루브릭 후보로만 제한(폴백 보장) |
| `service_b/feedback_hint_generator.py` | 인게임 힌트(keyword/sentence_pattern/situation/action) 생성 |
| `service_b/focus_on_form_report_policy.py` | Focus-on-Form 교정 타깃 산출 |
| `service_b/level_adaptation_controller.py` | 진행 중 레벨 적응 조정 |

- 관련 커밋: `df68ff3`(English level hint agent + 정책 그래프 인프라, 06-12),
  `a99b28d`(피드백 서비스·hint agent, 06-09).
- 회귀 가드: `test_focus_on_form_report_policy.py`.

### 12.5 최종 점수 & Bad Ending 정책

| 모듈 | 책임 |
|---|---|
| `service_b/final_result_score_policy.py` | Alpha 최종 스코어보드 점수·티어·강점/취약점 산출 및 검증 |
| `service_b/bad_ending_policy.py` | 인내심/의심 한계 초과 시 bad ending 분기 가드 |

- 관련 커밋: `174926d`(최종 점수 정책·검증, 06-05), `f1ca214`(bad ending guard, 06-17).
- 회귀 가드: `test_final_result_score_policy.py`, `test_dev_b_bad_ending_branch.py`,
  `test_scenario_nodes_bad_ending.py`.

### 12.6 학습 기록 영속화 & 실행 로깅

| 모듈 | 책임 |
|---|---|
| `service_b/openkb_feedback_writer.py` | B 소유 OpenKB `dev_b` 네임스페이스에 error capture·out-game 피드백 seed·Focus-on-Form 타깃·리포트 아이템·분기 결정·상태 델타를 **JSONL + 마크다운**으로 결정론 기록 |
| `service_b/developer_b_agent_run_logger.py` | Developer B 통합 AgentRun 실행 추적 로깅 |

- 관련 커밋: `eb51775`(OpenKB 통합·피드백 생성, 06-04), `2fbf91a`(AgentRun 로거, 06-04).
- 회귀 가드: `test_developer_b_agent_run_log.py`.

### 12.7 억까(트집) 장소·수화물 레벨별 배정 — 본 작업계획서(§0~§9)

- 데이터 테이블 `data/challenge_tables.py`(장소 17·수화물 18종, 난이도 1~12),
  픽 서비스 `service_b/challenge_assignment_service.py`(`TSL_TO_DIFFICULTY_RANGE`,
  `pick_location`/`pick_customs_item`, 빈 풀 인접 폴백, `to_random_customs_item_context`).
- 밸런스 단일 소스를 B 순수함수로 소유, 실행·영속화는 C(§9, §11).
- 관련 커밋: `0cc62aa`(코어 스키마 + 억까 픽 서비스, 06-17).
- 회귀 가드: `test_challenge_assignment.py`.

### 12.8 계약·문서 산출물

- `docs/contracts/developer_b_json_final_v1.md`, `developer_b_json_key_value_contract_v1.md`,
  `developer_b_report_and_dialogue_seed_contract.md`, `docs/dev_b_rubric.md`.
- 타 팀 의존은 `docs/contracts/change_requests.md`(`[CR-B-EOKKKA]`)와
  `docs/handoff.md`로 양방향 연결(§10 절차).
- 관련 커밋: `4e6c640`(JSON Key-Value 계약 + 포트폴리오 문서, 06-04).

