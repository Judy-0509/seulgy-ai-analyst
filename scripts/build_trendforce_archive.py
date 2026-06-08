"""TrendForce News 아카이브 빌더.

전략:
  - sitemap에 새 URL 형식 누락이라 페이지네이션 직접 크롤
  - URL 패턴 `/news/YYYY/MM/DD/news-{slug}/`에서 날짜 파싱 (lastmod 대용)
  - 사용자 지정 시작 날짜(YYYY-MM-DD)까지 거꾸로 페이지 순회
  - 각 기사에서 og:title + og:description 추출

사용:
    python scripts/build_trendforce_archive.py                 # 최근 2개월 (Counterpoint와 동일)
    python scripts/build_trendforce_archive.py 2026-03-01      # 특정 날짜부터 현재까지
    python scripts/build_trendforce_archive.py 2026-03-01 50   # 시작 날짜 + 페이지 상한

산출:
    data/archives/trendforce.json
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

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "trendforce.json"

SITE_BASE = "https://www.trendforce.com"
INDEX_TEMPLATE = SITE_BASE + "/news/page/{n}/"
ARTICLE_URL_PATTERN = re.compile(r"/news/(\d{4})/(\d{2})/(\d{2})/news-[a-z0-9\-]+/?$")

DEFAULT_DAYS_BACK = 60   # Counterpoint 2026-03 ~ 04 ≈ 약 60일
MAX_PAGES = 100          # 안전 cap (페이지당 ~8건이면 100 × 8 = 800 entry — 2개월 여유)
CONCURRENCY = 6
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def extract_article_links(html: str) -> list[tuple[str, str]]:
    """페이지 HTML에서 article URL + 날짜 추출.

    URL 패턴 `/news/YYYY/MM/DD/news-...` → (full_url, "YYYY-MM-DD")
    """
    soup = BeautifulSoup(html, "html.parser")
    out = {}  # url → date
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            href = SITE_BASE + href
        m = ARTICLE_URL_PATTERN.search(href)
        if not m:
            continue
        y, mo, d = m.group(1), m.group(2), m.group(3)
        article_date = f"{y}-{mo}-{d}"
        # 정규화 (trailing slash 통일)
        norm = href.rstrip("/")
        if norm not in out:
            out[norm] = article_date
    return list(out.items())


def extract_meta(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title, desc = "", ""
    el_t = soup.find("meta", property="og:title")
    if el_t and el_t.get("content"):
        title = re.sub(r"\s+", " ", el_t["content"]).strip()
    el_d = soup.find("meta", property="og:description")
    if el_d and el_d.get("content"):
        desc = re.sub(r"\s+", " ", el_d["content"]).strip()
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc


async def collect_urls_until(client: httpx.AsyncClient, cutoff_date: str, max_pages: int) -> list[tuple[str, str]]:
    """페이지 1, 2, 3... 순회하며 cutoff_date 이전 기사가 나타날 때까지 URL 수집."""
    collected: dict[str, str] = {}
    last_seen_date = None
    print(f"\n  [1/3] 페이지네이션 크롤 (cutoff: {cutoff_date}, max_pages: {max_pages})")
    for page in range(1, max_pages + 1):
        url = INDEX_TEMPLATE.format(n=page)
        s, html = await fetch(client, url)
        if s != 200:
            print(f"    [page {page:3d}] HTTP {s} — 종료")
            break
        links = extract_article_links(html)
        if not links:
            print(f"    [page {page:3d}] article 0건 — 종료")
            break

        new_count = 0
        page_oldest = None
        for u, d in links:
            if d < cutoff_date:
                # cutoff 이전 기사도 같은 페이지에 섞일 수 있음 — 추가는 하지 않고 트래킹만
                page_oldest = d if (page_oldest is None or d < page_oldest) else page_oldest
                continue
            if u not in collected:
                collected[u] = d
                new_count += 1
            page_oldest = d if (page_oldest is None or d < page_oldest) else page_oldest

        last_seen_date = page_oldest or last_seen_date
        print(f"    [page {page:3d}] new {new_count:2d}, total {len(collected):3d}, oldest {page_oldest or '?'}")

        # 페이지의 최노 기사 날짜가 cutoff보다 이전이면 종료
        if page_oldest and page_oldest < cutoff_date:
            print(f"    → 페이지 {page}의 최노 {page_oldest} < cutoff {cutoff_date} → 종료")
            break

    return list(collected.items())


async def fetch_meta_all(client: httpx.AsyncClient, url_dates: list[tuple[str, str]]) -> list[dict]:
    """동시성 제한 하에 각 URL에서 og:title + og:description 추출."""
    print(f"\n  [2/3] 메타 추출 ({len(url_dates)}건, concurrency {CONCURRENCY})")
    sem = asyncio.Semaphore(CONCURRENCY)
    entries: list[dict] = []
    ok_count = 0
    fail_count = 0

    async def _one(idx: int, url: str, dt: str):
        nonlocal ok_count, fail_count
        async with sem:
            s, html = await fetch(client, url)
            if s != 200:
                fail_count += 1
                return None
            title, desc = extract_meta(html)
            if not title and not desc:
                fail_count += 1
                return None
            ok_count += 1
            if (idx + 1) % 25 == 0:
                print(f"    진행: {idx+1}/{len(url_dates)} (ok {ok_count}, fail {fail_count})")
            # TrendForce는 lastmod이 따로 없어 URL 날짜를 ISO 형식으로 변환
            return {
                "url": url,
                "title": title,
                "description": desc,
                "lastmod": dt + "T00:00:00.000Z",
                "source": "TrendForce",
                "tier": 1,
            }

    tasks = [_one(i, u, d) for i, (u, d) in enumerate(url_dates)]
    results = await asyncio.gather(*tasks)
    entries = [r for r in results if r]
    print(f"  → 메타 추출 완료: {len(entries)}건 (실패 {fail_count}건)")
    return entries


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        urls = {e["url"] for e in entries if e.get("url")}
        return entries, urls
    except Exception:
        return [], set()


async def build(cutoff_date: str, max_pages: int) -> dict:
    print("=" * 76)
    print("  TrendForce News Archive Builder")
    print(f"  cutoff: {cutoff_date}, max_pages: {max_pages}")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing_entries)}건 (있으면 재fetch 생략)")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as c:
        url_dates = await collect_urls_until(c, cutoff_date, max_pages)
        if not url_dates:
            print("\n  ! URL 수집 실패")
            return {}
        url_dates.sort(key=lambda x: x[1], reverse=True)

        # known_urls에 있는 것은 fetch 스킵
        new_pairs = [(u, d) for u, d in url_dates if u not in known_urls]
        skipped = len(url_dates) - len(new_pairs)
        print(f"  → 신규 URL: {len(new_pairs)}건 (기존 보유 {skipped}건 스킵)")

        new_entries = await fetch_meta_all(c, new_pairs) if new_pairs else []

    # Merge + dedup + 정렬
    all_entries = existing_entries + new_entries
    seen = set()
    merged: list[dict] = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    print("\n  [3/3] 아카이브 저장")
    archive = {
        "source": "TrendForce",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "cutoff_date": cutoff_date,
        "max_pages_used": max_pages,
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "previously_known": len(existing_entries),
        "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"  → 저장: {ARCHIVE_PATH}  ({size_kb:.1f} KB)")
    print("\n" + "=" * 76)
    print(f"  완료. 총 {len(merged)}건 (신규 +{len(new_entries)}, 기존 {len(existing_entries)})")
    print("=" * 76)
    return archive


def show_samples(archive: dict, kw_list: list[str]):
    entries = archive.get("entries", [])
    if not entries:
        return
    print("\n  키워드별 매칭 샘플:")
    for kw in kw_list:
        kw_l = kw.lower()
        matched = [
            e for e in entries
            if kw_l in (e["title"] + " " + e["description"]).lower()
        ]
        print(f"\n  · '{kw}' → {len(matched)}건")
        for e in matched[:3]:
            print(f"      [{e['lastmod'][:10]}] {e['title'][:80]}")


def parse_args():
    """CLI: [cutoff_date YYYY-MM-DD] [max_pages]"""
    cutoff = (date.today() - timedelta(days=DEFAULT_DAYS_BACK)).isoformat()
    max_pages = MAX_PAGES
    if len(sys.argv) > 1:
        a1 = sys.argv[1]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a1):
            cutoff = a1
        else:
            try:
                # 숫자면 days_back으로 해석
                days = int(a1)
                cutoff = (date.today() - timedelta(days=days)).isoformat()
            except ValueError:
                print(f"사용법: python {sys.argv[0]} [YYYY-MM-DD | days_back] [max_pages]")
                sys.exit(1)
    if len(sys.argv) > 2:
        try:
            max_pages = int(sys.argv[2])
        except ValueError:
            pass
    return cutoff, max_pages


async def main():
    cutoff, max_pages = parse_args()
    archive = await build(cutoff, max_pages)
    show_samples(archive, ["foldable", "iPhone", "Samsung", "memory", "OLED", "TSMC", "Apple"])


if __name__ == "__main__":
    asyncio.run(main())
