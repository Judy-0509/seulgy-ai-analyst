"""Omdia (omdia.tech.informa.com) 아카이브 빌더.

Omdia는 Cloudflare로 일반 브라우저 UA를 차단하지만 Googlebot UA는 통과시킨다.
robots.txt에서 알려준 sitemap을 통해 매월 발행 article 목록을 얻을 수 있다.

전략:
  1. 월별 archive sitemap (sitemap-articles-{month-name}-{YYYY}.xml) 순회
  2. URL 패턴 `/om{ID}/{slug}` (개별 article) 추출 + sitemap-general의 `/insights/{YYYY}/...` 보강
  3. 각 URL의 og:title + og:description 추출
  4. 증분 업데이트 (기존 archive 보존, 신규만 fetch)

산출:
  data/archives/omdia.json

사용:
  python scripts/build_omdia_archive.py            # 2026 (default)
  python scripts/build_omdia_archive.py 2025       # 2025 전체
  python scripts/build_omdia_archive.py 2026 5     # 2026의 최근 5개월만
"""
import asyncio
import io
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "omdia.json"

SITE_BASE = "https://omdia.tech.informa.com"
MONTHLY_SITEMAP_TEMPLATE = SITE_BASE + "/sitemap-articles-{mname}-{year}.xml"
GENERAL_SITEMAP = SITE_BASE + "/sitemap-general.xml"

