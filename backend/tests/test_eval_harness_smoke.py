from backend.tests.eval_harness.runner import load_all_scenarios
from backend.tests.eval_harness.reporter import run_all_scenarios, print_summary_report

def test_eval_harness_deterministic_smoke() -> None:
    """모든 YAML 시나리오를 로드하여 결정형 채점만으로 테스트를 수행하고 통과율이 80% 이상인지 검증합니다.
    
    실제 OpenAI API 키가 없는 CI 환경에서도 작동 가능한 결정적 검증 인프라(Evaluation Harness)입니다.
    """
    # 1. 모든 시나리오 로드
    scenarios = load_all_scenarios()
    assert len(scenarios) >= 30, f"최소 30개의 시나리오가 로드되어야 합니다. 로드된 개수: {len(scenarios)}"
    
    # 2. LLM Judge 없이 결정형 채점만 실행
    # (MURPHY_EVAL_USE_LLM_JUDGE는 기본 설정이 아니므로 통상 스킵됨)
    summary = run_all_scenarios(scenarios, use_llm=False)
    
    # 3. 콘솔에 요약 출력
    print_summary_report(summary)
    
    # 4. 통과율이 80% 이상인지 단언(assert)
    assert summary["pass_rate"] >= 0.8, f"평가 하네스 통과율이 80% 미만입니다. 현재 통과율: {summary['pass_rate'] * 100:.2f}%"
