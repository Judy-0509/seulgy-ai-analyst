"""Boston Dynamics 블로그/뉴스 아카이브 빌더.

전략:
  - bostondynamics.com/blog 페이지 HTML 파싱
  - 본문 접근 가능 (공개)
  - 증분 업데이트: 기존 URL 재fetch 생략

실행:
    python scripts/build_boston_dynamics_archive.py

산출:
    data/archives/boston_dynamics.json
"""
import asyncio
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "boston_dynamics.json"
SOURCE_NAME  = "Boston Dynamics"
SITE_BASE    = "https://bostondynamics.com"
BLOG_URL     = "https://bostondynamics.com/blog/"

CONCURRENCY     = 3
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data    = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        return entries, {e["url"] for e in entries if e.get("url")}
    except Exception:
        return [], set()


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def parse_blog_index(html: str) -> list[tuple[str, str, str]]:
    """블로그 목록에서 (url, title, date) 추출."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    # 카드 패턴 탐색: <a href="/blog/...">
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"/blog/[a-z0-9\-]+", href):
            continue
        url = href if href.startswith("http") else SITE_BASE + href
        # 중복 제거
        if any(u == url for u, _, _ in results):
            continue
        # 제목: a 내부 또는 가장 가까운 heading
        title = ""
        heading = a.find(["h1", "h2", "h3", "h4"])
        if heading:
            title = heading.get_text(" ", strip=True)
        if not title:
            title = a.get_text(" ", strip=True)[:120].strip()
        # 날짜: 근처 <time> 또는 날짜처럼 보이는 텍스트
        date = ""
        parent = a.parent
        for _ in range(4):
            if parent is None:
                break
            time_el = parent.find("time")
            if time_el:
                date = time_el.get("datetime") or time_el.get_text(strip=True)
                break
            parent = parent.parent
        if title and url != BLOG_URL:
            results.append((url, title, date))
    return results


def extract_meta(html: str, url: str) -> tuple[str, str, str]:
    """og:title, og:description, article:published_time 추출."""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    desc  = ""
    date  = ""
    for prop in ["og:title"]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            title = re.sub(r"\s+", " ", el["content"]).strip()
    for prop in ["og:description", "description"]:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if el and el.get("content"):
            desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
            break
    for prop in ["article:published_time", "article:modified_time"]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            date = el["content"]
            break
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc, date


async def build() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Archive Builder")
    print("=" * 60)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        print(f"\n  [1/3] 블로그 목록 수집: {BLOG_URL}")
        status, html = await fetch(client, BLOG_URL)
        if status != 200:
            print(f"  ⚠ 블로그 목록 접근 실패: HTTP {status}")
            pairs = []
        else:
            pairs = parse_blog_index(html)
            print(f"  → 발견: {len(pairs)}건")

        new_pairs = [(u, t, d) for u, t, d in pairs if u not in known_urls]
        skipped   = len(pairs) - len(new_pairs)
        print(f"  → 신규: {len(new_pairs)}건 (기존 {skipped}건 스킵)")

        print(f"\n  [2/3] 기사 메타 fetch (신규 {len(new_pairs)}건)")
        sem = asyncio.Semaphore(CONCURRENCY)
        new_entries: list[dict] = []

        async def fetch_article(url: str, fallback_title: str, fallback_date: str):
            async with sem:
                st, body = await fetch(client, url)
                if st == 200:
                    title, desc, date = extract_meta(body, url)
                else:
                    title, desc, date = fallback_title, "", fallback_date
                if not title:
                    title = fallback_title
                if not date:
                    date = fallback_date
                return {
                    "url":         url,
                    "title":       title,
                    "description": desc,
                    "lastmod":     date,
                    "source":      SOURCE_NAME,
                    "tier":        1,
                }

        tasks   = [fetch_article(u, t, d) for u, t, d in new_pairs]
        results = await asyncio.gather(*tasks)
        new_entries = [r for r in results if r and r.get("title")]
        print(f"  → 완료: {len(new_entries)}건")

    all_entries = existing_entries + new_entries
    seen: set[str] = set()
    merged: list[dict] = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    print(f"\n  [3/3] 저장: {len(merged)}건 (신규 +{len(new_entries)})")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "blog_url":         BLOG_URL,
        "body_access":      "public",
        "entry_count":      len(merged),
        "newly_added":      len(new_entries),
        "previously_known": len(existing_entries),
        "entries":          merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"  → {ARCHIVE_PATH}  ({size_kb:.1f} KB)")
    print("=" * 60)
    return archive


if __name__ == "__main__":
    asyncio.run(build())
