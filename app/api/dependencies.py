from __future__ import annotations

from functools import lru_cache

from sqlalchemy.orm import sessionmaker

from app.application.use_cases import MeteringService
from app.core.config import get_settings
from app.infrastructure.ai.mock_provider import MockAIProvider
from app.infrastructure.db.repositories import PostgresMeteringRepository
from app.infrastructure.db.session import create_session_factory


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    return create_session_factory(get_settings())


@lru_cache(maxsize=1)
def get_repository() -> PostgresMeteringRepository:
    return PostgresMeteringRepository(get_session_factory())


@lru_cache(maxsize=1)
def get_ai_provider() -> MockAIProvider:
    return MockAIProvider()


@lru_cache(maxsize=1)
def get_metering_service() -> MeteringService:
    return MeteringService(get_repository(), get_ai_provider())
