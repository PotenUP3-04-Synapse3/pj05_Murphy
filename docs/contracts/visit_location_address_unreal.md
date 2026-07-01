# 입국신고서 방문지 주소(`assigned_visit_location_address`) — Unreal 수신·표시 가이드

> 작성일: 2026-07-01
> 범위: 억까 **장소**에 표시용 주소 문자열을 추가. 판정/난이도/대사 로직은 변경 없음.
> 배경: NPC(심사관)가 "구체적인 주소가 어디냐"고 물어도 플레이어가 화면에서 읽고 답할 주소가 없었음. 이를 위해 장소마다 짧은 주소를 부여하고 `game_state`로 전달함.

---

## 1. 무엇이 추가됐나

`GameState`에 필드 **하나** 추가됨 (기존 `assigned_visit_location*` 옆):

| 필드 | 타입 | 예시 | 비고 |
|------|------|------|------|
| `assigned_visit_location_id` | string | `LOC_DOWNTOWN_HOTEL` | (기존) 드리븐 키 |
| `assigned_visit_location` | string | `Downtown Luxury Hotel` | (기존) 영문 장소명 |
| `assigned_visit_location_ko` | string | `시내 중심 호텔` | (기존) 한글 장소명 |
| **`assigned_visit_location_address`** | string | `102 N End Ave, New York, NY` | **신규.** 공백 포함 30자 미만 보장 |
| `visit_location_difficulty` | int | `1` | (기존) 1–12 |
| `visit_location_suspicion_reason` | string | `예약 정보가 …` | (기존) NPC 대사 근거 |

- 값은 **비행기씬 종료(`FLIGHT_999_COMPLETE`) 응답부터** 채워지고, 이후 모든 턴의 `UnrealResponse.game_state`에 그대로 실려 옵니다(round-trip). Unreal은 별도 요청 없이 매 턴 `game_state`에서 읽으면 됩니다.
- 배정 전(비행 챕터 진행 중)에는 이 필드들이 **`null`** 입니다.

---

## 2. 입국신고서 UI에 어떻게 표시하나

권장 표기 형식 (기존 화면 문자열을 이 형식으로 교체):

```
{assigned_visit_location}, {assigned_visit_location_address} ({assigned_visit_location_ko})
```

예시 렌더 결과:

```
Downtown Luxury Hotel, 102 N End Ave, New York, NY (시내 중심 호텔)
Remote Uninhabited Island, Isle, 14.5N 171.2W (무인도)
Secret Society HQ, Basement, 1 Cipher Ln, NY (비밀 결사 본부)
```

### Unreal(C++/Blueprint) 조립 예 (의사코드)

```cpp
FString Name    = GameState.assigned_visit_location;         // "Downtown Luxury Hotel"
FString Addr    = GameState.assigned_visit_location_address; // "102 N End Ave, New York, NY"
FString NameKo  = GameState.assigned_visit_location_ko;      // "시내 중심 호텔"

FString FormText;
if (!Name.IsEmpty())
{
    FormText = Name;
    if (!Addr.IsEmpty())   FormText += TEXT(", ") + Addr;
    if (!NameKo.IsEmpty()) FormText += TEXT(" (") + NameKo + TEXT(")");
}
else
{
    FormText = TEXT("");  // 아직 미배정 → 신고서 칸 비움 또는 플레이스홀더
}
```

---

## 3. 주의사항

1. **null 가드 필수**: 비행 챕터에서는 `assigned_visit_location_address == null`. 이때 주소 칸을 비우거나 "기내 진단 후 자동 배정" 같은 플레이스홀더로 처리하세요. 위 예처럼 `Name`이 비면 조립을 건너뛰면 됩니다.
2. **주소는 표시용**입니다. 플레이어가 이 주소를 그대로 말하든 다르게 말하든 **NPC는 사실 일치 여부를 검증하지 않습니다.** 판정은 기존 로직(장소 억까 사유 기반)과 동일합니다. 즉 주소는 "플레이어가 답할 거리"를 주기 위한 소품입니다.
3. **길이**: `assigned_visit_location_address`는 항상 공백 포함 30자 미만. UI 폭 설계 시 이 상한을 기준으로 잡으면 됩니다.
4. **주소 형태는 장소 성격별로 다름**: 도심형은 도로명 주소(`102 N End Ave, New York, NY`), 무인도·광산·방공호 등은 좌표/구역형(`Isle, 14.5N 171.2W`, `Bunker 7, Restricted Zone`)입니다. 파싱하지 말고 **문자열 그대로 표시**하세요.

---

## 4. 24개 장소 주소 참조표

값의 단일 진실 공급원은 [`challenge_tables.py`](../../backend/app/data/challenge_tables.py)의 `LOCATIONS`. 드리븐은 `assigned_visit_location_id` 기준.

| location_id | address (`address_en`) |
|-------------|------------------------|
| LOC_SECRET_SOCIETY | Basement, 1 Cipher Ln, NY |
| LOC_UNMARKED_LAB | Lot 9, No Sign Rd, NV |
| LOC_DESERT_MINE | Mile 88, Mojave Desert, CA |
| LOC_UNDERGROUND_BUNKER | Bunker 7, Restricted Zone |
| LOC_MILITARY_BASE | Bldg 12, Base Camp, TX |
| LOC_BORDER_CHECKPOINT | Gate 3, Border Line, TX |
| LOC_REMOTE_ISLAND | Isle, 14.5N 171.2W |
| LOC_DIAMOND_MINE | Shaft 4, Mine Rd, AK |
| LOC_DOUBTFUL_CLINIC | Rm 2F, 88 Back St, NJ |
| LOC_PRIVATE_AUCTION | 5 Velvet Hall, Boston, MA |
| LOC_STREET_STALL | Stall 7, Market Aly, NY |
| LOC_MYSTERIOUS_HOUSE | 13 Hollow Hill Rd, CT |
| LOC_ANONYMOUS_OFFICE | Unit 0, 50 Vague Ave, NY |
| LOC_SUBURB_WAREHOUSE | 200 Depot Rd, Newark, NJ |
| LOC_LOCAL_MARKET | Booth 9, Flea Mkt, NY |
| LOC_NIGHT_DISTRICT | 7 Neon St, Las Vegas, NV |
| LOC_BUDGET_HOSTEL | 12 Cheap St, Newark, NJ |
| LOC_UNLICENSED_HOMESTAY | 30 Quiet Ln, Queens, NY |
| LOC_BACKPACKER_HOSTEL | 5 Dorm Rd, Brooklyn, NY |
| LOC_ROADSIDE_MOTEL | Rt 9, Mile 40, Albany, NY |
| LOC_FRIENDS_HOUSE | 88 Maple St, Newark, NJ |
| LOC_RELATIVE_APARTMENT | Apt 4B, 21 Elm St, NY |
| LOC_DOWNTOWN_HOTEL | 102 N End Ave, New York, NY |
| LOC_AIRPORT_HOTEL | 1 Terminal Rd, JFK, NY |
