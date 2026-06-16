from __future__ import annotations

import json
from pathlib import Path

def test_scenario_nodes_bad_ending_existence_and_types() -> None:
    json_path = Path("backend/app/data/scenario_nodes.json")
    assert json_path.exists(), "scenario_nodes.json file must exist"
    
    data = json.loads(json_path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", {})
    
    expected_nodes = [
        "FLIGHT_BAD_END_VERBAL_ABUSE",
        "IMM_BAD_END_VERBAL_ABUSE",
        "BAG_BAD_END_VERBAL_ABUSE"
    ]
    
    for node_id in expected_nodes:
        assert node_id in nodes, f"Node {node_id} must exist in scenario_nodes.json"
        node = nodes[node_id]
        
        assert node.get("node_type") == "ending", f"Node {node_id} must have type ending"
        
        transition = node.get("transition", {})
        assert transition.get("unreal_event") == "SHOW_BAD_END_SCOREBOARD", f"Node {node_id} transition must trigger SHOW_BAD_END_SCOREBOARD"
        assert transition.get("next_chapter_id") == "CH0_05_RESULT", f"Node {node_id} transition must route to CH0_05_RESULT"
        
        branch_candidates = node.get("branch_candidates", {})
        for candidate_key, candidate_val in branch_candidates.items():
            assert candidate_val == node_id, f"Node {node_id} branch candidate {candidate_key} must point to itself"
