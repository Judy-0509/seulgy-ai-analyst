"""Gartner 보도자료 아카이브 빌더.

전략:
  - gartner.com WAF가 모든 httpx/bot 요청 차단 (403)
  - Playwright Chromium으로 뉴스룸 목록 페이지 접근
  - 개별 기사 페이지는 추가 CAPTCHA → 방문하지 않음
  - URL slug 자체가 헤드라인: 날짜 + 제목을 slug에서 직접 파싱
  - 증분 업데이트: 기존 archive 보존, 신규만 추가
  - 일별 CronJob으로 실행 → 매일 ~9건씩 누적

수집 범위:
  - gartner.com/en/newsroom/press-releases (목록 페이지)
  - 연구 관련 키워드 필터링 없음 (전체 수집, viewer에서 검색)

사용:
  python scripts/build_gartner_archive.py

산출:
  data/archives/gartner.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "gartner.json"

SITE_BASE = "https://www.gartner.com"
NEWSROOM_URL = SITE_BASE + "/en/newsroom/press-releases"

PR_PATH_RE = re.compile(r"^/en/newsroom/press-releases/(\d{4}-\d{1,2}-\d{1,2})-(.+)$")
DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def slug_to_title(slug: str) -> str:
    """URL slug → 읽기 좋은 제목. 'gartner-says-ai-...' → 'Gartner Says Ai ...'"""
    return slug.replace("-", " ").strip().title()


def normalise_date(raw: str) -> str:
    """'2026-4-7' → '2026-04-07'"""
    m = DATE_RE.match(raw)
    if not m:
        return raw
    y, mo, d = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


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


async def collect_links() -> list[tuple[str, str, str]]:
    """Playwright로 뉴스룸 목록 로드 → [(full_url, date, title)] 반환."""
    from playwright.async_api import async_playwright

    results: list[tuple[str, str, str]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        print(f"  뉴스룸 로딩: {NEWSROOM_URL}")
        await page.goto(NEWSROOM_URL, wait_until="domcontentloaded", timeout=40000)

        # JS 렌더링 + 스크롤로 lazy-load 트리거
        await page.wait_for_timeout(4000)
        for _ in range(6):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(800)
        await page.wait_for_timeout(2000)

        # 모든 앵커에서 보도자료 링크 추출
        hrefs = await page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.getAttribute('href'))"
        )
        seen: set[str] = set()
        for href in hrefs:
            if not href:
                continue
            m = PR_PATH_RE.match(href)
            if not m:
                continue
            raw_date, slug = m.group(1), m.group(2)
            date_iso = normalise_date(raw_date)
            title = slug_to_title(slug)
            full_url = SITE_BASE + href
            if full_url not in seen:
                seen.add(full_url)
                results.append((full_url, date_iso, title))

        await browser.close()

    results.sort(key=lambda x: x[1], reverse=True)
    return results


async def build() -> dict:
    print("=" * 76)
    print("  Gartner Archive Builder")
    print("  source: newsroom/press-releases (Playwright), title from URL slug")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/2] 기존 archive 로드: {len(existing_entries)}건")

    print("\n  [1/2] 뉴스룸 수집")
    all_items = await collect_links()
    print(f"  → {len(all_items)}건 발견")

    new_items = [(u, d, t) for u, d, t in all_items if u not in known_urls]
    skipped = len(all_items) - len(new_items)
    print(f"  → 신규: {len(new_items)}건 (기존 {skipped}건 스킵)")

    new_entries = [
        {
            "url": url,
            "title": title,
            "description": "",
            "lastmod": date + "T00:00:00",
            "source": "Gartner",
            "tier": 1,
        }
        for url, date, title in new_items
    ]

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

    print("\n  [2/2] 아카이브 저장")
    archive = {
        "source": "Gartner",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "previously_known": len(existing_entries),
        "note": "title from URL slug; no description (article pages blocked by CAPTCHA)",
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
        matched = [e for e in entries if kw_l in e["title"].lower()]
        print(f"\n  · '{kw}' → {len(matched)}건")
        for e in matched[:3]:
            print(f"      [{e['lastmod'][:10]}] {e['title'][:80]}")


async def main():
    archive = await build()
    show_samples(archive, ["AI", "device", "smartphone", "PC", "semiconductor", "forecast"])


if __name__ == "__main__":
    asyncio.run(main())
