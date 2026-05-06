"""CCS Insight 아카이브 빌더.

전략:
  - sitemap.xml = WP YOAST sitemapindex
  - post-sitemap*.xml + press-sitemap.xml urlset 파싱
  - og:title/description 추출

사용:
  python scripts/build_ccs_insight_archive.py

산출:
  data/archives/ccs_insight.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "ccs_insight.json"
SITE_BASE = "https://www.ccsinsight.com"
SITEMAP_INDEX = SITE_BASE + "/sitemap.xml"

CONCURRENCY = 6
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/xml,application/xml,text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

RELEVANT_KEYWORDS = ("post-sitemap", "press-sitemap")


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def parse_sitemap_index(xml: str) -> list[str]:
    soup = BeautifulSoup(xml, "xml")
    out = []
    for s in soup.find_all("sitemap"):
        loc_el = s.find("loc")
        if not loc_el:
            continue
        loc = loc_el.text.strip()
        if any(k in loc for k in RELEVANT_KEYWORDS):
            out.append(loc)
    return out


def parse_urlset(xml: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(xml, "xml")
    out = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm = u.find("lastmod")
        if not loc:
            continue
        url = loc.text.strip()
        if any(part in url for part in ("/category/", "/tag/", "/author/", "/wp-content/")):
            continue
        if url.rstrip("/") in (SITE_BASE.rstrip("/"), SITE_BASE.rstrip("/") + "/insight"):
            continue
        out.append((url, (lm.text if lm else "").strip()))
    return out


def extract_meta(html: str) -> tuple[str, str]:
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
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        return entries, {e["url"] for e in entries if e.get("url")}
    except Exception:
        return [], set()


async def build() -> dict:
    print("=" * 76)
    print("  CCS Insight Archive Builder")
    print(f"  sitemap: {SITEMAP_INDEX}")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        print("\n  [1/3] sitemap index 수집")
        s, xml = await fetch(client, SITEMAP_INDEX)
        if s != 200:
            print(f"  ! sitemap HTTP {s}")
            return {}
        sub_sitemaps = parse_sitemap_index(xml)
        print(f"  → 자식 post/press-sitemap {len(sub_sitemaps)}개")

        all_pairs: list[tuple[str, str]] = []
        for sm in sub_sitemaps:
            s2, xml2 = await fetch(client, sm)
            if s2 != 200:
                print(f"    [{s2}] {sm} skip")
                continue
            pairs = parse_urlset(xml2)
            print(f"    [{s2}] {sm}: {len(pairs)}건")
            all_pairs.extend(pairs)

        seen = set()
        uniq = []
        for u, lm in all_pairs:
            if u in seen:
                continue
            seen.add(u)
            uniq.append((u, lm))

        new_pairs = [(u, lm) for u, lm in uniq if u not in known_urls]
        print(f"\n  → URL 총 {len(uniq)}건 (신규 {len(new_pairs)}, 기존 {len(uniq)-len(new_pairs)} 스킵)")

        new_entries: list[dict] = []
        if new_pairs:
            print(f"\n  [2/3] og:title/description 추출 (concurrency={CONCURRENCY})")
            sem = asyncio.Semaphore(CONCURRENCY)
            ok = empty = 0

            async def task(idx: int, url: str, lm: str):
                nonlocal ok, empty
                async with sem:
                    s_, html = await fetch(client, url)
                    if s_ != 200:
                        return None
                    title, desc = extract_meta(html)
                    if not title and not desc:
                        empty += 1
                        return None
                    ok += 1
                    if (idx + 1) % 25 == 0:
                        print(f"    진행: {idx+1}/{len(new_pairs)} (ok {ok}, empty {empty})")
                    return {
                        "url": url,
                        "title": title,
                        "description": desc,
                        "lastmod": lm,
                        "source": "CCS Insight",
                        "tier": 1,
                    }

            tasks = [task(i, u, lm) for i, (u, lm) in enumerate(new_pairs)]
            results = await asyncio.gather(*tasks)
            new_entries = [r for r in results if r]
            print(f"  → 신규 추출: {len(new_entries)}건 (실패 {len(new_pairs)-len(new_entries)})")
        else:
            print("\n  [2/3] 신규 URL 없음 — fetch 생략")

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

    print("\n  [3/3] 아카이브 저장")
    archive = {
        "source": "CCS Insight",
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
    print(f"  → 저장: {ARCHIVE_PATH} ({size_kb:.1f} KB)")
    print("\n" + "=" * 76)
    print(f"  완료. 총 {len(merged)}건 (신규 +{len(new_entries)})")
    print("=" * 76)
    return archive


def show_samples(archive: dict, kw_list: list[str]):
    if not archive:
        return
    entries = archive.get("entries", [])
    print("\n  키워드별 매칭 샘플:")
    for kw in kw_list:
        kw_l = kw.lower()
        matched = [
            e for e in entries
            if kw_l in (e["title"] + " " + e.get("description", "")).lower()
        ]
        print(f"\n  · '{kw}' → {len(matched)}건")
        for e in matched[:3]:
            print(f"      [{(e.get('lastmod') or '')[:10]}] {e['title'][:80]}")


async def main():
    archive = await build()
    show_samples(
        archive,
        ["smartphone", "iPhone", "Samsung", "5G", "carrier", "AI"],
    )


if __name__ == "__main__":
    asyncio.run(main())
