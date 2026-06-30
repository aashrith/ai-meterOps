from typing import Protocol

from app.domain.models import QuotaPolicy, UsageRecord


class QuotaRepository(Protocol):
    def get_user_policy(self, external_key: str) -> QuotaPolicy | None:
        ...


class UsageRepository(Protocol):
    def append(self, record: UsageRecord) -> None:
        ...

