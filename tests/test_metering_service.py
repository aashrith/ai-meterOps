from __future__ import annotations

import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_metering_service
from app.application.use_cases import GenerateTextCommand, MeteringService, UpsertQuotaCommand
from app.domain.errors import GenerationFailed, MeteringStateInconsistent, QuotaExceeded
from app.domain.models import GenerationResult, QuotaPolicy, Reservation, UsageRecord, UsageSummary
from app.domain.policies import calculate_billable_credits
from app.main import app


@dataclass
class FakeAIProvider:
    delay_seconds: float = 0.0

    def generate(self, prompt: str, max_completion_tokens: int) -> tuple[str, dict[str, int]]:
        if "[fail]" in prompt:
            raise RuntimeError("mock AI failure")
        if self.delay_seconds:
            import time

            time.sleep(self.delay_seconds)
        prompt_tokens = max(1, len(prompt.split()))
        extra_completion = 4 if "[over]" in prompt else 0
        completion_tokens = max_completion_tokens + extra_completion
        return (
            f"mock-response: {prompt[:32]}",
            {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        )


@dataclass
class FakeMeteringRepository:
    policies: dict[str, QuotaPolicy] = field(default_factory=dict)
    reservations: dict[str, dict] = field(default_factory=dict)
    ledger: dict[str, UsageRecord] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def upsert_policy(self, user_key: str, quota_limit_credits: int, credit_multiplier: Decimal) -> QuotaPolicy:
        with self.lock:
            policy = QuotaPolicy(user_key, quota_limit_credits, Decimal(credit_multiplier))
            self.policies[user_key] = policy
            return policy

    def get_policy(self, user_key: str) -> QuotaPolicy | None:
        with self.lock:
            return self.policies.get(user_key)

    def create_reservation(
        self,
        user_key: str,
        request_id: str,
        prompt_tokens: int,
        max_completion_tokens: int,
    ) -> tuple[Reservation, UsageSummary]:
        with self.lock:
            policy = self.policies.get(user_key)
            if policy is None:
                summary = UsageSummary(user_key, 0, Decimal("1"), 0, 0)
                return Reservation(request_id, user_key, 0, prompt_tokens + max_completion_tokens, "missing", "no quota"), summary

            estimated_total_tokens = prompt_tokens + max_completion_tokens
            estimated_credits = calculate_billable_credits(estimated_total_tokens, policy.credit_multiplier)

            if request_id in self.ledger:
                summary = self._summary(user_key)
                return Reservation(request_id, user_key, estimated_credits, estimated_total_tokens, "duplicate", None, policy.credit_multiplier), summary

            existing = self.reservations.get(request_id)
            if existing is not None:
                status = "in_progress" if existing["status"] == "reserved" else "duplicate"
                summary = self._summary(user_key)
                return Reservation(
                    request_id,
                    user_key,
                    estimated_credits,
                    estimated_total_tokens,
                    status,
                    existing.get("error_message"),
                    policy.credit_multiplier,
                ), summary

            summary = self._summary(user_key)
            if estimated_credits > summary.remaining_credits:
                return (
                    Reservation(request_id, user_key, estimated_credits, estimated_total_tokens, "quota_exceeded", None, policy.credit_multiplier),
                    summary,
                )

            self.reservations[request_id] = {
                "user_key": user_key,
                "estimated_credits": estimated_credits,
                "estimated_total_tokens": estimated_total_tokens,
                "status": "reserved",
                "error_message": None,
            }
            return (
                Reservation(request_id, user_key, estimated_credits, estimated_total_tokens, "reserved", None, policy.credit_multiplier),
                self._summary(user_key),
            )

    def finalize_success(self, user_key: str, request_id: str, usage: UsageRecord) -> GenerationResult:
        with self.lock:
            self.reservations[request_id]["status"] = "completed"
            self.ledger[request_id] = usage
            summary = self._summary(user_key)
            quota_status = "within_quota"
            if summary.used_credits > summary.quota_limit_credits:
                quota_status = "over_quota"
            elif summary.remaining_credits == 0:
                quota_status = "at_quota"
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
        with self.lock:
            if request_id in self.reservations:
                self.reservations[request_id]["status"] = "failed"
                self.reservations[request_id]["error_message"] = error_message
                reservation = self.reservations[request_id]
                return Reservation(
                    request_id,
                    user_key,
                    reservation["estimated_credits"],
                    reservation["estimated_total_tokens"],
                    "failed",
                    error_message,
                    self.policies[user_key].credit_multiplier,
                )
            return Reservation(request_id, user_key, 0, 0, "failed", error_message, self.policies[user_key].credit_multiplier if user_key in self.policies else Decimal("1"))

    def get_usage_summary(self, user_key: str) -> UsageSummary | None:
        with self.lock:
            if user_key not in self.policies:
                return None
            return self._summary(user_key)

    def list_usage_records(self, user_key: str) -> Iterable[UsageRecord]:
        with self.lock:
            return [record for record in sorted(self.ledger.values(), key=lambda record: record.created_at, reverse=True) if record.user_key == user_key]

    def get_generation_result(self, request_id: str) -> GenerationResult | None:
        with self.lock:
            record = self.ledger.get(request_id)
            if record is None:
                return None
            summary = self._summary(record.user_key)
            quota_status = "within_quota"
            if summary.used_credits > summary.quota_limit_credits:
                quota_status = "over_quota"
            elif summary.remaining_credits == 0:
                quota_status = "at_quota"
            return GenerationResult(
                request_id=record.request_id,
                output_text=record.output_text,
                prompt_tokens=record.prompt_tokens,
                completion_tokens=record.completion_tokens,
                total_tokens=record.total_tokens,
                estimated_credits=record.estimated_credits,
                billable_credits=record.billable_credits,
                remaining_credits=summary.remaining_credits,
                quota_status=quota_status,
                multiplier_snapshot=record.multiplier_snapshot,
                created_at=record.created_at,
            )

    def _summary(self, user_key: str) -> UsageSummary:
        policy = self.policies[user_key]
        used_credits = sum(record.billable_credits for record in self.ledger.values() if record.user_key == user_key)
        reserved_credits = sum(
            reservation["estimated_credits"]
            for reservation in self.reservations.values()
            if reservation["user_key"] == user_key and reservation["status"] == "reserved"
        )
        return UsageSummary(
            user_key=user_key,
            quota_limit_credits=policy.quota_limit_credits,
            credit_multiplier=policy.credit_multiplier,
            used_credits=used_credits,
            reserved_credits=reserved_credits,
        )


@pytest.fixture
def service() -> tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]:
    repository = FakeMeteringRepository()
    ai_provider = FakeAIProvider()
    return MeteringService(repository, ai_provider), repository, ai_provider


