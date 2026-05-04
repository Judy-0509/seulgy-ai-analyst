"""body_fetcher 테스트 (AC #4 #5)."""
import importlib
import pytest


@pytest.fixture
def fetcher_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BODY_CACHE_DB", str(tmp_path / "test.db"))
    from src.services import body_cache
    importlib.reload(body_cache)
    from src.services import body_fetcher
    importlib.reload(body_fetcher)
    yield body_fetcher, body_cache


def test_blocked_source_no_network(fetcher_env, monkeypatch):
    """BLOCKED_SOURCES 는 fetch 시도 없이 즉시 'blocked' 마킹."""
    body_fetcher, body_cache = fetcher_env

    # httpx.Client 호출 시 fail → 호출되면 안 됨
    def _no_call(*args, **kwargs):
        raise AssertionError("httpx should NOT be called for BLOCKED_SOURCES")

    monkeypatch.setattr("httpx.Client", _no_call)

    result = body_fetcher.fetch_or_cached("https://reuters.com/x", source="Reuters")
    assert result == ""
    assert body_cache.is_blocked("https://reuters.com/x")
    row = body_cache.get_body("https://reuters.com/x")
    assert row["status"] == "blocked"
    assert row["extractor"] == "skip"


def test_naver_research_skipped(fetcher_env, monkeypatch):
    """SKIP_SOURCES (Naver) 는 'empty' 상태로 즉시 캐시. fetch 안 함."""
    body_fetcher, body_cache = fetcher_env

    def _no_call(*args, **kwargs):
        raise AssertionError("httpx should NOT be called for SKIP_SOURCES")
    monkeypatch.setattr("httpx.Client", _no_call)

    result = body_fetcher.fetch_or_cached(
        "https://stock.pstatic.net/x.pdf", source="Naver Research"
    )
    assert result == ""
    row = body_cache.get_body("https://stock.pstatic.net/x.pdf")
    assert row["status"] == "empty"


def test_cache_hit_no_network(fetcher_env, monkeypatch):
    """두번째 호출 시 httpx.Client 호출 안됨 (cache hit)."""
    body_fetcher, body_cache = fetcher_env

    # 1차: 캐시에 직접 저장
    body_cache.put_body(
        "https://test.com/cached", "cached body", "TestSrc", "ok", "httpx"
    )

    # 2차: fetch_or_cached 호출 → httpx 호출되면 안 됨
    def _no_call(*args, **kwargs):
        raise AssertionError("httpx should NOT be called when cache hit")
    monkeypatch.setattr("httpx.Client", _no_call)

    result = body_fetcher.fetch_or_cached(
        "https://test.com/cached", source="TestSrc"
    )
    assert result == "cached body"


def test_blocked_cache_hit_returns_empty(fetcher_env, monkeypatch):
    """이전에 'blocked' 마킹된 URL → 빈 문자열 반환, 재시도 안 함."""
    body_fetcher, body_cache = fetcher_env

    body_cache.put_body(
        "https://blocked/1", "", "Reuters", "blocked", "httpx"
    )

    def _no_call(*args, **kwargs):
        raise AssertionError("httpx should NOT be called for blocked cache hit")
    monkeypatch.setattr("httpx.Client", _no_call)

    result = body_fetcher.fetch_or_cached("https://blocked/1", source="Reuters")
    assert result == ""


def test_extract_body_short_returns_empty():
    """본문 < 200자 → 'empty' 상태."""
    from src.services.body_fetcher import _extract_body
    short_html = "<html><body><p>short</p></body></html>"
    body_len, _ = _extract_body(short_html)
    assert body_len < 200


def test_extract_body_article_tag():
    """article 태그가 있으면 우선 추출."""
    from src.services.body_fetcher import _extract_body
    html = (
        "<html><body>"
        "<article>" + ("This is meaningful content. " * 30) + "</article>"
        "<p>noise</p></body></html>"
    )
    body_len, body = _extract_body(html)
    assert body_len > 200
    assert "meaningful content" in body
    assert "noise" not in body  # article 태그 우선이라 외부 p는 제외
