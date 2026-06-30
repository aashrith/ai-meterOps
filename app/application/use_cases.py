from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.errors import (
    GenerationFailed,
    QuotaConfigurationMissing,
    QuotaExceeded,
    RequestAlreadyExists,
    RequestInProgress,
)
from app.domain.models import GenerationResult, GenerationUsage, UsageRecord, UsageSummary
from app.domain.policies import calculate_billable_credits, count_prompt_tokens
from app.ports.ai import AIProvider
from app.ports.repositories import MeteringRepository


@dataclass(slots=True)
class UpsertQuotaCommand:
    quota_limit_credits: int
    credit_multiplier: Decimal


@dataclass(slots=True)
class GenerateTextCommand:
    request_id: str
    prompt: str
    max_completion_tokens: int = 16


class MeteringService:
    def __init__(self, repository: MeteringRepository, ai_provider: AIProvider) -> None:
        self._repository = repository
        self._ai_provider = ai_provider

    def upsert_quota(self, user_key: str, command: UpsertQuotaCommand) -> QuotaPolicy:
        return self._repository.upsert_policy(user_key, command.quota_limit_credits, command.credit_multiplier)

    def get_usage_summary(self, user_key: str) -> UsageSummary:
        summary = self._repository.get_usage_summary(user_key)
        if summary is None:
            raise QuotaConfigurationMissing(user_key)
        return summary

    def list_usage_records(self, user_key: str) -> list[UsageRecord]:
        return list(self._repository.list_usage_records(user_key))

    def generate_text(self, user_key: str, command: GenerateTextCommand) -> GenerationResult:
        existing = self._repository.get_generation_result(command.request_id)
        if existing is not None:
            return existing

        prompt_tokens = count_prompt_tokens(command.prompt)

        reservation, summary = self._repository.create_reservation(
            user_key=user_key,
            request_id=command.request_id,
            prompt_tokens=prompt_tokens,
            max_completion_tokens=command.max_completion_tokens,
        )
        if reservation.status == "missing":
            raise QuotaConfigurationMissing(user_key)
        if reservation.status == "in_progress":
            raise RequestInProgress(command.request_id)
        if reservation.status == "duplicate":
            existing = self._repository.get_generation_result(command.request_id)
            if existing is not None:
                return existing
            raise RequestAlreadyExists(command.request_id)
        if reservation.status == "quota_exceeded":
            raise QuotaExceeded(
                f"user={user_key} estimated={reservation.estimated_credits} remaining={summary.remaining_credits}"
            )

        try:
            output_text, usage = self._ai_provider.generate(command.prompt, command.max_completion_tokens)
        except Exception as exc:  # pragma: no cover - covered by failure test via fake provider
            self._repository.mark_failed(user_key, command.request_id, str(exc))
            raise GenerationFailed(str(exc)) from exc

        generation_usage = GenerationUsage(
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
        )
        multiplier_snapshot = reservation.multiplier_snapshot or summary.credit_multiplier
        billable_credits = calculate_billable_credits(generation_usage.total_tokens, multiplier_snapshot)
        record = UsageRecord(
            request_id=command.request_id,
            user_key=user_key,
            prompt_tokens=generation_usage.prompt_tokens,
            completion_tokens=generation_usage.completion_tokens,
            total_tokens=generation_usage.total_tokens,
            multiplier_snapshot=multiplier_snapshot,
            estimated_credits=reservation.estimated_credits,
            billable_credits=billable_credits,
            output_text=output_text,
            status="completed",
            created_at=datetime.now(tz=UTC),
        )
        return self._repository.finalize_success(user_key, command.request_id, record)
