"""캐시 통합 본문 fetch (sync). 호출부에서 asyncio.to_thread 로 wrap 권장.

흐름:
  1. body_cache.get_body(url) → 있으면 즉시 반환 (재시도 안 함)
  2. SKIP_SOURCES (Naver) → 'empty' 마킹 후 빈 문자열 (description에 PDF text 이미 있음)
  3. BLOCKED_SOURCES (Reuters/Omdia/Yole) → 'blocked' 마킹 후 빈 문자열
  4. FETCHABLE → httpx → 본문 추출 → 캐시 저장

Status 분기 (모두 결정론적 캐시 — 재시도하려면 cache clear 필요):
  - 401/403/429/202 → 'blocked' (영구 차단)
  - 그 외 4xx/5xx → 'error' (캐시됨, 재시도 안 함 — clear_body_cache 명시 호출 필요)
  - 200 + body < 200자 → 'empty' (의미있는 본문 없음)
  - 200 + body >= 200자 → 'ok'
"""
import re
import httpx
from bs4 import BeautifulSoup
from . import body_cache

# 첫 fetch 시도에서 차단 확인된 소스 (status_code 401/403/202 또는 CAPTCHA)
BLOCKED_SOURCES = {"Reuters", "Omdia", "Yole Group"}

# Naver Research: description 필드에 PDF 텍스트 이미 있으므로 별도 fetch 불필요
SKIP_SOURCES = {"Naver Research"}

# httpx 직접 fetch 가능한 소스
FETCHABLE_SOURCES = {"Counterpoint Research", "IDC", "Morgan Stanley", "TrendForce"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _extract_body(html: str) -> tuple[int, str]:
    """article > main > p tags 순으로 추출. (글자수, 정제된 텍스트)."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("article") or soup.find("main")
    if body:
        text = body.get_text(" ", strip=True)
    else:
        ps = [
            p.get_text(" ", strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) > 30
        ]
        text = " ".join(ps)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text), text


def fetch_or_cached(url: str, source: str = "") -> str:
    """캐시 우선. 없으면 fetch + 저장. ok 외 status는 빈 문자열 반환.

    sync. async context에서는 await asyncio.to_thread(fetch_or_cached, url, source) 권장.
    """
    cached = body_cache.get_body(url)
    if cached:
        return cached["body"] if cached["status"] == "ok" else ""

    if source in SKIP_SOURCES:
        body_cache.put_body(url, "", source, "empty", "skip")
        return ""

    if source in BLOCKED_SOURCES:
        body_cache.put_body(url, "", source, "blocked", "skip")
        return ""

    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as c:
            r = c.get(url)
        if r.status_code in (401, 403, 429, 202):
            body_cache.put_body(url, "", source, "blocked", "httpx")
            return ""
        if r.status_code != 200:
            body_cache.put_body(url, "", source, "error", "httpx")
            return ""
        body_len, body = _extract_body(r.text)
        if body_len < 200:
            body_cache.put_body(url, "", source, "empty", "httpx")
            return ""
        body_capped = body[:5000]
        body_cache.put_body(url, body_capped, source, "ok", "httpx")
        return body_capped
    except Exception:
        body_cache.put_body(url, "", source, "error", "httpx")
        return ""
