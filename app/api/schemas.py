from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", examples=["ok"])


class GenerateTextRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    request_id: str = Field(..., min_length=1, max_length=128)


class GenerateTextResponse(BaseModel):
    request_id: str
    output_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    billable_credits: int
    remaining_credits: int


class UpsertQuotaRequest(BaseModel):
    quota_limit_credits: int = Field(..., ge=0)
    credit_multiplier: float = Field(..., gt=0)


class UsageSummaryResponse(BaseModel):
    user_key: str
    quota_limit_credits: int
    credit_multiplier: float
    used_credits: int
    remaining_credits: int


class UsageRecordResponse(BaseModel):
    request_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    multiplier_snapshot: float
    billable_credits: int

