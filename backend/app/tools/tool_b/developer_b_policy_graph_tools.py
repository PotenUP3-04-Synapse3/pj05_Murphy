from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from backend.app.agents.agent_b.english_level_hint_agent import (
    OpenKBPolicyWriter,
    _decision_summary,
    _EnglishLevelHintPolicyCore,
    _feedback_fallback_used,
    _feedback_generation_summary,
    _model_name,
    _openkb_write_summary,
    _policy_input_summary,
    _policy_output_summary,
    _validate_b_policy_output,
)
from backend.app.schemas.game_turn import Branch, DevBPolicyInput, DevBPolicyOutput, LevelHint, StateDelta
from backend.app.services.service_b.developer_b_agent_run_logger import DeveloperBAgentRunLogger
from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGeneration, FeedbackHintGenerator
from backend.app.services.service_b.level_adaptation_controller import LevelAdaptationController
from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter
from backend.app.services.service_b.scenario_state_machine import ScenarioDecision, ScenarioStateMachine
from backend.app.services.service_b.tier_difficulty_controller import TierDifficultyController, TierDifficultyResult
from backend.app.services.service_b.flight_smalltalk_diagnostic_policy import FlightSmallTalkDiagnosticPolicy


DEVELOPER_B_POLICY_GRAPH_NAME = "developer_b_policy_graph"
DEVELOPER_B_POLICY_GRAPH_TOOL_STYLE = "developer_b_policy_graph_tools"
DEVELOPER_B_POLICY_GRAPH_NODE_NAMES = (
    "start_agent_run",
    "decide_scenario_branch",
    "derive_level_and_hint",
    "derive_feedback_strategy",
    "evaluate_tier_difficulty",
    "build_base_policy_output",
    "generate_feedback_hint",
    "apply_feedback_generation",
    "attach_report_and_dialogue_seeds",
    "validate_policy_output",
    "write_openkb_feedback",
    "finish_agent_run",
)

BAGGAGE_SERVICE_NODE_IDS = {
    "BAG_001_REPORT_MISSING_AT_DESK",
    "BAG_002_PROVIDE_CLAIM_TAG",
    "BAG_003_CONFIRM_SEARCHED_CAROUSEL",
    "BAG_004_STAFF_REDIRECT_TO_CUSTOMS_HOLD",
}

CUSTOMS_OFFICER_NODE_IDS = {
    "BAG_005_CUSTOMS_HOLD_EXPLANATION",
    "BAG_006_EXPLAIN_RANDOM_CUSTOMS_ITEM",
    "BAG_007_CUSTOMS_CLEARANCE",
}


