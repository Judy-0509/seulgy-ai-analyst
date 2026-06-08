"""Yole Group Strategy Insights 아카이브 빌더.

전략:
  - AWS WAF JS 챌린지 → Playwright Chromium으로 우회
  - FacetWP 페이지네이션: .facetwp-page[data-page="N"] 클릭 → DOM 업데이트 대기
  - 총 614개 기사, 31페이지, 페이지당 20개 (2026-05-01 기준)
  - 리스팅 DOM에서 URL + 날짜 추출, 개별 기사 페이지에서 og:description 추출
  - 증분 업데이트 (기존 archive 보존, 신규만 fetch)

사용:
  python scripts/build_yole_archive.py               # 2026-01-01 이후
  python scripts/build_yole_archive.py 2026-03-01    # 특정 날짜 이후
  python scripts/build_yole_archive.py 2025-01-01    # 2025 포함

산출:
  data/archives/yole.json
"""
import asyncio
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "yole.json"

SITE_BASE = "https://www.yolegroup.com"
INDEX_URL = SITE_BASE + "/strategy-insights/"

DEFAULT_CUTOFF = "2026-01-01"
MAX_PAGES = 35          # 현재 31페이지 + 여유
META_CONCURRENCY = 4    # 기사 메타 동시 fetch 탭 수

MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

ARTICLE_URL_RE = re.compile(
    r"https://www\.yolegroup\.com/strategy-insights/[a-z0-9][a-z0-9\-]+/$"
)


def parse_date_str(raw: str) -> str:
    """'APRIL 23, 2026' or 'April 23, 2026' → '2026-04-23'. 실패 시 ''."""
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", raw or "")
    if not m:
        return ""
    mon = m.group(1).lower()
    day = m.group(2).zfill(2)
    yr = m.group(3)
    return f"{yr}-{MONTH_MAP.get(mon, '00')}-{day}"


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


async def extract_articles_from_page(page) -> list[tuple[str, str]]:
    """현재 Playwright 페이지에서 (url, date_iso) 목록 추출."""
    handles = await page.query_selector_all("a[href*='/strategy-insights/']")
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for h in handles:
        try:
            href = (await h.get_attribute("href")) or ""
            if not ARTICLE_URL_RE.match(href):
                continue
            if href in seen:
                continue
            seen.add(href)
            text = await h.inner_text()
            art_date = parse_date_str(text)
            results.append((href, art_date))
        except Exception:
            continue
    return results


async def collect_all_urls(browser_ctx, cutoff: str) -> list[tuple[str, str]]:
    """FacetWP JS API(FWP.paged + FWP.fetchData)로 페이지를 순회하며 기사 URL + 날짜 수집.

    주의: btn.click()은 Playwright 합성 클릭으로 FacetWP 핸들러가 발화되지 않음.
    대신 evaluate()로 FWP JS API를 직접 호출한다.
    """
    collected: dict[str, str] = {}
    print(f"\n  [1/3] FacetWP JS 순회 (cutoff: {cutoff})")

    tab = await browser_ctx.new_page()
    try:
        # 첫 페이지 로드 (WAF 자동 해결 + FWP 초기화)
        await tab.goto(INDEX_URL, wait_until="networkidle", timeout=35000)

        # 총 페이지 수 / 기사 수 확인
        total_pages = await tab.evaluate(
            "() => typeof FWP !== 'undefined' && FWP.settings && FWP.settings.pager"
            " ? FWP.settings.pager.total_pages : 31"
        )
        total_pages = min(int(total_pages), MAX_PAGES)
        total_rows = await tab.evaluate(
            "() => typeof FWP !== 'undefined' && FWP.settings && FWP.settings.pager"
            " ? FWP.settings.pager.total_rows : '?'"
        )
        print(f"  총 {total_rows}건 / {total_pages}페이지")

        for page_num in range(1, total_pages + 1):
            # 현재 페이지 기사 추출
            articles = await extract_articles_from_page(tab)

            page_oldest = None
            new_count = 0
            stop = False

            for href, art_date in articles:
                if href in collected:
                    continue
                if art_date and art_date < cutoff:
                    if page_oldest is None or art_date < page_oldest:
                        page_oldest = art_date
                    stop = True
                    continue
                collected[href] = art_date
                new_count += 1
                if art_date and (page_oldest is None or art_date < page_oldest):
                    page_oldest = art_date

            print(f"    [page {page_num:2d}/{total_pages}] new {new_count:2d}, total {len(collected):3d}, oldest {page_oldest or '?'}")

            if stop:
                print(f"    → cutoff {cutoff} 도달 → 수집 종료")
                break

            if page_num >= total_pages:
                break

            # 다음 페이지: FWP JS API 직접 호출 (btn.click()은 합성 이벤트라 FWP 미발화)
            next_page = page_num + 1
            try:
                await tab.evaluate(f"FWP.paged = {next_page}; FWP.fetchData();")
                await tab.wait_for_selector(
                    f".facetwp-page.active[data-page='{next_page}']",
                    timeout=15000,
                )
                await tab.wait_for_load_state("networkidle", timeout=10000)
            except Exception as e:
                print(f"    [page {next_page}] 이동 오류: {e}")
                await asyncio.sleep(2)

    finally:
        await tab.close()

    return list(collected.items())


