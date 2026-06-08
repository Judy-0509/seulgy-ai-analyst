"""Reuters 아카이브 빌더.

전략:
  - Reuters는 Cloudflare JS 챌린지 → 개별 기사 페이지 접근 불가 (401)
  - 단, sitemap은 Googlebot UA로 접근 가능
  - 일반 sitemap: <news:title> 없음 → URL slug에서 제목 파생 (키워드 검색에 충분)
  - news-sitemap: <news:title> 있으나 최근 2일치만 커버
  - 전략: 일반 sitemap(~2주치) 수집 후 news-sitemap 실제 제목으로 보강
  - 증분 업데이트로 주 1회 실행 시 신규 기사 누적

수집 섹션 (URL 경로 기준):
  /technology/, /business/, /markets/

사용:
  python scripts/build_reuters_archive.py               # 2026-01-01 이후
  python scripts/build_reuters_archive.py 2025-01-01    # 2025 포함 (범위 내만 수집됨)

산출:
  data/archives/reuters.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "reuters.json"

SITE_BASE = "https://www.reuters.com"
GENERAL_SITEMAP_BASE = SITE_BASE + "/arc/outboundfeeds/sitemap/?outputType=xml"
NEWS_SITEMAP_BASE    = SITE_BASE + "/arc/outboundfeeds/news-sitemap/?outputType=xml"

DEFAULT_CUTOFF = "2026-01-01"
CONCURRENCY    = 4
REQUEST_TIMEOUT = 20
MAX_FROM = 10000   # from= 상한 (빈 페이지 나오면 조기 종료)
FROM_STEP = 100    # 일반 sitemap: 페이지당 100건

GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
HEADERS = {
    "User-Agent": GOOGLEBOT_UA,
    "Accept": "text/xml,text/html,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

RELEVANT_SECTIONS = (
    "/technology/",
    "/business/",
    "/markets/",
)


def slug_to_title(url: str) -> str:
    """Reuters URL slug에서 사람이 읽을 수 있는 제목 파생.

    예: /technology/apple-iphone-record-sales-2026-05-01/
        → 'Apple Iphone Record Sales'
    """
    path = url.rstrip("/")
    slug = path.split("/")[-1]
    slug = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", slug)   # 날짜 접미사 제거
    slug = re.sub(r"--[a-z]+$", "", slug)               # --flm 류 접미사 제거
    return slug.replace("-", " ").strip().title()


def is_relevant(url: str) -> bool:
    path = url.replace(SITE_BASE, "")
    return any(path.startswith(sec) for sec in RELEVANT_SECTIONS)


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def parse_general_sitemap(xml: str) -> list[tuple[str, str]]:
    """일반 sitemap → (loc, lastmod_date) 리스트."""
    soup = BeautifulSoup(xml, "xml")
    out = []
    for u in soup.find_all("url"):
        loc_el = u.find("loc")
        lm_el  = u.find("lastmod")
        if not loc_el:
            continue
        url = loc_el.text.strip()
        lm  = lm_el.text.strip()[:10] if lm_el else ""
        out.append((url, lm))
    return out


def parse_news_sitemap(xml: str) -> dict[str, str]:
    """news-sitemap → {url: real_title} 딕셔너리."""
    soup = BeautifulSoup(xml, "xml")
    out = {}
    for u in soup.find_all("url"):
        loc_el   = u.find("loc")
        title_el = u.find("title")
        if not loc_el or not title_el:
            continue
        url   = loc_el.text.strip()
        title = re.sub(r"\s+", " ", title_el.get_text()).strip()
        if title:
            out[url] = title
    return out


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


async def collect_general_sitemap(
    client: httpx.AsyncClient, cutoff: str
) -> dict[str, str]:
    """일반 sitemap 순회 → {url: lastmod_date} (관련 섹션만)."""
    collected: dict[str, str] = {}
    stop_flag = False
    total_pages = 0
    total_items = 0

    for from_val in range(0, MAX_FROM, FROM_STEP):
        if stop_flag:
            break
        s, xml = await fetch(client, f"{GENERAL_SITEMAP_BASE}&from={from_val}")
        if s != 200 or not xml.strip().startswith("<?xml"):
            print(f"    from={from_val:5d}: 빈 페이지 → 종료")
            break

        items = parse_general_sitemap(xml)
        if not items:
            print(f"    from={from_val:5d}: 0건 → 종료")
            break

        total_pages += 1
        total_items += len(items)
        page_new = 0

        for url, lm in items:
            if lm and lm < cutoff:
                stop_flag = True
                continue
            if not is_relevant(url):
                continue
            if url not in collected:
                collected[url] = lm
                page_new += 1

        oldest = min((d for d in collected.values() if d), default="?")
        print(
            f"    from={from_val:5d}: {len(items)}건 | 관련 신규 {page_new}건 | "
            f"누계 {len(collected)}건 | oldest {oldest}"
        )
        if stop_flag:
            print(f"    → cutoff {cutoff} 도달 → 수집 종료")
            break

    print(f"  → 일반 sitemap {total_pages}페이지({total_items}건) → 관련 {len(collected)}건")
    return collected


async def collect_news_titles(client: httpx.AsyncClient) -> dict[str, str]:
    """news-sitemap에서 실제 제목 수집 → {url: title}."""
    titles: dict[str, str] = {}
    for from_val in range(0, 2000, 100):
        s, xml = await fetch(client, f"{NEWS_SITEMAP_BASE}&from={from_val}")
        if s != 200 or not xml.strip().startswith("<?xml"):
            break
        batch = parse_news_sitemap(xml)
        if not batch:
            break
        titles.update(batch)
    print(f"  → news-sitemap 실제 제목 {len(titles)}건 수집")
    return titles


async def build(cutoff: str) -> dict:
    print("=" * 76)
    print("  Reuters Archive Builder")
    print(f"  cutoff: {cutoff}, UA: Googlebot, sections: technology/business/markets")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        print("\n  [1/3] 일반 sitemap 수집")
        url_dates = await collect_general_sitemap(client, cutoff)

        print("\n  [2/3] news-sitemap 제목 보강")
        real_titles = await collect_news_titles(client)

    new_pairs = [(u, d) for u, d in url_dates.items() if u not in known_urls]
    skipped = len(url_dates) - len(new_pairs)
    print(f"  → 신규: {len(new_pairs)}건 (기존 {skipped}건 스킵)")

    new_entries: list[dict] = []
    for url, lm in new_pairs:
        title = real_titles.get(url) or slug_to_title(url)
        if not title:
            continue
        new_entries.append({
            "url": url,
            "title": title,
            "description": "",
            "lastmod": lm + "T00:00:00" if len(lm) == 10 else lm,
            "source": "Reuters",
            "tier": 1,
        })

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

    print("\n  [3/3] 아카이브 저장")
    archive = {
        "source": "Reuters",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "cutoff_date": cutoff,
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "previously_known": len(existing_entries),
        "note": "title from news-sitemap (recent) or URL slug; no description (Cloudflare blocks article pages)",
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
        matched = [
            e for e in entries
            if kw_l in e["title"].lower()
        ]
        print(f"\n  · '{kw}' → {len(matched)}건")
        for e in matched[:3]:
            date_str = (e.get("lastmod") or "")[:10]
            print(f"      [{date_str}] {e['title'][:80]}")


def parse_args():
    cutoff = DEFAULT_CUTOFF
    if len(sys.argv) > 1:
        a1 = sys.argv[1]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a1):
            cutoff = a1
        else:
            print(f"사용법: python {sys.argv[0]} [YYYY-MM-DD]")
            sys.exit(1)
    return cutoff


async def main():
    cutoff = parse_args()
    archive = await build(cutoff)
    show_samples(
        archive,
        ["smartphone", "Samsung", "Apple", "TSMC", "semiconductor",
         "memory", "DRAM", "AI chip", "tariff", "iPhone"],
    )


if __name__ == "__main__":
    asyncio.run(main())