class DeveloperBPolicyGraphTools(_EnglishLevelHintPolicyCore):
    def __init__(
        self,
        *,
        state_machine: ScenarioStateMachine | None = None,
        level_controller: LevelAdaptationController | None = None,
        tier_controller: TierDifficultyController | None = None,
        feedback_generator: FeedbackHintGenerator | None = None,
        openkb_writer: OpenKBPolicyWriter | None = None,
        agent_run_root: Path | None = None,
        agent_run_logger: DeveloperBAgentRunLogger | None = None,
    ) -> None:
        super().__init__(
            state_machine=state_machine,
            level_controller=level_controller,
            tier_controller=tier_controller,
            feedback_generator=feedback_generator,
            openkb_writer=openkb_writer or OpenKBFeedbackWriter(),
            agent_run_root=agent_run_root,
            agent_run_logger=agent_run_logger,
        )
        self.active_agent_run: dict[str, Any] | None = None

    def start_agent_run_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        agent_run = self.agent_run_logger.start_run(payload)
        self.active_agent_run = agent_run
        _attach_langgraph_runtime_metadata(agent_run)
        input_summary = _policy_input_summary(payload)
        self.agent_run_logger.record_event(
            agent_run,
            event="agent_start",
            status="started",
            data_loaded=input_summary,
        )
        self.agent_run_logger.record_data_flow(
            agent_run,
            from_node="dev_b_policy_input",
            to_node="scenario_state_machine",
            payload_summary=input_summary,
        )
        return {"agent_run": agent_run, "input_summary": input_summary}

    def decide_scenario_branch_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        agent_run = _require_agent_run(state)
        input_summary = _require_dict(state, "input_summary")
        
        is_flight_smalltalk = (payload.scene_id == "FLIGHT_A_001_SEATMATE_SMALLTALK" or payload.current_node_id.startswith("FLIGHT_"))
        if is_flight_smalltalk:
            diagnostic_policy = FlightSmallTalkDiagnosticPolicy()
            decision = diagnostic_policy.decide_conversational(payload)
            tool_name = "flight_smalltalk_diagnostic_policy.decide_conversational"
        else:
            decision = self.state_machine.decide(payload)
            tool_name = "scenario_state_machine.decide"

        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=_decision_summary(decision),
        )
        return {"decision": decision}

    def derive_level_and_hint_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        decision = _require_state_value(state, "decision", ScenarioDecision)
        agent_run = _require_agent_run(state)

        english_level = self.level_controller.english_level(payload)
        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="level_adaptation_controller.english_level",
            output_summary={"english_level": english_level},
        )

        hint_policy = self.level_controller.hint_policy(payload, decision)
        needs_hint, hint_level, hint_type, _hint_kr = hint_policy
        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="level_adaptation_controller.hint_policy",
            output_summary={
                "needs_hint": needs_hint,
                "hint_level": hint_level,
                "hint_type": hint_type,
            },
        )
        return {"english_level": english_level, "hint_policy": hint_policy}

    def derive_feedback_strategy_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        decision = _require_state_value(state, "decision", ScenarioDecision)
        agent_run = _require_agent_run(state)

        feedback_strategy = self.level_controller.feedback_strategy(decision)
        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="level_adaptation_controller.feedback_strategy",
            output_summary={"feedback_strategy": feedback_strategy},
        )

        has_form_issue = self.level_controller.has_form_issue(payload)
        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="level_adaptation_controller.has_form_issue",
            output_summary={"has_form_issue": has_form_issue},
        )
        return {"feedback_strategy": feedback_strategy, "has_form_issue": has_form_issue}

    def evaluate_tier_difficulty_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        decision = _require_state_value(state, "decision", ScenarioDecision)
        has_form_issue = _require_bool(state, "has_form_issue")
        agent_run = _require_agent_run(state)

        tier_result = self.tier_controller.evaluate(payload, decision, has_form_issue=has_form_issue)
        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="tier_difficulty_controller.evaluate",
            output_summary={
                "rubric_total": tier_result.rubric_scores.total,
                "travel_speaking_level": tier_result.difficulty_profile.travel_speaking_level,
            },
        )
        return {"tier_result": tier_result}

    def build_base_policy_output_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        decision = _require_state_value(state, "decision", ScenarioDecision)
        tier_result = _require_state_value(state, "tier_result", TierDifficultyResult)
        english_level = _require_string(state, "english_level")
        feedback_strategy = _require_string(state, "feedback_strategy")
        has_form_issue = _require_bool(state, "has_form_issue")
        needs_hint, hint_level, hint_type, hint_kr = _require_hint_policy(state)

        output = DevBPolicyOutput(
            contract_version="dev_b_policy.v1",
            node_id=payload.current_node_id,
            npc_emotion=self._build_npc_emotion(payload, decision),
            evaluation=self._build_evaluation(payload, decision, has_form_issue),
            level_hint=LevelHint(
                english_level=english_level,
                travel_speaking_level=payload.player_profile.travel_speaking_level,
                cefr_estimate=self.level_controller.cefr_estimate(english_level),
                needs_hint=needs_hint,
                hint_level=hint_level,
                hint_type=hint_type,
                hint_kr=hint_kr,
                example_en=payload.node_context.recommended_expression,
                avoid_expression=self._avoid_expression(payload),
                recommended_expression=payload.node_context.recommended_expression,
                cumulative_confidence=decision.cumulative_confidence if hasattr(decision, "cumulative_confidence") else None,
            ),
            in_game_feedback=self._build_in_game_feedback(payload, decision, feedback_strategy),
            error_capture=self._build_error_capture(payload, decision, has_form_issue),
            out_game_feedback_seed=self._build_out_game_feedback_seed(payload, decision, has_form_issue),
            branch=Branch(
                branch_type=decision.branch_type,
                next_action=decision.next_action,
                next_node_id=decision.next_node_id,
                branch_reason=decision.branch_reason,
                allowed_next_node_checked=True,
            ),
            state_delta=StateDelta(
                patience_delta=decision.patience_delta,
                suspicion_delta=decision.suspicion_delta,
                retry_count_delta=decision.retry_count_delta,
                hint_count_delta=decision.hint_count_delta,
            ),
            dialogue_directive=self._build_dialogue_directive(payload, decision),
            report_item=self._build_report_item(payload, decision, has_form_issue),
            rubric_scores=tier_result.rubric_scores,
            difficulty_profile=tier_result.difficulty_profile,
        )
        return {"output": output}

    def generate_feedback_hint_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        decision = _require_state_value(state, "decision", ScenarioDecision)
        tier_result = _require_state_value(state, "tier_result", TierDifficultyResult)
        output = _require_state_value(state, "output", DevBPolicyOutput)
        agent_run = _require_agent_run(state)

        feedback_generation = self.feedback_generator.generate(
            payload=payload,
            decision=decision,
            base_output=output,
            tier_result=tier_result,
            focus_on_form_explanation_kr=self._focus_on_form_explanation(payload, output),
        )
        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status="completed",
            tool_name="feedback_hint_generator.generate",
            output_summary=_feedback_generation_summary(feedback_generation),
        )
        return {"feedback_generation": feedback_generation}

    def apply_feedback_generation_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        tier_result = _require_state_value(state, "tier_result", TierDifficultyResult)
        output = _require_state_value(state, "output", DevBPolicyOutput)
        feedback_generation = _require_state_value(state, "feedback_generation", FeedbackHintGeneration)

        if feedback_generation.rubric_scores is not None:
            tier_result = self.tier_controller.from_rubric_scores(
                feedback_generation.rubric_scores,
                tier=payload.player_profile.tier,
            )
        output = output.model_copy(
            update={
                "evaluation": output.evaluation.model_copy(
                    update={"feedback_note": feedback_generation.feedback_note}
                ),
                "level_hint": output.level_hint.model_copy(update={"hint_kr": feedback_generation.hint_kr}),
                "report_item": output.report_item.model_copy(
                    update={
                        "summary": feedback_generation.report_summary,
                        "improvement": feedback_generation.report_improvement,
                        "example_answer": feedback_generation.example_answer,
                    }
                ),
                "rubric_scores": tier_result.rubric_scores,
                "difficulty_profile": tier_result.difficulty_profile,
                "feedback_generation": feedback_generation.trace,
            }
        )
        return {"output": output, "tier_result": tier_result}

    def attach_report_and_dialogue_seeds_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        output = _require_state_value(state, "output", DevBPolicyOutput)

        output = output.model_copy(
            update={
                "report_seed_summary": self._build_report_seed_summary(payload, output),
                "dialogue_seed": self._build_dialogue_seed(payload, output, decision=state.get("decision")),
            }
        )
        return {"output": output}

    def validate_policy_output_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        output = _require_state_value(state, "output", DevBPolicyOutput)

        _validate_b_policy_output(payload, output)
        return {"output": output}

    def write_openkb_feedback_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        payload = _require_state_value(state, "payload", DevBPolicyInput)
        output = _require_state_value(state, "output", DevBPolicyOutput)
        agent_run = _require_agent_run(state)

        try:
            openkb_write = self.openkb_writer.write_policy_output(payload, output)
        except Exception as exc:
            openkb_write = self.openkb_writer.failure_result(exc)
        openkb_status = "completed" if openkb_write.succeeded else "failed"
        self.agent_run_logger.record_event(
            agent_run,
            event="tool_call",
            status=openkb_status,
            tool_name="openkb_feedback_writer.write_policy_output",
            output_summary=_openkb_write_summary(openkb_write),
        )

        output = output.model_copy(update={"openkb_write": openkb_write})
        self.agent_run_logger.record_data_flow(
            agent_run,
            from_node="openkb_feedback_writer",
            to_node="dev_b_policy_output",
            payload_summary=_policy_output_summary(output),
        )
        return {"openkb_write": openkb_write, "output": output}

    def finish_agent_run_tool(self, state: Mapping[str, Any]) -> dict[str, Any]:
        input_summary = _require_dict(state, "input_summary")
        output = _require_state_value(state, "output", DevBPolicyOutput)
        agent_run = _require_agent_run(state)

        output_summary = _policy_output_summary(output)
        self.agent_run_logger.record_event(
            agent_run,
            event="agent_end",
            status="completed",
            output_summary=output_summary,
        )
        self.agent_run_logger.complete_and_append(
            agent_run,
            status="completed",
            summary={
                "input": input_summary,
                "output": output_summary,
                "fallback_used": _feedback_fallback_used(output),
                "audio_url": None,
            },
            model_name=_model_name(output),
        )
        self.active_agent_run = None
        return {"output": output}

    def complete_failed_run(self, payload: DevBPolicyInput, exc: Exception) -> None:
        if self.active_agent_run is None:
            return

        agent_run = self.active_agent_run
        input_summary = _policy_input_summary(payload)
        error_summary = {"error": str(exc), "error_type": exc.__class__.__name__}
        self.agent_run_logger.record_event(
            agent_run,
            event="agent_end",
            status="failed",
            error=str(exc),
        )
        self.agent_run_logger.fail_and_append(
            agent_run,
            error=exc,
            summary={
                "input": input_summary,
                "output": error_summary,
                "fallback_used": False,
                "audio_url": None,
            },
        )
        self.active_agent_run = None

    def _npc_role(self, payload: DevBPolicyInput) -> str:
        if payload.current_node_id.startswith("FLIGHT_"):
            return "seatmate_passenger"
        if payload.current_node_id in CUSTOMS_OFFICER_NODE_IDS:
            return "customs_officer"
        if payload.current_node_id in BAGGAGE_SERVICE_NODE_IDS or payload.current_node_id.startswith("BAG_"):
            return "baggage_service_agent"
        return "immigration_officer"


