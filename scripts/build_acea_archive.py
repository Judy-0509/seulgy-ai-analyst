"""ACEA (European Automobile Manufacturers' Association) 아카이브 빌더.

전략: sitemap_index.xml → press-release sub-sitemap 다수 → og:meta 추출.
2026년 발행만 보존. EU OEM 공식 통계·press release.

실행: python scripts/build_acea_archive.py
산출: data/archives/acea.json
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

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "acea.json"
SOURCE_NAME  = "ACEA"
SITE_BASE    = "https://www.acea.auto"
SITEMAP_URL  = "https://www.acea.auto/sitemap_index.xml"
# Sub-sitemap 우선순위 키워드 (모두 포함하면 됨)
SUB_SITEMAP_INCLUDE = ["news-articles", "pr-regular", "pr-pc", "pr-cv", "news-director"]
YEAR_FILTER  = "2026"
MAX_ARTICLES = 600
CONCURRENCY  = 5
REQUEST_TIMEOUT = 25

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                  "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def load_existing():
    if not ARCHIVE_PATH.exists(): return [], set()
    try:
        d = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        es = d.get("entries") or []
        return es, {e["url"] for e in es if e.get("url")}
    except Exception:
        return [], set()


def is_2026(lm): return bool(lm) and lm.startswith(YEAR_FILTER)


async def fetch(client, url):
    try:
        r = await client.get(url)
        return r.status_code, r.text
    except Exception as e:
        return 0, str(e)


def parse_sitemap(xml_body):
    """returns (sub_sitemap_urls, [(url, lastmod), ...])."""
    soup = BeautifulSoup(xml_body, "xml")
    sub_sitemaps = [loc.text.strip() for sm in soup.find_all("sitemap")
                    if (loc := sm.find("loc"))]
    pairs = []
    for u in soup.find_all("url"):
        loc = u.find("loc"); lm = u.find("lastmod")
        if loc:
            pairs.append((loc.text.strip(), lm.text.strip() if lm else ""))
    return sub_sitemaps, pairs


def extract_meta(html):
    soup = BeautifulSoup(html, "html.parser")
    title = desc = pub = ""
    for prop, key in [("og:title", "t"), ("og:description", "d")]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            v = re.sub(r"\s+", " ", el["content"]).strip()
            if key == "t": title = v
            else: desc = v
    if not title:
        t = soup.find("title")
        if t: title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    pt = soup.find("meta", property="article:published_time")
    if pt and pt.get("content"): pub = pt["content"][:19]
    return title, desc, pub


async def collect_urls(client):
    """sitemap_index → 사용 가능한 sub-sitemap → article URLs 수집."""
    st, body = await fetch(client, SITEMAP_URL)
    if st != 200:
        print(f"  ✗ sitemap_index 실패 [{st}]")
        return []
    sub_sitemaps, _ = parse_sitemap(body)
    use_subs = [s for s in sub_sitemaps if any(k in s for k in SUB_SITEMAP_INCLUDE)]
    print(f"  → sub-sitemap: 전체 {len(sub_sitemaps)}, 사용 {len(use_subs)}")
    for s in use_subs:
        print(f"      • {s}")

    pairs = []
    for sm_url in use_subs:
        # ACEA의 일부 sub-sitemap이 http://를 사용 — https로 강제 업그레이드
        sm_url = sm_url.replace("http://", "https://")
        s, b = await fetch(client, sm_url)
        if s == 200:
            _, more = parse_sitemap(b)
            pairs.extend(more)

    pairs2026 = [(u, lm) for u, lm in pairs if is_2026(lm)]
    seen = set(); uniq = []
    for u, lm in sorted(pairs2026, key=lambda x: x[1] or "", reverse=True):
        if u not in seen:
            seen.add(u); uniq.append((u, lm))
    return uniq[:MAX_ARTICLES]


async def build():
    print("=" * 60); print(f"  {SOURCE_NAME} Archive Builder"); print("=" * 60)
    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True, headers=HEADERS) as client:
        print(f"\n  [1/3] sitemap 수집: {SITEMAP_URL}")
        all_pairs = await collect_urls(client)
        new_pairs = [(u, lm) for u, lm in all_pairs if u not in known_urls]
        print(f"      전체 2026년 {len(all_pairs)}건, 신규 {len(new_pairs)}건")

        new_entries = []
        if new_pairs:
            print(f"\n  [2/3] og:meta 추출 ({len(new_pairs)}건, 동시 {CONCURRENCY})")
            sem = asyncio.Semaphore(CONCURRENCY)
            ok_cnt = 0

            async def fetch_meta(idx, url, lm):
                nonlocal ok_cnt
                async with sem:
                    s, html = await fetch(client, url)
                    if s != 200: return None
                    title, desc, pub = extract_meta(html)
                    if not title: return None
                    ok_cnt += 1
                    if (idx + 1) % 25 == 0:
                        print(f"      진행: {idx+1}/{len(new_pairs)} (ok {ok_cnt})")
                    return {"url": url, "title": title, "description": desc,
                            "lastmod": pub or lm, "source": SOURCE_NAME, "tier": 1}

            results = await asyncio.gather(*[fetch_meta(i, u, lm) for i, (u, lm) in enumerate(new_pairs)])
            new_entries = [r for r in results if r and is_2026(r["lastmod"])]
            print(f"      추출 완료: {len(new_entries)}건")
        else:
            print("\n  [2/3] 신규 없음 — fetch 생략")

    all_entries = existing_entries + new_entries
    seen = set(); merged = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen: continue
        if not is_2026(e.get("lastmod", "")): continue
        seen.add(u); merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    print(f"\n  [3/3] 저장: {len(merged)}건 (신규 +{len(new_entries)})")
    archive = {
        "source": SOURCE_NAME, "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "sitemap_url": SITEMAP_URL, "year_filter": YEAR_FILTER,
        "entry_count": len(merged), "newly_added": len(new_entries),
        "previously_known": len(existing_entries), "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {ARCHIVE_PATH}  ({ARCHIVE_PATH.stat().st_size/1024:.1f} KB)")
    print("=" * 60)
    return archive


if __name__ == "__main__":
    asyncio.run(build())
