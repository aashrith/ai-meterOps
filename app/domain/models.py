from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class QuotaPolicy:
    user_key: str
    quota_limit_credits: int
    credit_multiplier: Decimal


@dataclass(slots=True)
class UsageSummary:
    user_key: str
    quota_limit_credits: int
    credit_multiplier: Decimal
    used_credits: int
    reserved_credits: int

    @property
    def remaining_credits(self) -> int:
        remaining = self.quota_limit_credits - self.used_credits - self.reserved_credits
        return remaining if remaining > 0 else 0


@dataclass(slots=True)
class UsageRecord:
    request_id: str
    user_key: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    multiplier_snapshot: Decimal
    estimated_credits: int
    billable_credits: int
    output_text: str
    status: str
    created_at: datetime


@dataclass(slots=True)
class Reservation:
    request_id: str
    user_key: str
    estimated_credits: int
    estimated_total_tokens: int
    status: str
    error_message: str | None
    multiplier_snapshot: Decimal | None = None


@dataclass(slots=True)
class GenerationUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(slots=True)
class GenerationResult:
    request_id: str
    output_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_credits: int
    billable_credits: int
    remaining_credits: int
    quota_status: str
    multiplier_snapshot: Decimal
    created_at: datetime
