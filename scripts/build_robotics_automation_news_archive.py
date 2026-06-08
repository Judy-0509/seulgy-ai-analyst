"""Robotics & Automation News 아카이브 빌더.

전략: sitemap XML 기반 (14개), URL에 날짜 포함 → 6개월 필터.
증분 업데이트: 기존 URL 재fetch 없음.

실행:
    python scripts/build_robotics_automation_news_archive.py         # 최근 6개월
    python scripts/build_robotics_automation_news_archive.py 12      # 최근 12개월

산출:
    data/archives/robotics_automation_news.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "robotics_automation_news.json"
SOURCE_NAME  = "Robotics & Automation News"
SITE_BASE    = "https://roboticsandautomationnews.com"
SITEMAP_INDEX       = SITE_BASE + "/sitemap.xml"
SITEMAP_SUB_INDEX   = SITE_BASE + "/sitemap-index-1.xml"  # 실제 기사 sitemap들 포함

DEFAULT_MONTHS = 6
CONCURRENCY    = 4
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

DATE_IN_URL = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def cutoff_date(months: int) -> str:
    today = date.today()
    d = today - timedelta(days=months * 30)
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


def parse_sitemap_index(xml: str) -> list[str]:
    soup = BeautifulSoup(xml, "xml")
    return [loc.text.strip() for loc in soup.find_all("loc") if loc.text.strip()]


def parse_sitemap(xml: str, cutoff: str) -> list[tuple[str, str]]:
    """URL + lastmod 추출. cutoff 이전은 생략."""
    soup = BeautifulSoup(xml, "xml")
    out = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm  = u.find("lastmod")
        if not loc:
            continue
        url = loc.text.strip()
        lm_str = (lm.text.strip()[:10] if lm else "") or url_date(url)
        if lm_str and lm_str < cutoff:
            continue
        out.append((url, lm_str))
    return out


def extract_meta(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = ""
    el = soup.find("meta", property="og:title")
    if el and el.get("content"):
        title = re.sub(r"\s+", " ", el["content"]).strip()
    for prop in ["og:description", "description"]:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if el and el.get("content"):
            desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
            break
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc


async def build(months: int) -> dict:
    cutoff = cutoff_date(months)
    print("=" * 70)
    print(f"  {SOURCE_NAME} Archive Builder")
    print(f"  기간: 최근 {months}개월 (cutoff: {cutoff})")
    print("=" * 70)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        # 1. sitemap 수집 (2단계 중첩: index → sub-index → 실제 sitemaps)
        print("\n  [1/3] sitemap index 수집")
        st, xml = await fetch(client, SITEMAP_SUB_INDEX)
        if st != 200:
            # fallback: 최상위 index
            st, xml = await fetch(client, SITEMAP_INDEX)
        if st != 200:
            print(f"  ⚠ sitemap 접근 실패: HTTP {st}")
            return {}

        sitemap_urls = parse_sitemap_index(xml)
        # 기사 sitemap만 (sitemap-N.xml 형태)
        sitemap_urls = [u for u in sitemap_urls if re.search(r"/sitemap-\d+\.xml", u)]
        # 번호 역순 정렬 (최신 = 높은 번호)
        sitemap_urls.sort(key=lambda u: int(re.search(r"sitemap-(\d+)", u).group(1)), reverse=True)
        print(f"  → sitemap {len(sitemap_urls)}개 발견")

        # 2. 각 sitemap에서 URL 수집
        print("\n  [2/3] 개별 sitemap URL 수집")
        all_pairs: list[tuple[str, str]] = []
        stop_flag = False

        for i, sm_url in enumerate(sitemap_urls):
            if stop_flag:
                break
            st, xml = await fetch(client, sm_url)
            if st != 200:
                print(f"    [{i+1:2d}] skip (HTTP {st}): {sm_url}")
                continue
            pairs = parse_sitemap(xml, cutoff)
            all_pairs.extend(pairs)
            oldest = min((d for _, d in pairs if d), default="?") if pairs else "?"
            print(f"    [{i+1:2d}] {len(pairs):4d}건  oldest={oldest}  {sm_url.split('/')[-1]}")
            # 모든 항목이 cutoff보다 오래됐으면 중단
            if pairs:
                dates = [d for _, d in pairs if d]
                if dates and max(dates) < cutoff:
                    print(f"    → cutoff {cutoff} 도달 → 수집 종료")
                    stop_flag = True

        # 중복 제거
        seen_u: set[str] = set()
        unique: list[tuple[str, str]] = []
        for u, d in all_pairs:
            if u not in seen_u:
                seen_u.add(u)
                unique.append((u, d))
        print(f"  → 중복 제거 후: {len(unique)}건")

        # 기존 URL 스킵
        new_pairs = [(u, d) for u, d in unique if u not in known_urls]
        print(f"  → 신규: {len(new_pairs)}건 (기존 {len(unique)-len(new_pairs)}건 스킵)")

        # 3. 신규 URL 메타 fetch
        print(f"\n  [3/3] 기사 메타 fetch (신규 {len(new_pairs)}건, 동시 {CONCURRENCY})")
        sem = asyncio.Semaphore(CONCURRENCY)
        ok = err = 0

        async def fetch_meta(url: str, lm: str):
            nonlocal ok, err
            async with sem:
                st, html = await fetch(client, url)
                if st != 200:
                    err += 1
                    return None
                title, desc = extract_meta(html)
                if not title:
                    err += 1
                    return None
                ok += 1
                date_str = lm or url_date(url)
                if len(date_str) == 10:
                    date_str += "T00:00:00"
                return {
                    "url":         url,
                    "title":       title,
                    "description": desc,
                    "lastmod":     date_str,
                    "source":      SOURCE_NAME,
                    "tier":        1,
                }

        tasks   = [fetch_meta(u, d) for u, d in new_pairs]
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
    print(f"\n  → 저장: {ARCHIVE_PATH}  ({size_kb:.1f} KB)")
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
