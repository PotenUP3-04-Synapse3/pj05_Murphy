from typing import Any

from backend.app.schemas.game_turn import FinalScoreState
from backend.app.services.service_b.final_result_score_policy import FinalResultScorePolicy


def _rubric(total: int) -> dict[str, int]:
    values_by_total = {
        6: [1, 1, 1, 1, 1, 1],
        9: [2, 1, 1, 2, 2, 1],
        12: [2, 2, 2, 2, 2, 2],
    }
    values = values_by_total[total]
    return {
        "comprehension": values[0],
        "fluency": values[1],
        "grammar_accuracy": values[2],
        "vocabulary_range": values[3],
        "clarity": values[4],
        "interaction_problem_solving": values[5],
        "total": total,
    }


def _record(
    *,
    node_id: str,
    total: int,
    verdict: str = "SUCCESS",
    focus_targets: list[str] | None = None,
    report_improvement: str = "Keep answers concise and polite.",
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "evaluation": {
            "verdict": verdict,
            "feedback_tags": ["intent_matched"],
        },
        "rubric_scores": _rubric(total),
        "out_game_feedback_seed": {
            "include_in_final_report": bool(focus_targets),
            "focus_on_form_targets": focus_targets or [],
            "report_priority": "medium" if focus_targets else "low",
        },
        "report_item": {
            "summary": f"{node_id} was evaluated.",
            "improvement": report_improvement,
            "example_answer": "Thank you, officer.",
            "score_tags": ["task_success_good"],
        },
        "branch": {"branch_type": "success", "next_node_id": "NEXT"},
        "state_delta": {
            "patience_delta": 0,
            "suspicion_delta": 0,
            "retry_count_delta": 0,
            "hint_count_delta": 0,
        },
    }


def _record_with_rubric(
    *,
    node_id: str,
    rubric: dict[str, int],
    verdict: str = "SUCCESS",
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "evaluation": {
            "verdict": verdict,
            "feedback_tags": ["intent_matched"],
        },
        "rubric_scores": {**rubric, "total": sum(rubric.values())},
        "out_game_feedback_seed": {
            "include_in_final_report": False,
            "focus_on_form_targets": [],
            "report_priority": "low",
        },
        "report_item": {
            "summary": f"{node_id} was evaluated.",
            "improvement": "Keep answers concise and polite.",
            "example_answer": "Thank you.",
            "score_tags": ["task_success_good"],
        },
        "branch": {"branch_type": "success", "next_node_id": "NEXT"},
        "state_delta": {
            "patience_delta": 0,
            "suspicion_delta": 0,
            "retry_count_delta": 0,
            "hint_count_delta": 0,
        },
    }


def test_final_score_excludes_final_node_when_prior_scores_exist() -> None:
    result = FinalResultScorePolicy().build_result(
        [
            _record(node_id="IMM_002_PURPOSE", total=6),
            _record(node_id="IMM_003_DURATION", total=9),
            _record(node_id="IMM_007_FINAL_DECISION", total=12),
        ],
        final_state=FinalScoreState(patience=80, suspicion=20, retry_count=1, hint_count=0),
    )

    assert result.final_recommendation == "CONDITIONAL_PASS"
    assert result.rank == "Bronze Pass"
    assert result.final_score_100 == 63
    assert result.quantitative_scores.overall == 63
    assert result.quantitative_scores.scoring_policy == "simple_average"
    assert result.report_summary.included_node_count == 2
    assert result.report_summary.best_node == "IMM_003_DURATION"
    assert result.report_summary.weakest_node == "IMM_002_PURPOSE"


