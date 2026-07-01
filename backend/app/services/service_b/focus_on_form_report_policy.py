from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CARD_PATH = Path("backend/app/kb/dev_b/focus_on_form_cards.json")
PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3}


class FocusOnFormReportPolicy:
    """
    학습자가 게임 중 취약했던 문법이나 영어 표현(Focus-on-Form)에 대한 맞춤형 교정 리포트를 생성하는 정책 클래스입니다.
    
    초보자 가이드: 플레이어가 게임을 플레이하는 동안 기록된 오류(error_capture) 데이터를 수집하고 분류합니다. 
    가장 자주 틀렸거나 심각도가 높은 표현 문제(priority 순)를 추려내어, 
    어느 상황(node_id)에서 어떤 오답(original_utterances)을 냈고 어떻게 고쳐야 하는지(suggested_expressions) 
    개별 학습 카드 형식으로 리포트를 가공해 줍니다.
    """
    def __init__(self, card_path: Path | None = None, runtime_root: Path | None = None) -> None:
        """
        교정 카드 정보가 담긴 JSON 경로와 세션 로그의 저장 경로를 설정하여 정책 객체를 초기화합니다.
        
        Args:
            card_path: Focus-on-Form 카드 정보가 저장된 JSON 파일 경로 (기본값: focus_on_form_cards.json)
            runtime_root: 읽어올 세션 로그 파일들이 저장된 디렉터리 경로
        """
        self.card_path = card_path or DEFAULT_CARD_PATH
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")

    def build_report(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """
        주어진 대화 턴 레코드 목록을 분석하여 최종 Focus-on-Form 리포트 데이터를 생성합니다.
        
        Args:
            records: 이번 플레이 세션의 턴별 로그 레코드 리스트
            
        Returns:
            학습 카드 리스트와 다음 추천 연습 문구가 담긴 리포트 딕셔너리
        """
        cards = self._load_cards()
        grouped = self._group_records(records, cards)
        if not grouped:
            return {
                "report_mode": "focus_on_form",
                "overall_summary_kr": "아직 최종 리포트에 포함할 Focus-on-Form 기록이 없습니다.",
                "focus_on_form_items": [],
                "personalized_next_step": {
                    "target": None,
                    "practice_prompt_kr": "다음 플레이에서 공항 상황을 한 문장으로 답해보세요.",
                    "answer_example": "I'm here for tourism.",
                },
            }

        items = sorted(
            grouped.values(),
            key=lambda item: (-PRIORITY_RANK.get(str(item["priority"]), 1), -int(item["occurrence_count"])),
        )
        for item in items:
            item.pop("occurrence_count", None)

        self._dedupe_examples_across_items(items)

        top_item = items[0]
        return {
            "report_mode": "focus_on_form",
            "overall_summary_kr": "이번 플레이에서 반복된 영어 표현 이슈를 Focus-on-Form 기준으로 정리했습니다.",
            "focus_on_form_items": items,
            "personalized_next_step": {
                "target": top_item["focus_on_form_target"],
                "practice_prompt_kr": top_item["practice_prompt_kr"],
                "answer_example": top_item["answer_example"],
            },
        }

    def build_session_report(self, session_id: str) -> dict[str, Any]:
        """
        세션 ID를 입력받아 저장된 세션 로그 파일을 조회하고, Focus-on-Form 성적표를 빌드합니다.
        
        Args:
            session_id: 분석할 게임 세션 ID
            
        Returns:
            빌드된 학습 피드백 리포트 딕셔너리
        """
        from backend.app.services.service_b.final_result_score_policy import OpenKBFinalResultRecordReader
        reader = OpenKBFinalResultRecordReader(runtime_root=self.runtime_root)
        records = reader.read_session_records(session_id)
        return self.build_report(records)

    def _dedupe_examples_across_items(self, items: list[dict[str, Any]]) -> None:
        """
        여러 학습 카드에 걸쳐 동일한 모범 표현(suggested_expressions)이 반복 노출되지 않도록
        전역 중복을 제거합니다. 폴백 시 카드마다 같은 recommended_expression이 채워져
        최종 화면에서 "같은 문장이 여러 번" 보이던 문제를 방지합니다.

        각 카드는 최소 한 개의 모범 표현을 유지합니다(모두 중복이면 answer_example로 보강).
        """
        seen: set[str] = set()
        for item in items:
            deduped: list[str] = []
            for expression in item.get("suggested_expressions", []):
                if expression in seen:
                    continue
                seen.add(expression)
                deduped.append(expression)
            if not deduped:
                fallback = str(item.get("answer_example", ""))
                deduped = [fallback] if fallback else list(item.get("suggested_expressions", []))[:1]
            item["suggested_expressions"] = deduped

    def _group_records(
        self,
        records: list[dict[str, Any]],
        cards: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """
        입력된 대화 레코드들을 순회하며, 교정 대상 형태(focus_on_form_targets)별로 데이터를 그룹핑합니다.
        """
        grouped: dict[str, dict[str, Any]] = {}
        for record in records:
            targets = self._focus_targets(record)
            for target in targets:
                item = grouped.setdefault(target, self._new_item(target, cards.get(target), record))
                item["occurrence_count"] = int(item["occurrence_count"]) + 1
                self._append_unique(item["source_node_ids"], str(record.get("node_id", "")))
                self._append_record_examples(item, record, target)
                item["priority"] = self._higher_priority(str(item["priority"]), self._record_priority(record))
        return grouped

    def _new_item(
        self,
        target: str,
        card: dict[str, Any] | None,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """
        특정 교정 대상 형태에 대한 리포트 카드 템플릿(딕셔너리)을 신규 생성합니다.
        """
        fallback_example = self._fallback_example(record)
        return {
            "focus_on_form_target": target,
            "title_kr": str((card or {}).get("title_kr") or "표현 명확하게 다듬기"),
            "rule_summary_kr": str(
                (card or {}).get("rule_summary_kr") or "상황에 맞는 핵심 정보를 더 명확한 영어 문장으로 말해보세요."
            ),
            "original_utterances": [],
            "suggested_expressions": [],
            "practice_prompt_kr": str(
                (card or {}).get("practice_prompt_kr") or "같은 상황을 더 명확한 영어 문장으로 다시 말해보세요."
            ),
            "answer_example": str((card or {}).get("answer_example") or fallback_example),
            "priority": self._record_priority(record),
            "source_node_ids": [],
            "occurrence_count": 0,
        }

    def _focus_targets(self, record: dict[str, Any]) -> list[str]:
        """
        레코드에서 리포트에 포함할 형태 초점(Focus on Form) 교정 대상 키워드 목록을 수집합니다.
        """
        seed = record.get("out_game_feedback_seed")
        if isinstance(seed, dict):
            if seed.get("include_in_final_report") is False:
                return []
            values = seed.get("focus_on_form_targets")
            if isinstance(values, list) and values:
                return _unique_strings(values)
        values = record.get("focus_on_form_targets")
        if isinstance(values, list):
            return _unique_strings(values)
        return []

    def _append_record_examples(self, item: dict[str, Any], record: dict[str, Any], target: str) -> None:
        """
        현재 턴 레코드에서 플레이어 오답과 추천 표현 예시를 찾아와 리포트 카드의 예시 목록에 추가합니다.
        """
        matched_examples = self._examples_from_error_items(record, target)
        if matched_examples:
            for original, suggested in matched_examples:
                self._append_unique(item["original_utterances"], original)
                self._append_unique(item["suggested_expressions"], suggested)
            return

        self._append_unique(item["original_utterances"], str(record.get("player_text", "")))
        self._append_unique(item["suggested_expressions"], self._fallback_example(record))

    def _examples_from_error_items(self, record: dict[str, Any], target: str) -> list[tuple[str, str]]:
        """
        턴 에러 감지 결과(Error Capture)에서 해당 타겟에 매칭되는 오답 및 추천 수정본의 쌍들을 리스트로 찾아 반환합니다.
        """
        error_capture = record.get("error_capture")
        if not isinstance(error_capture, dict):
            return []
        error_items = error_capture.get("error_items")
        if not isinstance(error_items, list):
            return []

        examples: list[tuple[str, str]] = []
        for item in error_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("focus_on_form_target", "")) != target:
                continue
            original = str(item.get("original_utterance") or record.get("player_text") or "")
            suggested = str(item.get("suggested_expression") or self._fallback_example(record))
            examples.append((original, suggested))
        return examples

    def _fallback_example(self, record: dict[str, Any]) -> str:
        """
        모범 추천 표현을 찾지 못했을 때 사용할 기본 폴백용 문구를 추출하여 반환합니다.
        """
        report_item = record.get("report_item")
        if isinstance(report_item, dict):
            example = report_item.get("example_answer")
            if isinstance(example, str) and example.strip():
                return example
        return "I'm here for tourism."

    def _record_priority(self, record: dict[str, Any]) -> str:
        """
        해당 레코드의 리포트 반영 우선순위 수준(low, medium, high)을 확인합니다.
        """
        seed = record.get("out_game_feedback_seed")
        if isinstance(seed, dict):
            priority = seed.get("report_priority")
            if priority in PRIORITY_RANK:
                return str(priority)
        return "low"

    def _higher_priority(self, left: str, right: str) -> str:
        """
        두 우선순위 등급 중에서 가중치가 더 높은 쪽의 등급명을 반환합니다.
        """
        return left if PRIORITY_RANK.get(left, 1) >= PRIORITY_RANK.get(right, 1) else right

    def _load_cards(self) -> dict[str, dict[str, Any]]:
        """
        Focus-on-Form 카드 사전 데이터베이스 파일(cards.json)을 읽어 딕셔너리로 불러옵니다.
        """
        if not self.card_path.exists():
            return {}
        payload = json.loads(self.card_path.read_text(encoding="utf-8"))
        cards = payload.get("cards")
        if not isinstance(cards, dict):
            return {}
        return {str(key): value for key, value in cards.items() if isinstance(value, dict)}

    def _append_unique(self, values: list[str], value: str) -> None:
        """
        리스트에 중복되지 않고 값이 비어있지 않은 문자열 요소만 추가합니다.
        """
        if value and value not in values:
            values.append(value)


def _unique_strings(values: list[Any]) -> list[str]:
    """
    제공된 리스트에서 중복을 없애고 유효한 문자열들만 고유 리스트로 조립하여 반환합니다.
    """
    unique: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in unique:
            unique.append(text)
    return unique
