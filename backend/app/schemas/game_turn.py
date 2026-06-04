from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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


class GameState(BaseModel):
    inventory: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    completed_intents: list[str] = Field(default_factory=list)
    current_objective: str


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
    player_profile: PlayerProfile
    scenario_state: ScenarioState
    game_state: GameState
    previous_node_results: list[PreviousNodeResult] = Field(default_factory=list)
    client_allowed_next_nodes: list[str] = Field(default_factory=list)
    client_context: ClientContext | None = None


class MockAudioInput(BaseModel):
    mock_wav_path: str | None = None
    transcript: str | None = None
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
    stt_model: Literal["whisper-large-v3-turbo"]
    stt_primary_runtime: Literal["local"]
    stt_fallback_runtime: Literal["api"]
    stt_runtime_used: Literal["local", "api"]


class HintPolicy(BaseModel):
    keyword: list[str] = Field(default_factory=list)
    sentence_pattern: str
    situation_hint: str
    action_hint: str


class NodeContext(BaseModel):
    node_id: str
    chapter_id: str
    npc_question: str
    npc_question_goal: str
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
    extracted_slots: dict[str, str]
    missing_slots: list[str]
    needs_clarification: bool


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
    player_profile: PlayerProfile
    scenario_state: ScenarioState
    node_context: NodeContext
    understanding: UnderstandingOutput
    previous_node_results: list[PreviousNodeResult] = Field(default_factory=list)
    client_allowed_next_nodes: list[str] = Field(default_factory=list)


class Scores(BaseModel):
    task_success: int
    clarity: int
    grammar: int
    vocabulary: int
    problem_solving: int
    politeness: int


class RubricScores(BaseModel):
    comprehension: int = Field(ge=0, le=2)
    fluency: int = Field(ge=0, le=2)
    grammar_accuracy: int = Field(ge=0, le=2)
    vocabulary_range: int = Field(ge=0, le=2)
    clarity: int = Field(ge=0, le=2)
    interaction_problem_solving: int = Field(ge=0, le=2)
    total: int = Field(ge=0, le=12)


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
    next_action: Literal["ADVANCE", "REASK", "GIVE_HINT", "WARNING", "FAIL_END", "FINAL_DECISION"]
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
    evaluation: Evaluation
    level_hint: LevelHint
    in_game_feedback: InGameFeedback
    error_capture: ErrorCapture
    out_game_feedback_seed: OutGameFeedbackSeed
    branch: Branch
    state_delta: StateDelta
    report_item: ReportItem
    dialogue_directive: DialogueDirective | None = None
    openkb_write: OpenKBWriteResult | None = None
    rubric_scores: RubricScores | None = None
    difficulty_profile: DifficultyProfile | None = None
    feedback_generation: FeedbackGenerationTrace | None = None


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


class DevADialogueOutput(BaseModel):
    contract_version: Literal["dev_a_dialogue.v1"]
    speaker: str
    text: str
    tone: str
    animation: str
    feedback_kr: str | None = None
    audio_url: str | None = None


class RecordedErrorSummary(BaseModel):
    recorded: bool
    storage_format: Literal["markdown"]
    error_log_markdown_path: str | None = None
    recorded_error_count: int


class NpcResponse(BaseModel):
    speaker: str
    text: str
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


class DebugInfo(BaseModel):
    stt_model: str
    stt_confidence: float | None
    understanding_confidence: float
    contract_versions: list[str]


class SttResponse(BaseModel):
    model: str
    primary_runtime: Literal["local"]
    fallback_runtime: Literal["api"]
    runtime_used: Literal["local", "api"]
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
    stt: SttResponse
    npc: NpcResponse
    ui: UiResponse
    state_delta: StateDelta
    evaluation: EvaluationResponse
    report: ReportResponse
    debug: DebugInfo
