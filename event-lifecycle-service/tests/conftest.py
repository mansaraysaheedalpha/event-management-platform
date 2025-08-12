import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database, drop_database
from datetime import datetime, timedelta, timezone

from app.main import app
from app.db.base_class import Base
from app.db.session import get_db
from app.api import deps
from app.schemas.token import TokenPayload

# --- Test Database Setup ---
TEST_DATABASE_URL = "postgresql://admin:secret@localhost:5433/test_db"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    """
    Create a test database for the entire test session, and drop it after.
    'autouse=True' makes this fixture run automatically for the session.
    """
    if database_exists(engine.url):
        drop_database(engine.url)
    create_database(engine.url)

    yield  # The tests run here

    drop_database(engine.url)


@pytest.fixture(scope="function")
def db_session():
    """
    Provide a clean database session with all tables created for each test function.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Base.metadata.create_all(bind=connection)  # Create tables for the test

    db = TestingSessionLocal(bind=connection)

    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        Base.metadata.drop_all(bind=connection)  # Drop tables after the test
        connection.close()


# --- Test API Client Fixture ---
@pytest.fixture(scope="function")
def client(db_session):
    """
    Provide a FastAPI test client that uses the clean db_session for each test.
    """

    def override_get_db():
        yield db_session

    def override_get_current_user():
        expires = datetime.now(timezone.utc) + timedelta(hours=24)
        return TokenPayload(
            sub="test_user_123", org_id="acme-corp", exp=int(expires.timestamp())
        )

    # Apply the overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[deps.get_current_user] = override_get_current_user

    yield TestClient(app)

    # Clean up the overrides after the test
    del app.dependency_overrides[get_db]
    del app.dependency_overrides[deps.get_current_user]
