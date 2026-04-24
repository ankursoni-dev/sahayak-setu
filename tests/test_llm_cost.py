"""Cost estimation sanity checks."""

from backend.services.llm_cost import estimate_cost_usd, MODEL_RATES


def test_known_model_cost_is_non_zero():
    cost = estimate_cost_usd("meta-llama/llama-3.3-70b-instruct", 1000, 500)
    assert cost > 0
    # Roughly: 1000*0.23/1M + 500*0.40/1M = 0.00023 + 0.0002 = 0.00043
    assert 0.0003 < cost < 0.001


def test_unknown_model_returns_zero():
    assert estimate_cost_usd("nonexistent-model", 1000, 500) == 0.0


def test_zero_tokens_returns_zero():
    assert estimate_cost_usd("gemini-2.0-flash", 0, 0) == 0.0


def test_rate_table_has_all_primary_models():
    # Guard against accidentally removing rate rows the logger depends on.
    required = {
        "gemini-2.0-flash",
        "groq-llama-3.3",
        "meta-llama/llama-3.3-70b-instruct",
    }
    assert required.issubset(MODEL_RATES.keys())
