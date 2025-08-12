import pytest
from fastapi.testclient import TestClient
from app.main import app  # Import our main FastAPI app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """
    A fixture that provides a test client for the FastAPI application.
    """
    with TestClient(app) as c:
        yield c
