from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.errors import MeteringStateInconsistent
from app.domain.models import GenerationResult, QuotaPolicy, Reservation, UsageRecord, UsageSummary
from app.domain.policies import calculate_billable_credits
from app.infrastructure.db.models import QuotaReservationORM, UsageLedgerORM, UserORM


class PostgresMeteringRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def upsert_policy(self, user_key: str, quota_limit_credits: int, credit_multiplier: Decimal) -> QuotaPolicy:
        now = datetime.now(tz=UTC)
        with self._session_factory() as session, session.begin():
            user = (
                session.execute(select(UserORM).where(UserORM.user_key == user_key).with_for_update())
                .scalars()
                .one_or_none()
            )
            if user is None:
                user = UserORM(
                    user_key=user_key,
                    quota_limit_credits=quota_limit_credits,
                    credit_multiplier=credit_multiplier,
                    created_at=now,
                    updated_at=now,
                )
                session.add(user)
            else:
                user.quota_limit_credits = quota_limit_credits
                user.credit_multiplier = credit_multiplier
                user.updated_at = now
            return QuotaPolicy(
                user_key=user.user_key,
                quota_limit_credits=user.quota_limit_credits,
                credit_multiplier=Decimal(user.credit_multiplier),
            )

    def get_policy(self, user_key: str) -> QuotaPolicy | None:
        with self._session_factory() as session:
            user = session.get(UserORM, user_key)
            if user is None:
                return None
            return QuotaPolicy(
                user_key=user.user_key,
                quota_limit_credits=user.quota_limit_credits,
                credit_multiplier=Decimal(user.credit_multiplier),
            )

    def create_reservation(
        self,
        user_key: str,
        request_id: str,
        prompt_tokens: int,
        max_completion_tokens: int,
    ) -> tuple[Reservation, UsageSummary]:
        now = datetime.now(tz=UTC)
        with self._session_factory() as session, session.begin():
            user = (
                session.execute(
                    select(UserORM).where(UserORM.user_key == user_key).with_for_update()
                )
                .scalars()
                .one_or_none()
            )
            if user is None:
                summary = UsageSummary(
                    user_key=user_key,
                    quota_limit_credits=0,
                    credit_multiplier=Decimal("1"),
                    used_credits=0,
                    reserved_credits=0,
                )
                return (
                    Reservation(request_id, user_key, 0, prompt_tokens + max_completion_tokens, "missing", "no quota"),
                    summary,
                )

            estimated_total_tokens = prompt_tokens + max_completion_tokens
            multiplier_snapshot = Decimal(user.credit_multiplier)
            estimated_credits = calculate_billable_credits(estimated_total_tokens, multiplier_snapshot)

            existing_ledger = session.execute(
                select(UsageLedgerORM).where(UsageLedgerORM.request_id == request_id)
            ).scalars().one_or_none()
            if existing_ledger is not None:
                summary = self._build_summary(session, user)
                return (
                    Reservation(
                        request_id,
                        user_key,
                        estimated_credits,
                        estimated_total_tokens,
                        "duplicate",
                        None,
                        multiplier_snapshot,
                    ),
                    summary,
                )

            existing_reservation = session.execute(
                select(QuotaReservationORM).where(QuotaReservationORM.request_id == request_id)
            ).scalars().one_or_none()
            if existing_reservation is not None:
                status = "in_progress" if existing_reservation.status == "reserved" else "duplicate"
                summary = self._build_summary(session, user)
                return (
                    Reservation(
                        request_id,
                        user_key,
                        estimated_credits,
                        estimated_total_tokens,
                        status,
                        existing_reservation.error_message,
                        multiplier_snapshot,
                    ),
                    summary,
                )

            summary_before = self._build_summary(session, user)
            if estimated_credits > summary_before.remaining_credits:
                return (
                    Reservation(
                        request_id,
                        user_key,
                        estimated_credits,
                        estimated_total_tokens,
                        "quota_exceeded",
                        None,
                        multiplier_snapshot,
                    ),
                    summary_before,
                )

            reservation = QuotaReservationORM(
                id=str(uuid4()),
                user_key=user_key,
                request_id=request_id,
                estimated_credits=estimated_credits,
                estimated_total_tokens=estimated_total_tokens,
                actual_credits=None,
                actual_total_tokens=None,
                status="reserved",
                error_message=None,
                created_at=now,
                updated_at=now,
            )
            session.add(reservation)
            summary_after = UsageSummary(
                user_key=user.user_key,
                quota_limit_credits=user.quota_limit_credits,
                credit_multiplier=multiplier_snapshot,
                used_credits=summary_before.used_credits,
                reserved_credits=summary_before.reserved_credits + estimated_credits,
            )
            return (
                Reservation(
                    request_id,
                    user_key,
                    estimated_credits,
                    estimated_total_tokens,
                    "reserved",
                    None,
                    multiplier_snapshot,
                ),
                summary_after,
            )

    def finalize_success(self, user_key: str, request_id: str, usage: UsageRecord) -> GenerationResult:
        with self._session_factory() as session, session.begin():
            user = (
                session.execute(select(UserORM).where(UserORM.user_key == user_key).with_for_update())
                .scalars()
                .one_or_none()
            )
            if user is None:
                raise MeteringStateInconsistent(f"missing quota policy for user={user_key}")
            reservation = (
                session.execute(
                    select(QuotaReservationORM).where(QuotaReservationORM.request_id == request_id)
                )
                .scalars()
                .one_or_none()
            )
            if reservation is None:
                raise MeteringStateInconsistent(f"missing reservation for request_id={request_id}")
            reservation.status = "completed"
            reservation.actual_credits = usage.billable_credits
            reservation.actual_total_tokens = usage.total_tokens
            reservation.updated_at = datetime.now(tz=UTC)
            reservation.error_message = None

            ledger = UsageLedgerORM(
                id=str(uuid4()),
                user_key=user_key,
                request_id=request_id,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                multiplier_snapshot=usage.multiplier_snapshot,
                estimated_credits=usage.estimated_credits,
                billable_credits=usage.billable_credits,
                output_text=usage.output_text,
                status=usage.status,
                created_at=usage.created_at,
            )
            session.add(ledger)
            summary = self._build_summary(session, user)
            quota_status = "within_quota"
            if summary.remaining_credits == 0 and summary.used_credits >= summary.quota_limit_credits:
                quota_status = "at_quota"
            if summary.used_credits > summary.quota_limit_credits:
                quota_status = "over_quota"
            return GenerationResult(
                request_id=request_id,
                output_text=usage.output_text,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                estimated_credits=usage.estimated_credits,
                billable_credits=usage.billable_credits,
                remaining_credits=summary.remaining_credits,
                quota_status=quota_status,
                multiplier_snapshot=usage.multiplier_snapshot,
                created_at=usage.created_at,
            )

    def mark_failed(self, user_key: str, request_id: str, error_message: str) -> Reservation:
        with self._session_factory() as session, session.begin():
            user = session.get(UserORM, user_key)
            reservation = (
                session.execute(
                    select(QuotaReservationORM).where(
                        QuotaReservationORM.request_id == request_id,
                        QuotaReservationORM.user_key == user_key,
                    )
                )
                .scalars()
                .one_or_none()
            )
            if reservation is None:
                raise MeteringStateInconsistent(
                    f"missing reservation for request_id={request_id} user={user_key}"
                )
            if user is None:
                raise MeteringStateInconsistent(f"missing quota policy for user={user_key}")
            reservation.status = "failed"
            reservation.error_message = error_message
            reservation.updated_at = datetime.now(tz=UTC)
            return Reservation(
                request_id=request_id,
                user_key=user_key,
                estimated_credits=reservation.estimated_credits,
                estimated_total_tokens=reservation.estimated_total_tokens,
                status="failed",
                error_message=error_message,
                multiplier_snapshot=Decimal(user.credit_multiplier) if user is not None else None,
            )

    def get_usage_summary(self, user_key: str) -> UsageSummary | None:
        with self._session_factory() as session:
            user = session.get(UserORM, user_key)
            if user is None:
                return None
            return self._build_summary(session, user)

    def list_usage_records(self, user_key: str) -> Iterable[UsageRecord]:
        with self._session_factory() as session:
            rows = (
                session.execute(
                    select(UsageLedgerORM)
                    .where(UsageLedgerORM.user_key == user_key)
                    .order_by(UsageLedgerORM.created_at.desc())
                )
                .scalars()
                .all()
            )
            for row in rows:
                yield UsageRecord(
                    request_id=row.request_id,
                    user_key=row.user_key,
                    prompt_tokens=row.prompt_tokens,
                    completion_tokens=row.completion_tokens,
                    total_tokens=row.total_tokens,
                    multiplier_snapshot=Decimal(row.multiplier_snapshot),
                    estimated_credits=row.estimated_credits,
                    billable_credits=row.billable_credits,
                    output_text=row.output_text,
                    status=row.status,
                    created_at=row.created_at,
                )

    def get_generation_result(self, request_id: str) -> GenerationResult | None:
        with self._session_factory() as session:
            ledger = (
                session.execute(select(UsageLedgerORM).where(UsageLedgerORM.request_id == request_id))
                .scalars()
                .one_or_none()
            )
            if ledger is None:
                return None
            user = session.get(UserORM, ledger.user_key)
            if user is None:
                return None
            summary = self._build_summary(session, user)
            quota_status = "within_quota"
            if summary.remaining_credits == 0 and summary.used_credits >= summary.quota_limit_credits:
                quota_status = "at_quota"
            if summary.used_credits > summary.quota_limit_credits:
                quota_status = "over_quota"
            return GenerationResult(
                request_id=ledger.request_id,
                output_text=ledger.output_text,
                prompt_tokens=ledger.prompt_tokens,
                completion_tokens=ledger.completion_tokens,
                total_tokens=ledger.total_tokens,
                estimated_credits=ledger.estimated_credits,
                billable_credits=ledger.billable_credits,
                remaining_credits=summary.remaining_credits,
                quota_status=quota_status,
                multiplier_snapshot=Decimal(ledger.multiplier_snapshot),
                created_at=ledger.created_at,
            )

    def _build_summary(self, session: Session, user: UserORM) -> UsageSummary:
        used_credits = (
            session.execute(
                select(func.coalesce(func.sum(UsageLedgerORM.billable_credits), 0)).where(
                    UsageLedgerORM.user_key == user.user_key
                )
            )
            .scalar_one()
        )
        reserved_credits = (
            session.execute(
                select(func.coalesce(func.sum(QuotaReservationORM.estimated_credits), 0)).where(
                    QuotaReservationORM.user_key == user.user_key,
                    QuotaReservationORM.status == "reserved",
                )
            )
            .scalar_one()
        )
        return UsageSummary(
            user_key=user.user_key,
            quota_limit_credits=user.quota_limit_credits,
            credit_multiplier=Decimal(user.credit_multiplier),
            used_credits=int(used_credits),
            reserved_credits=int(reserved_credits),
        )
