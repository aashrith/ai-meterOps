from decimal import Decimal
from math import ceil


def calculate_billable_credits(total_tokens: int, multiplier: Decimal) -> int:
    return ceil(total_tokens * multiplier)


def estimate_total_tokens(prompt_tokens: int, max_completion_tokens: int) -> int:
    return prompt_tokens + max_completion_tokens


def count_prompt_tokens(prompt: str) -> int:
    return max(1, len(prompt.split()))
