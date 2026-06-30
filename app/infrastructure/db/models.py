from __future__ import annotations

from decimal import Decimal
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    user_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    quota_limit_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    credit_multiplier: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuotaReservationORM(Base):
    __tablename__ = "quota_reservations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_key: Mapped[str] = mapped_column(String(128), ForeignKey("users.user_key"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    estimated_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageLedgerORM(Base):
    __tablename__ = "usage_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_key: Mapped[str] = mapped_column(String(128), ForeignKey("users.user_key"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    multiplier_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    estimated_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    billable_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    output_text: Mapped[str] = mapped_column(String(4000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
