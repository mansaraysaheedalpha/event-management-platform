# tests/conftest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import create_database, database_exists, drop_database
from unittest.mock import MagicMock

from app.main import app
from app.api import deps
from app.db.session import get_db
from app.db.base_class import Base
from app.core.config import settings

# --- E2E Test Database Setup ---
TEST_DATABASE_URL = settings.DATABASE_URL_LOCAL.replace(
    "/event_manager_db", "/event_manager_db_test"
)
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    if database_exists(engine.url):
        drop_database(engine.url)
    create_database(engine.url)
    Base.metadata.create_all(bind=engine)
    yield
    drop_database(engine.url)


@pytest.fixture(scope="function")
def db_session_e2e():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# --- Mock Authentication Setup ---
class MockTokenPayload:
    def __init__(self, sub="user_123", org_id="org_abc"):
        self.sub = sub
        self.org_id = org_id


def override_get_current_user():
    return MockTokenPayload()


# --- Test Client Fixture ---
@pytest.fixture(scope="function")
def test_client():
    """
    Provides a TestClient where the database and authentication are mocked.
    This is for INTEGRATION tests.
    """
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_client_e2e(db_session_e2e):
    """
    Provides a TestClient that uses the LIVE test database and mock auth.
    This is for E2E tests.
    """

    def override_get_db_e2e():
        yield db_session_e2e

    app.dependency_overrides[get_db] = override_get_db_e2e
    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
