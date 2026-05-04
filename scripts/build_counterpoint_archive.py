"""Counterpoint Research Insights 아카이브 빌더.

실행:
    python scripts/build_counterpoint_archive.py                # 최근 3개월
    python scripts/build_counterpoint_archive.py 6              # 최근 6개월
    python scripts/build_counterpoint_archive.py 12             # 최근 12개월

산출:
    data/archives/counterpoint.json   {entries: [...], built_at, total_months}

각 entry: {
    "url":         "https://counterpointresearch.com/en/insights/...",
    "title":       "<og:title>",
    "description": "<og:description>",  # 보통 1~2문단 풀 요약
    "lastmod":     "2026-04-30T22:43:41.883Z",
    "source":      "Counterpoint Research",
    "tier":        1,
}
"""
import asyncio
import io
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Windows CP949 콘솔 인코딩 우회
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "counterpoint.json"
SITE_BASE = "https://counterpointresearch.com"
SITEMAP_URL_TEMPLATE = SITE_BASE + "/en/insights/sitemap/{ym}.xml"

DEFAULT_MONTHS = 3
CONCURRENCY = 6  # 동시 fetch 개수 (너무 높이면 차단 위험)
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def recent_months(n: int) -> list[str]:
    """최근 n개월 'YYYY-MM' 목록 (현재 월부터 거꾸로)."""
    today = date.today()
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def parse_sitemap(xml_body: str) -> list[tuple[str, str]]:
    """sitemap에서 (loc, lastmod) 페어 추출 — /insights/ 글만."""
    out = []
    soup = BeautifulSoup(xml_body, "xml")
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm = u.find("lastmod")
        if not loc:
            continue
        url = loc.text.strip()
        if "/insights/" not in url:
            continue
        if url.rstrip("/").endswith("/insights"):
            continue
        out.append((url, (lm.text if lm else "").strip()))
    return out


def extract_meta(html: str) -> tuple[str, str]:
    """og:title + og:description 추출."""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    desc = ""
    for prop, target in [("og:title", "title"), ("og:description", "desc")]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            content = re.sub(r"\s+", " ", el["content"]).strip()
            if target == "title":
                title = content
            else:
                desc = content
    # fallback: <title> 태그
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc


def load_existing() -> tuple[list[dict], set[str]]:
    """기존 archive 로드 → (entries, known_url_set). 없으면 빈 값."""
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        urls = {e["url"] for e in entries if e.get("url")}
        return entries, urls
    except Exception:
        return [], set()


async def build(months: int) -> dict:
    print("=" * 76)
    print(f"  Counterpoint Research Archive Builder")
    print(f"  대상 개월: {months}, 동시 fetch: {CONCURRENCY}")
    print("=" * 76)

    # 기존 archive 로드 (증분 모드)
    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing_entries)}건 (있으면 재fetch 생략)")

    target_months = recent_months(months)
    print(f"\n  [1/3] sitemap 수집 ({len(target_months)}개월)")

    pairs: list[tuple[str, str]] = []
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT, follow_redirects=True, headers=HEADERS
    ) as client:
        for ym in target_months:
            url = SITEMAP_URL_TEMPLATE.format(ym=ym)
            t0 = time.time()
            status, body = await fetch(client, url)
            dt = round(time.time() - t0, 2)
            if status == 200:
                month_pairs = parse_sitemap(body)
                pairs.extend(month_pairs)
                print(f"    [{status}] {ym}: {len(month_pairs):3d}건 ({dt}s)")
            else:
                print(f"    [{status}] {ym}: skip ({dt}s)")

        # 중복 제거 (lastmod 기준 최신순)
        seen = set()
        uniq = []
        pairs.sort(key=lambda x: x[1] or "", reverse=True)
        for u, lm in pairs:
            if u in seen:
                continue
            seen.add(u)
            uniq.append((u, lm))
        print(f"  → 중복 제거 후: {len(uniq)}건")

        # known_urls에 이미 있는 URL은 fetch 생략
        new_pairs = [(u, lm) for u, lm in uniq if u not in known_urls]
        skipped = len(uniq) - len(new_pairs)
        print(f"  → 신규 URL: {len(new_pairs)}건 (기존 보유 {skipped}건 스킵)")

        if new_pairs:
            print(f"\n  [2/3] og:title/description 추출 (신규 {len(new_pairs)}건)")
            sem = asyncio.Semaphore(CONCURRENCY)
            ok_cnt = 0
            empty_cnt = 0

            async def fetch_meta(idx: int, url: str, lm: str):
                nonlocal ok_cnt, empty_cnt
                async with sem:
                    status, html = await fetch(client, url)
                    if status != 200:
                        return None
                    title, desc = extract_meta(html)
                    if not title and not desc:
                        empty_cnt += 1
                        return None
                    ok_cnt += 1
                    if (idx + 1) % 25 == 0:
                        print(f"    진행: {idx+1}/{len(new_pairs)} (ok {ok_cnt}, empty {empty_cnt})")
                    return {
                        "url": url,
                        "title": title,
                        "description": desc,
                        "lastmod": lm,
                        "source": "Counterpoint Research",
                        "tier": 1,
                    }

            tasks = [fetch_meta(i, u, lm) for i, (u, lm) in enumerate(new_pairs)]
            results = await asyncio.gather(*tasks)
            new_entries = [r for r in results if r]
            print(f"  → 신규 추출 완료: {len(new_entries)}건 (실패 {len(new_pairs) - len(new_entries)}건)")
        else:
            print(f"\n  [2/3] 신규 URL 없음 — fetch 생략")
            new_entries = []

    # Merge: 기존 + 신규, URL dedup, lastmod desc 정렬
    all_entries = existing_entries + new_entries
    seen_url = set()
    merged: list[dict] = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen_url:
            continue
        seen_url.add(u)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    # 저장
    print(f"\n  [3/3] 아카이브 저장")
    archive = {
        "source": "Counterpoint Research",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "total_months": months,
        "month_window": target_months,
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
    """키워드별 매칭 샘플 표시."""
    entries = archive["entries"]
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


async def main():
    months = DEFAULT_MONTHS
    if len(sys.argv) > 1:
        try:
            months = int(sys.argv[1])
        except ValueError:
            print(f"사용법: python {sys.argv[0]} [개월수]")
            sys.exit(1)

    archive = await build(months)
    show_samples(archive, ["foldable", "iPhone", "Samsung", "memory", "China", "AI"])


if __name__ == "__main__":
    asyncio.run(main())
