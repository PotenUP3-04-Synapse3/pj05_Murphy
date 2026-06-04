import json
from pathlib import Path
from typing import Any

import pytest

from backend.app.agents.agent_b.english_level_hint_agent import EnglishLevelHintAgent
from backend.app.services.service_b.feedback_hint_generator import FeedbackHintGenerator
from backend.app.services.service_b.openkb_feedback_writer import OpenKBFeedbackWriter
from backend.tests.dev_b.test_developer_b_policy_engine import (
    _FailingOpenKBWriter,
    _FakeFeedbackLLMClient,
    _node_context,
    _policy_input,
)


def _agent_run_records(root: Path) -> list[dict[str, Any]]:
    path = root / "unified_agent_runs.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_developer_b_appends_unified_agent_run_for_success_turn(tmp_path: Path) -> None:
    payload = _policy_input(player_text="I'm here for tourism.")

    result = EnglishLevelHintAgent(
        openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"),
        agent_run_root=tmp_path,
    ).evaluate_turn(payload)

    records = _agent_run_records(tmp_path)
    record = records[0]
    tool_names = [
        event.get("tool_name")
        for event in record["events"]
        if event.get("event") == "tool_call"
    ]
    raw_log = (tmp_path / "unified_agent_runs.jsonl").read_text(encoding="utf-8")
    readable_log = (tmp_path / "unified_agent_runs.md").read_text(encoding="utf-8")

    assert result.branch.next_node_id == "IMM_003_DURATION"
    assert record["schema_version"] == "unified_agent_run.v1"
    assert record["agent_name"] == "english_level_hint_agent"
    assert record["owner"] == "developer_b"
    assert record["request_id"] == payload.request_id
    assert record["session_id"] == payload.session_id
    assert record["turn_index"] == payload.turn_index
    assert record["status"] == "completed"
    assert record["model"]["model_name"] == "rule_based"
    assert record["summary"]["input"]["player_text_preview"] == "I'm here for tourism."
    assert "player_text" not in record["summary"]["input"]
    assert '"player_text":' not in raw_log
    assert record["summary"]["output"]["verdict"] == "SUCCESS"
    assert record["summary"]["output"]["branch_type"] == "success"
    assert record["summary"]["output"]["next_node_id"] == "IMM_003_DURATION"
    assert record["summary"]["output"]["openkb_write_succeeded"] is True
    assert tool_names == [
        "scenario_state_machine.decide",
        "level_adaptation_controller.english_level",
        "level_adaptation_controller.hint_policy",
        "level_adaptation_controller.feedback_strategy",
        "level_adaptation_controller.has_form_issue",
        "tier_difficulty_controller.evaluate",
        "feedback_hint_generator.generate",
        "openkb_feedback_writer.write_policy_output",
    ]
    assert record["metadata"]["data_flow"][0]["from"] == "dev_b_policy_input"
    assert record["metadata"]["data_flow"][-1]["to"] == "dev_b_policy_output"
    assert "## Agent Run: english_level_hint_agent / developer_b" in readable_log


def test_developer_b_agent_run_records_llm_feedback_mode(tmp_path: Path) -> None:
    payload = _policy_input(
        player_text="I don't know.",
        intent_success=False,
        confidence=0.6,
        extracted_slots={},
        missing_slots=["visit_purpose"],
        retry_count=2,
        previous_fail_count=2,
    )

    result = EnglishLevelHintAgent(
        feedback_generator=FeedbackHintGenerator(mode="llm", llm_client=_FakeFeedbackLLMClient()),
        openkb_writer=OpenKBFeedbackWriter(runtime_root=tmp_path / "openkb" / "dev_b"),
        agent_run_root=tmp_path,
    ).evaluate_turn(payload)

    record = _agent_run_records(tmp_path)[0]
    feedback_event = next(
        event
        for event in record["events"]
        if event.get("tool_name") == "feedback_hint_generator.generate"
    )

    assert result.feedback_generation is not None
    assert result.feedback_generation.mode == "llm"
    assert record["model"]["model_name"] == "fake-dev-b-model"
    assert feedback_event["output_summary"]["mode"] == "llm"
    assert feedback_event["output_summary"]["used_llm"] is True
    assert record["summary"]["output"]["feedback_generation_mode"] == "llm"


def test_developer_b_agent_run_records_openkb_write_failure_without_changing_policy(
    tmp_path: Path,
) -> None:
    payload = _policy_input()

    result = EnglishLevelHintAgent(
        openkb_writer=_FailingOpenKBWriter(),
        agent_run_root=tmp_path,
    ).evaluate_turn(payload)

    record = _agent_run_records(tmp_path)[0]
    openkb_event = next(
        event
        for event in record["events"]
        if event.get("tool_name") == "openkb_feedback_writer.write_policy_output"
    )

    assert result.evaluation.verdict == "SUCCESS"
    assert result.branch.branch_type == "success"
    assert result.openkb_write is not None
    assert result.openkb_write.succeeded is False
    assert record["status"] == "completed"
    assert record["summary"]["output"]["openkb_write_succeeded"] is False
    assert openkb_event["status"] == "failed"
    assert openkb_event["output_summary"]["error_message"] == "simulated write failure"


def test_developer_b_agent_run_records_failed_policy_exception(tmp_path: Path) -> None:
    context = _node_context()
    payload = _policy_input(node_context=context.model_copy(update={"allowed_next_nodes": []}))

    with pytest.raises(ValueError, match="allowed_next_nodes"):
        EnglishLevelHintAgent(agent_run_root=tmp_path).evaluate_turn(payload)

    record = _agent_run_records(tmp_path)[0]

    assert record["status"] == "failed"
    assert record["summary"]["output"]["error_type"] == "ValueError"
    assert "allowed_next_nodes" in record["summary"]["output"]["error"]
    assert record["events"][-1]["event"] == "agent_end"
    assert record["events"][-1]["status"] == "failed"
