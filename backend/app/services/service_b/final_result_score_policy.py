from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal, TypeAlias

from backend.app.schemas.game_turn import (
    FinalReportSummary,
    FinalResult,
    FinalScoreState,
    QuantitativeScores,
)

FINAL_DECISION_NODE_ID = "IMM_007_FINAL_DECISION"
SCENE_SCORE_WEIGHTS = {
    "flight": 20,
    "immigration": 50,
    "baggage": 30,
}
RUBRIC_FIELDS = [
    "comprehension",
    "fluency",
    "grammar_accuracy",
    "vocabulary_range",
    "clarity",
    "interaction_problem_solving",
]
FinalRecommendation: TypeAlias = Literal[
    "PASS",
    "CONDITIONAL_PASS",
    "SECONDARY_ROOM",
    "COMIC_FAIL",
    "UNRANKED",
]
FinalRank: TypeAlias = Literal[
    "Gold Pass",
    "Silver Pass",
    "Bronze Pass",
    "Secondary Review",
    "Comic Fail",
    "Unranked",
]


class OpenKBFinalResultRecordReader:
    def __init__(self, runtime_root: Path | None = None) -> None:
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")

    def read_session_records(self, session_id: str) -> list[dict[str, Any]]:
        jsonl_path = self.runtime_root / f"{session_id}.jsonl"
        if not jsonl_path.exists():
            return []

        records: list[dict[str, Any]] = []
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records


