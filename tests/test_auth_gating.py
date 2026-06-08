"""Auth gating tests: verify 3-tier access control on key endpoints.

Mocking strategy:
- `src.auth.verify_token` is patched with AsyncMock so async await works.
- `src.auth.ADMIN_EMAILS` is patched directly (module-level set, env var won't work).
- TestClient wraps the FastAPI app; raise_server_exceptions=False lets us inspect 4xx.
"""
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.server import app

client = TestClient(app, raise_server_exceptions=False)

MEMBER_USER = {"id": "uid-member", "email": "member@example.com"}
ADMIN_USER  = {"id": "uid-admin",  "email": "admin@example.com"}
ADMIN_EMAIL = "admin@example.com"

MEMBER_TOKEN = "member-token"
ADMIN_TOKEN  = "admin-token"

MEMBER_HEADERS = {"Authorization": f"Bearer {MEMBER_TOKEN}"}
ADMIN_HEADERS  = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


# ── helpers ──────────────────────────────────────────────────────────────────

def _mock_verify(token: str):
    """Return the right user dict based on token, or None."""
    if token == MEMBER_TOKEN:
        return MEMBER_USER
    if token == ADMIN_TOKEN:
        return ADMIN_USER
    return None


# ── MEMBER-gated: GET /api/reports/{slug} ─────────────────────────────────

class TestReportDetailGating:
    def test_no_token_returns_401(self):
        resp = client.get("/api/reports/some-slug")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        with patch("src.auth.verify_token", new=AsyncMock(return_value=None)):
            resp = client.get("/api/reports/some-slug",
                              headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401

    def test_member_token_passes_auth(self):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            resp = client.get("/api/reports/nonexistent", headers=MEMBER_HEADERS)
        # auth passes → 404 (report doesn't exist) rather than 401/403
        assert resp.status_code in (200, 404)

    def test_admin_token_also_passes(self):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/reports/nonexistent", headers=ADMIN_HEADERS)
        assert resp.status_code in (200, 404)


# ── ADMIN-gated: POST /api/archives/refresh ───────────────────────────────

class TestArchivesRefreshGating:
    def test_no_token_returns_401(self):
        resp = client.post("/api/archives/refresh")
        assert resp.status_code == 401

    def test_member_returns_403(self):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.post("/api/archives/refresh", headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_admin_passes(self):
        # Mock the background orchestrator so the test never launches a real build.
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                with patch("src.server._run_archive_orchestrator", new=AsyncMock()):
                    resp = client.post("/api/archives/refresh", headers=ADMIN_HEADERS)
        assert resp.status_code not in (401, 403)


# ── ADMIN-gated: DELETE /api/reports/{slug} ───────────────────────────────

class TestReportDeleteGating:
    def test_no_token_returns_401(self):
        resp = client.delete("/api/reports/some-slug")
        assert resp.status_code == 401

    def test_member_returns_403(self):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.delete("/api/reports/some-slug", headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_admin_passes_auth(self):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.delete("/api/reports/nonexistent", headers=ADMIN_HEADERS)
        # auth passes → 404 (slug absent) rather than 401/403
        assert resp.status_code in (200, 404)


# ── ADMIN-gated: PUT /api/keywords ────────────────────────────────────────

class TestKeywordsPutGating:
    def test_no_token_returns_401(self):
        resp = client.put("/api/keywords", json={"keywords": ["test"]})
        assert resp.status_code == 401

    def test_member_returns_403(self):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.put("/api/keywords",
                                  json={"keywords": ["test"]},
                                  headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_admin_passes(self):
        # Mock the file write so the test never clobbers the real keywords data file.
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                with patch("pathlib.Path.write_text"):
                    resp = client.put("/api/keywords",
                                      json={"keywords": ["smartphone"]},
                                      headers=ADMIN_HEADERS)
        assert resp.status_code not in (401, 403)


# ── PUBLIC: GET /api/archives/status (smoke test stays green) ─────────────

class TestPublicEndpointsUnchanged:
    def test_archives_status_no_auth(self):
        resp = client.get("/api/archives/status")
        assert resp.status_code == 200

    def test_reports_list_no_auth(self):
        resp = client.get("/api/reports")
        assert resp.status_code == 200

    def test_topics_suggested_no_auth(self):
        resp = client.get("/api/topics/suggested")
        assert resp.status_code == 200


# ── GET /api/me ────────────────────────────────────────────────────────────

class TestMeEndpoint:
    def test_no_token_returns_401(self):
        resp = client.get("/api/me")
        assert resp.status_code == 401

    def test_member_returns_email_not_admin(self):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/me", headers=MEMBER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "member@example.com"
        assert data["is_admin"] is False

    def test_admin_returns_is_admin_true(self):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/me", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@example.com"
        assert data["is_admin"] is True


# ── Path traversal: GET /reports/{filename} must not escape reports/ ──────────

class TestReportFileTraversal:
    def test_encoded_traversal_does_not_leak_files(self):
        """A member must never read files outside reports/ via encoded ../ .

        Asserts on response CONTENT (not status), since an escaped path may be
        normalized by the client or fall through to the SPA index.html — either
        way the actual source/secret file contents must never be returned.
        """
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            resp = client.get(
                "/reports/..%2f..%2fpyproject.toml", headers=MEMBER_HEADERS
            )
        assert "[build-system]" not in resp.text
        assert "requires-python" not in resp.text
