from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Iterable

from sqlalchemy.orm import Session

from app.domain.models import QuotaPolicy, UsageRecord


@dataclass(slots=True)
class PostgresQuotaRepository:
    """SQLAlchemy-backed adapter for quota configuration."""

    session_factory: Callable[[], Session]

    def get_user_policy(self, external_key: str) -> QuotaPolicy | None:
        raise NotImplementedError("Quota repository wiring comes in the next scaffold step.")


@dataclass(slots=True)
class PostgresUsageRepository:
    """SQLAlchemy-backed adapter for the usage ledger."""

    session_factory: Callable[[], Session]

    def append(self, record: UsageRecord) -> None:
        raise NotImplementedError("Usage ledger wiring comes in the next scaffold step.")

    def list_for_user(self, external_key: str) -> Iterable[UsageRecord]:
        raise NotImplementedError("Usage history wiring comes in the next scaffold step.")
