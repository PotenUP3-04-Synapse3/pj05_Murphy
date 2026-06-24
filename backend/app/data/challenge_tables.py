"""Data tables and entries for Eokkka (unfair accusation) challenges.

This module acts as the single source of truth for location and customs item
challenges. Developer B defines these entries, their associated difficulties
(mapped directly to TSL 1-12 rubric scores), and the suspicion reasons that
Developer A's dialogue agent uses to generate NPC dialogue.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocationEntry:
    """A travel location option assigned based on the player's diagnostic TSL.

    Difficulty maps to the total rubric scores (1-12). The suspicion reason
    is forwarded to Developer A to construct natural interrogation dialogue.
    """

    location_id: str
    name_en: str
    name_ko: str
    difficulty: int  # Range: 1 to 12
    suspicion_reason: str


@dataclass(frozen=True)
class CustomsItemEntry:
    """A customs item option revealed in baggage claim based on the player's TSL.

    Difficulty maps to the total rubric scores (1-12). The suspicion reason
    explains why the customs officer is suspicious of the item.
    """

    item_id: str
    name_en: str
    name_ko: str
    item_category: str
    difficulty: int  # Range: 1 to 12
    suspicion_reason: str


# List of 24 locations covering difficulties 1 to 12, two entries per difficulty.
# Counts: 12x2, 11x2, 10x2, 9x2, 8x2, 7x2, 6x2, 5x2, 4x2, 3x2, 2x2, 1x2. Total = 24 items.
LOCATIONS: list[LocationEntry] = [
    LocationEntry(
        "LOC_SECRET_SOCIETY",
        "Secret Society HQ",
        "비밀 결사단 기지",
        12,
        "방문 목적지가 비밀 결사단의 본부로 보입니다.",
    ),
    LocationEntry(
        "LOC_UNMARKED_LAB",
        "Unmarked Research Lab",
        "미표기 연구 실험실",
        12,
        "지도에 표기되지 않은 의심스러운 개인 연구소입니다.",
    ),
    LocationEntry(
        "LOC_DESERT_MINE",
        "Abandoned Gold Mine",
        "버려진 금광",
        11,
        "일반적인 관광지가 아닌 사막 깊은 곳의 버려진 금광입니다.",
    ),
    LocationEntry(
        "LOC_UNDERGROUND_BUNKER",
        "Underground Nuclear Bunker",
        "지하 핵 방공호",
        11,
        "민간인의 출입이 제한되는 지하 군사 방공호 구역입니다.",
    ),
    LocationEntry(
        "LOC_MILITARY_BASE",
        "Active Military Base",
        "현역 군사 기지",
        10,
        "군사 작전이 수행 중인 보안 구역 내 숙소입니다.",
    ),
    LocationEntry(
        "LOC_BORDER_CHECKPOINT",
        "Restricted Border Checkpoint",
        "통제 국경 검문소",
        10,
        "민간 출입이 통제되는 국경 검문소 인접 구역입니다.",
    ),
    LocationEntry(
        "LOC_REMOTE_ISLAND",
        "Remote Uninhabited Island",
        "외딴 무인도",
        9,
        "교통편이 지원되지 않는 황량한 무인도에 머물 예정입니다.",
    ),
    LocationEntry(
        "LOC_DIAMOND_MINE",
        "Diamond Mining Facility",
        "다이아몬드 채굴 광산",
        9,
        "상업적 다이아몬드 채굴 시설에 위치한 비공식 거처입니다.",
    ),
    LocationEntry(
        "LOC_DOUBTFUL_CLINIC",
        "Unregistered Research Clinic",
        "미등록 연구 클리닉",
        8,
        "정식 허가를 받지 않은 연구용 메디컬 센터입니다.",
    ),
    LocationEntry(
        "LOC_PRIVATE_AUCTION",
        "Private Antique Auction Hall",
        "개인 골동품 경매장",
        8,
        "고가의 골동품이 거래되는 비공식 경매장에 방문할 예정입니다.",
    ),
    LocationEntry(
        "LOC_STREET_STALL",
        "Illegal Street Market",
        "불법 거리 가판대",
        7,
        "허가받지 않은 거리 상인들의 숙소 구역입니다.",
    ),
    LocationEntry(
        "LOC_MYSTERIOUS_HOUSE",
        "Mysterious Empty Mansion",
        "의문의 빈 저택",
        7,
        "오랫동안 비어 있는 것으로 보고된 버려진 저택입니다.",
    ),
    LocationEntry(
        "LOC_ANONYMOUS_OFFICE",
        "Anonymous Shared Office",
        "익명의 공유 오피스",
        6,
        "상주 주소가 등록되지 않은 임시 공유 사무실 공간입니다.",
    ),
    LocationEntry(
        "LOC_SUBURB_WAREHOUSE",
        "Suburban Industrial Warehouse",
        "교외 산업 창고",
        6,
        "주거용 시설이 아닌 상업 지구의 대형 교외 창고입니다.",
    ),
    LocationEntry(
        "LOC_LOCAL_MARKET",
        "Local Flea Market Area",
        "현지 번개 장터 구역",
        5,
        "현지 상인들이 임시로 거주하는 벼룩시장 내부입니다.",
    ),
    LocationEntry(
        "LOC_NIGHT_DISTRICT",
        "Late-night Entertainment District",
        "심야 유흥가",
        5,
        "야간 영업 시설이 밀집한 유흥가 인근 숙소입니다.",
    ),
    LocationEntry(
        "LOC_BUDGET_HOSTEL",
        "Ultra Budget Guest House",
        "초저가 게스트하우스",
        4,
        "안전 등급이 극히 낮은 도시 외곽의 게스트하우스입니다.",
    ),
    LocationEntry(
        "LOC_UNLICENSED_HOMESTAY",
        "Unlicensed Homestay",
        "무허가 민박",
        4,
        "정식 숙박업 허가가 없는 개인 운영 민박입니다.",
    ),
    LocationEntry(
        "LOC_BACKPACKER_HOSTEL",
        "Backpacker Hostel",
        "배낭여행자 공용 호스텔",
        3,
        "투숙객 신원 관리가 느슨한 공용 도미토리 호스텔입니다.",
    ),
    LocationEntry(
        "LOC_ROADSIDE_MOTEL",
        "Roadside Motel",
        "도로변 모텔",
        3,
        "장기 투숙객이 잦은 도시 외곽의 도로변 모텔입니다.",
    ),
    LocationEntry(
        "LOC_FRIENDS_HOUSE",
        "Friend's House",
        "친구 집",
        2,
        "보증인이 명확하지 않은 지인의 개인 자택입니다.",
    ),
    LocationEntry(
        "LOC_RELATIVE_APARTMENT",
        "Relative's Apartment",
        "친척 아파트",
        2,
        "보증인 확인이 필요한 친척의 개인 거주지입니다.",
    ),
    LocationEntry(
        "LOC_DOWNTOWN_HOTEL",
        "Downtown Luxury Hotel",
        "시내 중심 호텔",
        1,
        "예약 정보가 신뢰할 수 있는 일반 관광용 도심 호텔입니다.",
    ),
    LocationEntry(
        "LOC_AIRPORT_HOTEL",
        "Airport Transit Hotel",
        "공항 환승 호텔",
        1,
        "공식 등록된 공항 내 환승 전용 호텔입니다.",
    ),
]


# ---------------------------------------------------------------------------
# Customs items: 24 entries covering difficulties 1 to 12, two per difficulty.
# Source: data/assets/dev-b/억까_수화물리스트.md
# ---------------------------------------------------------------------------
CUSTOMS_ITEMS: list[CustomsItemEntry] = [
    # ── TSL 1: Survival (difficulty 1-3) ──────────────────────────────────
    CustomsItemEntry(
        "ITEM_MISMATCHED_SOCKS",
        "A pair of mismatched socks",
        "짝짝이 양말 세트",
        "clothing",
        1,
        "내부에 미세 물품을 은닉했는지 의심받을 수 있으나 통과 자체는 크게 어렵지 않음.",
    ),
    CustomsItemEntry(
        "ITEM_PRINTED_PAPERS",
        "A bunch of safe printed A4 papers",
        "그냥 인쇄된 A4 용지 뭉치",
        "document",
        1,
        "심사관이 꼬투리를 잡으려고 한 장씩 넘겨보며 시간은 끌 수 있으나 걸릴 이유는 없음.",
    ),
    CustomsItemEntry(
        "ITEM_BLEND_BOOK",
        'A book titled "How to perfectly blend into a local community"',
        "'현지인처럼 완벽하게 동화되는 법'이라는 책",
        "book",
        2,
        "단순 관광객이라면서 현지 정착 관련 서적을 소지해 불법 체류 의도를 의심받음.",
    ),
    CustomsItemEntry(
        "ITEM_SNOW_GLOBE",
        "A souvenir snow globe",
        "기념품 스노우 글로브",
        "souvenir",
        2,
        "내부 액체 성분이 보안 검색대에서 액체물 반입 제한에 걸릴 수 있으나 기념품임을 설명하면 통과 가능.",
    ),
    CustomsItemEntry(
        "ITEM_SECRET_DIARY",
        "An old diary written in a secret code",
        "본인만 알아볼 수 있는 글씨체로 쓴 일기장",
        "document",
        3,
        "악필이나 암호문처럼 보여 범죄 모의나 수상한 기록으로 오해받아 내용 검증을 요구받을 수 있음.",
    ),
    CustomsItemEntry(
        "ITEM_RICE_WINE",
        "An unopened bottle of Korean rice wine",
        "미개봉 막걸리 한 병",
        "beverage",
        3,
        "알코올 반입량 제한 확인이 필요하며 수제 라벨로 인해 성분 불명 주류로 의심받을 수 있음.",
    ),
    # ── TSL 2: Functional (difficulty 4-6) ────────────────────────────────
    CustomsItemEntry(
        "ITEM_WORLD_MAP",
        "A fully detailed physical map of the world",
        "세계지도 실물 브로마이드",
        "map",
        4,
        "디지털 시대에 굳이 대형 실물 지도를 지참한 점에 대해 첩보나 불법 루트 개척 의심 가능.",
    ),
    CustomsItemEntry(
        "ITEM_HOMEMADE_GOCHUJANG",
        "A large jar of homemade hot pepper paste",
        "대용량 수제 고추장",
        "food",
        4,
        "상업 포장이 아닌 수제 발효 식품이라 성분 확인 및 식품 위생 검역 대상이 되며 누출 위험도 있음.",
    ),
    CustomsItemEntry(
        "ITEM_COMPRESSED_WIPES",
        "Compressed wipes",
        "압축 티슈",
        "hygiene",
        5,
        "불법 약물이나 팽창식 위험물로 오인될 수 있어 풀어서 확인당할 수 있음.",
    ),
    CustomsItemEntry(
        "ITEM_CASH_ENVELOPES",
        "Multiple sealed envelopes with cash",
        "현금이 든 봉투 여러 개",
        "cash",
        5,
        "1만 달러 미만이라도 여러 봉투에 분산 소지하면 의도적 분산(structuring) 및 자금 세탁 의심 대상.",
    ),
    CustomsItemEntry(
        "ITEM_POWER_BANK",
        "High-capacity power bank 20000mAh",
        "대용량 보조배터리",
        "electronics",
        6,
        "용량 기준 초과 시 화재 위험물로 분류되어 위탁 수하물 반입이 절대 불가능함.",
    ),
    CustomsItemEntry(
        "ITEM_CAMERA_DRONE",
        "A camera drone with battery pack",
        "카메라 드론 (배터리 포함)",
        "electronics",
        6,
        "배터리 용량 규제 및 무인기 반입 허가 필요 여부로 보안 검색에서 장시간 확인 대상이 됨.",
    ),
    # ── TSL 3: Independent (difficulty 7-9) ───────────────────────────────
    CustomsItemEntry(
        "ITEM_HOMEMADE_KIMCHI",
        "Homemade Kimchi packed in a plastic bag",
        "엄마가 비닐에 싸 준 김치",
        "food",
        7,
        "상업 포장이 안 된 미인증 식품이며, 기압 차로 액체가 누출될 경우 위생 문제로 폐기 유력.",
    ),
    CustomsItemEntry(
        "ITEM_UNLABELED_HERBAL_TEA",
        "Unlabeled herbal tea bags",
        "라벨 없는 한방 차 티백",
        "tea",
        7,
        "미인증 식물 성분이 들어 있어 식물 검역 및 성분 확인 대상이 되며 정체불명 약초로 의심받음.",
    ),
    CustomsItemEntry(
        "ITEM_MISUTGARU",
        "Misutgaru",
        "미숫가루",
        "food",
        8,
        "백색 가루 형태는 성분 검사 전까지 마약류 의심을 피하기 어려워 확인 시간이 오래 걸림.",
    ),
    CustomsItemEntry(
        "ITEM_UNLABELED_PILLS",
        "A large amount of unlabeled prescription pills",
        "라벨 없는 처방약 다량",
        "medicine",
        8,
        "정품 포장 없이 소분된 알약 다수는 마약류 또는 규제 약물로 의심받아 처방전 없이는 통과 극히 어려움.",
    ),
    CustomsItemEntry(
        "ITEM_GOLD_BAR",
        "1kg Gold bar",
        "금괴 1kg",
        "valuable",
        9,
        "자산 신고 누락 시 밀수 및 자금 세탁 혐의로 즉시 현장 압수 및 형사 처벌 가능.",
    ),
    CustomsItemEntry(
        "ITEM_BEEF_NOODLES",
        "Beef-flavored instant noodles",
        "쇠고기라면(면+스프)",
        "food",
        9,
        "스프 내 육류 성분 포함으로 인해 검역 과정에서 걸리면 폐기 처분될 확률 높음.",
    ),
    # ── TSL 4: Strategic (difficulty 10-12) ───────────────────────────────
    CustomsItemEntry(
        "ITEM_TOY_KNIFE",
        "Toy knife",
        "장난감 칼",
        "weapon_replica",
        10,
        "보안 검색대에서 실제 무기 및 테러 위협 물품으로 오인되어 엄격히 단속 및 압수.",
    ),
    CustomsItemEntry(
        "ITEM_BEEF_JERKY",
        "Beef jerky",
        "육포",
        "food",
        10,
        "아프리카돼지열병 등 동물 질병 유입 우려로 축산물 가공품은 예외 없이 강력 제한.",
    ),
    CustomsItemEntry(
        "ITEM_WILD_GINSENG",
        "wild ginseng root",
        "산삼 뿌리",
        "agriculture",
        11,
        "생식물 및 토양은 생태계 교란 및 병해충 유입 위험으로 엄격히 금지되어 통과 불가.",
    ),
    CustomsItemEntry(
        "ITEM_COUNTERFEIT_BAG",
        "Counterfeit GUGGI bag",
        "짝퉁 GUGGI bag",
        "counterfeit",
        11,
        "지식재산권 침해 물품으로 대량 혹은 상습 반입 의심 시 무조건 압수 조치.",
    ),
    CustomsItemEntry(
        "ITEM_CHEONGSIMHWAN",
        "Cheongsimhwan",
        "청심환",
        "medicine",
        12,
        "성분 식별이 불가능한 한약재 계열이라 마약류 오인 가능성이 매우 높고 설명이 불가능함.",
    ),
    CustomsItemEntry(
        "ITEM_PATEK_WATCHES",
        "10 Patek Philippe watches",
        "파텍 필립 시계 10개",
        "luxury",
        12,
        "대놓고 상업적 밀수 및 관세 포탈 의심 품목으로 즉시 압수 및 사법 처리 대상.",
    ),
]
