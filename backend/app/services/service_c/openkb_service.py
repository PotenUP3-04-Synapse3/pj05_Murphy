"""Load scenario node context for Developer C.

Beginner guide:
OpenKB is the local knowledge source for scenario nodes.  Given a chapter id
and node id, this service reads `scenario_nodes.json`, validates the requested
node, and converts raw JSON into the `NodeContext` schema used by
Understanding, Developer B, and response validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

from backend.app.schemas.game_turn import HintPolicy, NodeContext

NodeType = Literal["dialogue", "transition", "result", "ending"]
_ALLOWED_NODE_TYPES = {"dialogue", "transition", "result", "ending"}


class OpenKBService:
    def __init__(self, scenario_node_path: Path | None = None) -> None:
        self.scenario_node_path = scenario_node_path or Path("backend/app/data/scenario_nodes.json")

    def get_node_context(self, chapter_id: str, current_node_id: str) -> NodeContext:
        payload = self._load_scenario_nodes()
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
            scenario_id=str(payload.get("scenario_id", "ALPHA_AIRPORT_ARRIVAL")),
            chapter_id=str(node["chapter_id"]),
            node_type=_parse_node_type(node.get("node_type", "dialogue"), current_node_id),
            transition=node.get("transition"),
            npc_question=str(node["npc_question"]),
            npc_question_goal=str(node["npc_question_goal"]),
            objective_kr=node.get("objective_kr"),
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


def _parse_node_type(value: Any, current_node_id: str) -> NodeType:
    if not isinstance(value, str) or value not in _ALLOWED_NODE_TYPES:
        raise ValueError(f"Unsupported node_type for {current_node_id}: {value!r}")
    return cast(NodeType, value)
