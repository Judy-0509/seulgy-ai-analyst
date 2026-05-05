"""TechCrunch Robotics 아카이브 빌더.

전략: /category/robotics/page/N/ 페이지네이션 크롤링.
      URL에서 날짜 직접 파싱 (YYYY/MM/DD 포함).
      증분 업데이트: 기존 URL 재fetch 없음.

실행:
    python scripts/build_techcrunch_robotics_archive.py         # 최근 6개월
    python scripts/build_techcrunch_robotics_archive.py 12      # 최근 12개월

산출:
    data/archives/techcrunch_robotics.json
"""
import asyncio
import io
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "techcrunch_robotics.json"
SOURCE_NAME  = "TechCrunch"
SITE_BASE    = "https://techcrunch.com"
CATEGORY_BASE = SITE_BASE + "/category/robotics/page/{}/"

DEFAULT_MONTHS = 6
MAX_PAGES      = 60
CONCURRENCY    = 4
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://techcrunch.com/",
}

DATE_IN_URL = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def cutoff_date(months: int) -> str:
    d = date.today() - timedelta(days=months * 30)
    return d.strftime("%Y-%m-%d")


def url_date(url: str) -> str:
    m = DATE_IN_URL.search(url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


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


def parse_article_links(html: str) -> list[str]:
    """카테고리 페이지에서 기사 URL 추출."""
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if DATE_IN_URL.search(href) and "techcrunch.com" in href:
            # 카테고리/태그 페이지 자체 URL 제외
            if href not in urls and "/category/" not in href and "/tag/" not in href:
                urls.append(href)
    return list(dict.fromkeys(urls))  # 순서 유지 dedup


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = pub_date = ""
    el = soup.find("meta", property="og:title")
    if el and el.get("content"):
        title = re.sub(r"\s+", " ", el["content"]).strip()
    for prop in ["og:description", "description"]:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if el and el.get("content"):
            desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
            break
    el = soup.find("meta", property="article:published_time")
    if el and el.get("content"):
        pub_date = el["content"]
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc, pub_date


async def build(months: int) -> dict:
    cutoff = cutoff_date(months)
    print("=" * 70)
    print(f"  {SOURCE_NAME} Robotics Archive Builder")
    print(f"  기간: 최근 {months}개월 (cutoff: {cutoff})")
    print("=" * 70)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    # 1. 카테고리 페이지 순회
    print(f"\n  [1/3] 카테고리 페이지 순회 (최대 {MAX_PAGES}페이지)")
    all_urls: list[str] = []

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        stop_flag = False
        for page in range(1, MAX_PAGES + 1):
            if stop_flag:
                break
            page_url = CATEGORY_BASE.format(page)
            st, html = await fetch(client, page_url)
            if st == 404 or st == 0:
                print(f"    page {page:3d}: 종료 (HTTP {st})")
                break
            if st != 200:
                print(f"    page {page:3d}: skip (HTTP {st})")
                continue

            links = parse_article_links(html)
            if not links:
                print(f"    page {page:3d}: 기사 없음 → 종료")
                break

            new_on_page = 0
            for url in links:
                d = url_date(url)
                if d and d < cutoff:
                    stop_flag = True
                    continue
                if url not in all_urls:
                    all_urls.append(url)
                    new_on_page += 1

            oldest = min((url_date(u) for u in links if url_date(u)), default="?")
            print(f"    page {page:3d}: {len(links):3d}건 발견, 신규 {new_on_page}건, oldest={oldest}")
            if stop_flag:
                print(f"    → cutoff {cutoff} 도달 → 순회 종료")

        print(f"  → 수집 URL: {len(all_urls)}건")

        # 기존 URL 스킵
        new_urls = [u for u in all_urls if u not in known_urls]
        print(f"  → 신규: {len(new_urls)}건 (기존 {len(all_urls)-len(new_urls)}건 스킵)")

        # 2. 신규 URL 메타 fetch
        print(f"\n  [2/3] 기사 메타 fetch (신규 {len(new_urls)}건, 동시 {CONCURRENCY})")
        sem = asyncio.Semaphore(CONCURRENCY)
        ok = err = 0

        async def fetch_meta(url: str):
            nonlocal ok, err
            async with sem:
                st, html = await fetch(client, url)
                if st != 200:
                    err += 1
                    return None
                title, desc, pub_date = extract_meta(html)
                if not title:
                    err += 1
                    return None
                ok += 1
                lm = pub_date or (url_date(url) + "T00:00:00")
                return {
                    "url":         url,
                    "title":       title,
                    "description": desc,
                    "lastmod":     lm,
                    "source":      SOURCE_NAME,
                    "tier":        1,
                }

        tasks   = [fetch_meta(u) for u in new_urls]
        results = await asyncio.gather(*tasks)
        new_entries = [r for r in results if r]
        print(f"  → 완료: {ok}건, 실패: {err}건")

    # Merge + dedup + 정렬
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

    print(f"\n  [3/3] 저장")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "months":           months,
        "cutoff_date":      cutoff,
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
    print(f"  완료. 총 {len(merged)}건 (신규 +{len(new_entries)}, 기존 {len(existing_entries)})")
    print("=" * 70)
    return archive


async def main():
    months = DEFAULT_MONTHS
    if len(sys.argv) > 1:
        try:
            months = int(sys.argv[1])
        except ValueError:
            print(f"사용법: python {sys.argv[0]} [개월수]")
            sys.exit(1)
    await build(months)


if __name__ == "__main__":
    asyncio.run(main())
