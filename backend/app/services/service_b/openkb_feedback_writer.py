from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import (
    DevBPolicyInput,
    DevBPolicyOutput,
    OpenKBWriteResult,
    PolicyTurnFeedbackRecord,
)


class OpenKBFeedbackWriter:
    """
    Developer B의 평가 정책 출력 결과를 OpenKB 데이터 저장소에 기록하는 라이터 클래스입니다.
    
    초보자 가이드: 플레이어의 발화에 대한 세부 평가 결과(성적 점수, 감정 정보, 피드백 등)를 
    세션별 JSONL 파일(누적) 및 개별 Markdown 파일(Turn별 상세 설명 문서)로 안전하게 하드디스크에 기록합니다.
    """
    namespace = "dev_b"

    def __init__(
        self,
        *,
        runtime_root: Path | None = None,
        content_root: Path | None = None,
    ) -> None:
        """
        OpenKB 저장소와 컨텐츠 경로를 초기화합니다.
        
        Args:
            runtime_root: 세션 로그가 저장될 런타임 디렉터리 경로
            content_root: 학습 콘텐츠 데이터가 들어 있는 디렉터리 경로
        """
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_b")
        self.content_root = content_root or Path("backend/app/kb/dev_b")

    def write_policy_output(
        self,
        payload: DevBPolicyInput,
        output: DevBPolicyOutput,
    ) -> OpenKBWriteResult:
        """
        정책 계산이 끝난 출력(output) 결과물을 기반으로 OpenKB 레코드를 빌드하고, 
        JSONL 로그 및 Markdown 문서를 파일 시스템에 물리적으로 기록합니다.
        
        Args:
            payload: 입력 상태 데이터
            output: 정책 실행 결과 데이터
            
        Returns:
            기록 성공 여부와 저장된 파일 경로 등을 담은 OpenKBWriteResult 객체
        """
        if str(self.runtime_root).strip() == "":
            raise ValueError("OpenKB runtime_root must not be empty.")

        record = self._build_record(payload, output)
        record_id = str(record["record_id"])
        self.runtime_root.mkdir(parents=True, exist_ok=True)

        record_file_key = payload.room_id or payload.session_id
        jsonl_path = self.runtime_root / f"{record_file_key}.jsonl"
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
        """
        기록 과정 중 예기치 못한 에러가 발생했을 때, 에러 기록을 남겨 에러 정보를 추적할 수 있도록 
        실패 결과(OpenKBWriteResult) 객체를 리턴합니다.
        """
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
        """
        OpenKB 저장소 규격에 맞춰 저장할 Turn별 상세 피드백 로그 딕셔너리를 빌드합니다.
        """
        error_ids = [item.error_id for item in output.error_capture.error_items] or ["no_error"]
        record_id = self._record_id(payload, error_ids)
        record = {
            "namespace": self.namespace,
            "record_schema_version": "dev_b_openkb_record.v2",
            "record_kind": "policy_turn_feedback",
            "record_id": record_id,
            "contract_version": output.contract_version,
            "request_id": payload.request_id,
            "session_id": payload.session_id,
            "player_id": payload.player_id,
            "room_id": payload.room_id,
            "chapter_id": payload.chapter_id,
            "scene_id": payload.scene_id,
            "node_id": payload.current_node_id,
            "turn_index": payload.turn_index,
            "player_text": payload.player_text,
            "input_source": payload.input_source.model_dump(),
            "understanding_summary_kr": payload.understanding.meaning_summary_kr,
            "understanding": payload.understanding.model_dump(),
            "evaluation": output.evaluation.model_dump(),
            "level_hint": output.level_hint.model_dump(),
            "error_capture": output.error_capture.model_dump(),
            "out_game_feedback_seed": output.out_game_feedback_seed.model_dump(),
            "report_seed_summary": output.report_seed_summary.model_dump() if output.report_seed_summary else None,
            "dialogue_seed": output.dialogue_seed.model_dump() if output.dialogue_seed else None,
            "focus_on_form_targets": output.out_game_feedback_seed.focus_on_form_targets,
            "report_item": output.report_item.model_dump(),
            "rubric_scores": output.rubric_scores.model_dump() if output.rubric_scores else None,
            "difficulty_profile": output.difficulty_profile.model_dump() if output.difficulty_profile else None,
            "feedback_generation": output.feedback_generation.model_dump() if output.feedback_generation else None,
            "branch": output.branch.model_dump(),
            "state_delta": output.state_delta.model_dump(),
            "speaker_player_id": payload.speaker_player_id,
            "bag_owner_player_id": payload.bag_owner_player_id,
            "addressed_player_id": payload.addressed_player_id,
        }
        # Validate through Pydantic record schema (WP-R0)
        validated_record = PolicyTurnFeedbackRecord.model_validate(record)
        return validated_record.model_dump()

    def _record_id(self, payload: DevBPolicyInput, error_ids: list[str]) -> str:
        """
        요청 ID, 노드 ID, 턴 수, 에러 코드 조합을 SHA-256 해싱하여 16자리의 고유한 레코드 ID를 생성합니다.
        """
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
        """
        기존 JSONL 파일에서 동일한 고유 레코드 ID를 가진 엔트리가 존재하는지 검사합니다.
        """
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
        """
        빌드된 레코드 딕셔너리를 활용하여 한눈에 보기 편한 Markdown 피드백 상세 보고서 문서를 동적으로 작성합니다.
        """
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