# Omdia는 Cloudflare 차단 — Googlebot UA로 우회
GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
HEADERS = {
    "User-Agent": GOOGLEBOT_UA,
    "Accept": "text/xml,text/html,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

CONCURRENCY = 4  # Omdia는 봇 허용하지만 과한 요청 방지
REQUEST_TIMEOUT = 25

MONTHS_LOWER = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

# /om{ID}/{slug} 패턴 — 실제 article URL
ARTICLE_PATTERN = re.compile(r"/om\d+/[a-z0-9\-]+")


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def parse_sitemap(xml_body: str, url_filter=None) -> list[tuple[str, str]]:
    """sitemap에서 (loc, lastmod) 추출. url_filter callable로 필터링."""
    soup = BeautifulSoup(xml_body, "xml")
    out = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm = u.find("lastmod")
        if not loc:
            continue
        url = loc.text.strip()
        lmt = (lm.text if lm else "").strip()
        if url_filter and not url_filter(url):
            continue
        out.append((url, lmt))
    return out


def extract_meta(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title, desc = "", ""
    el_t = soup.find("meta", property="og:title")
    if el_t and el_t.get("content"):
        title = re.sub(r"\s+", " ", el_t["content"]).strip()
    el_d = soup.find("meta", property="og:description")
    if el_d and el_d.get("content"):
        desc = re.sub(r"\s+", " ", el_d["content"]).strip()
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


async def collect_urls(client: httpx.AsyncClient, year: int, months_back: int | None) -> list[tuple[str, str]]:
    """대상 월(month) 사이트맵에서 /om{ID} URL + /insights URL 수집."""
    print("\n  [1/3] sitemap 수집")

    # 대상 월 결정
    today = date.today()
    if months_back:
        targets = []
        y, m = today.year, today.month
        for _ in range(months_back):
            if y == year:
                targets.append(MONTHS_LOWER[m - 1])
            m -= 1
            if m == 0:
                m = 12
                y -= 1
            if y < year:
                break
        targets = list(reversed(targets))
    else:
        # 1년 전체
        targets = MONTHS_LOWER

    pairs: list[tuple[str, str]] = []
    seen = set()

    # 월별 archive sitemap (om{ID} 패턴)
    for mname in targets:
        url = MONTHLY_SITEMAP_TEMPLATE.format(mname=mname, year=year)
        s, body = await fetch(client, url)
        if s != 200:
            print(f"    [{s}] {mname}-{year}: skip")
            continue
        month_pairs = parse_sitemap(body, url_filter=lambda u: bool(ARTICLE_PATTERN.search(u)))
        added = 0
        for u, lm in month_pairs:
            if u in seen:
                continue
            seen.add(u)
            pairs.append((u, lm))
            added += 1
        print(f"    [{s}] {mname}-{year}: /om 패턴 {added}건 수집 (sitemap 전체 {len(month_pairs)}건 중)")

    # /insights URL 보강 (sitemap-general)
    print("\n    /insights 보강 (sitemap-general)")
    s, body = await fetch(client, GENERAL_SITEMAP)
    if s == 200:
        ins_pairs = parse_sitemap(
            body,
            url_filter=lambda u: f"/insights/{year}/" in u
        )
        added = 0
        for u, lm in ins_pairs:
            if u in seen:
                continue
            seen.add(u)
            pairs.append((u, lm))
            added += 1
        print(f"    /insights/{year}: {added}건 추가")

    print(f"\n  → 총 URL: {len(pairs)}건")
    return pairs


async def fetch_meta_all(client: httpx.AsyncClient, pairs: list[tuple[str, str]]) -> list[dict]:
    if not pairs:
        return []
    print(f"\n  [2/3] og:title/description 추출 ({len(pairs)}건)")
    sem = asyncio.Semaphore(CONCURRENCY)
    ok_cnt = 0
    fail_cnt = 0
    empty_cnt = 0

    async def fetch_one(idx: int, url: str, lm: str):
        nonlocal ok_cnt, fail_cnt, empty_cnt
        async with sem:
            s, html = await fetch(client, url)
            if s != 200:
                fail_cnt += 1
                return None
            title, desc = extract_meta(html)
            if not title and not desc:
                empty_cnt += 1
                return None
            ok_cnt += 1
            if (idx + 1) % 50 == 0:
                print(f"    진행: {idx+1}/{len(pairs)} (ok {ok_cnt}, fail {fail_cnt}, empty {empty_cnt})")
            return {
                "url": url,
                "title": title,
                "description": desc,
                "lastmod": lm,
                "source": "Omdia",
                "tier": 1,
            }

    tasks = [fetch_one(i, u, lm) for i, (u, lm) in enumerate(pairs)]
    results = await asyncio.gather(*tasks)
    entries = [r for r in results if r]
    print(f"  → 메타 추출 완료: {len(entries)}건 (실패 {fail_cnt}, 빈 {empty_cnt})")
    return entries


async def build(year: int, months_back: int | None) -> dict:
    print("=" * 76)
    print("  Omdia Archive Builder")
    print(f"  year: {year}, months_back: {months_back or 'all'}, UA: Googlebot")
    print("=" * 76)

    existing, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as c:
        all_pairs = await collect_urls(c, year, months_back)
        new_pairs = [(u, lm) for u, lm in all_pairs if u not in known_urls]
        skipped = len(all_pairs) - len(new_pairs)
        print(f"  → 신규: {len(new_pairs)}건 (기존 {skipped}건 스킵)")

        new_entries = await fetch_meta_all(c, new_pairs)

    # Merge
    all_entries = existing + new_entries
    seen_url = set()
    merged: list[dict] = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen_url:
            continue
        seen_url.add(u)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    print("\n  [3/3] 아카이브 저장")
    archive = {
        "source": "Omdia",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "year": year,
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "previously_known": len(existing),
        "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"  → 저장: {ARCHIVE_PATH}  ({size_kb:.1f} KB)")
    print("\n" + "=" * 76)
    print(f"  완료. 총 {len(merged)}건 (신규 +{len(new_entries)})")
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
    year = 2026
    months_back = None
    if len(sys.argv) > 1:
        try:
            year = int(sys.argv[1])
        except ValueError:
            print(f"사용법: python {sys.argv[0]} [year] [months_back]")
            sys.exit(1)
    if len(sys.argv) > 2:
        try:
            months_back = int(sys.argv[2])
        except ValueError:
            pass
    return year, months_back


async def main():
    year, months_back = parse_args()
    archive = await build(year, months_back)
    show_samples(archive, ["smartphone", "foldable", "iPhone", "Samsung", "OLED", "memory", "DRAM", "TSMC"])


if __name__ == "__main__":
    asyncio.run(main())
