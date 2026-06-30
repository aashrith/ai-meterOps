from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.settings import Settings


def create_engine_from_settings(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(settings: Settings):
    engine = create_engine_from_settings(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
