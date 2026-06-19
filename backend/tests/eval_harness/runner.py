import json
import os
import yaml  # type: ignore[import-untyped]
from typing import Any, Dict, List
from backend.app.agents.agent_a.npc_dialogue_agent import generate_npc_dialogue_from_level_design
from backend.app.services.service_a.npc_roster_service import resolve_npc_profile

# 프로젝트 루트 경로를 기준으로 scenario_nodes.json의 경로를 확인합니다.
_SCENARIO_NODES_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "app", "data", "scenario_nodes.json")
)

def _load_scenario_nodes() -> Dict[str, Any]:
    """scenario_nodes.json 파일을 안전하게 로드합니다."""
    if not os.path.exists(_SCENARIO_NODES_PATH):
        raise FileNotFoundError(f"시나리오 노드 파일이 존재하지 않습니다: {_SCENARIO_NODES_PATH}")
    with open(_SCENARIO_NODES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """두 개의 사전을 재귀적으로 결합(Deep Merge)합니다."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def build_base_payload(npc_id: str, node_id: str, scenario_id: str = "default") -> Dict[str, Any]:
    """지정된 NPC ID 및 노드 ID에 맞춘 최소 유효성 페이로드(Payload)를 조립합니다."""
    # NPC 프로필을 로스터 서비스에서 검색
    profile = resolve_npc_profile(npc_id)
    
    # 시나리오 노드 메타 정보 획득
    try:
        nodes_data = _load_scenario_nodes()
        node_meta = nodes_data.get("nodes", {}).get(node_id, {})
    except Exception:
        node_meta = {}

    recommended_expr = node_meta.get("recommended_expression", "")
    npc_question = node_meta.get("npc_question", "")
    npc_question_goal = node_meta.get("npc_question_goal", "")

    # 세션 ID는 시나리오 ID 기반으로 deterministic하게 설정
    session_id = f"eval_{scenario_id}"

    base_payload = {
        "session_id": session_id,
        "npc": {
            "npc_id": profile.npc_id,
            "display_name": profile.display_name,
            "role": profile.role,
        },
        "node_id": node_id,
        "player_text": "",
        "node_context": {
            "node_id": node_id,
            "npc_question": npc_question,
            "recommended_expression": recommended_expr,
        },
        "evaluation_summary": {
            "task_success": True,
            "clarity": 0.9,
        },
        "level_hint": {
            "english_level": "intermediate",
            "recommended_expression": recommended_expr,
        },
        "in_game_feedback": {
            "npc_recast_line_candidate": None
        },
        "dialogue_seed": {
            "surface_goal": npc_question_goal
        },
        "branch": {
            "branch_type": "success"
        },
        "incivility": {
            "tier": 0
        }
    }
    return base_payload

def run_scenario(scenario: Dict[str, Any], *, use_llm: bool = False, llm_client: Any = None) -> Dict[str, Any]:
    """개별 시나리오를 로드하여 대화 턴(Turn)을 시뮬레이션하고 결과를 수집합니다."""
    scenario_id = scenario["id"]
    npc_id = scenario["npc_id"]
    node_id = scenario["node_id"]
    player_inputs = scenario.get("player_inputs", [])
    expected = scenario.get("expected", {})
    payload_overrides = scenario.get("payload_overrides", {})

    # 베이스 페이로드 빌드 및 오버라이드 병합
    payload = build_base_payload(npc_id, node_id, scenario_id)
    payload = _deep_merge(payload, payload_overrides)

    turns = []
    
    # 순차적으로 다중 턴(Multi-turn) 실행
    for player_input in player_inputs:
        # 단일 턴 데이터 업데이트
        current_payload = payload.copy()
        current_payload["player_text"] = player_input
        
        # NPC 대사 에이전트 구동
        result = generate_npc_dialogue_from_level_design(
            current_payload,
            use_llm=use_llm,
            llm_client=llm_client
        )
        
        turns.append({
            "player_text": player_input,
            "result": result
        })
        
        # 다음 턴을 위해 메모리 등에 상태 전파할 수 있도록 페이로드 정보 보정 가능
        # (필요한 경우 result 대사를 dialogue_history에 축적하는 로직을 추가하여 멀티턴을 더 사실적으로 묘사)

    return {
        "scenario_id": scenario_id,
        "npc_id": npc_id,
        "node_id": node_id,
        "turns": turns,
        "expected": expected
    }

def load_all_scenarios() -> List[Dict[str, Any]]:
    """scenarios 디렉토리 내의 모든 YAML 시나리오 파일을 찾아 단일 리스트로 병합하여 반환합니다."""
    scenarios_dir = os.path.join(os.path.dirname(__file__), "scenarios")
    if not os.path.exists(scenarios_dir):
        return []
        
    scenarios = []
    for filename in os.listdir(scenarios_dir):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(scenarios_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f)
                    if isinstance(data, list):
                        scenarios.extend(data)
                    elif isinstance(data, dict):
                        scenarios.append(data)
                except Exception as e:
                    print(f"YAML 파싱 에러 ({filename}): {e}")
                    
    return scenarios