def test_generate_records_usage_and_remaining(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, repository, _ = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(100, Decimal("1.0")))

    result = metering_service.generate_text(
        "alice",
        GenerateTextCommand(request_id="req-1", prompt="hello world", max_completion_tokens=10),
    )

    assert result.request_id == "req-1"
    assert result.billable_credits > 0
    assert result.remaining_credits < 100

    summary = metering_service.get_usage_summary("alice")
    assert summary.used_credits == result.billable_credits
    assert summary.remaining_credits == 100 - result.billable_credits
    assert repository.get_generation_result("req-1") is not None


def test_multiplier_changes_credit_cost_between_users(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, _, _ = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(100, Decimal("1.0")))
    metering_service.upsert_quota("bob", UpsertQuotaCommand(100, Decimal("2.0")))

    alice = metering_service.generate_text(
        "alice",
        GenerateTextCommand(request_id="req-a", prompt="short prompt", max_completion_tokens=10),
    )
    bob = metering_service.generate_text(
        "bob",
        GenerateTextCommand(request_id="req-b", prompt="short prompt", max_completion_tokens=10),
    )

    assert bob.billable_credits == alice.billable_credits * 2


def test_users_can_have_different_quota_limits(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, _, _ = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(5, Decimal("1.0")))
    metering_service.upsert_quota("bob", UpsertQuotaCommand(100, Decimal("1.0")))

    with pytest.raises(QuotaExceeded):
        metering_service.generate_text(
            "alice",
            GenerateTextCommand(request_id="req-alice-quota", prompt="short prompt", max_completion_tokens=10),
        )

    result = metering_service.generate_text(
        "bob",
        GenerateTextCommand(request_id="req-bob-quota", prompt="short prompt", max_completion_tokens=10),
    )

    assert result.request_id == "req-bob-quota"
    assert result.billable_credits > 0


def test_quota_exceeded_rejects_before_ai(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, _, _ = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(5, Decimal("1.0")))

    with pytest.raises(QuotaExceeded):
        metering_service.generate_text(
            "alice",
            GenerateTextCommand(request_id="req-quota", prompt="too expensive", max_completion_tokens=20),
        )


def test_ai_failure_releases_reservation(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, _, _ = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(50, Decimal("1.0")))

    with pytest.raises(GenerationFailed):
        metering_service.generate_text(
            "alice",
            GenerateTextCommand(request_id="req-fail", prompt="please fail [fail]", max_completion_tokens=10),
        )

    summary = metering_service.get_usage_summary("alice")
    assert summary.used_credits == 0
    assert summary.reserved_credits == 0


