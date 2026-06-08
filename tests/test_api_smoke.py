"""Smoke tests: verify the app boots and key public endpoints respond with HTTP 200."""
from fastapi.testclient import TestClient

from src.server import app

client = TestClient(app, raise_server_exceptions=False)


def test_root_responds():
    """GET / should return 200 (JSON fallback when frontend/dist is absent)."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_archives_status_responds():
    """GET /api/archives/status is unauthenticated and backed only by local JSON files."""
    resp = client.get("/api/archives/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "archives" in data
    assert "total_entries" in data
