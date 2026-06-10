import json
from pathlib import Path
from typing import Any

from backend.app.services.service_b.focus_on_form_report_policy import FocusOnFormReportPolicy


CARD_PATH = Path("backend/app/kb/dev_b/focus_on_form_cards.json")
CURRENT_DEV_B_FOCUS_TARGETS = {
    "purpose_statement",
    "duration_statement",
    "stay_location_statement",
    "return_ticket_statement",
    "declaration_explanation",
    "bag_content_explanation",
    "problem_statement",
    "bag_description",
    "flight_or_tag_statement",
    "delivery_request",
    "follow_up_question",
    "sentence_completion",
    "smalltalk_response_clarity",
}


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


def test_static_cards_cover_current_dev_b_focus_targets() -> None:
    payload = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    cards = payload["cards"]

    assert set(cards) >= CURRENT_DEV_B_FOCUS_TARGETS


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


def test_focus_on_form_report_ignores_records_excluded_from_final_report() -> None:
    record = _record(focus_targets=["sentence_completion"])
    record["out_game_feedback_seed"]["include_in_final_report"] = False

    report = FocusOnFormReportPolicy().build_report([record])

    assert report["focus_on_form_items"] == []
    assert report["personalized_next_step"]["target"] is None


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


def test_focus_on_form_report_can_be_built_from_full_scenario_session_jsonl(tmp_path: Path) -> None:
    runtime_root = tmp_path / "openkb" / "dev_b"
    runtime_root.mkdir(parents=True)
    session_path = runtime_root / "session_alpha.jsonl"
    session_path.write_text(
        "\n".join(
            [
                json.dumps(
                    _record(
                        node_id="FLIGHT_001_SEATMATE_SMALLTALK",
                        focus_targets=["smalltalk_response_clarity"],
                        original="I go New York. First time.",
                        suggested="Yes, I'm going to New York for a short trip.",
                        priority="low",
                    ),
                    ensure_ascii=False,
                ),
                json.dumps(_record(node_id="IMM_002_PURPOSE", focus_targets=["purpose_statement"]), ensure_ascii=False),
                json.dumps(
                    _record(node_id="BAG_003_REPORT_MISSING_BAG", focus_targets=["problem_statement"]),
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = FocusOnFormReportPolicy(runtime_root=runtime_root).build_session_report("session_alpha")

    assert report["report_mode"] == "focus_on_form"
    assert [item["focus_on_form_target"] for item in report["focus_on_form_items"]] == [
        "purpose_statement",
        "problem_statement",
        "smalltalk_response_clarity",
    ]
    assert report["personalized_next_step"]["target"] == "purpose_statement"


def test_focus_on_form_report_does_not_return_branch_verdict_or_score_authority() -> None:
    report = FocusOnFormReportPolicy().build_report([_record()])

    assert "branch" not in report
    assert "verdict" not in report
    assert "score" not in report
    assert "final_score_100" not in report
