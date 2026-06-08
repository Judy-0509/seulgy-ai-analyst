"""SAE International 아카이브 빌더.

전략: sitemap.xml 크롤 → og:title / og:description 추출. 증분 모드.

실행:
    python scripts/build_sae_archive.py

산출:
    data/archives/sae.json
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

# ── 상수 (파일마다 교체) ──────────────────────────────────────────
ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "sae.json"
SOURCE_NAME  = "SAE International"
SITE_BASE    = "https://www.sae.org"
SITEMAP_URL  = "https://www.sae.org/sitemap.xml"
URL_INCLUDES: list[str] = ["/news/", "/publications/", "/blog/", "/automotive/"]
URL_EXCLUDES: list[str] = ["/store/", "/membership/", "/events/register", "/careers/", "/standards/"]
MAX_ARTICLES = 300
CONCURRENCY  = 5
REQUEST_TIMEOUT = 20
# ──────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
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
        r = await client.get(url)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def parse_sitemap(xml_body: str) -> tuple[list[str], list[tuple[str, str]]]:
    """(sub_sitemap_urls, [(article_url, lastmod)]) 반환."""
    soup = BeautifulSoup(xml_body, "xml")
    sub_sitemaps = [loc.text.strip() for sm in soup.find_all("sitemap")
                    if (loc := sm.find("loc"))]
    articles = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm  = u.find("lastmod")
        if loc:
            articles.append((loc.text.strip(), lm.text.strip() if lm else ""))
    return sub_sitemaps, articles


def filter_url(url: str) -> bool:
    if URL_INCLUDES and not any(inc in url for inc in URL_INCLUDES):
        return False
    if URL_EXCLUDES and any(exc in url for exc in URL_EXCLUDES):
        return False
    return True


def extract_meta(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = ""
    for prop, key in [("og:title", "title"), ("og:description", "desc")]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            val = re.sub(r"\s+", " ", el["content"]).strip()
            if key == "title": title = val
            else: desc = val
    if not title:
        t = soup.find("title")
        if t: title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc


async def collect_urls(client: httpx.AsyncClient) -> list[tuple[str, str]]:
    """sitemap(index) → [(url, lastmod)] 수집."""
    status, body = await fetch(client, SITEMAP_URL)
    if status != 200:
        print(f"  ✗ sitemap 실패 [{status}]: {SITEMAP_URL}")
        return []

    sub_sitemaps, articles = parse_sitemap(body)

    if sub_sitemaps:
        print(f"  → sitemap index: sub-sitemap {len(sub_sitemaps)}개")
        for sm_url in sub_sitemaps:
            s, b = await fetch(client, sm_url)
            if s == 200:
                _, more = parse_sitemap(b)
                articles.extend(more)

    filtered = [(u, lm) for u, lm in articles if filter_url(u)]
    seen: set[str] = set()
    uniq: list[tuple[str, str]] = []
    for u, lm in sorted(filtered, key=lambda x: x[1] or "", reverse=True):
        if u not in seen:
            seen.add(u)
            uniq.append((u, lm))
    return uniq[:MAX_ARTICLES]


async def build() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Archive Builder")
    print("=" * 60)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT, follow_redirects=True, headers=HEADERS
    ) as client:
        print(f"\n  [1/3] sitemap 수집: {SITEMAP_URL}")
        all_pairs = await collect_urls(client)
        new_pairs  = [(u, lm) for u, lm in all_pairs if u not in known_urls]
        print(f"  → 전체 {len(all_pairs)}건, 신규 {len(new_pairs)}건")

        new_entries: list[dict] = []
        if new_pairs:
            print(f"\n  [2/3] og:meta 추출 ({len(new_pairs)}건, 동시 {CONCURRENCY})")
            sem = asyncio.Semaphore(CONCURRENCY)
            ok_cnt = 0

            async def fetch_meta(idx: int, url: str, lm: str):
                nonlocal ok_cnt
                async with sem:
                    s, html = await fetch(client, url)
                    if s != 200:
                        return None
                    title, desc = extract_meta(html)
                    if not title:
                        return None
                    ok_cnt += 1
                    if (idx + 1) % 20 == 0:
                        print(f"    진행: {idx+1}/{len(new_pairs)} (ok {ok_cnt})")
                    return {
                        "url": url, "title": title, "description": desc,
                        "lastmod": lm, "source": SOURCE_NAME, "tier": 1,
                    }

            tasks = [fetch_meta(i, u, lm) for i, (u, lm) in enumerate(new_pairs)]
            results = await asyncio.gather(*tasks)
            new_entries = [r for r in results if r]
            print(f"  → 추출 완료: {len(new_entries)}건")
        else:
            print("\n  [2/3] 신규 없음 — fetch 생략")

    all_entries = existing_entries + new_entries
    seen_url: set[str] = set()
    merged: list[dict] = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen_url:
            continue
        seen_url.add(u)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    print(f"\n  [3/3] 저장: {len(merged)}건 (신규 +{len(new_entries)})")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "sitemap_url":      SITEMAP_URL,
        "entry_count":      len(merged),
        "newly_added":      len(new_entries),
        "previously_known": len(existing_entries),
        "entries":          merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"  → {ARCHIVE_PATH}  ({size_kb:.1f} KB)")
    print("=" * 60)
    return archive


if __name__ == "__main__":
    asyncio.run(build())
