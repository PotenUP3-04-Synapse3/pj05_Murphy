from dataclasses import dataclass


# 게임 내에 존재하는 NPC들의 정적 프로필(Profile) 명세를 정의하는 데이터 클래스(Data Class)입니다.
@dataclass(frozen=True)
class NPCProfile:
    npc_id: str             # 고유한 NPC 식별 코드 (예: officer_hale)
    display_name: str       # 화면에 표시될 공식 이름 (예: Officer Hale)
    role: str               # 담당 역할군 (예: immigration_officer)
    default_animation: str  # 대기 상태에서 취할 기본 애니메이션 키값
    fallback_text: str      # 통신 두절 등 에러 시 노출할 안전 대사
    mock_voice_id: str      # 로컬 개발 및 유닛 테스트 시 매핑할 가짜 목소리 아이디
    persona_instruction: str # LLM 프롬프트에 결합할 이 NPC의 성격 및 말투 지침입니다.
    elevenlabs_voice_id: str | None = None  # ElevenLabs 전용 목소리 식별 코드


# 기본값으로 지정할 NPC 식별 아이디입니다.
_DEFAULT_NPC_ID = "hale"

# 게임 내 캐릭터 정보들을 등록하여 보관하는 데이터베이스 역할의 딕셔너리(Dictionary) 인스턴스입니다.
_NPC_ROSTER: dict[str, NPCProfile] = {
    "arabella": NPCProfile(
        npc_id="arabella",
        display_name="Arabella",
        role="seatmate",
        default_animation="move",
        fallback_text="Hi there! Traveling is always exciting, isn't it?",
        mock_voice_id="arabella_mock",
        persona_instruction="very friendly, warm, patient, socially easygoing, and welcoming passenger.",
        elevenlabs_voice_id="Z3R5wn05IrDiVCyEkUrK",
    ),
    "novak": NPCProfile(
        npc_id="novak",
        display_name="Novak",
        role="seatmate",
        default_animation="move",
        fallback_text="Hello. Pleased to meet you.",
        mock_voice_id="novak_mock",
        persona_instruction="polite, slightly quiet, but friendly and helpful passenger.",
        elevenlabs_voice_id="3TStB8f3X3To0Uj5R7RK",
    ),
    "hale": NPCProfile(
        npc_id="hale",
        display_name="Officer Hale",
        role="immigration_officer",
        default_animation="move",
        fallback_text="State the purpose of your visit clearly.",
        mock_voice_id="hale_mock",
        persona_instruction="stern, direct, and authoritative immigration officer.",
        elevenlabs_voice_id="dXtC3XhB9GtPusIpNtQx",
    ),
    "harris": NPCProfile(
        npc_id="harris",
        display_name="Officer Harris",
        role="immigration_officer",
        default_animation="move",
        fallback_text="Passport, please. I need to see your documentation.",
        mock_voice_id="harris_mock",
        persona_instruction="professional, meticulous, yet supportive immigration officer.",
        elevenlabs_voice_id="u0REnIJvUgcGQYW2Ux8K",
    ),
    "dan": NPCProfile(
        npc_id="dan",
        display_name="Officer Dan",
        role="security_officer",
        default_animation="move",
        fallback_text="Please stop there. What is inside this luggage?",
        mock_voice_id="dan_mock",
        persona_instruction="firm, alert, and strict security officer.",
        elevenlabs_voice_id="1cuDPO8sIMatoOE4Z2Zv",
    ),
    "brielle": NPCProfile(
        npc_id="brielle",
        display_name="Brielle",
        role="baggage_agent",
        default_animation="move",
        fallback_text="Hello, how can I assist you with your baggage claim?",
        mock_voice_id="brielle_mock",
        persona_instruction="helpful, bright, polite, and service-oriented baggage claim desk clerk.",
        elevenlabs_voice_id="6u6JbqKdaQy89ENzLSju",
    )
}


def resolve_npc_profile(npc_id: str | None) -> NPCProfile:
    """NPC의 식별자 키(Key)를 입력받아 등록된 NPCProfile 객체를 반환합니다. 키가 없거나 조회되지 않으면 기본 캐릭터를 리턴합니다."""
    normalized_id = _normalize_npc_id(npc_id)
    return _NPC_ROSTER.get(normalized_id, _NPC_ROSTER[_DEFAULT_NPC_ID])


def resolve_npc_profile_by_display_name(display_name: str | None) -> NPCProfile | None:
    """화면에 나타나는 출력 이름(Display Name)을 기준으로 NPC 프로필 정보를 검색하여 획득합니다."""
    if not display_name:
        return None
    normalized_name = display_name.strip().casefold()
    for profile in _NPC_ROSTER.values():
        if profile.display_name.casefold() == normalized_name:
            return profile
    return None


def _normalize_npc_id(npc_id: str | None) -> str:
    """입력받은 NPC ID 문자열에 존재할 수 있는 빈칸과 대소문자를 정규화합니다.
    레거시 ID 접두사(officer_, flight_seatmate_, desk_clerk_)가 있으면 제거하여 하위 호환성을 제공합니다.
    폐기된 NPC인 'miller'가 전달되는 경우, 기본 캐릭터이자 실제 입국심사관인 'hale'로 자동 전환합니다.
    """
    if not npc_id:
        return _DEFAULT_NPC_ID
    cleaned = npc_id.strip().lower()
    
    if cleaned.startswith("officer_"):
        cleaned = cleaned.replace("officer_", "")
    elif cleaned.startswith("flight_seatmate_"):
        cleaned = cleaned.replace("flight_seatmate_", "")
    elif cleaned.startswith("desk_clerk_"):
        cleaned = cleaned.replace("desk_clerk_", "")
        
    if cleaned == "miller":
        return "hale"
        
    return cleaned
