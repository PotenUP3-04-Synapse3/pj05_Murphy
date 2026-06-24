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


# List of 18 customs items covering difficulties 1 to 12.
CUSTOMS_ITEMS: list[CustomsItemEntry] = [
    CustomsItemEntry(
        "ITEM_URANIUM_ORE",
        "Uranium Ore Specimen",
        "우라늄 광석 표본",
        "mineral",
        12,
        "방사능 수치가 의심되는 알 수 없는 광석입니다.",
    ),
    CustomsItemEntry(
        "ITEM_GOLD_BARS",
        "Unmarked Gold Bars",
        "미신고 금괴",
        "valuable",
        11,
        "신고 기준을 초과하는 상당한 양의 미등록 금괴입니다.",
    ),
    CustomsItemEntry(
        "ITEM_SPY_CAMERA",
        "Miniature Spy Camera",
        "초소형 스파이 카메라",
        "electronics",
        10,
        "불법 촬영에 사용될 수 있는 은폐형 레코더 장치입니다.",
    ),
    CustomsItemEntry(
        "ITEM_MILITARY_DRONE",
        "Military Grade Drone",
        "군용 드론",
        "electronics",
        9,
        "항공 보안 구역에서 촬영을 할 수 있는 고성능 촬영 장비입니다.",
    ),
    CustomsItemEntry(
        "ITEM_LUXURY_WATCH",
        "Undeclared Luxury Watch",
        "미신고 명품 시계",
        "luxury",
        8,
        "미국 세관 면세 한도를 크게 초과하는 고급 손목시계입니다.",
    ),
    CustomsItemEntry(
        "ITEM_EXOTIC_SEEDS",
        "Exotic Plant Seeds",
        "외래 식물 씨앗",
        "agriculture",
        7,
        "생태계 교란 가능성이 있는 미인증 유기농 농산물 종자입니다.",
    ),
    CustomsItemEntry(
        "ITEM_ANTIQUE_VASE",
        "Antique Porcelain Vase",
        "골동품 도자기 화병",
        "antique",
        6,
        "문화재 밀반출 가능성이 우려되는 감정서 없는 도자기입니다.",
    ),
    CustomsItemEntry(
        "ITEM_RAW_MEAT",
        "Raw Beef Strips",
        "생소고기 육포",
        "meat",
        5,
        "구역 전염병 예방에 위배되는 미검역 생고기 식품입니다.",
    ),
    CustomsItemEntry(
        "ITEM_COSMETICS",
        "Premium Cosmetics Set",
        "프리미엄 화장품 세트",
        "cosmetics",
        5,
        "선물용으로 의심되는 포장된 화장품 세트입니다.",
    ),
    CustomsItemEntry(
        "ITEM_PRESCRIPTION_DRUG",
        "Prescription Painkillers",
        "처방 진통제",
        "medicine",
        4,
        "처방전이 없는 대량의 오남용 위험管制 의약품입니다.",
    ),
    CustomsItemEntry(
        "ITEM_HERBAL_TEA",
        "Herbal Tea Packets",
        "한방 차 티백",
        "food",
        4,
        "수입 금지 한약재 성분이 포함될 가능성이 있는 차 티백입니다.",
    ),
    CustomsItemEntry(
        "ITEM_MISUTGARU",
        "Korean Grain Powder",
        "미숫가루 가루",
        "food",
        3,
        "성분이 명시되지 않은 미확인 가루 식품입니다.",
    ),
    CustomsItemEntry(
        "ITEM_DRIED_SQUID",
        "Dried Squid Packs",
        "조미 건오징어",
        "food",
        3,
        "건조되었으나 검역 처리가 되지 않은 수산물 식품입니다.",
    ),
    CustomsItemEntry(
        "ITEM_CHEONGSIMHWAN",
        "Traditional Cheongsimhwan Pills",
        "전통 청심환",
        "medicine",
        2,
        "성분 확인이 요구되는 불투명한 전통 한방 구슬 알약입니다.",
    ),
    CustomsItemEntry(
        "ITEM_KIMCHI",
        "Homemade Cabbage Kimchi",
        "수제 배추김치",
        "food",
        2,
        "냄새와 밀봉 상태가 불안정한 자택 제조 발효 김치입니다.",
    ),
    CustomsItemEntry(
        "ITEM_RED_GINSENG",
        "Korean Red Ginseng Extract",
        "홍삼 에센스",
        "medicine",
        1,
        "개인 건강 증진용 건강 보조 식품입니다.",
    ),
    CustomsItemEntry(
        "ITEM_RAMEN",
        "Instant Ramen Packs",
        "컵라면",
        "food",
        1,
        "육류 수입 금지 성분이 일부 포함될 수 있는 레토르트 라면입니다.",
    ),
]
