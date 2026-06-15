"""Estimate token usage cost for Developer C LLM calls.

Beginner guide:
OpenAI-style APIs return token counts, not a finished bill.  This helper turns
those counts into a small diagnostic cost estimate for AgentRun logs.  Gameplay
must never branch on this value; it is only for debugging and budget awareness.
"""

from __future__ import annotations

from typing import Any

OPENAI_TEXT_MODEL_PRICES_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
}


def build_model_usage_summary(
    *,
    model_name: str,
    usage: dict[str, Any] | None,
) -> dict[str, Any]:
    input_tokens = _int_or_zero((usage or {}).get("input_tokens"))
    output_tokens = _int_or_zero((usage or {}).get("output_tokens"))
    total_tokens = _int_or_zero((usage or {}).get("total_tokens")) or input_tokens + output_tokens
    return {
        "model_name": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimate_openai_llm_cost_usd(
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    }


def estimate_openai_llm_cost_usd(
    *,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    rates = OPENAI_TEXT_MODEL_PRICES_USD_PER_1M.get(model_name)
    if rates is None:
        return 0.0
    input_per_1m, output_per_1m = rates
    input_cost = input_tokens / 1_000_000 * input_per_1m
    output_cost = output_tokens / 1_000_000 * output_per_1m
    return round(input_cost + output_cost, 8)


def _int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) else 0
