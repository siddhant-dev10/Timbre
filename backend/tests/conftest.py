import os
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.scripts.seed_db import seed_database
from app.models.citizen import Citizen
from app.models.service_scheme import ServiceScheme
from app.models.simulation import SimulationRecord
from app.models.call_job import CallJobRecord

# Use a clean test SQLite file
TEST_DB_PATH = backend_dir.parent / "data" / "test_timbre.db"
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    csv_path = backend_dir.parent / "data" / "demo" / "Timbre_Fake_Citizens.csv"
    seed_database(csv_path=csv_path, db_session=session)
    session.close()
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
