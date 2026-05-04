"""body_cache 단위 테스트 (AC #4 #5 #8)."""
import importlib
import os
import sqlite3
import pytest


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """tmp_path 기반 격리된 body_cache 모듈."""
    monkeypatch.setenv("BODY_CACHE_DB", str(tmp_path / "test.db"))
    from src.services import body_cache
    importlib.reload(body_cache)
    yield body_cache


def test_put_get_roundtrip(cache):
    cache.put_body("https://x/1", "hello world", "TestSrc", "ok", "httpx")
    row = cache.get_body("https://x/1")
    assert row is not None
    assert row["body"] == "hello world"
    assert row["status"] == "ok"
    assert row["source"] == "TestSrc"
    assert row["char_count"] == 11
    assert row["extractor"] == "httpx"


def test_upsert_keeps_one_row(cache):
    cache.put_body("https://x/1", "first", "S", "ok", "httpx")
    cache.put_body("https://x/1", "second", "S", "ok", "httpx")
    assert cache.stats()["total"] == 1
    assert cache.get_body("https://x/1")["body"] == "second"


def test_clear_by_source(cache):
    cache.put_body("https://a/1", "a", "SrcA", "ok", "httpx")
    cache.put_body("https://a/2", "a2", "SrcA", "ok", "httpx")
    cache.put_body("https://b/1", "b", "SrcB", "ok", "httpx")
    n = cache.clear(source="SrcA")
    assert n == 2
    assert cache.stats()["total"] == 1


def test_clear_by_url(cache):
    cache.put_body("https://x/1", "a", "S", "ok", "httpx")
    cache.put_body("https://x/2", "b", "S", "ok", "httpx")
    n = cache.clear(url="https://x/1")
    assert n == 1
    assert cache.stats()["total"] == 1


def test_clear_all(cache):
    cache.put_body("https://x/1", "a", "S", "ok", "httpx")
    cache.put_body("https://x/2", "b", "S", "ok", "httpx")
    n = cache.clear()
    assert n == 2
    assert cache.stats()["total"] == 0


def test_is_blocked(cache):
    cache.put_body("https://blocked/1", "", "Reuters", "blocked", "skip")
    cache.put_body("https://ok/1", "good", "S", "ok", "httpx")
    assert cache.is_blocked("https://blocked/1") is True
    assert cache.is_blocked("https://ok/1") is False
    assert cache.is_blocked("https://unknown/1") is False


def test_has_body(cache):
    assert cache.has_body("https://x/1") is False
    cache.put_body("https://x/1", "a", "S", "ok", "httpx")
    assert cache.has_body("https://x/1") is True


def test_wal_mode_active(cache):
    cache.put_body("https://x/1", "a", "S", "ok", "httpx")
    conn = sqlite3.connect(cache.DB_PATH)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"


def test_stats_aggregates(cache):
    cache.put_body("https://a/1", "hello", "SrcA", "ok", "httpx")
    cache.put_body("https://a/2", "hi", "SrcA", "blocked", "skip")
    cache.put_body("https://b/1", "world", "SrcB", "ok", "httpx")
    s = cache.stats()
    assert s["total"] == 3
    assert s["by_source"] == {"SrcA": 2, "SrcB": 1}
    assert s["by_status"] == {"ok": 2, "blocked": 1}
    assert s["total_chars"] == len("hello") + len("hi") + len("world")
