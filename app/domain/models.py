from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class QuotaPolicy:
    user_id: UUID
    quota_limit_credits: int
    credit_multiplier: float


@dataclass(slots=True)
class UsageRecord:
    user_id: UUID
    request_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    multiplier_snapshot: float
    billable_credits: int

