"""Token cost estimation and accounting utilities for LLM operations."""

import re


def estimate_tokens(text: str) -> int:
    """Fallback utility to estimate token count from raw text.

    Uses a standard heuristic of roughly 4 characters per token.

    Args:
        text: Raw string content.

    Returns:
        int: Estimated token count.
    """
    if not text:
        return 0
    # Clean whitespace and estimate based on character count
    cleaned_text = re.sub(r"\s+", " ", text).strip()
    return max(1, len(cleaned_text) // 4)


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the estimated monetary cost in USD for a given LLM execution.

    Args:
        model: Model name.
        prompt_tokens: Tokens in the input prompt.
        completion_tokens: Tokens in the generated response.

    Returns:
        float: Estimated cost in USD.
    """
    model_lower = model.lower()

    # Gemini pricing tiers
    if "gemini" in model_lower and "pro" in model_lower:
        input_rate = 1.25 / 1_000_000
        output_rate = 5.00 / 1_000_000
    elif "gemini" in model_lower and "flash" in model_lower:
        input_rate = 0.075 / 1_000_000
        output_rate = 0.30 / 1_000_000
    # OpenAI pricing tiers
    elif "gpt-4o" in model_lower:
        input_rate = 2.50 / 1_000_000
        output_rate = 10.00 / 1_000_000
    elif "gpt-4o-mini" in model_lower:
        input_rate = 0.15 / 1_000_000
        output_rate = 0.60 / 1_000_000
    # Anthropic pricing tiers
    elif "claude" in model_lower and "opus" in model_lower:
        input_rate = 15.00 / 1_000_000
        output_rate = 75.00 / 1_000_000
    elif "claude" in model_lower and "sonnet" in model_lower:
        input_rate = 3.00 / 1_000_000
        output_rate = 15.00 / 1_000_000
    elif "claude" in model_lower and "haiku" in model_lower:
        input_rate = 0.25 / 1_000_000
        output_rate = 1.25 / 1_000_000
    # General Fallback
    else:
        input_rate = 1.00 / 1_000_000
        output_rate = 3.00 / 1_000_000

    cost = (prompt_tokens * input_rate) + (completion_tokens * output_rate)
    return round(cost, 6)