def test_usage_summary_reports_remaining_and_reservations(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, _, _ = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(100, Decimal("1.5")))

    result = metering_service.generate_text(
        "alice",
        GenerateTextCommand(request_id="req-summary", prompt="usage summary prompt", max_completion_tokens=10),
    )

    summary = metering_service.get_usage_summary("alice")
    assert summary.user_key == "alice"
    assert summary.credit_multiplier == Decimal("1.5")
    assert summary.used_credits == result.billable_credits
    assert summary.remaining_credits == 100 - result.billable_credits
    records = metering_service.list_usage_records("alice")
    assert len(records) == 1
    assert records[0].estimated_credits == result.estimated_credits


def test_multiplier_update_does_not_change_prior_usage_records(
    service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider],
) -> None:
    metering_service, _, _ = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(100, Decimal("1.0")))

    first = metering_service.generate_text(
        "alice",
        GenerateTextCommand(request_id="req-old", prompt="original prompt", max_completion_tokens=10),
    )

    metering_service.upsert_quota("alice", UpsertQuotaCommand(100, Decimal("2.0")))

    second = metering_service.generate_text(
        "alice",
        GenerateTextCommand(request_id="req-new", prompt="new prompt", max_completion_tokens=10),
    )

    records = {record.request_id: record for record in metering_service.list_usage_records("alice")}
    assert records["req-old"].multiplier_snapshot == Decimal("1.0")
    assert records["req-new"].multiplier_snapshot == Decimal("2.0")
    assert first.multiplier_snapshot == Decimal("1.0")
    assert second.multiplier_snapshot == Decimal("2.0")


def test_actual_usage_can_differ_from_estimate(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, _, _ = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(100, Decimal("1.0")))

    result = metering_service.generate_text(
        "alice",
        GenerateTextCommand(request_id="req-over", prompt="show me the [over] case", max_completion_tokens=10),
    )

    assert result.billable_credits > result.estimated_credits


def test_near_simultaneous_requests_respect_reserved_credits(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, _, ai_provider = service
    metering_service.upsert_quota("alice", UpsertQuotaCommand(15, Decimal("1.0")))
    ai_provider.delay_seconds = 0.05

    def generate(request_id: str) -> str:
        return metering_service.generate_text(
            "alice",
            GenerateTextCommand(request_id=request_id, prompt="two token prompt", max_completion_tokens=8),
        ).request_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(generate, "req-1"),
            pool.submit(generate, "req-2"),
        ]
        completed = []
        for future in futures:
            try:
                completed.append(future.result())
            except QuotaExceeded:
                completed.append("quota-exceeded")

    assert "req-1" in completed
    assert "quota-exceeded" in completed


def test_api_routes_accept_and_return_dtos(service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider]) -> None:
    metering_service, _, _ = service

    app.dependency_overrides[get_metering_service] = lambda: metering_service
    client = TestClient(app)
    try:
        quota_response = client.put(
            "/users/alice/quota",
            json={"quota_limit_credits": 100, "credit_multiplier": "1.0"},
        )
        assert quota_response.status_code == 200

        response = client.post(
            "/users/alice/generate",
            json={"request_id": "req-api", "prompt": "hello api", "max_completion_tokens": 10},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["request_id"] == "req-api"
        assert body["billable_credits"] > 0

        usage_response = client.get("/users/alice/usage")
        assert usage_response.status_code == 200
        usage_body = usage_response.json()
        assert usage_body["used_credits"] == body["billable_credits"]

        history_response = client.get("/users/alice/usage/records")
        assert history_response.status_code == 200
        history_body = history_response.json()
        assert len(history_body["items"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_api_returns_clear_error_for_inconsistent_state(
    service: tuple[MeteringService, FakeMeteringRepository, FakeAIProvider],
) -> None:
    metering_service, repository, _ = service

    class BrokenRepository(FakeMeteringRepository):
        def finalize_success(self, user_key: str, request_id: str, usage: UsageRecord) -> GenerationResult:
            raise MeteringStateInconsistent(f"missing reservation for request_id={request_id} user={user_key}")

    broken_repository = BrokenRepository(
        policies=repository.policies,
        reservations=repository.reservations,
        ledger=repository.ledger,
        lock=repository.lock,
    )
    broken_service = MeteringService(broken_repository, FakeAIProvider())
    broken_service.upsert_quota("alice", UpsertQuotaCommand(100, Decimal("1.0")))

    app.dependency_overrides[get_metering_service] = lambda: broken_service
    client = TestClient(app)
    try:
        response = client.post(
            "/users/alice/generate",
            json={"request_id": "req-broken", "prompt": "hello api", "max_completion_tokens": 10},
        )
        assert response.status_code == 500
        assert response.json()["error"] == "inconsistent_state"
    finally:
        app.dependency_overrides.clear()
