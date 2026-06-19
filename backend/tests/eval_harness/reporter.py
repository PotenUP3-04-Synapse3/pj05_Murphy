import os
import json
import time
from typing import Any, Dict, List
from backend.tests.eval_harness.runner import run_scenario
from backend.tests.eval_harness.scorers.deterministic import score_turn
from backend.tests.eval_harness.scorers.llm_judge import judge_turn

# 리포트 저장용 기본 디렉토리 정의
_REPORTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "reports")
)

def run_all_scenarios(scenarios: List[Dict[str, Any]], *, use_llm: bool = False, llm_client: Any = None) -> Dict[str, Any]:
    """등록된 모든 시나리오를 구동하고 채점한 뒤 종합 리포트 데이터를 생성합니다."""
    results = []
    total_checks = 0
    passed_checks = 0
    
    for scenario in scenarios:
        # 시나리오 수행
        scenario_res = run_scenario(scenario, use_llm=use_llm, llm_client=llm_client)
        expected = scenario_res["expected"]
        scenario_passed = True
        scenario_scores = []

        # 각 턴에 대한 검증 수행
        for turn_idx, turn in enumerate(scenario_res["turns"]):
            # 1. 결정형(Deterministic) 채점 수행
            det_scores = score_turn(turn, expected)
            
            # 2. LLM Judge 채점 수행 (옵션)
            llm_score = None
            if "rubric_for_judge" in expected:
                llm_score = judge_turn(expected["rubric_for_judge"], turn)
            
            # 턴 결과 수집
            turn_results = {}
            for key, score in det_scores.items():
                total_checks += 1
                if score["passed"]:
                    passed_checks += 1
                else:
                    scenario_passed = False
                turn_results[key] = score
                
            if llm_score and not llm_score.get("skipped"):
                total_checks += 1
                if llm_score["passed"]:
                    passed_checks += 1
                else:
                    scenario_passed = False
                turn_results["llm_judge"] = llm_score
                
            scenario_scores.append({
                "turn_index": turn_idx,
                "player_text": turn["player_text"],
                "npc_text": turn["result"].get("npc_text", ""),
                "checks": turn_results
            })
            
        # 추가 분기 타입 체크
        if "branch_type_in" in expected:
            # 시나리오 설정의 branch가 expected["branch_type_in"]에 포함되는지 확인
            # scenario["payload_overrides"]["branch"]["branch_type"] 혹은 기본값 success
            actual_branch = scenario.get("payload_overrides", {}).get("branch", {}).get("branch_type", "success")
            branch_passed = actual_branch in expected["branch_type_in"]
            total_checks += 1
            if branch_passed:
                passed_checks += 1
            else:
                scenario_passed = False
                
            scenario_scores.append({
                "turn_index": -1,
                "player_text": "[SYSTEM_BRANCH_CHECK]",
                "npc_text": "",
                "checks": {
                    "branch_type_in": {
                        "passed": branch_passed,
                        "details": f"기대 분기 리스트: {expected['branch_type_in']}, 실제 인입 분기: '{actual_branch}'"
                    }
                }
            })

        results.append({
            "scenario_id": scenario_res["scenario_id"],
            "npc_id": scenario_res["npc_id"],
            "node_id": scenario_res["node_id"],
            "passed": scenario_passed,
            "scores": scenario_scores
        })

    # 전체 통과율 산출
    pass_rate = (passed_checks / total_checks) if total_checks > 0 else 1.0
    
    summary = {
        "timestamp": int(time.time()),
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "pass_rate": pass_rate,
        "results": results
    }

    # 리포트 JSON 파일 저장
    if not os.path.exists(_REPORTS_DIR):
        os.makedirs(_REPORTS_DIR)
    
    report_file_path = os.path.join(_REPORTS_DIR, f"report_{summary['timestamp']}.json")
    with open(report_file_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        
    return summary

def print_summary_report(summary: Dict[str, Any]) -> None:
    """콘솔 창에 채점 종합 요약 결과를 보기 쉽게 출력합니다."""
    print("\n" + "="*80)
    print("                      EVALUATION HARNESS REPORT SUMMARY")
    print("="*80)
    print(f"Timestamp    : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(summary['timestamp']))}")
    print(f"Total Checks : {summary['total_checks']}")
    print(f"Passed Checks: {summary['passed_checks']}")
    print(f"Pass Rate    : {summary['pass_rate'] * 100:.2f}%")
    print("-"*80)
    print(f"{'Scenario ID':<40} | {'Status':<8} | Failed Checks")
    print("-"*80)
    
    for res in summary["results"]:
        status = "PASSED" if res["passed"] else "FAILED"
        failed_keys = []
        for score in res["scores"]:
            for key, chk in score["checks"].items():
                if not chk["passed"]:
                    failed_keys.append(f"{key}(turn {score['turn_index']})")
                    
        failed_str = ", ".join(failed_keys) if failed_keys else "-"
        print(f"{res['scenario_id']:<40} | {status:<8} | {failed_str}")
        
    print("="*80 + "\n")
