"""CarNewsChina 아카이브 빌더 (영문 중국 자동차 시장 매체).

전략: RSS + sitemap. 2026년 발행만 보존.
실행: python scripts/build_carnewschina_archive.py
산출: data/archives/carnewschina.json
"""
import asyncio
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import feedparser
import httpx
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "carnewschina.json"
SOURCE_NAME  = "CarNewsChina"
SITE_BASE    = "https://carnewschina.com"
RSS_URL      = "https://carnewschina.com/feed/"
SITEMAP_URL  = "https://carnewschina.com/post-sitemap.xml"
YEAR_FILTER  = "2026"
MAX_ARTICLES = 400
CONCURRENCY  = 5
REQUEST_TIMEOUT = 20

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


def parse_rss_date(entry):
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try: return datetime(*t[:6]).isoformat(timespec="seconds")
            except Exception: pass
    return ""


def strip_html(t): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()
def is_2026(lm):   return bool(lm) and lm.startswith(YEAR_FILTER)


async def fetch(client, url):
    try:
        r = await client.get(url)
        return r.status_code, r.text
    except Exception as e:
        return 0, str(e)


def parse_sitemap(xml_body):
    soup = BeautifulSoup(xml_body, "xml")
    pairs = []
    for u in soup.find_all("url"):
        loc = u.find("loc"); lm = u.find("lastmod")
        if loc:
            pairs.append((loc.text.strip(), lm.text.strip() if lm else ""))
    return pairs


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


async def build():
    print("=" * 60); print(f"  {SOURCE_NAME} Archive Builder"); print("=" * 60)
    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True, headers=HEADERS) as client:
        new_entries = []

        print(f"\n  [1/3] RSS 수집: {RSS_URL}")
        feed = feedparser.parse(RSS_URL, agent=HEADERS["User-Agent"])
        rss_added = 0
        for e in feed.entries:
            url = e.get("link", "").strip()
            if not url or url in known_urls: continue
            lm = parse_rss_date(e)
            if not is_2026(lm): continue
            new_entries.append({
                "url": url,
                "title": strip_html(e.get("title", "")),
                "description": strip_html(e.get("summary", ""))[:500],
                "lastmod": lm, "source": SOURCE_NAME, "tier": 2,
            })
            known_urls.add(url); rss_added += 1
        print(f"      RSS 신규 {rss_added}건 (2026년)")

        print(f"\n  [2/3] sitemap 수집: {SITEMAP_URL}")
        st, body = await fetch(client, SITEMAP_URL)
        sitemap_added = 0
        if st == 200:
            pairs = [(u, lm) for u, lm in parse_sitemap(body) if is_2026(lm)][:MAX_ARTICLES]
            new_pairs = [(u, lm) for u, lm in pairs if u not in known_urls]
            print(f"      sitemap 2026년 {len(pairs)}건, fetch 대상 {len(new_pairs)}건")
            sem = asyncio.Semaphore(CONCURRENCY)

            async def fetch_meta(u, lm):
                async with sem:
                    s, html = await fetch(client, u)
                    if s != 200: return None
                    t, d, p = extract_meta(html)
                    if not t: return None
                    return {"url": u, "title": t, "description": d, "lastmod": p or lm,
                            "source": SOURCE_NAME, "tier": 2}

            results = await asyncio.gather(*[fetch_meta(u, lm) for u, lm in new_pairs])
            for r in results:
                if r and is_2026(r["lastmod"]):
                    new_entries.append(r); sitemap_added += 1
        else:
            print(f"      sitemap 실패 [{st}]")
        print(f"      sitemap 신규 {sitemap_added}건")

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
        "rss_url": RSS_URL, "sitemap_url": SITEMAP_URL, "year_filter": YEAR_FILTER,
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
