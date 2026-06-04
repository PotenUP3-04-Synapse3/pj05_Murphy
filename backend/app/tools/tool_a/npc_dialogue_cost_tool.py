GPT_4O_MINI_INPUT_PER_1M = 0.15
GPT_4O_MINI_OUTPUT_PER_1M = 0.30


def estimate_openai_cost_usd(
    *,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    # 비용은 운영 추적용 추정값이며 실제 청구 비용과 다를 수 있다.
    if model_name != "gpt-4o-mini":
        return 0.0
    input_cost = input_tokens / 1_000_000 * GPT_4O_MINI_INPUT_PER_1M
    output_cost = output_tokens / 1_000_000 * GPT_4O_MINI_OUTPUT_PER_1M
    return round(input_cost + output_cost, 8)