async def fetch_article_meta(browser_ctx, url: str) -> tuple[str, str]:
    """개별 기사 og:title + og:description 추출."""
    tab = await browser_ctx.new_page()
    try:
        await tab.goto(url, wait_until="networkidle", timeout=25000)
        html = await tab.content()
    except Exception:
        return "", ""
    finally:
        await tab.close()

    og_t = re.search(r'og:title[^>]*content="([^"]+)"', html)
    og_d = re.search(r'og:description[^>]*content="([^"]+)"', html)
    title = re.sub(r"\s+", " ", og_t.group(1)).strip() if og_t else ""
    desc  = re.sub(r"\s+", " ", og_d.group(1)).strip() if og_d else ""
    if not title:
        t = re.search(r"<title>([^<]+)</title>", html)
        if t:
            title = re.sub(r"\s+", " ", t.group(1)).strip()
    return title, desc


async def fetch_all_meta(browser_ctx, url_dates: list[tuple[str, str]]) -> list[dict]:
    print(f"\n  [2/3] og:meta 추출 ({len(url_dates)}건, concurrency {META_CONCURRENCY})")
    sem = asyncio.Semaphore(META_CONCURRENCY)
    ok_cnt = 0
    fail_cnt = 0

    async def _one(idx: int, url: str, dt: str):
        nonlocal ok_cnt, fail_cnt
        async with sem:
            title, desc = await fetch_article_meta(browser_ctx, url)
            if not title and not desc:
                fail_cnt += 1
                return None
            ok_cnt += 1
            if (idx + 1) % 20 == 0:
                print(f"    진행: {idx+1}/{len(url_dates)} (ok {ok_cnt}, fail {fail_cnt})")
            return {
                "url": url,
                "title": title,
                "description": desc,
                "lastmod": dt + "T00:00:00" if dt else "",
                "source": "Yole Group",
                "tier": 1,
            }

    tasks = [_one(i, u, d) for i, (u, d) in enumerate(url_dates)]
    results = await asyncio.gather(*tasks)
    entries = [r for r in results if r]
    print(f"  → 메타 추출 완료: {len(entries)}건 (실패 {fail_cnt}건)")
    return entries


async def build(cutoff: str) -> dict:
    print("=" * 76)
    print("  Yole Group Strategy Insights Archive Builder")
    print(f"  cutoff: {cutoff}, via: Playwright Chromium + FacetWP click")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing_entries)}건")

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )

        url_dates = await collect_all_urls(ctx, cutoff)

        new_pairs = [(u, d) for u, d in url_dates if u not in known_urls]
        skipped = len(url_dates) - len(new_pairs)
        print(f"  → 신규 URL: {len(new_pairs)}건 (기존 보유 {skipped}건 스킵)")

        new_entries = await fetch_all_meta(ctx, new_pairs) if new_pairs else []

        await browser.close()

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
        "source": "Yole Group",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "cutoff_date": cutoff,
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
    show_samples(archive, ["smartphone", "memory", "DRAM", "foldable", "OLED", "AI", "Samsung", "Apple", "TSMC"])


if __name__ == "__main__":
    asyncio.run(main())
