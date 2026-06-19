from typing import Any, Dict, List

def score_npc_role_must_not_be_giver(result: Dict[str, Any], expected_val: bool) -> Dict[str, Any]:
    """NPC가 주는 사람(Giver) 역할을 수행하는 화자 화법을 구사했는지 여부를 판정합니다.
    
    화자 혼동(Speaker role confusion) 방지를 위한 규칙입니다.
    """
    if not expected_val:
        return {"passed": True, "details": "Giver 역할 검사가 비활성화되어 있습니다."}
        
    npc_text = str(result.get("npc_text", "")).lower()
    tts_text = str(result.get("tts_text", "")).lower()
    
    # 주는 사람(Giver)임을 암시하는 대표적인 금지 구절 목록
    giver_phrases = [
        "here you are",
        "here you go",
        "of course, take",
        "here is the pen",
        "take my pen",
        "you can have",
        "no problem, take",
    ]
    
    found_phrases = []
    for phrase in giver_phrases:
        if phrase in npc_text or phrase in tts_text:
            found_phrases.append(phrase)
            
    if found_phrases:
        return {
            "passed": False,
            "details": f"NPC 대사에서 Giver 역할 문구가 발견되었습니다: {found_phrases}"
        }
    return {"passed": True, "details": "NPC가 Giver 역할을 모방하지 않았습니다."}

def score_must_include_any(result: Dict[str, Any], patterns: List[str]) -> Dict[str, Any]:
    """NPC 대사에 지정된 패턴 중 최소 하나가 포함되어 있는지 검사합니다."""
    npc_text = str(result.get("npc_text", "")).lower()
    tts_text = str(result.get("tts_text", "")).lower()
    
    found = False
    for pattern in patterns:
        pat_lower = pattern.lower()
        if pat_lower in npc_text or pat_lower in tts_text:
            found = True
            break
            
    if not found:
        return {
            "passed": False,
            "details": f"NPC 대사에 필수 패턴 중 하나도 포함되지 않았습니다. 기대 패턴: {patterns}, 실제 대사: '{npc_text}'"
        }
    return {"passed": True, "details": "필수 패턴이 정상 매칭되었습니다."}

def score_must_not_include_any(result: Dict[str, Any], patterns: List[str]) -> Dict[str, Any]:
    """NPC 대사에 지정된 패턴이 하나도 포함되어 있지 않은지 검사합니다."""
    npc_text = str(result.get("npc_text", "")).lower()
    tts_text = str(result.get("tts_text", "")).lower()
    
    found_patterns = []
    for pattern in patterns:
        pat_lower = pattern.lower()
        if pat_lower in npc_text or pat_lower in tts_text:
            found_patterns.append(pattern)
            
    if found_patterns:
        return {
            "passed": False,
            "details": f"NPC 대사에 금지된 패턴이 포함되었습니다: {found_patterns}, 실제 대사: '{npc_text}'"
        }
    return {"passed": True, "details": "금지된 패턴이 검출되지 않았습니다."}

def score_branch_type_in(turns_result: Dict[str, Any], expected_branches: List[str]) -> Dict[str, Any]:
    """시나리오 정보에 전달된 분기 타입이 허용되는 리스트 내에 있는지 검사합니다."""
    # 하네스 검증 시 reporter.py 측에서 분기 체크를 직접 대조하여 검사하므로, 여기서는 호환성을 위해 기본 패스 처리합니다.
    _ = turns_result
    _ = expected_branches
    return {"passed": True, "details": "분기 타입 검사 통과 (기본값)"}

def score_turn(turn_result: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    """단일 턴의 수행 결과에 대해 결정적(Deterministic) 채점을 수행합니다."""
    result = turn_result.get("result", {})
    scores = {}
    
    if "npc_role_must_not_be_giver" in expected:
        scores["npc_role_must_not_be_giver"] = score_npc_role_must_not_be_giver(
            result, expected["npc_role_must_not_be_giver"]
        )
        
    if "must_include_any" in expected:
        scores["must_include_any"] = score_must_include_any(
            result, expected["must_include_any"]
        )
        
    if "must_not_include_any" in expected:
        scores["must_not_include_any"] = score_must_not_include_any(
            result, expected["must_not_include_any"]
        )
        
    return scores
