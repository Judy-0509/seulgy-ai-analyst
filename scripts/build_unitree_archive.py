"""Unitree Robotics 뉴스 아카이브 빌더.

전략:
  - unitree.com/news 페이지 HTML 파싱 (공개)
  - 증분 업데이트

실행:
    python scripts/build_unitree_archive.py

산출:
    data/archives/unitree.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "unitree.json"
SOURCE_NAME  = "Unitree Robotics"
SITE_BASE    = "https://www.unitree.com"
NEWS_URLS    = [
    "https://www.unitree.com/news/",
    "https://www.unitree.com/category/news/",
]

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


def parse_article_links(html: str, base: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"/(news|article|post)/[a-z0-9\-]+", href, re.I):
            continue
        url = href if href.startswith("http") else SITE_BASE + href
        if url in seen:
            continue
        seen.add(url)
        title = ""
        heading = a.find(["h1", "h2", "h3", "h4"])
        if heading:
            title = heading.get_text(" ", strip=True)
        if not title:
            title = a.get_text(" ", strip=True)[:120].strip()
        date = ""
        parent = a.parent
        for _ in range(5):
            if parent is None:
                break
            time_el = parent.find("time")
            if time_el:
                date = time_el.get("datetime") or time_el.get_text(strip=True)
                break
            parent = parent.parent
        if title and len(title) > 5:
            results.append((url, title, date))
    return results


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = date = ""
    el = soup.find("meta", property="og:title")
    if el and el.get("content"):
        title = re.sub(r"\s+", " ", el["content"]).strip()
    for prop in ["og:description", "description"]:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if el and el.get("content"):
            desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
            break
    for prop in ["article:published_time"]:
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

    pairs: list[tuple[str, str, str]] = []
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        for news_url in NEWS_URLS:
            print(f"\n  [1/3] 뉴스 목록 수집: {news_url}")
            status, html = await fetch(client, news_url)
            if status != 200:
                print(f"  ⚠ 접근 실패: HTTP {status}")
                continue
            found = parse_article_links(html, news_url)
            print(f"  → 발견: {len(found)}건")
            pairs.extend(found)

        # 중복 제거
        seen_pair: set[str] = set()
        unique_pairs = []
        for u, t, d in pairs:
            if u not in seen_pair:
                seen_pair.add(u)
                unique_pairs.append((u, t, d))
        pairs = unique_pairs

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
                    title, desc, date = extract_meta(body)
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
