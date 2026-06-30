from math import ceil


def calculate_billable_credits(total_tokens: int, multiplier: float) -> int:
    return ceil(total_tokens * multiplier)

