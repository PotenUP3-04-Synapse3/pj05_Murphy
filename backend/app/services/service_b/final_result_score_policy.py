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

FINAL_DECISION_NODE_IDS = {"IMM_007_FINAL_DECISION", "ALPHA_999_FINAL_SCOREBOARD"}
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
    """
    OpenKB에 저장되어 있는 세션 로그 레코드들을 읽어오는 리더 클래스입니다.
    
    초보자 가이드: 게임 진행 중 OpenKB에 저장된 JSONL 형태의 대화 히스토리 데이터를 
    파이썬 객체(리스트/딕셔너리)로 파싱하여 로드해 줍니다.
    """
    def __init__(self, runtime_root: Path | None = None) -> None:
        """
        OpenKB 저장소 루트 경로를 설정하여 리더 인스턴스를 초기화합니다.
        """
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")

    def read_session_records(self, session_id: str) -> list[dict[str, Any]]:
        """
        특정 게임 세션(session_id)에 해당하는 로그 파일을 읽어 레코드 목록을 반환합니다.
        
        Args:
            session_id: 조회할 게임 세션 ID
            
        Returns:
            대화 턴별 로그 레코드들이 담긴 딕셔너리 리스트
        """
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
    """
    게임 완료 시, 세션 전체의 대화 기록과 평가 지표를 분석하여 최종 성적 및 판정 결과를 내리는 정책 클래스입니다.
    
    초보자 가이드: 비행기 내 소담(flight), 입국 심사(immigration), 수하물(baggage) 영역 등에서 
    각각 누적된 점수의 가중치를 반영하여 overall 점수를 환산하고, 인내심(patience) 고갈 여부나 의심도(suspicion) 수치에 따라 
    'Gold Pass', 'Secondary Review' 등의 합격 등급을 결정합니다.
    """
    def build_result(
        self,
        records: list[dict[str, Any]],
        *,
        final_state: FinalScoreState | None = None,
    ) -> FinalResult:
        """
        세션의 대화 레코드들을 바탕으로 종합적인 성적표(FinalResult)를 생성합니다.
        
        Args:
            records: 게임 세션 전체의 턴별 로그 레코드 리스트
            final_state: (선택) 인내심, 의심도 등의 최종 게임 상태 데이터
            
        Returns:
            종합 평가, 합격 등급, 영역별 정량 점수, 학습 요약이 포함된 FinalResult 객체
        """
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
        """
        주어진 세션 레코드 중에서 루브릭 총점 및 세부 항목 점수가 유효하게 기록된 턴 로그만 선별합니다.
        """
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
        """
        종합 성적 산출 대상에서 챕터 마감 노드(IMM_007 등)와 같이 점수가 배정되지 않는 노드를 필터링하여 제외합니다.
        """
        non_final_records = [
            record
            for record in scored_records
            if str(record.get("node_id", "")) not in FINAL_DECISION_NODE_IDS
        ]
        return non_final_records or scored_records

    def _quantitative_scores(self, included_records: list[dict[str, Any]]) -> QuantitativeScores:
        """
        수집된 턴별 성적 레코드를 비행(flight), 입국심사(immigration), 수하물(baggage) 등 
        영역별 가중치를 반영해 백분율 환산 영역 점수 및 최종 종합 점수(overall)를 산출합니다.
        """
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
        """
        노드 ID 접두사를 검사하여 해당 기록의 대화 상황 영역 분류 키(flight, immigration, baggage)를 결정합니다.
        """
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
        """
        종합 점수와 플레이어 최종 수치(인내심 고갈 여부, 누적 의심도 등), 심각한 실패(Critical Fail) 감지 여부를 분석해 
        최종 통과 등급과 그 판정 태그 목록을 튜플로 반환합니다.
        """
        reason_tags: list[str] = ["scene_normalized_dimension_average_policy"]
        verdicts = [self._verdict(record) for record in included_records]
        has_critical_fail = any(verdict == "CRITICAL_FAIL" for verdict in verdicts)
        has_non_success = any(verdict in {"FAIL", "PARTIAL", "UNCLEAR"} for verdict in verdicts)

        has_verbal_abuse = False
        for record in included_records:
            eval_dict = record.get("evaluation") or {}
            tags = eval_dict.get("feedback_tags") or []
            if "verbal_abuse" in tags:
                has_verbal_abuse = True
                break

        if has_verbal_abuse:
            reason_tags.append("verbal_abuse")
            return "COMIC_FAIL", reason_tags

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
        """
        최종 합격 추천 결과와 점수를 기반으로 시각적인 골드/실버/브론즈 패스 등급 명칭을 정해 반환합니다.
        """
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
        """
        가장 잘 수행한 턴, 가장 개선이 필요했던 턴, 피드백 분석 결과 등을 종합해 요약 안내 보고서 객체를 생성합니다.
        """
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
        """
        종합 성적 결과(합격, 조건부 등)에 따라 성적 리포트 상단에 전시할 요약 설명 텍스트를 반환합니다.
        """
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
        """
        지정된 턴 로그에서 핵심 개선 지침 사항을 읽어와 문자열로 반환합니다.
        """
        report_item = record.get("report_item")
        if isinstance(report_item, dict):
            improvement = report_item.get("improvement")
            if isinstance(improvement, str) and improvement.strip():
                return improvement
        return "Keep answers concise and polite."

    def _state_from_records(self, records: list[dict[str, Any]]) -> FinalScoreState:
        """
        세션 대화 로그들의 상태 변동량(State Delta)을 누적 연산하여 인내심, 의심도 등의 최종 게임 수치를 복원합니다.
        """
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
        """
        세션 로그 전체를 탐색하며 교정이 필요한 형태 초점(Focus on Form) 주제 명칭들을 수집하여 중복 없이 반환합니다.
        """
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
        """
        레코드 내 평가 객체(evaluation)로부터 이번 턴 판정 결과(verdict) 값을 문자열로 안전하게 추출합니다.
        """
        evaluation = record.get("evaluation")
        if not isinstance(evaluation, dict):
            return ""
        verdict = evaluation.get("verdict")
        return str(verdict) if verdict is not None else ""

    def _rubric_total_to_100(self, total: int) -> int:
        """
        최대 12점인 루브릭 총점 수치를 100점 만점 기준으로 변환하여 정밀하게 반올림합니다.
        """
        return _round_half_up(total / 12 * 100)

    def _rubric_dimension_to_100(self, value: int) -> int:
        """
        최대 2점인 세부 항목 수치를 100점 만점 기준으로 변환하여 반올림합니다.
        """
        return _round_half_up(value / 2 * 100)

    def _unranked_result(self) -> FinalResult:
        """
        평가 가능한 세션 기록 데이터가 존재하지 않을 때, 안전하게 출력할 기본 초기화 빈 성적표를 빌드합니다.
        """
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
    """
    정수 리스트의 평균을 계산하여 사사오입(반올림) 연산 후 정수로 반환합니다.
    """
    return _round_half_up(sum(values) / len(values))


def _round_half_up(value: float) -> int:
    """
    파이썬의 기본 사사오입 대신 보편적인 수학 반올림(Round half up)을 수행합니다.
    """
    return math.floor(value + 0.5)


def _int_value(value: Any) -> int:
    """
    정수 타입인 경우 값을 그대로 반환하고, 그렇지 않으면 0을 반환하여 타입 에러를 방지합니다.
    """
    return value if isinstance(value, int) else 0


def _unique(values: list[str]) -> list[str]:
    """
    문자열 리스트의 순서를 유지하며 중복된 요소를 고유하게 걸러내어 반환합니다.
    """
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
