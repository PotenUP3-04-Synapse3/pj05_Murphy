from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import DevBPolicyInput, DevBPolicyOutput, OpenKBWriteResult


class OpenKBFeedbackWriter:
    namespace = "dev_b"

    def __init__(
        self,
        *,
        runtime_root: Path | None = None,
        content_root: Path | None = None,
    ) -> None:
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")
        self.content_root = content_root or Path("backend/app/kb/dev_b")

    def write_policy_output(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> OpenKBWriteResult:
        if str(self.runtime_root).strip() == "":
            raise ValueError("OpenKB runtime_root must not be empty.")

        record = self._build_record(payload, output)
        record_id = str(record["record_id"])
        self.runtime_root.mkdir(parents=True, exist_ok=True)

        jsonl_path = self.runtime_root / f"{payload.session_id}.jsonl"
        markdown_path = self.runtime_root / f"{record_id}.md"

        if not self._record_exists(jsonl_path, record_id):
            with jsonl_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                file.write("\n")

        if not markdown_path.exists():
            markdown_path.write_text(self._build_markdown(record), encoding="utf-8")

        return OpenKBWriteResult(
            attempted=True,
            succeeded=True,
            namespace=self.namespace,
            record_id=record_id,
            jsonl_path=str(jsonl_path),
            markdown_path=str(markdown_path),
            error_message=None,
        )

    def failure_result(self, error: Exception) -> OpenKBWriteResult:
        return OpenKBWriteResult(
            attempted=True,
            succeeded=False,
            namespace=self.namespace,
            record_id=None,
            jsonl_path=None,
            markdown_path=None,
            error_message=str(error),
        )

    def _build_record(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> dict[str, Any]:
        error_ids = [item.error_id for item in output.error_capture.error_items] or ["no_error"]
        record_id = self._record_id(payload, error_ids)
        return {
            "namespace": self.namespace,
            "record_schema_version": "dev_b_openkb_record.v2",
            "record_kind": "policy_turn_feedback",
            "record_id": record_id,
            "contract_version": output.contract_version,
            "request_id": payload.request_id,
            "session_id": payload.session_id,
            "player_id": payload.player_id,
            "chapter_id": payload.chapter_id,
            "scene_id": payload.scene_id,
            "node_id": payload.current_node_id,
            "turn_index": payload.turn_index,
            "player_text": payload.player_text,
            "input_source": payload.input_source.model_dump(),
            "understanding_summary_kr": payload.understanding.meaning_summary_kr,
            "evaluation": output.evaluation.model_dump(),
            "level_hint": output.level_hint.model_dump(),
            "error_capture": output.error_capture.model_dump(),
            "out_game_feedback_seed": output.out_game_feedback_seed.model_dump(),
            "focus_on_form_targets": output.out_game_feedback_seed.focus_on_form_targets,
            "report_item": output.report_item.model_dump(),
            "rubric_scores": output.rubric_scores.model_dump() if output.rubric_scores else None,
            "difficulty_profile": output.difficulty_profile.model_dump() if output.difficulty_profile else None,
            "feedback_generation": output.feedback_generation.model_dump() if output.feedback_generation else None,
            "branch": output.branch.model_dump(),
            "state_delta": output.state_delta.model_dump(),
        }

    def _record_id(self, payload: DevBPolicyInput, error_ids: list[str]) -> str:
        raw_key = ":".join(
            [
                payload.request_id,
                payload.current_node_id,
                str(payload.turn_index),
                ",".join(error_ids),
            ]
        )
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
        return f"dev_b_{digest}"

    def _record_exists(self, jsonl_path: Path, record_id: str) -> bool:
        if not jsonl_path.exists():
            return False
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if existing.get("record_id") == record_id:
                return True
        return False

    def _build_markdown(self, record: dict[str, Any]) -> str:
        report_item = record["report_item"]
        error_capture = record["error_capture"]
        focus_targets = ", ".join(record["focus_on_form_targets"]) or "none"
        feedback_generation = record.get("feedback_generation") or {}
        difficulty_profile = record.get("difficulty_profile") or {}
        lines = [
            f"# Developer B OpenKB Record - {record['record_id']}",
            "",
            f"- Record Schema: {record['record_schema_version']}",
            f"- Record Kind: {record['record_kind']}",
            f"- Session: {record['session_id']}",
            f"- Request: {record['request_id']}",
            f"- Node: {record['node_id']}",
            f"- Turn: {record['turn_index']}",
            f"- Player Text: {record['player_text']}",
            f"- Verdict: {record['evaluation']['verdict']}",
            f"- Branch: {record['branch']['branch_type']} -> {record['branch']['next_node_id']}",
            f"- Focus-on-Form: {focus_targets}",
            f"- Feedback Generation: {feedback_generation.get('mode', 'unknown')}",
            f"- Difficulty: {difficulty_profile.get('travel_speaking_level', 'unknown')}",
            "",
            "## Report Seed",
            "",
            f"- Summary: {report_item['summary']}",
            f"- Improvement: {report_item['improvement']}",
            f"- Example: {report_item['example_answer']}",
            "",
            "## Error Capture",
            "",
            error_capture.get("markdown_entry") or "No error markdown entry.",
            "",
        ]
        return "\n".join(lines)
