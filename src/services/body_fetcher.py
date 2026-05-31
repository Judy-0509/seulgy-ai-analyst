"""캐시 통합 본문 fetch (sync). 호출부에서 asyncio.to_thread 로 wrap 권장.

흐름:
  1. body_cache.get_body(url) → 있으면 즉시 반환
  2. SKIP_SOURCES (Naver) → 'empty' 마킹 후 빈 문자열 (description에 PDF text 이미 있음)
  3. BLOCKED_SOURCES (Omdia/Yole) → Wayback Machine 시도 → 실패 시 'wayback_miss'
  4. FETCHABLE → httpx → 본문 추출 → 캐시 저장

Status 분기:
  - 'ok'           → 본문 있음 (httpx 또는 wayback으로 성공)
  - 'blocked'      → HTTP 401/403/429/202 차단
  - 'wayback_miss' → BLOCKED_SOURCES 이지만 Wayback에도 없음 (재시도 안 함)
  - 'empty'        → 200이지만 본문 < 200자
  - 'error'        → 그 외 4xx/5xx (재시도하려면 cache clear 필요)
"""
import re
import httpx
from bs4 import BeautifulSoup
from . import body_cache

# 첫 fetch 시도에서 차단 확인된 소스 (403/CAPTCHA/paywall) — Wayback Machine 폴백 시도
BLOCKED_SOURCES = {"Omdia", "Yole Group"}

# 정책상 어떤 형태의 fetch도 시도하지 않는 소스 (ToS / robots.txt 명시 차단).
# 즉시 'blocked'/'skip' 으로 캐시에 마킹하고 본문은 비워둔다 — Wayback도 시도 안 함.
HARD_BLOCKED_SOURCES = {"Reuters"}

# Naver Research: description 필드에 PDF 텍스트 이미 있으므로 별도 fetch 불필요
SKIP_SOURCES = {"Naver Research"}

# httpx 직접 fetch 가능한 소스
FETCHABLE_SOURCES = {
    "Counterpoint Research", "IDC", "TrendForce",
    "MacRumors", "AppleInsider", "9to5Mac", "9to5Google", "Digitimes", "Wccftech",
    # Automotive (2026-05-30 robots.txt 정밀 재검토 통과 — docs/crawling_robots_review.md)
    # 제외(metadata-only): Automotive World, Transport & Environment = robots에서 AI 크롤러 명시 차단.
    "WardsAuto", "Automotive Dive", "InsideEVs", "CnEVPost", "CarNewsChina",
    "VW Group", "JATO Dynamics", "Cox Automotive", "ACEA", "BloombergNEF", "RMI",
    "Motor1",  # 2026-05-30: robots clean(AI봇 차단 없음), 본문 5000+자 추출 확인
}

# robots.txt / ToS 정책상 본문 fetch 금지 — metadata only.
# state_machine.py는 FETCHABLE_SOURCES ∪ BLOCKED_SOURCES 에만 fetch 시도하므로,
# 이 셋에 들어있는 이름은 (둘 다 미등록 상태로) 자동 skip됨. 본 셋은 문서/감사 목적.
# 근거: docs/crawling_robots_review.md
METADATA_ONLY_SOURCES = {
    "DigiTimes Asia",       # robots.txt: GPTBot/The Knowledge AI 차단; codex 정책 metadata-only
    "CCS Insight",          # 유료 리서치 firm; codex 정책 metadata-only
    # 2026-05-30 robots.txt에서 AI 크롤러 명시 차단 확인 → fetch 안 함 (metadata only)
    "Automotive World",        # robots: GPTBot/ClaudeBot/CCBot/Google-Extended/Bytespider/Amazonbot/Applebot-Extended 전면 Disallow
    "Transport & Environment", # robots: GPTBot/Google-Extended Disallow
    "Autocar",                 # robots: GPTBot Disallow + 본문 추출 thin(~400자, JS) → metadata only
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_WAYBACK_API = "https://archive.org/wayback/available"


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


def _fetch_via_wayback(url: str) -> str:
    """Wayback Machine에서 차단된 URL의 캐시 버전 시도.

    성공 시 본문 문자열 반환, 실패 시 빈 문자열.
    """
    try:
        r = httpx.get(_WAYBACK_API, params={"url": url}, timeout=10)
        if r.status_code != 200:
            return ""
        snapshot = r.json().get("archived_snapshots", {}).get("closest", {})
        if not snapshot.get("available"):
            return ""
        wayback_url = snapshot["url"]
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as c:
            r2 = c.get(wayback_url)
        if r2.status_code != 200:
            return ""
        body_len, body = _extract_body(r2.text)
        if body_len < 200:
            return ""
        return body[:5000]
    except Exception:
        return ""


def fetch_or_cached(url: str, source: str = "") -> str:
    """캐시 우선. 없으면 fetch + 저장. ok 외 status는 빈 문자열 반환.

    sync. async context에서는 await asyncio.to_thread(fetch_or_cached, url, source) 권장.
    """
    cached = body_cache.get_body(url)
    if cached:
        if cached["status"] == "ok":
            return cached["body"]
        if cached["status"] == "wayback_miss":
            return ""  # Wayback 이미 시도했고 없음 — 재시도 안 함
        if source not in BLOCKED_SOURCES:
            return ""  # blocked/error/empty — 재시도 안 함
        # BLOCKED_SOURCES + 이전 상태가 'blocked' → Wayback 아직 미시도, fall through

    if source in HARD_BLOCKED_SOURCES:
        body_cache.put_body(url, "", source, "blocked", "skip")
        return ""

    if source in SKIP_SOURCES:
        body_cache.put_body(url, "", source, "empty", "skip")
        return ""

    if source in BLOCKED_SOURCES:
        body = _fetch_via_wayback(url)
        if body:
            body_cache.put_body(url, body, source, "ok", "wayback")
            return body
        body_cache.put_body(url, "", source, "wayback_miss", "wayback")
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
