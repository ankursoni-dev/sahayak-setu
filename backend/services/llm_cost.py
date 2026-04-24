"""Per-call cost estimation for LLM usage. Numbers are USD per 1M tokens.

The table is approximate and intended for operational budgeting — not billing.
Update as providers change pricing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# USD per 1M tokens (input, output). Source: public pricing pages as of 2026-Q1.
MODEL_RATES: dict[str, tuple[float, float]] = {
    # OpenRouter-hosted models (representative selection).
    "meta-llama/llama-3.3-70b-instruct": (0.23, 0.40),
    "meta-llama/llama-3.1-8b-instruct": (0.05, 0.08),
    "mistralai/mistral-7b-instruct": (0.06, 0.06),
    "qwen/qwen-2.5-72b-instruct": (0.35, 0.40),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "google/gemini-flash-1.5-8b": (0.05, 0.15),
    # Direct providers
    "gemini-2.0-flash": (0.10, 0.40),
    "groq-llama-3.3": (0.59, 0.79),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = MODEL_RATES.get(model)
    if not rates:
        return 0.0
    in_rate, out_rate = rates
    return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000


def log_usage(
    *,
    model: str,
    task: str,
    prompt_tokens: int,
    completion_tokens: int,
    trace_id: str | None = None,
) -> None:
    cost = estimate_cost_usd(model, prompt_tokens, completion_tokens)
    logger.info(
        "llm_usage",
        extra={
            "model": model,
            "task": task,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd_estimate": round(cost, 6),
            "trace_id": (trace_id or "")[:16],
        },
    )
