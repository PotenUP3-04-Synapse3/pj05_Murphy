# GPT-4o-mini 모델의 1백만 토큰당 입력(Input) 비용 지표(USD)입니다.
GPT_4O_MINI_INPUT_PER_1M = 0.15
# GPT-4o-mini 모델의 1백만 토큰당 출력(Output) 비용 지표(USD)입니다.
GPT_4O_MINI_OUTPUT_PER_1M = 0.30


def estimate_openai_cost_usd(
    *,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """사용된 토큰(Token) 통계 데이터를 바탕으로 OpenAI API 사용에 소요된 대략적 달러 비용(Cost USD)을 계산합니다.
    
    주의: 이 비용은 에이전트 모니터링을 위한 추정치이며, OpenAI 공식 실제 청구액과 차이가 날 수 있습니다.
    """
    if model_name != "gpt-4o-mini":
        return 0.0
    input_cost = input_tokens / 1_000_000 * GPT_4O_MINI_INPUT_PER_1M
    output_cost = output_tokens / 1_000_000 * GPT_4O_MINI_OUTPUT_PER_1M
    return round(input_cost + output_cost, 8)
