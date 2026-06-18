import json
from pathlib import Path

SCENARIO_NODE_PATH = Path("backend/app/data/scenario_nodes.json")

def test_scenario_nodes_referential_integrity() -> None:
    assert SCENARIO_NODE_PATH.exists(), "scenario_nodes.json file must exist"
    
    with open(SCENARIO_NODE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    nodes = data.get("nodes", {})
    defined_nodes = set(nodes.keys())
    
    referenced_nodes = set()
    for node_id, node in nodes.items():
        # branch candidates
        branch_candidates = node.get("branch_candidates", {})
        for key, val in branch_candidates.items():
            if val:
                referenced_nodes.add(val)
        # allowed_next_nodes
        allowed = node.get("allowed_next_nodes", [])
        for val in allowed:
            if val:
                referenced_nodes.add(val)
                
    # chapter entry nodes
    for chapter in data.get("chapters", []):
        entry = chapter.get("entry_node_id")
        if entry:
            referenced_nodes.add(entry)
        entries = chapter.get("entry_node_ids", [])
        for entry in entries:
            referenced_nodes.add(entry)
            
    missing = referenced_nodes - defined_nodes
    
    # Assert that missing nodes is completely empty
    assert len(missing) == 0, f"Referenced nodes {missing} are not defined in nodes DB of scenario_nodes.json"
