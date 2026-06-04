from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.schemas.game_turn import HintPolicy, NodeContext


class OpenKBService:
    def __init__(self, scenario_node_path: Path | None = None) -> None:
        self.scenario_node_path = scenario_node_path or Path("backend/app/data/scenario_nodes.json")

    def get_node_context(self, chapter_id: str, current_node_id: str) -> NodeContext:
        payload = self._load_scenario_nodes()
        if payload.get("chapter_id") != chapter_id:
            raise ValueError(f"Unsupported chapter: {chapter_id}")

        nodes = payload.get("nodes")
        if not isinstance(nodes, dict):
            raise ValueError("Scenario node data must include a nodes object.")

        node = nodes.get(current_node_id)
        if not isinstance(node, dict):
            raise ValueError(f"Unsupported node: {chapter_id}/{current_node_id}")

        if node.get("chapter_id") != chapter_id:
            raise ValueError(f"Node chapter mismatch: {chapter_id}/{current_node_id}")

        branch_candidates = node.get("branch_candidates")
        if not isinstance(branch_candidates, dict):
            raise ValueError(f"Node is missing branch candidates: {current_node_id}")

        return NodeContext(
            node_id=str(node["node_id"]),
            chapter_id=str(node["chapter_id"]),
            npc_question=str(node["npc_question"]),
            npc_question_goal=str(node["npc_question_goal"]),
            required_intents=list(node["required_intents"]),
            required_slots=list(node["required_slots"]),
            optional_slots=list(node.get("optional_slots", [])),
            critical_slots=list(node.get("critical_slots", [])),
            allowed_slot_values=dict(node.get("allowed_slot_values", {})),
            risk_keywords=list(node.get("risk_keywords", [])),
            recommended_expression=str(node["recommended_expression"]),
            base_hint_kr=str(node["base_hint_kr"]),
            hint_policy=HintPolicy(**node["hint_policy"]),
            success_next_node=str(branch_candidates["success"]),
            retry_next_node=str(branch_candidates["retry"]),
            clarify_next_node=str(branch_candidates["clarify"]),
            hint_next_node=str(branch_candidates["hint"]),
            warning_next_node=str(branch_candidates["warning"]),
            allowed_next_nodes=list(node["allowed_next_nodes"]),
        )

    def _load_scenario_nodes(self) -> dict[str, Any]:
        return json.loads(self.scenario_node_path.read_text(encoding="utf-8"))
