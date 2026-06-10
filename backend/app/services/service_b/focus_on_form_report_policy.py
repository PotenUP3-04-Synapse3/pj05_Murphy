from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CARD_PATH = Path("backend/app/kb/dev_b/focus_on_form_cards.json")
PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3}


class FocusOnFormReportPolicy:
    def __init__(self, card_path: Path | None = None, runtime_root: Path | None = None) -> None:
        self.card_path = card_path or DEFAULT_CARD_PATH
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")

    def build_report(self, records: list[dict[str, Any]]) -> dict[str, Any]:
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
        jsonl_path = self.runtime_root / f"{session_id}.jsonl"
        if not jsonl_path.exists():
            return self.build_report([])

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
        return self.build_report(records)

    def _group_records(
        self,
        records: list[dict[str, Any]],
        cards: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
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
        matched_examples = self._examples_from_error_items(record, target)
        if matched_examples:
            for original, suggested in matched_examples:
                self._append_unique(item["original_utterances"], original)
                self._append_unique(item["suggested_expressions"], suggested)
            return

        self._append_unique(item["original_utterances"], str(record.get("player_text", "")))
        self._append_unique(item["suggested_expressions"], self._fallback_example(record))

    def _examples_from_error_items(self, record: dict[str, Any], target: str) -> list[tuple[str, str]]:
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
        report_item = record.get("report_item")
        if isinstance(report_item, dict):
            example = report_item.get("example_answer")
            if isinstance(example, str) and example.strip():
                return example
        return "I'm here for tourism."

    def _record_priority(self, record: dict[str, Any]) -> str:
        seed = record.get("out_game_feedback_seed")
        if isinstance(seed, dict):
            priority = seed.get("report_priority")
            if priority in PRIORITY_RANK:
                return str(priority)
        return "low"

    def _higher_priority(self, left: str, right: str) -> str:
        return left if PRIORITY_RANK.get(left, 1) >= PRIORITY_RANK.get(right, 1) else right

    def _load_cards(self) -> dict[str, dict[str, Any]]:
        if not self.card_path.exists():
            return {}
        payload = json.loads(self.card_path.read_text(encoding="utf-8"))
        cards = payload.get("cards")
        if not isinstance(cards, dict):
            return {}
        return {str(key): value for key, value in cards.items() if isinstance(value, dict)}

    def _append_unique(self, values: list[str], value: str) -> None:
        if value and value not in values:
            values.append(value)


def _unique_strings(values: list[Any]) -> list[str]:
    unique: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in unique:
            unique.append(text)
    return unique
