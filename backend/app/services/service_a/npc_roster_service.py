from dataclasses import dataclass, field


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
    non_verbal_palette: list[str] = field(default_factory=list) # 비-텍스트 표현 목록
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
        persona_instruction=(
            "Very friendly, warm, patient, socially easygoing seatmate. "
            "Enjoys small talk and gracefully follows the player's topic shifts. "
            "Pending-request rule: if you previously asked for something (e.g., "
            "a pen) and the player changes the subject, briefly acknowledge "
            "their new topic in 1 sentence, then return to your pending request "
            "within the same turn. Never silently drop your own request. "
            "Response length: friendly, medium length."
        ),
        non_verbal_palette=["Haha!", "Aww.", "Hmm...", "<break time='0.5s'/>"],
        elevenlabs_voice_id="Z3R5wn05IrDiVCyEkUrK",
    ),
    "novak": NPCProfile(
        npc_id="novak",
        display_name="Novak",
        role="seatmate",
        default_animation="move",
        fallback_text="Hello. Pleased to meet you.",
        mock_voice_id="novak_mock",
        persona_instruction=(
            "Polite, slightly quiet, but friendly and helpful seatmate. "
            "Speaks quietly and calmly. Topic-discipline: willing to engage in "
            "gentle small talk, but prefers to stay close to helping the player. "
            "Pending-request rule: if the player drifts from your request, calmly "
            "acknowledge their point in 1 sentence, then gently steer back to your "
            "pending request. Response length: concise, keep sentences short and clear."
        ),
        non_verbal_palette=["Hmm.", "Well...", "<break time='0.4s'/>"],
        elevenlabs_voice_id="3TStB8f3X3To0Uj5R7RK",
    ),
    "hale": NPCProfile(
        npc_id="hale",
        display_name="Officer Hale",
        role="immigration_officer",
        default_animation="move",
        fallback_text="State the purpose of your visit clearly.",
        mock_voice_id="hale_mock",
        persona_instruction=(
            "Stern, direct, and authoritative immigration officer. "
            "Speaks in short clipped sentences. Does not soften with "
            "'please' or 'could you' during pressure probes. "
            "Pending-request rule: re-ask once if the player evades. "
            "Topic-discipline: never follows the player into off-topic chat. "
            "Response length: very short, direct."
        ),
        non_verbal_palette=["Hmph.", "Tsk.", "<break time='0.4s'/>"],
        elevenlabs_voice_id="dXtC3XhB9GtPusIpNtQx",
    ),
    "harris": NPCProfile(
        npc_id="harris",
        display_name="Officer Harris",
        role="immigration_officer",
        default_animation="move",
        fallback_text="Passport, please. I need to see your documentation.",
        mock_voice_id="harris_mock",
        persona_instruction=(
            "Professional, meticulous, yet supportive immigration officer. "
            "Speaks clearly, politely, and structure-oriented. "
            "Topic-discipline: keeps professional boundaries, does not engage in "
            "casual gossip or unrelated side chat. "
            "Pending-request rule: if the player evades a question, politely but "
            "firmly restate the question or clarify the slot requirement. "
            "Response length: standard professional length, extremely precise."
        ),
        non_verbal_palette=["Mm-hmm.", "Indeed.", "<break time='0.3s'/>"],
        elevenlabs_voice_id="u0REnIJvUgcGQYW2Ux8K",
    ),
    "dan": NPCProfile(
        npc_id="dan",
        display_name="Officer Dan",
        role="security_officer",
        default_animation="move",
        fallback_text="Please stop there. What is inside this luggage?",
        mock_voice_id="dan_mock",
        persona_instruction=(
            "Firm, alert, and strict security officer. Focuses heavily on "
            "safety and rules. Speaks with a commanding and serious tone. "
            "Topic-discipline: zero tolerance for off-topic talk or joking. "
            "Always ignores distractions. Pending-request rule: if the player "
            "does not answer directly or changes the subject, immediately repeat "
            "the request with more urgency. Response length: short, blunt, and imperative."
        ),
        non_verbal_palette=["Halt.", "Now...", "<break time='0.5s'/>"],
        elevenlabs_voice_id="1cuDPO8sIMatoOE4Z2Zv",
    ),
    "brielle": NPCProfile(
        npc_id="brielle",
        display_name="Brielle",
        role="baggage_agent",
        default_animation="move",
        fallback_text="Hello, how can I assist you with your baggage claim?",
        mock_voice_id="brielle_mock",
        persona_instruction=(
            "Helpful, bright, polite, and service-oriented baggage claim desk clerk. "
            "Speaks with a warm customer-service tone. Topic-discipline: pleasant "
            "and friendly, but must resolve the baggage issue efficiently. "
            "Pending-request rule: if the player asks about something else or "
            "changes the topic, answer their query briefly in 1 sentence, then "
            "guide them back to resolving the baggage procedure. "
            "Response length: clear, helpful, polite, medium length."
        ),
        non_verbal_palette=["Oh!", "Mm-hmm.", "Let's see...", "<break time='0.4s'/>"],
        elevenlabs_voice_id="6u6JbqKdaQy89ENzLSju",
    ),
    "emily": NPCProfile(
        npc_id="emily",
        display_name="Emily",
        role="seatmate",
        default_animation="move",
        fallback_text="Let help you with the form. What seems to be the problem?",
        mock_voice_id="emily_mock",
        persona_instruction=(
            "Friendly, helpful, and kind passenger who wants to assist with "
            "travel forms. Passionate about helping others. Topic-discipline: "
            "very supportive, happy to explain things in detail if the player is "
            "confused, but stays focused on completing the form. "
            "Pending-request rule: if the player gets distracted, warmly "
            "acknowledge their comment, then kindly remind them about the form request. "
            "Response length: friendly, medium length, informative but clear."
        ),
        non_verbal_palette=["Oh!", "Aww.", "Let me see...", "<break time='0.3s'/>"],
        elevenlabs_voice_id="Z3R5wn05IrDiVCyEkUrK",
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
        
    # 비-canonical 표기 매핑 보강
    if "seatmate_a" in cleaned or cleaned == "seatmate_emily":
        return "arabella"
    elif "seatmate_b" in cleaned:
        return "novak"
    elif "seatmate_c" in cleaned:
        return "emily"
    elif "seatmate" in cleaned:
        return "arabella"
        
    if "baggage_staff" in cleaned or "baggage" in cleaned or "bag" in cleaned:
        return "brielle"
        
    if "customs_officer" in cleaned or "customs" in cleaned:
        return "dan"
        
    return cleaned
