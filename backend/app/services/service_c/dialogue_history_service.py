"""B가 기록 시점에 알 수 없는 대화 히스토리 정보를 C가 보관합니다.

초보자용 설명:
Developer B는 Developer A가 최종 NPC 대사를 만들기 전에 OpenKB 정책 기록을
작성합니다. 그래서 B 기록에는 플레이어 답변과 분기 결과는 남지만, 최종
`npc.text`는 들어갈 수 없습니다. 이 C-owned 서비스는 A가 응답한 뒤 작은
sidecar 기록을 남깁니다. 다음 턴에서는 이 sidecar를 B 세션 기록과 조인해서,
B-owned OpenKB 파일을 수정하지 않고도 A에게 "직전에 NPC가 실제로 한 말"을
전달할 수 있습니다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import (
    DevADialogueOutput,
    DevBPolicyOutput,
    NormalizedInput,
    PrePrototypeRequest,
    UnderstandingOutput,
)


class DialogueHistoryService:
    """C-owned NPC 대사 히스토리 sidecar 기록을 저장하고 읽습니다.

    초보자용 설명:
    이 클래스는 의도적으로 `backend/runtime/openkb/dev_b`가 아니라
    `backend/runtime/openkb/dev_c` 아래에 기록합니다. Developer C는 최종
    오케스트레이션 순서를 알고 있고, 플레이어 발화와 Developer A의 최종 NPC 대사를
    모두 볼 수 있습니다. 그래서 C가 작은 조인 테이블을 따로 유지하면 이후
    `dialogue_history` payload를 만들 때 안전하게 사용할 수 있습니다.
    """

    namespace = "dev_c"

    def __init__(self, runtime_root: Path | None = None) -> None:
        self.runtime_root = runtime_root or Path("backend/runtime/openkb/dev_c/dialogue_history")

    def write_turn_dialogue(
        self,
        *,
        request: PrePrototypeRequest,
        normalized_input: NormalizedInput,
        understanding: UnderstandingOutput,
        dev_b_output: DevBPolicyOutput,
        dev_a_output: DevADialogueOutput,
    ) -> dict[str, Any]:
        """한 턴의 최종 NPC 대사를 C-owned sidecar 저장소에 추가합니다.

        초보자용 설명:
        `record_id`를 기준으로 중복 쓰기를 막습니다. 로컬 테스트 중 같은 요청이
        다시 실행되더라도 C는 같은 NPC 히스토리 row를 두 번 append하지 않습니다.
        """

        if str(self.runtime_root).strip() == "":
            raise ValueError("Dialogue history runtime_root must not be empty.")

        record = self._build_record(
            request=request,
            normalized_input=normalized_input,
            understanding=understanding,
            dev_b_output=dev_b_output,
            dev_a_output=dev_a_output,
        )
        record_id = str(record["record_id"])
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        jsonl_path = self.runtime_root / f"{request.turn.session.session_id}.jsonl"

        if not self._record_exists(jsonl_path, record_id):
            with jsonl_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                file.write("\n")

        return {
            "attempted": True,
            "succeeded": True,
            "namespace": self.namespace,
            "record_id": record_id,
            "jsonl_path": str(jsonl_path),
            "npc_text_preview": _preview(dev_a_output.text),
        }

    def read_session_records(self, session_id: str) -> list[dict[str, Any]]:
        """하나의 세션에 대한 C-owned sidecar 기록을 읽습니다."""

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

    def _build_record(
        self,
        *,
        request: PrePrototypeRequest,
        normalized_input: NormalizedInput,
        understanding: UnderstandingOutput,
        dev_b_output: DevBPolicyOutput,
        dev_a_output: DevADialogueOutput,
    ) -> dict[str, Any]:
        record_id = self._record_id(request)
        return {
            "namespace": self.namespace,
            "record_schema_version": "dev_c_dialogue_history.v1",
            "record_kind": "npc_dialogue_turn",
            "record_id": record_id,
            "request_id": request.turn.request_id,
            "session_id": request.turn.session.session_id,
            "player_id": request.turn.session.player_id,
            "chapter_id": request.turn.session.chapter_id,
            "scene_id": request.turn.session.scene_id,
            "node_id": request.turn.session.current_node_id,
            "turn_index": request.turn.session.turn_index,
            "player_text": normalized_input.player_text,
            "understanding": {
                "intent": understanding.intent,
                "confidence": understanding.confidence,
                "extracted_slots": dict(understanding.extracted_slots),
            },
            "branch": dev_b_output.branch.model_dump(),
            "dialogue_seed": (
                dev_b_output.dialogue_seed.model_dump()
                if dev_b_output.dialogue_seed is not None
                else None
            ),
            "npc": {
                "speaker": dev_a_output.speaker,
                "text": dev_a_output.text,
                "tone": dev_a_output.tone,
                "animation": dev_a_output.animation,
                "audio_url": dev_a_output.audio_url,
            },
        }

    def _record_id(self, request: PrePrototypeRequest) -> str:
        raw_key = ":".join(
            [
                request.turn.request_id,
                request.turn.session.current_node_id,
                str(request.turn.session.turn_index),
            ]
        )
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
        return f"dev_c_dialogue_{digest}"

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


def _preview(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
