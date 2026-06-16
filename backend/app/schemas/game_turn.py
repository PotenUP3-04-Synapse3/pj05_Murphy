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

from pydantic import BaseModel, Field, model_validator

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
    chapter_id: str
    scene_id: str
    current_node_id: str
    turn_index: int


class NpcContext(BaseModel):
    npc_id: str
    npc_role: str
    last_npc_message: str


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
    """Optional Alpha baggage item chosen by Unreal or a local CSV table.

    Beginner guide:
    Alpha baggage can reveal a random "why is this in your suitcase?" item.
    Unreal still owns the visual reveal, but C needs this small context object
    so Understanding, Developer B, and Developer A can keep the dialogue about
    the same item.  Every field is additive and optional except the display
    name, so older requests can keep omitting the object.
    """

    item_id: str | None = None
    item_name: str
    item_category: str | None = None
    item_description: str | None = None
    visit_location: str | None = None
    declared: bool | None = None
    source: str | None = None


class GameState(BaseModel):
    inventory: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    completed_intents: list[str] = Field(default_factory=list)
    current_objective: str
    random_customs_item: RandomCustomsItemContext | None = None


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
    status: Literal["chapter_complete"]
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


class SlotEvidence(BaseModel):
    slot: str
    value: str
    confidence: float = Field(ge=0, le=1)
    evidence_text: str


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
    do_not_generate_npc_text: bool


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
    current_node_id: str
    player_text: str
    npc: NpcContext
    node_context: NodeContext
    understanding: UnderstandingOutput
    developer_b_policy: DevBPolicyOutput
    transition: TransitionContext | None = None
    random_customs_item: RandomCustomsItemContext | None = None


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
    state_delta: StateDelta
    evaluation: EvaluationResponse
    report: ReportResponse
    debug: DebugInfo


class UnrealResultResponse(BaseModel):
    contract_version: Literal["dev_c_unreal_result.v1"]
    session_id: str
    final_result: FinalResult
    out_game_feedback: dict[str, Any] | None = None
