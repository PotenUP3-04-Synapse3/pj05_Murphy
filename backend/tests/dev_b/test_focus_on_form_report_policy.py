from pathlib import Path
from typing import Any

from backend.app.services.service_b.focus_on_form_report_policy import FocusOnFormReportPolicy


def _record(
    *,
    node_id: str = "IMM_002_PURPOSE",
    focus_targets: list[str] | None = None,
    original: str = "Travel. New York.",
    suggested: str = "I'm here for tourism.",
    priority: str = "medium",
) -> dict[str, Any]:
    targets = focus_targets if focus_targets is not None else ["sentence_completion"]
    return {
        "record_schema_version": "dev_b_openkb_record.v2",
        "record_kind": "policy_turn_feedback",
        "scene_id": "JFK_IMMIGRATION_HALL",
        "node_id": node_id,
        "turn_index": 2,
        "player_text": original,
        "error_capture": {
            "should_record": True,
            "error_items": [
                {
                    "focus_on_form_target": target,
                    "original_utterance": original,
                    "suggested_expression": suggested,
                    "severity": "moderate",
                }
                for target in targets
            ],
        },
        "out_game_feedback_seed": {
            "include_in_final_report": True,
            "focus_on_form_targets": targets,
            "report_priority": priority,
        },
        "focus_on_form_targets": targets,
        "report_item": {
            "summary": "The answer needs another attempt.",
            "improvement": "Answer with a complete sentence.",
            "example_answer": suggested,
            "score_tags": ["retry_needed"],
        },
    }


def test_focus_on_form_report_groups_repeated_targets_and_preserves_examples() -> None:
    report = FocusOnFormReportPolicy().build_report(
        [
            _record(original="Travel. New York.", suggested="I'm here for tourism."),
            _record(
                node_id="IMM_003_DURATION",
                original="Five day.",
                suggested="I'll stay for five days.",
            ),
        ]
    )

    assert report["report_mode"] == "focus_on_form"
    assert report["overall_summary_kr"]
    assert len(report["focus_on_form_items"]) == 1
    item = report["focus_on_form_items"][0]
    assert item["focus_on_form_target"] == "sentence_completion"
    assert item["title_kr"] == "완전한 문장으로 답하기"
    assert item["original_utterances"] == ["Travel. New York.", "Five day."]
    assert item["suggested_expressions"] == ["I'm here for tourism.", "I'll stay for five days."]
    assert item["priority"] == "medium"
    assert item["source_node_ids"] == ["IMM_002_PURPOSE", "IMM_003_DURATION"]
    assert report["personalized_next_step"]["target"] == "sentence_completion"


def test_focus_on_form_report_handles_empty_records() -> None:
    report = FocusOnFormReportPolicy().build_report([])

    assert report == {
        "report_mode": "focus_on_form",
        "overall_summary_kr": "아직 최종 리포트에 포함할 Focus-on-Form 기록이 없습니다.",
        "focus_on_form_items": [],
        "personalized_next_step": {
            "target": None,
            "practice_prompt_kr": "다음 플레이에서 공항 상황을 한 문장으로 답해보세요.",
            "answer_example": "I'm here for tourism.",
        },
    }


def test_focus_on_form_report_uses_fallback_card_for_unknown_target(tmp_path: Path) -> None:
    card_path = tmp_path / "missing_cards.json"

    report = FocusOnFormReportPolicy(card_path=card_path).build_report(
        [
            _record(
                node_id="IMM_X",
                focus_targets=["unknown_target"],
                original="Maybe.",
                suggested="Could you clarify your answer?",
            )
        ]
    )

    item = report["focus_on_form_items"][0]
    assert item["focus_on_form_target"] == "unknown_target"
    assert item["title_kr"] == "표현 명확하게 다듬기"
    assert item["practice_prompt_kr"] == "같은 상황을 더 명확한 영어 문장으로 다시 말해보세요."
    assert item["answer_example"] == "Could you clarify your answer?"


def test_focus_on_form_report_uses_static_cards_for_baggage_targets() -> None:
    report = FocusOnFormReportPolicy().build_report(
        [
            _record(
                node_id="BAG_003_REPORT_MISSING_BAG",
                focus_targets=["problem_statement"],
                original="My bag no come.",
                suggested="My suitcase didn't arrive.",
                priority="high",
            )
        ]
    )

    item = report["focus_on_form_items"][0]
    assert item["focus_on_form_target"] == "problem_statement"
    assert item["title_kr"] == "문제 상황을 직접 말하기"
    assert item["answer_example"] == "My suitcase didn't arrive."
    assert item["priority"] == "high"


def test_focus_on_form_report_does_not_return_branch_verdict_or_score_authority() -> None:
    report = FocusOnFormReportPolicy().build_report([_record()])

    assert "branch" not in report
    assert "verdict" not in report
    assert "score" not in report
    assert "final_score_100" not in report
