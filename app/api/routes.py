from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_metering_service
from app.api.schemas import (
    GenerateTextRequest,
    GenerateTextResponse,
    HealthResponse,
    QuotaResponse,
    UpsertQuotaRequest,
    UsageRecordResponse,
    UsageRecordsResponse,
    UsageSummaryResponse,
)
from app.application.use_cases import GenerateTextCommand, MeteringService, UpsertQuotaCommand

router = APIRouter()


@router.get("/healthz", tags=["system"], response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse()


@router.put("/users/{user_key}/quota", response_model=QuotaResponse, tags=["quota"])
def upsert_quota(
    user_key: str,
    payload: UpsertQuotaRequest,
    service: MeteringService = Depends(get_metering_service),
) -> QuotaResponse:
    policy = service.upsert_quota(
        user_key,
        UpsertQuotaCommand(
            quota_limit_credits=payload.quota_limit_credits,
            credit_multiplier=payload.credit_multiplier,
        ),
    )
    return QuotaResponse(
        user_key=policy.user_key,
        quota_limit_credits=policy.quota_limit_credits,
        credit_multiplier=policy.credit_multiplier,
    )


@router.post("/users/{user_key}/generate", response_model=GenerateTextResponse, tags=["generation"])
def generate_text(
    user_key: str,
    payload: GenerateTextRequest,
    service: MeteringService = Depends(get_metering_service),
) -> GenerateTextResponse:
    result = service.generate_text(
        user_key,
        GenerateTextCommand(
            request_id=payload.request_id,
            prompt=payload.prompt,
            max_completion_tokens=payload.max_completion_tokens,
        ),
    )
    return GenerateTextResponse(
        request_id=result.request_id,
        output_text=result.output_text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        estimated_credits=result.estimated_credits,
        billable_credits=result.billable_credits,
        remaining_credits=result.remaining_credits,
        quota_status=result.quota_status,
        multiplier_snapshot=result.multiplier_snapshot,
    )


@router.get("/users/{user_key}/usage", response_model=UsageSummaryResponse, tags=["usage"])
def get_usage_summary(
    user_key: str,
    service: MeteringService = Depends(get_metering_service),
) -> UsageSummaryResponse:
    summary = service.get_usage_summary(user_key)
    return UsageSummaryResponse(
        user_key=summary.user_key,
        quota_limit_credits=summary.quota_limit_credits,
        credit_multiplier=summary.credit_multiplier,
        used_credits=summary.used_credits,
        reserved_credits=summary.reserved_credits,
        remaining_credits=summary.remaining_credits,
    )


@router.get("/users/{user_key}/usage/records", response_model=UsageRecordsResponse, tags=["usage"])
def list_usage_records(
    user_key: str,
    service: MeteringService = Depends(get_metering_service),
) -> UsageRecordsResponse:
    records = service.list_usage_records(user_key)
    return UsageRecordsResponse(
        items=[
            UsageRecordResponse(
                request_id=record.request_id,
                user_key=record.user_key,
                prompt_tokens=record.prompt_tokens,
                completion_tokens=record.completion_tokens,
                total_tokens=record.total_tokens,
                multiplier_snapshot=record.multiplier_snapshot,
                estimated_credits=record.estimated_credits,
                billable_credits=record.billable_credits,
                output_text=record.output_text,
                status=record.status,
                created_at=record.created_at,
            )
            for record in records
        ]
    )