def test_final_score_uses_scene_normalized_dimension_averages_not_turn_counts() -> None:
    result = FinalResultScorePolicy().build_result(
        [
            *[
                _record_with_rubric(
                    node_id="FLIGHT_001_SEATMATE_SMALLTALK",
                    rubric={
                        "comprehension": 0,
                        "fluency": 0,
                        "grammar_accuracy": 0,
                        "vocabulary_range": 0,
                        "clarity": 0,
                        "interaction_problem_solving": 0,
                    },
                )
                for _ in range(5)
            ],
            _record_with_rubric(
                node_id="IMM_002_PURPOSE",
                rubric={
                    "comprehension": 2,
                    "fluency": 2,
                    "grammar_accuracy": 2,
                    "vocabulary_range": 2,
                    "clarity": 2,
                    "interaction_problem_solving": 2,
                },
            ),
            _record_with_rubric(
                node_id="BAG_003_REPORT_MISSING_BAG",
                rubric={
                    "comprehension": 2,
                    "fluency": 2,
                    "grammar_accuracy": 2,
                    "vocabulary_range": 2,
                    "clarity": 2,
                    "interaction_problem_solving": 2,
                },
            ),
        ],
        final_state=FinalScoreState(patience=100, suspicion=0, retry_count=0, hint_count=0),
    )

    assert result.quantitative_scores.comprehension == 80
    assert result.quantitative_scores.fluency == 80
    assert result.quantitative_scores.grammar_accuracy == 80
    assert result.quantitative_scores.vocabulary_range == 80
    assert result.quantitative_scores.clarity == 80
    assert result.quantitative_scores.interaction_problem_solving == 80
    assert result.quantitative_scores.overall == 80
    assert result.final_score_100 == 80
    assert "scene_normalized_dimension_average_policy" in result.reason_tags


def test_focus_on_form_records_affect_report_summary_without_numeric_penalty() -> None:
    result = FinalResultScorePolicy().build_result(
        [
            _record(
                node_id="IMM_002_PURPOSE",
                total=12,
                focus_targets=["sentence_completion"],
                report_improvement="Use a complete sentence for the visit purpose.",
            )
        ],
        final_state=FinalScoreState(patience=90, suspicion=0, retry_count=0, hint_count=0),
    )

    assert result.final_recommendation == "PASS"
    assert result.final_score_100 == 100
    assert result.quantitative_scores.overall == 100
    assert "focus_on_form_recorded" in result.reason_tags
    assert result.report_summary.focus_on_form_targets == ["sentence_completion"]
    assert result.report_summary.main_improvement == "Use a complete sentence for the visit purpose."


def test_final_score_ignores_focus_targets_excluded_from_final_report() -> None:
    record = _record(
        node_id="IMM_002_PURPOSE",
        total=12,
        focus_targets=["sentence_completion"],
    )
    record["out_game_feedback_seed"]["include_in_final_report"] = False

    result = FinalResultScorePolicy().build_result(
        [record],
        final_state=FinalScoreState(patience=90, suspicion=0, retry_count=0, hint_count=0),
    )

    assert result.final_recommendation == "PASS"
    assert "focus_on_form_recorded" not in result.reason_tags
    assert result.report_summary.focus_on_form_targets == []


def test_critical_fail_overrides_high_score_for_final_recommendation() -> None:
    result = FinalResultScorePolicy().build_result(
        [_record(node_id="IMM_006_DECLARATION_CHECK", total=12, verdict="CRITICAL_FAIL")],
        final_state=FinalScoreState(patience=70, suspicion=75, retry_count=0, hint_count=0),
    )

    assert result.final_recommendation == "COMIC_FAIL"
    assert result.rank == "Comic Fail"
    assert result.final_score_100 == 100
    assert "critical_fail" in result.reason_tags
    assert "high_suspicion" in result.reason_tags


def test_empty_records_return_unranked_result() -> None:
    result = FinalResultScorePolicy().build_result([])

    assert result.final_recommendation == "UNRANKED"
    assert result.rank == "Unranked"
    assert result.final_score_100 == 0
    assert result.quantitative_scores.overall == 0
    assert result.report_summary.included_node_count == 0
