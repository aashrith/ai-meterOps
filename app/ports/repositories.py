from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Protocol

from app.domain.models import GenerationResult, QuotaPolicy, Reservation, UsageRecord, UsageSummary


class MeteringRepository(Protocol):
    def upsert_policy(self, user_key: str, quota_limit_credits: int, credit_multiplier: Decimal) -> QuotaPolicy:
        ...

    def get_policy(self, user_key: str) -> QuotaPolicy | None:
        ...

    def create_reservation(
        self,
        user_key: str,
        request_id: str,
        prompt_tokens: int,
        max_completion_tokens: int,
    ) -> tuple[Reservation, UsageSummary]:
        ...

    def finalize_success(
        self,
        user_key: str,
        request_id: str,
        usage: UsageRecord,
    ) -> GenerationResult:
        ...

    def mark_failed(self, user_key: str, request_id: str, error_message: str) -> Reservation:
        ...

    def get_usage_summary(self, user_key: str) -> UsageSummary | None:
        ...

    def list_usage_records(self, user_key: str) -> Iterable[UsageRecord]:
        ...

    def get_generation_result(self, request_id: str) -> GenerationResult | None:
        ...