class FinalResultScorePolicy:
    def build_result(
        self,
        records: list[dict[str, Any]],
        *,
        final_state: FinalScoreState | None = None,
    ) -> FinalResult:
        scored_records = self._scored_records(records)
        included_records = self._included_records(scored_records)
        state = final_state or self._state_from_records(records)

        if not included_records:
            return self._unranked_result()

        quantitative_scores = self._quantitative_scores(included_records)
        final_score = quantitative_scores.overall
        per_turn_scores = [self._rubric_total_to_100(record["rubric_scores"]["total"]) for record in included_records]
        recommendation, reason_tags = self._recommendation(included_records, final_score, state)
        focus_targets = self._focus_targets(records)
        if focus_targets:
            reason_tags.append("focus_on_form_recorded")

        return FinalResult(
            final_recommendation=recommendation,
            rank=self._rank(recommendation, final_score),
            final_score_100=final_score,
            reason_tags=_unique(reason_tags),
            quantitative_scores=quantitative_scores,
            report_summary=self._report_summary(
                included_records,
                per_turn_scores,
                recommendation,
                focus_targets,
            ),
        )

    def _scored_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scored: list[dict[str, Any]] = []
        for record in records:
            rubric_scores = record.get("rubric_scores")
            if not isinstance(rubric_scores, dict):
                continue
            total = rubric_scores.get("total")
            if not isinstance(total, int) or not 0 <= total <= 12:
                continue
            if any(not isinstance(rubric_scores.get(field), int) for field in RUBRIC_FIELDS):
                continue
            scored.append(record)
        return scored

    def _included_records(self, scored_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        non_final_records = [
            record
            for record in scored_records
            if str(record.get("node_id", "")) != FINAL_DECISION_NODE_ID
        ]
        return non_final_records or scored_records

    def _quantitative_scores(self, included_records: list[dict[str, Any]]) -> QuantitativeScores:
        scene_records: dict[str, list[dict[str, Any]]] = {}
        for record in included_records:
            scene_key = self._scene_key(record)
            if scene_key not in SCENE_SCORE_WEIGHTS:
                continue
            scene_records.setdefault(scene_key, []).append(record)

        if not scene_records:
            scene_records = {"immigration": included_records}

        weight_total = sum(SCENE_SCORE_WEIGHTS[scene_key] for scene_key in scene_records)
        averages: dict[str, int] = {}
        for field in RUBRIC_FIELDS:
            weighted_sum = 0
            for scene_key, records in scene_records.items():
                scene_average = _average_int(
                    [self._rubric_dimension_to_100(record["rubric_scores"][field]) for record in records]
                )
                weighted_sum += scene_average * SCENE_SCORE_WEIGHTS[scene_key]
            averages[field] = _round_half_up(weighted_sum / weight_total)

        overall = _average_int([averages[field] for field in RUBRIC_FIELDS])
        return QuantitativeScores(
            overall=overall,
            comprehension=averages["comprehension"],
            fluency=averages["fluency"],
            grammar_accuracy=averages["grammar_accuracy"],
            vocabulary_range=averages["vocabulary_range"],
            clarity=averages["clarity"],
            interaction_problem_solving=averages["interaction_problem_solving"],
            scoring_policy="simple_average",
        )

    def _scene_key(self, record: dict[str, Any]) -> str:
        node_id = str(record.get("node_id", ""))
        if node_id.startswith("FLIGHT_"):
            return "flight"
        if node_id.startswith("IMM_"):
            return "immigration"
        if node_id.startswith("BAG_"):
            return "baggage"
        return "optional"

    def _recommendation(
        self,
        included_records: list[dict[str, Any]],
        final_score: int,
        final_state: FinalScoreState,
    ) -> tuple[FinalRecommendation, list[str]]:
        reason_tags: list[str] = ["scene_normalized_dimension_average_policy"]
        verdicts = [self._verdict(record) for record in included_records]
        has_critical_fail = any(verdict == "CRITICAL_FAIL" for verdict in verdicts)
        has_non_success = any(verdict in {"FAIL", "PARTIAL", "UNCLEAR"} for verdict in verdicts)

        if has_critical_fail:
            reason_tags.append("critical_fail")
        if final_state.patience <= 0:
            reason_tags.append("patience_depleted")
        if final_state.suspicion >= 70:
            reason_tags.append("high_suspicion")
        if final_score < 40:
            reason_tags.append("score_below_40")
        if has_critical_fail or final_state.patience <= 0 or final_state.suspicion >= 70 or final_score < 40:
            return "COMIC_FAIL", reason_tags

        if final_state.suspicion >= 50:
            reason_tags.append("suspicion_review")
        if final_score < 60:
            reason_tags.append("score_below_60")
        if final_state.suspicion >= 50 or final_score < 60:
            return "SECONDARY_ROOM", reason_tags

        if final_score < 80:
            reason_tags.append("score_below_80")
        if has_non_success:
            reason_tags.append("non_success_verdict")
        if final_score < 80 or has_non_success:
            return "CONDITIONAL_PASS", reason_tags

        reason_tags.append("score_at_least_80")
        return "PASS", reason_tags

    def _rank(self, final_recommendation: FinalRecommendation, final_score: int) -> FinalRank:
        if final_recommendation == "UNRANKED":
            return "Unranked"
        if final_recommendation == "COMIC_FAIL":
            return "Comic Fail"
        if final_recommendation == "SECONDARY_ROOM":
            return "Secondary Review"
        if final_score >= 90:
            return "Gold Pass"
        if final_score >= 75:
            return "Silver Pass"
        if final_score >= 60:
            return "Bronze Pass"
        if final_score >= 40:
            return "Secondary Review"
        return "Comic Fail"

    def _report_summary(
        self,
        included_records: list[dict[str, Any]],
        per_turn_scores: list[int],
        final_recommendation: FinalRecommendation,
        focus_targets: list[str],
    ) -> FinalReportSummary:
        best_index = max(range(len(included_records)), key=lambda index: per_turn_scores[index])
        weakest_index = min(range(len(included_records)), key=lambda index: per_turn_scores[index])
        weakest_record = included_records[weakest_index]

        return FinalReportSummary(
            overall=self._overall_summary(final_recommendation),
            best_node=str(included_records[best_index].get("node_id", "")) or None,
            weakest_node=str(weakest_record.get("node_id", "")) or None,
            main_improvement=self._main_improvement(weakest_record),
            focus_on_form_targets=focus_targets,
            included_node_count=len(included_records),
        )

    def _overall_summary(self, final_recommendation: FinalRecommendation) -> str:
        if final_recommendation == "PASS":
            return "You passed the immigration check with clear, usable travel English."
        if final_recommendation == "CONDITIONAL_PASS":
            return "You completed the check, but some answers need more complete or precise English."
        if final_recommendation == "SECONDARY_ROOM":
            return "Your answers need secondary review because risk or score thresholds were triggered."
        if final_recommendation == "COMIC_FAIL":
            return "The run ended with a fail condition or serious immigration risk."
        return "No scored rubric records were available for the final report."

    def _main_improvement(self, record: dict[str, Any]) -> str:
        report_item = record.get("report_item")
        if isinstance(report_item, dict):
            improvement = report_item.get("improvement")
            if isinstance(improvement, str) and improvement.strip():
                return improvement
        return "Keep answers concise and polite."

    def _state_from_records(self, records: list[dict[str, Any]]) -> FinalScoreState:
        patience_delta = 0
        suspicion = 0
        retry_count = 0
        hint_count = 0
        for record in records:
            state_delta = record.get("state_delta")
            if not isinstance(state_delta, dict):
                continue
            patience_delta += _int_value(state_delta.get("patience_delta"))
            suspicion += _int_value(state_delta.get("suspicion_delta"))
            retry_count += _int_value(state_delta.get("retry_count_delta"))
            hint_count += _int_value(state_delta.get("hint_count_delta"))
        return FinalScoreState(
            patience=100 + patience_delta,
            suspicion=suspicion,
            retry_count=retry_count,
            hint_count=hint_count,
        )

    def _focus_targets(self, records: list[dict[str, Any]]) -> list[str]:
        targets: list[str] = []
        for record in records:
            seed = record.get("out_game_feedback_seed")
            if isinstance(seed, dict):
                if seed.get("include_in_final_report") is False:
                    continue
                values = seed.get("focus_on_form_targets")
                if isinstance(values, list):
                    targets.extend(str(value) for value in values if str(value).strip())
            fallback_values = record.get("focus_on_form_targets")
            if isinstance(fallback_values, list):
                targets.extend(str(value) for value in fallback_values if str(value).strip())
        return _unique(targets)

    def _verdict(self, record: dict[str, Any]) -> str:
        evaluation = record.get("evaluation")
        if not isinstance(evaluation, dict):
            return ""
        verdict = evaluation.get("verdict")
        return str(verdict) if verdict is not None else ""

    def _rubric_total_to_100(self, total: int) -> int:
        return _round_half_up(total / 12 * 100)

    def _rubric_dimension_to_100(self, value: int) -> int:
        return _round_half_up(value / 2 * 100)

    def _unranked_result(self) -> FinalResult:
        return FinalResult(
            final_recommendation="UNRANKED",
            rank="Unranked",
            final_score_100=0,
            reason_tags=["no_scored_rubric_records"],
            quantitative_scores=QuantitativeScores(
                overall=0,
                comprehension=0,
                fluency=0,
                grammar_accuracy=0,
                vocabulary_range=0,
                clarity=0,
                interaction_problem_solving=0,
                scoring_policy="simple_average",
            ),
            report_summary=FinalReportSummary(
                overall="No scored rubric records were available for the final report.",
                best_node=None,
                weakest_node=None,
                main_improvement="Complete at least one scored immigration answer.",
                focus_on_form_targets=[],
                included_node_count=0,
            ),
        )


def _average_int(values: list[int]) -> int:
    return _round_half_up(sum(values) / len(values))


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _int_value(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
