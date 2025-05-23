from fastapi.testclient import TestClient

from config import settings
from main import app

client = TestClient(app)


def test_health():
    print(settings.redis_url)
    response = client.get("/health")
    assert response.status_code == 200
