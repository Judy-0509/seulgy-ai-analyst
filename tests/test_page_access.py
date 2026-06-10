"""Tests for page-access store (src/page_access.py) and the new API endpoints.

Isolation strategy:
- `src.page_access.STORE_PATH` is monkeypatched to a tmp file so the real
  data/page_access.json is never touched.
- `src.auth.verify_token` is patched with AsyncMock (same pattern as test_auth_gating.py).
- `src.auth.ADMIN_EMAILS` is patched directly.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import src.page_access as page_access_mod
from src.server import app

client = TestClient(app, raise_server_exceptions=False)

MEMBER_USER  = {"id": "uid-member",  "email": "member@example.com"}
ADMIN_USER   = {"id": "uid-admin",   "email": "admin@example.com"}
ADMIN_EMAIL  = "admin@example.com"

MEMBER_TOKEN  = "pa-member-token"
ADMIN_TOKEN   = "pa-admin-token"
MEMBER_HEADERS = {"Authorization": f"Bearer {MEMBER_TOKEN}"}
ADMIN_HEADERS  = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def _mock_verify(token: str):
    if token == MEMBER_TOKEN:
        return MEMBER_USER
    if token == ADMIN_TOKEN:
        return ADMIN_USER
    return None


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def store_path(tmp_path, monkeypatch):
    """Point the page_access module at a fresh temp file for each test."""
    p = tmp_path / "page_access.json"
    monkeypatch.setattr("src.page_access.STORE_PATH", p)
    return p


# ── Unit tests: store functions ───────────────────────────────────────────────

class TestPageAccessStore:
    def test_has_access_missing_file(self, store_path):
        assert page_access_mod.has_access("user@x.com", "db") is False

    def test_granted_pages_missing_file(self, store_path):
        assert page_access_mod.granted_pages("user@x.com") == []

    def test_request_creates_file(self, store_path):
        page_access_mod.request_access("user@x.com", "db")
        assert store_path.exists()
        data = json.loads(store_path.read_text())
        assert len(data["requests"]) == 1
        assert data["requests"][0]["status"] == "pending"

    def test_request_idempotent_pending(self, store_path):
        page_access_mod.request_access("user@x.com", "db")
        page_access_mod.request_access("user@x.com", "db")
        data = json.loads(store_path.read_text())
        assert len(data["requests"]) == 1

    def test_request_noop_when_already_granted(self, store_path):
        page_access_mod.approve("user@x.com", "db")
        page_access_mod.request_access("user@x.com", "db")
        data = json.loads(store_path.read_text())
        # only the approved entry, no new pending
        pending = [r for r in data["requests"] if r["status"] == "pending"]
        assert len(pending) == 0

    def test_approve_grants_access(self, store_path):
        page_access_mod.request_access("user@x.com", "keywords")
        page_access_mod.approve("user@x.com", "keywords")
        assert page_access_mod.has_access("user@x.com", "keywords") is True

    def test_approve_marks_request_approved(self, store_path):
        page_access_mod.request_access("user@x.com", "db")
        page_access_mod.approve("user@x.com", "db")
        data = json.loads(store_path.read_text())
        assert data["requests"][0]["status"] == "approved"

    def test_list_requests_returns_pending(self, store_path):
        page_access_mod.request_access("a@x.com", "db")
        page_access_mod.request_access("b@x.com", "keywords")
        page_access_mod.approve("a@x.com", "db")
        pending = page_access_mod.list_requests("pending")
        assert len(pending) == 1
        assert pending[0]["email"] == "b@x.com"

    def test_invalid_page_raises(self, store_path):
        with pytest.raises(ValueError):
            page_access_mod.request_access("user@x.com", "usage")

    def test_email_lowercased(self, store_path):
        page_access_mod.approve("User@X.COM", "db")
        assert page_access_mod.has_access("user@x.com", "db") is True

    def test_read_does_not_write_when_file_missing(self, store_path):
        """has_access and granted_pages must never create the store file."""
        page_access_mod.has_access("x@x.com", "db")
        page_access_mod.granted_pages("x@x.com")
        assert not store_path.exists()


# ── API: POST /api/access/request ─────────────────────────────────────────────

class TestAccessRequestEndpoint:
    def test_unauthenticated_returns_401(self, store_path):
        resp = client.post("/api/access/request", json={"page": "db"})
        assert resp.status_code == 401

    def test_member_can_request(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.post("/api/access/request",
                                   json={"page": "db"},
                                   headers=MEMBER_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_invalid_page_returns_400(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.post("/api/access/request",
                                   json={"page": "usage"},
                                   headers=MEMBER_HEADERS)
        assert resp.status_code == 400


# ── API: GET /api/access/requests ─────────────────────────────────────────────

class TestAccessRequestsListEndpoint:
    def test_member_returns_403(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.get("/api/access/requests", headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_admin_returns_list(self, store_path):
        page_access_mod.request_access("someone@x.com", "db")
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/access/requests", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["requests"]) == 1
        assert data["requests"][0]["email"] == "someone@x.com"


# ── API: POST /api/access/approve ─────────────────────────────────────────────

class TestAccessApproveEndpoint:
    def test_member_returns_403(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.post("/api/access/approve",
                                   json={"email": "x@x.com", "page": "db"},
                                   headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_admin_can_approve(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.post("/api/access/approve",
                                   json={"email": "x@x.com", "page": "db"},
                                   headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert page_access_mod.has_access("x@x.com", "db") is True


# ── API: page-gated endpoints ─────────────────────────────────────────────────

class TestPageGatedEndpoints:
    """DB·Keywords 게이팅이 require_team으로 이관됨(4536688):
    member → 403 (page-access grant가 있어도), team/admin → 허용."""

    def test_keywords_member_no_grant_returns_403(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.get("/api/keywords", headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_keywords_admin_always_allowed(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/keywords", headers=ADMIN_HEADERS)
        assert resp.status_code not in (401, 403)

    def test_keywords_member_with_grant_still_403(self, store_path):
        """page-access grant는 더 이상 keywords 접근을 열지 않는다 (team 권한 필요)."""
        page_access_mod.approve("member@example.com", "keywords")
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.get("/api/keywords", headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_keywords_team_member_passes(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                with patch("src.roles.is_team", return_value=True):
                    resp = client.get("/api/keywords", headers=MEMBER_HEADERS)
        assert resp.status_code not in (401, 403)

    def test_archives_entries_member_no_grant_returns_403(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.get("/api/archives/entries?source=Counterpoint+Research",
                                  headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_archives_entries_member_with_grant_still_403(self, store_path):
        """page-access grant는 더 이상 DB 접근을 열지 않는다 (team 권한 필요)."""
        page_access_mod.approve("member@example.com", "db")
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                resp = client.get("/api/archives/entries?source=Counterpoint+Research",
                                  headers=MEMBER_HEADERS)
        assert resp.status_code == 403

    def test_archives_entries_team_member_passes(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", set()):
                with patch("src.roles.is_team", return_value=True):
                    resp = client.get("/api/archives/entries?source=Counterpoint+Research",
                                      headers=MEMBER_HEADERS)
        assert resp.status_code not in (401, 403)

    def test_archives_entries_admin_always_allowed(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/archives/entries?source=Counterpoint+Research",
                                  headers=ADMIN_HEADERS)
        assert resp.status_code not in (401, 403)


# ── API: /api/me includes pages ───────────────────────────────────────────────

class TestMeIncludesPages:
    def test_member_pages_empty_by_default(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/me", headers=MEMBER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "pages" in data
        assert data["pages"] == []

    def test_member_pages_after_grant(self, store_path):
        page_access_mod.approve("member@example.com", "db")
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/me", headers=MEMBER_HEADERS)
        assert resp.status_code == 200
        assert "db" in resp.json()["pages"]

    def test_admin_pages_contains_all(self, store_path):
        with patch("src.auth.verify_token", new=AsyncMock(side_effect=_mock_verify)):
            with patch("src.auth.ADMIN_EMAILS", {ADMIN_EMAIL}):
                resp = client.get("/api/me", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        pages = resp.json()["pages"]
        assert "db" in pages
        assert "keywords" in pages
