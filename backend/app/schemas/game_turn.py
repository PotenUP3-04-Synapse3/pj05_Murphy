"""Pydantic contracts shared by Developer C runtime components.

Beginner guide:
Most backend functions pass typed objects instead of loose dictionaries.  This
file defines those objects: Unreal request/response shapes, STT events,
Understanding output, Developer A/B adapter payloads, flow metadata, and result
screen payloads.  Think of it as the project's schema dictionary.  Business
logic should live in services and agents, while this file describes the data
they are allowed to exchange.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, model_validator

SttRuntimeUsed = Literal[
    "local",
    "api",
    "unreal_bridge",
    "stt_provider_websocket",
    "elevenlabs_relay",
    "local_batch_fallback",
    "mock",
]


class SessionContext(BaseModel):
    session_id: str
    player_id: str | None = None
    room_id: str | None = None
    chapter_id: str
    scene_id: str
    current_node_id: str
    turn_index: int

    @model_validator(mode="after")
    def validate_non_empty(self) -> SessionContext:
        if not self.session_id or not self.session_id.strip():
            raise ValueError("session_id cannot be empty or whitespace")
        return self


class NpcContext(BaseModel):
    npc_id: str
    npc_role: str
    last_npc_message: str

    @model_validator(mode="after")
    def validate_non_empty(self) -> NpcContext:
        if not self.npc_id or not self.npc_id.strip():
            raise ValueError("npc_id cannot be empty or whitespace")
        return self


class AudioMetadata(BaseModel):
    mime_type: str
    sample_rate_hz: int
    channels: int
    duration_ms: int
    language_hint: str | None = None


class InteractionContext(BaseModel):
    contract_version: Literal["dev_c_interaction_context.v1"] = "dev_c_interaction_context.v1"
    initiator: Literal["npc", "player"] = "npc"
    interaction_type: Literal["quest", "ambient", "tutorial", "system"] = "quest"
    quest_id: str | None = None
    interaction_id: str | None = None
    time_limit_s: int | None = Field(default=None, ge=1)
    first_contact: bool = False
    npc_can_initiate: bool | None = None
    player_can_initiate: bool | None = None


class PlayerProfile(BaseModel):
    nickname: str | None = None
    english_confidence: Literal["beginner", "intermediate", "advanced"] | None = None
    tier: Literal["Bronze", "Silver", "Gold"]
    travel_speaking_level: Literal[
        "TSL_1_SURVIVAL",
        "TSL_2_FUNCTIONAL",
        "TSL_3_INDEPENDENT",
        "TSL_4_STRATEGIC",
    ]


class ScenarioState(BaseModel):
    patience: int
    suspicion: int
    retry_count: int
    hint_count: int
    previous_fail_count: int
    completed_intents: list[str] = Field(default_factory=list)


class RandomCustomsItemContext(BaseModel):
    """Alpha 수화물 억까 아이템을 턴 사이에 유지하는 작은 데이터 묶음입니다.

    초보자용 설명:
    Developer B는 플레이어 레벨에 맞는 아이템 후보를 고르고, Developer C는 그
    결과를 `game_state`에 저장해서 Unreal과 다음 턴에 다시 전달합니다. Unreal은
    실제 시각 reveal을 담당하고, C는 A/B/Understanding이 같은 아이템을 기준으로
    대화하도록 이 컨텍스트만 운반합니다.
    """

    item_id: str | None = None
    item_name: str
    item_category: str | None = None
    item_description: str | None = None
    visit_location: str | None = None
    declared: bool | None = None
    source: str | None = None
    difficulty: int | None = None
    suspicion_reason: str | None = None


class CustomsItemJudgeContext(BaseModel):
    """세관 심사 단계(BAG_005/BAG_006)에서 Understanding LLM 및 rule 모드 판정기가 
    물품별 위험/의심 구체성을 판단하기 위해 제공받는 컨텍스트입니다.
    """
    item_name: str
    item_category: str | None = None
    difficulty: int
    suspicion_reason: str | None = None
    declared: bool = False


class ArrivalFormContext(BaseModel):
    """Unreal 입국신고서 UI에서 작성한 사실 정보를 담는 C-owned 계약입니다.

    Beginner guide:
    NPC가 이전 대화 전체를 길게 기억하도록 만들면 토큰 비용과 오류가 커집니다.
    대신 입국신고서처럼 게임 안에서 명확히 작성된 사실은 `GameState`에 구조화해서
    유지합니다.  C는 이 값을 Unreal 응답에 다시 돌려주고 Developer A payload에도
    전달해서 NPC가 신고서 내용과 플레이어 발화를 비교할 수 있게 합니다.
    """

    full_name: str | None = None
    address: str | None = None
    purpose: str | None = None
    stay_duration: str | None = Field(
        default=None,
        validation_alias=AliasChoices("stay_duration", "stay_length"),
    )
    declared_items: list[str] = Field(default_factory=list)


class ChallengeContext(BaseModel):
    """Developer A가 억까 의도를 이해하도록 전달하는 메타데이터입니다.

    초보자용 설명:
    A에게 고정 질문 문장을 넘기면 A가 그대로 읽어버릴 수 있습니다. 그래서 C는
    "왜 수상하게 보는지"라는 의도와 배정된 장소/아이템 정보만 전달합니다. A는 이
    메타데이터를 보고 NPC 대사를 직접 생성합니다.
    """

    challenge_type: Literal["visit_location", "customs_item"]
    assigned_visit_location: str | None = None
    assigned_visit_location_ko: str | None = None
    visit_location_difficulty: int | None = None
    visit_location_suspicion_reason: str | None = None
    item_id: str | None = None
    item_name: str | None = None
    item_category: str | None = None
    item_difficulty: int | None = None
    item_suspicion_reason: str | None = None


class GameState(BaseModel):
    inventory: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    completed_intents: list[str] = Field(default_factory=list)
    current_objective: str
    random_customs_item: RandomCustomsItemContext | None = None
    arrival_form: ArrivalFormContext | None = None

    # FLIGHT_999_COMPLETE에서 C가 배정하고 Unreal 입국신고서 UI가 표시할 장소 정보입니다.
    assigned_visit_location: str | None = None
    assigned_visit_location_ko: str | None = None
    visit_location_difficulty: int | None = None
    visit_location_suspicion_reason: str | None = None

    # 2P multiplayer identity fields
    speaker_player_id: str | None = None
    bag_owner_player_id: str | None = None
    addressed_player_id: str | None = None


class PreviousNodeResult(BaseModel):
    node_id: str
    verdict: str
    next_action: str
    feedback_tags: list[str] = Field(default_factory=list)


class ClientContext(BaseModel):
    platform: str | None = None
    input_device: str | None = None
    locale: str | None = None
    build_version: str | None = None


class UnrealTurnRequest(BaseModel):
    contract_version: Literal["dev_c_unreal_turn.v1"]
    request_id: str
    session: SessionContext
    npc: NpcContext
    audio: AudioMetadata
    interaction: InteractionContext = Field(default_factory=InteractionContext)
    player_profile: PlayerProfile
    scenario_state: ScenarioState
    game_state: GameState
    previous_node_results: list[PreviousNodeResult] = Field(default_factory=list)
    client_allowed_next_nodes: list[str] = Field(default_factory=list)
    client_context: ClientContext | None = None
    skip_requested: bool = False

    # 2P multiplayer identity fields
    speaker_player_id: str | None = None
    bag_owner_player_id: str | None = None
    addressed_player_id: str | None = None


class MockAudioInput(BaseModel):
    mock_wav_path: str | None = None
    transcript: str | None = None
    transcript_provider: SttRuntimeUsed | None = None
    file_name: str | None = None
    content_type: str | None = None
    audio_bytes: bytes | None = None


class PrePrototypeRequest(BaseModel):
    turn: UnrealTurnRequest
    audio: MockAudioInput


class InputSource(BaseModel):
    input_type: Literal["voice"]
    stt_confidence: float | None
    language_detected: str | None
    needs_repeat: bool


class NormalizedInput(BaseModel):
    player_text: str
    input_source: InputSource
    stt_model: str
    stt_primary_runtime: Literal["local"]
    stt_fallback_runtime: Literal["api"]
    stt_runtime_used: SttRuntimeUsed


class HintPolicy(BaseModel):
    keyword: list[str] = Field(default_factory=list)
    sentence_pattern: str
    situation_hint: str
    action_hint: str


class TransitionContext(BaseModel):
    """Unreal scene/scoreboard transition metadata shared across chapter endings.

    초보자용 설명:
    기존 C 전환 노드는 `chapter_complete`를 사용했고, B가 추가한 bad ending 노드는
    같은 의미로 `complete_chapter`를 사용합니다. 두 값 모두 "현재 챕터를 닫고 다음
    표시 단계로 넘어간다"는 뜻이므로 Alpha 통합에서는 둘 다 허용합니다.
    """

    status: Literal["chapter_complete", "complete_chapter"]
    completed_chapter_id: str
    next_chapter_id: str
    entry_node_id: str | None = None
    unreal_event: str
    requires_player_input: bool = False


class NodeContext(BaseModel):
    node_id: str
    scenario_id: str = "ALPHA_AIRPORT_ARRIVAL"
    chapter_id: str
    node_type: Literal["dialogue", "transition", "result", "ending"] = "dialogue"
    transition: TransitionContext | None = None
    npc_question: str
    npc_question_goal: str
    objective_kr: str | None = None
    required_intents: list[str]
    required_slots: list[str]
    optional_slots: list[str] = Field(default_factory=list)
    critical_slots: list[str] = Field(default_factory=list)
    allowed_slot_values: dict[str, list[str]] = Field(default_factory=dict)
    risk_keywords: list[str] = Field(default_factory=list)
    recommended_expression: str
    base_hint_kr: str
    hint_policy: HintPolicy
    success_next_node: str
    retry_next_node: str
    clarify_next_node: str
    hint_next_node: str
    warning_next_node: str
    allowed_next_nodes: list[str]
    customs_item_context: CustomsItemJudgeContext | None = None


class SlotEvidence(BaseModel):
    slot: str
    value: str
    confidence: float = Field(ge=0, le=1)
    evidence_text: str


class IncivilityClassification(BaseModel):
    """플레이어 발화의 무례함 정도를 표현하는 C-owned 안전 신호입니다.

    초보자용 설명:
    이 객체는 "게임을 실패시킬지"를 결정하지 않습니다. C는 사용자 발화에서
    욕설, 모욕, 위협 같은 표현이 있는지 tier 0-3으로 표시만 합니다. 실제
    bad ending 분기나 패널티는 Developer B가 이 신호를 참고해서 결정합니다.
    Developer A는 같은 신호를 받아 NPC가 얼마나 단호하게 반응할지 정합니다.
    """

    tier: int = Field(default=0, ge=0, le=3)
    detected_terms: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    category: Literal["none", "rudeness", "insult", "profanity", "slur", "threat"] = "none"
    source: Literal["none", "rule", "llm"] = "none"


class SocialContextCard(BaseModel):
    """Small conversation-pragmatics memo C can pass to B and A.

    Beginner guide:
    This card does not decide a scenario branch or write NPC dialogue. It is a
    compact note about the social shape of the player's latest utterance: did
    they answer, only greet, avoid a pending request, or need repair? Developer
    B may use it as soft progression evidence, and Developer A may use it as
    dialogue context.
    """

    scene_norm: Literal["general", "peer_smalltalk", "institutional_check", "service_recovery"] = "general"
    conversation_move: Literal[
        "unknown",
        "meaningful_answer",
        "greeting_only",
        "repeated_greeting",
        "low_content_non_answer",
        "filler",
        "off_topic",
        "clarification_request",
        "refusal",
    ] = "unknown"
    prior_turn_relation: Literal["unknown", "answered", "ignored", "asked_to_clarify", "non_answer"] = "unknown"
    social_pattern: Literal[
        "none",
        "greeting",
        "filler",
        "clarification_request",
        "low_content_non_answer",
        "off_topic",
    ] = "none"
    pending_social_obligation: str | None = None
    obligation_status: Literal["none", "open", "addressed", "ignored", "unclear"] = "none"
    social_obligation_lifecycle: Literal[
        "none",
        "open",
        "repaired_once",
        "dropped",
        "engagement_checked",
        "paused_or_closed",
    ] = "none"
    closed_hooks: list[str] = Field(default_factory=list)
    do_not_reopen: list[str] = Field(default_factory=list)
    engagement_quality: Literal["useful", "thin", "stalled", "unclear"] = "unclear"
    recommended_npc_move: Literal[
        "continue",
        "acknowledge_then_progress",
        "acknowledge_and_retry_request",
        "playful_boundary",
        "firm_redirect",
        "service_repair",
        "clarify",
    ] = "continue"
    pragmatics_confidence: float = Field(default=0.0, ge=0, le=1)
    reason: str = ""


class ConversationActCard(BaseModel):
    """General conversation-act memo for natural NPC turn-taking.

    Beginner guide:
    This card is softer than branch policy.  It tells Developer A what kind of
    social move the player just made: shared a concrete detail, asked the NPC
    the same question back, answered a delayed favor, or gave a thin non-answer.
    It helps the NPC satisfy human conversation duties without adding a new
    one-off rule for every phrase like "hello", "what", or "fine".
    """

    player_act: Literal[
        "unknown",
        "direct_answer",
        "self_disclosure",
        "reciprocal_question",
        "belated_obligation_answer",
        "social_non_answer",
        "clarification_request",
        "off_topic",
        "refusal",
        "threat",
    ] = "unknown"
    relation_to_previous: Literal[
        "unknown",
        "answers_current_prompt",
        "asks_npc_same_question",
        "extends_current_topic",
        "addresses_closed_obligation",
        "ignores_current_prompt",
        "changes_topic",
    ] = "unknown"
    npc_social_duty: Literal[
        "none",
        "respond_to_disclosure_then_follow_up",
        "answer_briefly_then_continue",
        "accept_belated_answer_then_continue",
        "repair_current_obligation",
        "close_or_pause",
        "formal_boundary",
    ] = "none"
    natural_next_move: Literal[
        "continue",
        "specific_acknowledgement",
        "self_disclose_then_follow_up",
        "accept_then_pivot",
        "clarify",
        "repair",
        "close",
    ] = "continue"
    topic_anchor: str = ""
    should_answer_player_question: bool = False
    should_avoid_generic_ack: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: str = ""
    reason: str = ""


class RiskEvidence(BaseModel):
    tags: list[str] = Field(default_factory=list)
    delta: int = 0


class PragmaticContextCard(BaseModel):
    """Situation-level meaning memo C can pass to B and A.

    Beginner guide:
    This card is stronger than `SocialContextCard`. Social context says how a
    turn behaves in conversation; pragmatic context says what the turn does in
    the real situation, such as refusing a required procedure or making a
    threat. Developer C may add a safety backstop so obvious high-risk meanings
    are not missed, but Developer B still owns branching and Developer A still
    owns final NPC wording.
    """

    player_move: Literal[
        "unknown",
        "meaningful_answer",
        "social_non_answer",
        "off_topic",
        "refusal",
        "violent_threat",
        "coercive_exit_request",
    ] = "unknown"
    target: Literal["none", "officer", "public_figure", "other_person", "self", "unknown"] = "none"
    threat_directness: Literal["none", "implied", "explicit_intent", "direct_threat"] = "none"
    risk_level: Literal["none", "low", "medium", "high", "critical"] = "none"
    procedural_posture: Literal[
        "continue",
        "clarify",
        "warn",
        "stop_normal_interview",
        "secondary_inspection",
        "end_interview",
    ] = "continue"
    recommended_b_move: Literal["continue", "reask", "clarify", "warning", "secondary_inspection"] = "continue"
    recommended_a_move: Literal["continue", "repair", "formal_boundary", "stern_boundary"] = "continue"
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: str = ""
    reason: str = ""



class UnderstandingOutput(BaseModel):
    intent: str
    intent_success: bool
    confidence: float
    meaning_summary_kr: str
    emotion: str
    answer_relevance: Literal["on_topic", "partially_related", "off_topic"]
    ambiguity_type: str
    risk_delta: int
    risk_reason: str
    risk_tags: list[str]
    slot_evidence: list[SlotEvidence] = Field(default_factory=list)
    extracted_slots: dict[str, str]
    missing_slots: list[str]
    needs_clarification: bool
    incivility: IncivilityClassification | None = None
    social_context: SocialContextCard = Field(default_factory=SocialContextCard)
    conversation_act: ConversationActCard = Field(default_factory=ConversationActCard)
    pragmatic_context: PragmaticContextCard = Field(default_factory=PragmaticContextCard)
    intent_satisfied: bool | None = None
    judgment_reason: str = ""
    satisfied: bool | None = None
    branch_hint: Literal["success", "retry", "clarify", "hint", "warning", "bad_end"] | None = None
    risk_evidence: RiskEvidence | None = None

    @model_validator(mode="after")
    def default_intent_satisfied(self) -> UnderstandingOutput:
        if self.intent_satisfied is None:
            self.intent_satisfied = self.intent_success
        if self.satisfied is None:
            self.satisfied = self.intent_satisfied
        if self.risk_evidence is None:
            self.risk_evidence = RiskEvidence(tags=self.risk_tags, delta=self.risk_delta)
        return self



# `Nomal` spelling follows the current external emotion enum contract.
NpcEmotion = Literal[
    "Nomal",
    "Joy",
    "Anger",
    "Sadness",
    "Panic",
    "Suspicion",
    "Disgust",
    "Fear",
    "Smirk",
    "Surprise",
    "Pain",
    "Confusion",
    "Boredom",
]


class DevBPolicyInput(BaseModel):
    contract_version: Literal["dev_b_policy.v1"]
    request_id: str
    session_id: str
    player_id: str | None = None
    room_id: str | None = None
    chapter_id: str
    scene_id: str
    current_node_id: str
    turn_index: int
    player_text: str
    input_source: InputSource
    interaction: InteractionContext = Field(default_factory=InteractionContext)
    player_profile: PlayerProfile
    scenario_state: ScenarioState
    node_context: NodeContext
    understanding: UnderstandingOutput
    random_customs_item: RandomCustomsItemContext | None = None
    previous_node_results: list[PreviousNodeResult] = Field(default_factory=list)
    client_allowed_next_nodes: list[str] = Field(default_factory=list)
    skip_requested: bool = False

    # 2P multiplayer identity fields
    speaker_player_id: str | None = None
    bag_owner_player_id: str | None = None
    addressed_player_id: str | None = None


class Scores(BaseModel):
    task_success: int
    clarity: int
    grammar: int
    vocabulary: int
    problem_solving: int
    politeness: int


class ReportSeedCategoryScores(BaseModel):
    task_success: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    grammar: int = Field(ge=0, le=100)
    vocabulary: int = Field(ge=0, le=100)
    politeness: int = Field(ge=0, le=100)
    problem_solving: int = Field(ge=0, le=100)


class ReportSeedStrength(BaseModel):
    title: str
    evidence: str
    ui_priority: int = Field(ge=1)


class ReportSeedCriticalBreakdown(BaseModel):
    user_utterance: str
    issue_type: Literal["grammar", "clarity", "vocabulary", "task", "politeness", "problem_solving"]
    why_it_matters: str
    better_version: str
    reusable_pattern: str
    ui_priority: int = Field(ge=1)


class ReportSeedCorrectedExample(BaseModel):
    original: str
    corrected: str
    brief_explanation: str
    pattern: str


class ReportSeedSummary(BaseModel):
    estimated_level: Literal["beginner", "intermediate", "advanced"]
    tier: Literal["Bronze", "Silver", "Gold"]
    scenario_result: Literal["passed", "conditional_pass", "failed"]
    overall_score_candidate: int = Field(ge=0, le=100)
    category_scores: ReportSeedCategoryScores
    strengths: list[ReportSeedStrength] = Field(default_factory=list)
    critical_breakdowns: list[ReportSeedCriticalBreakdown] = Field(default_factory=list)
    corrected_examples: list[ReportSeedCorrectedExample] = Field(default_factory=list)
    reusable_sentence_patterns: list[str] = Field(default_factory=list)
    next_practice_goal: str
    feedback_focus: list[str] = Field(default_factory=list)
    ui_priority_order: list[str] = Field(default_factory=list)
    display_policy_by_tier: dict[str, str] = Field(default_factory=dict)


class TurnHistoryEntry(BaseModel):
    """[DEPRECATED] A가 직전 대화 흐름을 복구할 수 있도록 넘기는 짧은 턴 기록입니다.

    이전 대화 기록(dialogue_history)을 전달하던 레거시 방식은 폐지 예정입니다.
    현재는 NPC 자체 단기 메모리가 사용되므로, 하위 호환성을 위해서만 유지됩니다.
    """

    node_id: str
    player_text_preview: str
    npc_text_preview: str
    filled_slots: dict[str, str] = Field(default_factory=dict)


class DialogueSeed(BaseModel):
    scene: str
    npc_role: str
    surface_goal: str
    hidden_assessment_goal: str
    opening_intent: str
    assessment_targets: list[str] = Field(default_factory=list)
    required_slots: list[str] = Field(default_factory=list)
    max_turns: int = Field(ge=1, le=12)
    difficulty_profile: str
    feedback_focus: list[str] = Field(default_factory=list)
    tone_guidance: str
    allowed_followup_intents: list[str] = Field(default_factory=list)
    stop_condition: str
    cumulative_confidence: float | None = None
    completion_closure_reason: str | None = None
    completion_closure_style: str | None = None
    completion_do_not_ask_new_question: bool = False

    # A가 고정 질문 대신 억까 의도만 보고 대사를 생성하도록 넘기는 컨텍스트입니다.
    challenge_context: ChallengeContext | None = None

    # B가 A에게 전달하는 의도 신호 (예: 장소 억까, 수화물 억까 등)
    suspicion_scope: Literal["location", "declaration", "none"] | None = "none"
    # [DEPRECATED] A가 같은 질문을 반복하지 않도록 C가 모든 노드에서 붙여 주는 최근 대화 요약입니다.
    # NPC가 자체 단기 메모리를 보유함에 따라 비활성화(Legacy) 중이며, 하위 호환성을 위해 유지됩니다.
    dialogue_history: list[TurnHistoryEntry] = Field(default_factory=list)

    # 기존 A/B 어댑터 호환을 위해 유지하는 펼친 형태의 억까 메타데이터입니다.
    assigned_visit_location: str | None = None
    assigned_visit_location_ko: str | None = None
    visit_location_difficulty: int | None = None
    visit_location_suspicion_reason: str | None = None
    item_id: str | None = None
    item_name: str | None = None
    item_category: str | None = None
    item_difficulty: int | None = None
    item_suspicion_reason: str | None = None


class RubricScores(BaseModel):
    comprehension: int = Field(ge=0, le=2)
    fluency: int = Field(ge=0, le=2)
    grammar_accuracy: int = Field(ge=0, le=2)
    vocabulary_range: int = Field(ge=0, le=2)
    clarity: int = Field(ge=0, le=2)
    interaction_problem_solving: int = Field(ge=0, le=2)
    total: int = Field(ge=0, le=12)


class FinalScoreState(BaseModel):
    patience: int = 100
    suspicion: int = 0
    retry_count: int = 0
    hint_count: int = 0


class QuantitativeScores(BaseModel):
    overall: int = Field(ge=0, le=100)
    comprehension: int = Field(ge=0, le=100)
    fluency: int = Field(ge=0, le=100)
    grammar_accuracy: int = Field(ge=0, le=100)
    vocabulary_range: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    interaction_problem_solving: int = Field(ge=0, le=100)
    scoring_policy: Literal["simple_average", "scene_normalized_dimension_average"]


class FinalReportSummary(BaseModel):
    overall: str
    best_node: str | None = None
    weakest_node: str | None = None
    main_improvement: str
    focus_on_form_targets: list[str] = Field(default_factory=list)
    included_node_count: int = Field(ge=0)


class FinalResult(BaseModel):
    final_recommendation: Literal[
        "PASS",
        "CONDITIONAL_PASS",
        "SECONDARY_ROOM",
        "COMIC_FAIL",
        "UNRANKED",
    ]
    rank: Literal[
        "Gold Pass",
        "Silver Pass",
        "Bronze Pass",
        "Secondary Review",
        "Comic Fail",
        "Unranked",
    ]
    # Unreal 결과 화면 로직용 4단계 티어. rank는 UI 표시 문구(" Pass" 포함, 6종)인 반면
    # tier는 게임 로직/분기용으로 합격 3단계(Gold/Silver/Bronze)와 비합격(Iron)만 구분합니다.
    tier: Literal["Gold", "Silver", "Bronze", "Iron"]
    final_score_100: int = Field(ge=0, le=100)
    reason_tags: list[str] = Field(default_factory=list)
    quantitative_scores: QuantitativeScores
    report_summary: FinalReportSummary


class DifficultyProfile(BaseModel):
    travel_speaking_level: str
    npc_speech_speed: Literal["slow", "normal", "natural"]
    question_complexity: Literal["basic", "standard", "expanded", "complex"]
    hint_frequency: Literal["high", "medium", "low"]
    pressure_level: Literal["low", "medium", "high"]


class FeedbackGenerationTrace(BaseModel):
    mode: Literal["rule", "llm", "fallback"]
    model: str | None = None
    used_llm: bool
    fallback_reason: str | None = None


class Evaluation(BaseModel):
    verdict: Literal["SUCCESS", "PARTIAL", "UNCLEAR", "FAIL", "CRITICAL_FAIL"]
    detected_intents: list[str]
    required_intents_passed: bool
    filled_slots: dict[str, str]
    missing_slots: list[str]
    scores: Scores
    feedback_tags: list[str]
    feedback_note: str | None = None


class LevelHint(BaseModel):
    english_level: Literal["beginner", "intermediate", "advanced"]
    travel_speaking_level: str
    cefr_estimate: str | None = None
    needs_hint: bool
    hint_level: Literal["none", "low", "medium", "high"]
    hint_type: str | None
    hint_kr: str | None
    example_en: str
    avoid_expression: str | None = None
    recommended_expression: str
    cumulative_confidence: float | None = None


class InGameFeedback(BaseModel):
    show: bool
    feedback_strategy: Literal[
        "recast",
        "clarification_request",
        "elicitation",
        "scaffolding_hint",
        "warning",
        "none",
    ]
    timing: Literal["during_dialogue_turn", "after_player_answer", "before_retry"]
    priority: Literal["low", "medium", "high"]
    purpose: str
    focus: str
    npc_recast_line_candidate: str | None
    clarification_prompt_candidate: str | None
    elicitation_cue_candidate: str | None
    scaffolding_hint: str | None
    recommended_expression: str | None = None
    display_duration_ms: int | None = None
    blocks_progression: bool


class ErrorItem(BaseModel):
    error_id: str
    node_id: str
    turn_index: int
    npc_question: str
    original_utterance: str
    intended_meaning_kr: str | None = None
    error_type: str
    error_scope: str
    focus_on_form_target: str
    suggested_expression: str
    severity: str
    affected_scores: list[str] = Field(default_factory=list)
    should_surface_in_game: bool
    should_surface_out_game: bool


class ErrorCapture(BaseModel):
    should_record: bool
    storage_format: Literal["markdown"]
    error_items: list[ErrorItem] = Field(default_factory=list)
    markdown_entry: str | None


class OutGameFeedbackSeed(BaseModel):
    include_in_final_report: bool
    openkb_query_tags: list[str]
    focus_on_form_targets: list[str]
    report_priority: Literal["low", "medium", "high"]


class OpenKBWriteResult(BaseModel):
    attempted: bool
    succeeded: bool
    namespace: str
    record_id: str | None = None
    jsonl_path: str | None = None
    markdown_path: str | None = None
    error_message: str | None = None


class Branch(BaseModel):
    branch_type: Literal["success", "retry", "clarify", "hint", "warning", "bad_end", "final"]
    next_action: Literal["ADVANCE", "REASK", "GIVE_HINT", "WARNING", "FAIL_END", "FINAL_DECISION", "COMPLETE_CHAPTER"]
    next_node_id: str
    branch_reason: str
    allowed_next_node_checked: bool


class StateDelta(BaseModel):
    patience_delta: int
    suspicion_delta: int
    retry_count_delta: int
    hint_count_delta: int


class DialogueDirective(BaseModel):
    purpose: str
    tone_hint: str
    target_slot: str | None = None
    do_not_generate_npc_text: bool | None = None
    topic_switch: bool | None = None
    length_target: int | None = None


class ReportItem(BaseModel):
    summary: str
    improvement: str
    example_answer: str
    score_tags: list[str]


class DevBPolicyOutput(BaseModel):
    contract_version: Literal["dev_b_policy.v1"]
    node_id: str
    npc_emotion: NpcEmotion = "Nomal"
    evaluation: Evaluation
    level_hint: LevelHint
    in_game_feedback: InGameFeedback
    error_capture: ErrorCapture
    out_game_feedback_seed: OutGameFeedbackSeed
    report_seed_summary: ReportSeedSummary | None = None
    dialogue_seed: DialogueSeed | None = None
    branch: Branch
    state_delta: StateDelta
    report_item: ReportItem
    dialogue_directive: DialogueDirective | None = None
    openkb_write: OpenKBWriteResult | None = None
    rubric_scores: RubricScores | None = None
    difficulty_profile: DifficultyProfile | None = None
    feedback_generation: FeedbackGenerationTrace | None = None
    final_result: FinalResult | None = None


class DevADialogueInput(BaseModel):
    contract_version: Literal["dev_a_dialogue.v1"]
    request_id: str
    session_id: str
    player_id: str | None = None
    room_id: str | None = None
    current_node_id: str
    player_text: str
    npc: NpcContext
    node_context: NodeContext
    understanding: UnderstandingOutput
    developer_b_policy: DevBPolicyOutput
    transition: TransitionContext | None = None
    random_customs_item: RandomCustomsItemContext | None = None
    game_state: GameState | None = None

    # 2P multiplayer identity fields
    speaker_player_id: str | None = None
    bag_owner_player_id: str | None = None
    addressed_player_id: str | None = None
    scope: str = "player"

    resolved_node_objective: str | None = None
    resolved_node_npc_question: str | None = None



class DevADialogueOutput(BaseModel):
    contract_version: Literal["dev_a_dialogue.v1"]
    speaker: str
    text: str
    tone: str
    animation: str
    feedback_kr: str | None = None
    audio_url: str | None = None
    diagnostics: list[dict[str, str]] = Field(default_factory=list)


class RecordedErrorSummary(BaseModel):
    recorded: bool
    storage_format: Literal["markdown"]
    error_log_markdown_path: str | None = None
    recorded_error_count: int


class NpcResponse(BaseModel):
    speaker: str
    text: str
    emotion: NpcEmotion
    tone: str
    animation: str
    audio_url: str | None = None


class UiFeedback(BaseModel):
    show: bool
    feedback_strategy: str
    priority: str


class UiResponse(BaseModel):
    show_hint: bool
    hint_kr: str | None
    recommended_expression: str | None
    in_game_feedback: UiFeedback


class EvaluationResponse(BaseModel):
    verdict: str
    scores: Scores
    feedback_tags: list[str]


class ReportResponse(BaseModel):
    recorded_error_count: int
    report_item: ReportItem
    final_result: FinalResult | None = None


class FlowResponse(BaseModel):
    contract_version: Literal["dev_c_unreal_flow.v1"] = "dev_c_unreal_flow.v1"
    transition_type: Literal["none", "scene_transition", "cutscene", "scoreboard"] = "none"
    transition_id: str | None = None
    from_scene_id: str | None = None
    to_scene_id: str | None = None
    cinematic_id: str | None = None
    skip_allowed: bool = False
    show_scoreboard: bool = False


class RealtimeTranscriptClientEvent(BaseModel):
    contract_version: Literal["dev_c_realtime_stt.v1"]
    event_type: Literal[
        "session_start",
        "audio_chunk",
        "partial_transcript",
        "final_transcript",
        "cancel",
    ]
    request_id: str
    session_id: str
    turn_index: int = Field(ge=0)
    sequence: int = Field(ge=0)
    chapter_id: str | None = None
    scene_id: str | None = None
    current_node_id: str | None = None
    provider: Literal["unreal_bridge", "stt_provider_websocket", "elevenlabs_relay", "mock"] = "unreal_bridge"
    language_hint: str | None = None
    transcript: str | None = None
    audio_base64: str | None = None
    commit: bool = False
    sample_rate_hz: int | None = Field(default=None, ge=8000)
    previous_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    language_detected: str | None = None

    @model_validator(mode="after")
    def require_transcript_for_transcript_events(self) -> "RealtimeTranscriptClientEvent":
        if self.event_type in {"partial_transcript", "final_transcript"}:
            if self.transcript is None or not self.transcript.strip():
                raise ValueError("transcript is required for transcript events")

        if self.event_type == "audio_chunk":
            if self.audio_base64 is None or not self.audio_base64.strip():
                raise ValueError("audio_base64 is required for audio_chunk events")

        return self


class RealtimeSubtitlePayload(BaseModel):
    text: str
    is_final: bool
    display_mode: Literal["replace"] = "replace"


class RealtimeTranscriptServerEvent(BaseModel):
    contract_version: Literal["dev_c_realtime_stt.v1"] = "dev_c_realtime_stt.v1"
    event_type: Literal[
        "session_started",
        "partial_transcript",
        "final_transcript",
        "session_cancelled",
        "contract_error",
        "provider_error",
    ]
    request_id: str | None = None
    session_id: str | None = None
    turn_index: int | None = None
    sequence: int | None = None
    provider: Literal[
        "unreal_bridge",
        "stt_provider_websocket",
        "elevenlabs_relay",
        "local_batch_fallback",
        "mock",
    ] | None = None
    subtitle: RealtimeSubtitlePayload | None = None
    committed: bool = False
    target_endpoint: str | None = None
    error_message: str | None = None


class TurnTimingMs(BaseModel):
    total_ms: int = Field(default=0, ge=0)
    stt_ms: int = Field(default=0, ge=0)
    openkb_ms: int = Field(default=0, ge=0)
    understanding_ms: int = Field(default=0, ge=0)
    developer_b_ms: int = Field(default=0, ge=0)
    logging_ms: int = Field(default=0, ge=0)
    developer_a_ms: int = Field(default=0, ge=0)
    response_build_ms: int = Field(default=0, ge=0)
    validation_ms: int = Field(default=0, ge=0)


class DebugInfo(BaseModel):
    stt_model: str
    stt_confidence: float | None
    understanding_confidence: float
    contract_versions: list[str]
    timing_ms: TurnTimingMs = Field(default_factory=TurnTimingMs)
    diagnostics: list[dict[str, str]] = Field(default_factory=list)


class SttResponse(BaseModel):
    model: str
    primary_runtime: Literal["local"]
    fallback_runtime: Literal["api"]
    runtime_used: SttRuntimeUsed
    player_text: str
    confidence: float | None
    language_detected: str | None
    needs_repeat: bool


class UnrealResponse(BaseModel):
    contract_version: Literal["dev_c_unreal_response.v1"]
    request_id: str
    session_id: str
    turn_index: int
    current_node_id: str
    next_node_id: str
    next_action: str
    transition: TransitionContext | None = None
    interaction: InteractionContext
    stt: SttResponse
    npc: NpcResponse
    ui: UiResponse
    flow: FlowResponse = Field(default_factory=FlowResponse)
    game_state: GameState | None = None
    state_delta: StateDelta
    evaluation: EvaluationResponse
    report: ReportResponse
    debug: DebugInfo


class UnrealResultResponse(BaseModel):
    contract_version: Literal["dev_c_unreal_result.v1"]
    session_id: str
    final_result: FinalResult
    out_game_feedback: dict[str, Any] | None = None


class PlayerRubricReport(BaseModel):
    player_id: str
    final_result: FinalResult
    out_game_feedback: dict[str, Any] | None = None


class UnrealRoomResultResponse(BaseModel):
    contract_version: Literal["dev_c_unreal_room_result.v1"] = "dev_c_unreal_room_result.v1"
    room_id: str
    team_outcome: str
    players: list[PlayerRubricReport]


class SetupPlayerProfile(BaseModel):
    player_id: str
    nickname: str | None = None
    english_confidence: Literal["beginner", "intermediate", "advanced"] | None = None
    tier: Literal["Bronze", "Silver", "Gold"]
    travel_speaking_level: Literal[
        "TSL_1_SURVIVAL",
        "TSL_2_FUNCTIONAL",
        "TSL_3_INDEPENDENT",
        "TSL_4_STRATEGIC",
    ] | None = None
    total_score: int | None = None


class BaggageSetupRequest(BaseModel):
    room_id: str
    player1_profile: SetupPlayerProfile
    player2_profile: SetupPlayerProfile


class BaggageSetupResponse(BaseModel):
    contract_version: Literal["dev_c_baggage_setup.v1"] = "dev_c_baggage_setup.v1"
    room_id: str
    bag_owner_player_id: str
    random_customs_item: RandomCustomsItemContext


class PolicyTurnFeedbackRecord(BaseModel):
    namespace: str = "dev_b"
    record_schema_version: Literal["dev_b_openkb_record.v2"] = "dev_b_openkb_record.v2"
    record_kind: Literal["policy_turn_feedback"] = "policy_turn_feedback"
    record_id: str = ""
    contract_version: str = ""
    request_id: str = ""
    session_id: str = ""
    player_id: str | None = None
    room_id: str | None = None
    chapter_id: str = ""
    scene_id: str = ""
    node_id: str = ""
    turn_index: int = 0
    player_text: str = ""
    input_source: dict[str, Any] = Field(default_factory=dict)
    understanding_summary_kr: str | None = None
    understanding: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any] = Field(default_factory=dict)
    level_hint: dict[str, Any] = Field(default_factory=dict)
    error_capture: dict[str, Any] = Field(default_factory=dict)
    out_game_feedback_seed: dict[str, Any] = Field(default_factory=dict)
    report_seed_summary: dict[str, Any] | None = None
    dialogue_seed: dict[str, Any] | None = None
    focus_on_form_targets: list[str] = Field(default_factory=list)
    report_item: dict[str, Any] = Field(default_factory=dict)
    rubric_scores: dict[str, Any] | None = None
    difficulty_profile: dict[str, Any] | None = None
    feedback_generation: dict[str, Any] | None = None
    branch: dict[str, Any] = Field(default_factory=dict)
    state_delta: dict[str, Any] = Field(default_factory=dict)

    # 2P multiplayer identity fields
    speaker_player_id: str | None = None
    bag_owner_player_id: str | None = None
    addressed_player_id: str | None = None


def is_shared_baggage(session: SessionContext) -> bool:
    """Helper to check if the session is in the shared baggage claim chapter/nodes."""
    return (
        session.current_node_id.startswith("BAG_")
        or session.chapter_id == "CH0_04_BAGGAGE_CLAIM"
    )
