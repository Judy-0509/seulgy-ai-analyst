"""Morgan Stanley Ideas 아카이브 빌더.

전략:
  - morganstanley.com/sitemap.xml 에서 /ideas/ URL 662건 추출 (lastmod 포함)
  - httpx Chrome UA로 개별 페이지 접근 → og:title + og:description 추출
  - Playwright 불필요 (httpx 200 OK 확인됨)
  - 증분 업데이트 (기존 archive 보존, 신규만 fetch)

사용:
  python scripts/build_morgan_stanley_archive.py

산출:
  data/archives/morgan_stanley.json
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

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "morgan_stanley.json"

SITE_BASE = "https://www.morganstanley.com"
SITEMAP_URL = SITE_BASE + "/sitemap.xml"

CONCURRENCY = 3
REQUEST_TIMEOUT = 20
REQUEST_DELAY = 1.2  # seconds between requests per semaphore slot
MAX_RETRIES = 2
RETRY_DELAY = 8.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    for attempt in range(MAX_RETRIES + 1):
        try:
            await asyncio.sleep(REQUEST_DELAY)
            r = await client.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429 or r.status_code == 403:
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
            return r.status_code, r.text
        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return 0, f"ERR: {e}"
    return 0, "ERR: max retries exceeded"


def parse_sitemap_ideas(xml: str) -> list[tuple[str, str]]:
    """sitemap에서 /ideas/ URL만 추출 → [(url, lastmod)]."""
    soup = BeautifulSoup(xml, "xml")
    out = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm = u.find("lastmod")
        if not loc:
            continue
        url = loc.text.strip()
        if "/ideas/" not in url:
            continue
        lastmod = lm.text.strip()[:10] if lm else ""
        out.append((url, lastmod))
    return out


def extract_meta(html: str) -> tuple[str, str]:
    """og:title + og:description 추출."""
    soup = BeautifulSoup(html, "html.parser")
    title, desc = "", ""
    og_t = soup.find("meta", property="og:title")
    if og_t and og_t.get("content"):
        title = re.sub(r"\s+", " ", og_t["content"]).strip()
        # "| Morgan Stanley" 접미사 제거
        title = re.sub(r"\s*\|\s*Morgan Stanley\s*$", "", title).strip()
    og_d = soup.find("meta", property="og:description")
    if og_d and og_d.get("content"):
        desc = re.sub(r"\s+", " ", og_d["content"]).strip()
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s*\|\s*Morgan Stanley\s*$", "", t.get_text()).strip()
    return title, desc


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


async def fetch_all_meta(
    client: httpx.AsyncClient, pairs: list[tuple[str, str]]
) -> list[dict]:
    print(f"\n  [2/3] og:meta 추출 ({len(pairs)}건, concurrency {CONCURRENCY})")
    sem = asyncio.Semaphore(CONCURRENCY)
    ok_cnt = 0
    fail_cnt = 0

    async def _one(idx: int, url: str, lm: str):
        nonlocal ok_cnt, fail_cnt
        async with sem:
            s, html = await fetch(client, url)
            if s != 200:
                fail_cnt += 1
                if s in (403, 429):
                    print(f"    ! 차단 감지 [{s}] {url[-50:]}")
                return None
            title, desc = extract_meta(html)
            if not title:
                fail_cnt += 1
                return None
            ok_cnt += 1
            if (idx + 1) % 25 == 0:
                print(f"    진행: {idx+1}/{len(pairs)} (ok {ok_cnt}, fail {fail_cnt})")
            return {
                "url": url,
                "title": title,
                "description": desc,
                "lastmod": lm + "T00:00:00" if len(lm) == 10 else lm,
                "source": "Morgan Stanley",
                "tier": 1,
            }

    tasks = [_one(i, u, lm) for i, (u, lm) in enumerate(pairs)]
    results = await asyncio.gather(*tasks)
    entries = [r for r in results if r]
    print(f"  → 메타 추출 완료: {len(entries)}건 (실패 {fail_cnt}건)")
    return entries


async def build() -> dict:
    print("=" * 76)
    print("  Morgan Stanley Ideas Archive Builder")
    print(f"  source: sitemap /ideas/ (662 URLs), httpx Chrome UA")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        # 1. sitemap에서 ideas URL 수집
        print(f"\n  [1/3] sitemap 파싱: {SITEMAP_URL}")
        s, xml = await fetch(client, SITEMAP_URL)
        if s != 200:
            print(f"  ! sitemap 접근 실패 [{s}]")
            return {}
        all_pairs = parse_sitemap_ideas(xml)
        all_pairs.sort(key=lambda x: x[1], reverse=True)
        print(f"  → ideas URL {len(all_pairs)}건 (lastmod 있는 것: {sum(1 for _, lm in all_pairs if lm)}건)")

        new_pairs = [(u, lm) for u, lm in all_pairs if u not in known_urls]
        skipped = len(all_pairs) - len(new_pairs)
        print(f"  → 신규: {len(new_pairs)}건 (기존 {skipped}건 스킵)")

        # 2. 개별 페이지 og:meta 추출
        new_entries = await fetch_all_meta(client, new_pairs) if new_pairs else []

    # 3. Merge + dedup + 정렬
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

    print(f"\n  [3/3] 아카이브 저장")
    archive = {
        "source": "Morgan Stanley",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "previously_known": len(existing_entries),
        "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
        matched = [e for e in entries if kw_l in (e["title"] + " " + e["description"]).lower()]
        print(f"\n  · '{kw}' → {len(matched)}건")
        for e in matched[:3]:
            print(f"      [{e['lastmod'][:10]}] {e['title'][:80]}")


async def main():
    archive = await build()
    show_samples(archive, [
        "AI", "semiconductor", "smartphone", "technology", "tariff",
        "TSMC", "Apple", "Samsung", "supply chain", "China",
    ])


if __name__ == "__main__":
    asyncio.run(main())
