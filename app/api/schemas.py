from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", examples=["ok"])


class UpsertQuotaRequest(BaseModel):
    quota_limit_credits: int = Field(..., ge=0)
    credit_multiplier: Decimal = Field(..., gt=0)


class QuotaResponse(BaseModel):
    user_key: str
    quota_limit_credits: int
    credit_multiplier: Decimal


class GenerateTextRequest(BaseModel):
    request_id: str = Field(..., min_length=1, max_length=128)
    prompt: str = Field(..., min_length=1, max_length=8000)
    max_completion_tokens: int = Field(default=16, ge=1, le=4096)


class GenerateTextResponse(BaseModel):
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


class UsageSummaryResponse(BaseModel):
    user_key: str
    quota_limit_credits: int
    credit_multiplier: Decimal
    used_credits: int
    reserved_credits: int
    remaining_credits: int


class UsageRecordResponse(BaseModel):
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


class UsageRecordsResponse(BaseModel):
    items: list[UsageRecordResponse]

