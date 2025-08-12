from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.utils.auth import get_user_authentication_headers
from tests.utils.ad import create_random_ad  # You would create this helper


def test_create_ad(client: TestClient, db: Session) -> None:
    headers = get_user_authentication_headers(db, org_id="org_ad_test")
    data = {
        "name": "Test Ad",
        "content_type": "BANNER",
        "media_url": "https://example.com/image.png",
        "click_url": "https://example.com",
    }

    response = client.post(
        "/api/v1/organizations/org_ad_test/ads", headers=headers, json=data
    )

    assert response.status_code == 201
    content = response.json()
    assert content["name"] == data["name"]