def _attach_langgraph_runtime_metadata(agent_run: dict[str, Any]) -> None:
    metadata = agent_run.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        agent_run["metadata"] = metadata

    metadata["runtime"] = {
        "policy_engine": "langgraph",
        "graph_name": DEVELOPER_B_POLICY_GRAPH_NAME,
        "tool_style": DEVELOPER_B_POLICY_GRAPH_TOOL_STYLE,
        "graph_nodes": list(DEVELOPER_B_POLICY_GRAPH_NODE_NAMES),
    }


def _require_state_value(state: Mapping[str, Any], key: str, expected_type: type[Any]) -> Any:
    value = state.get(key)
    if not isinstance(value, expected_type):
        raise RuntimeError(f"Developer B graph state is missing required value: {key}")
    return value


def _require_agent_run(state: Mapping[str, Any]) -> dict[str, Any]:
    value = state.get("agent_run")
    if isinstance(value, dict):
        return value
    raise RuntimeError("Developer B graph state is missing required value: agent_run")


def _require_dict(state: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = state.get(key)
    if isinstance(value, dict):
        return value
    raise RuntimeError(f"Developer B graph state is missing required dict: {key}")


def _require_string(state: Mapping[str, Any], key: str) -> Any:
    value = state.get(key)
    if isinstance(value, str):
        return value
    raise RuntimeError(f"Developer B graph state is missing required string: {key}")


def _require_bool(state: Mapping[str, Any], key: str) -> bool:
    value = state.get(key)
    if isinstance(value, bool):
        return value
    raise RuntimeError(f"Developer B graph state is missing required bool: {key}")


def _require_hint_policy(state: Mapping[str, Any]) -> tuple[Any, Any, Any, Any]:
    value = state.get("hint_policy")
    if isinstance(value, tuple) and len(value) == 4:
        return value
    raise RuntimeError("Developer B graph state is missing required hint_policy")
