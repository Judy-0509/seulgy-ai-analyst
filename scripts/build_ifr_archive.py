"""IFR (International Federation of Robotics) 프레스 릴리즈 아카이브 빌더.

전략:
  - ifr.org/sitemap_news.xml 에서 URL 목록 + lastmod 추출
  - 각 기사 페이지 og 메타로 제목/설명 보강

실행:
    python scripts/build_ifr_archive.py

산출:
    data/archives/ifr.json
"""
import asyncio
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "ifr.json"
SOURCE_NAME  = "IFR"
SITE_BASE    = "https://ifr.org"
SITEMAP_URLS = [
    "https://ifr.org/sitemap_news.xml",
    "https://ifr.org/sitemap.xml",
]

CONCURRENCY     = 3
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/xml,text/xml,text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


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


def parse_sitemap(xml: str) -> list[tuple[str, str]]:
    """(url, lastmod) 추출. 뉴스 sitemap은 news:publication_date 사용 가능."""
    out: list[tuple[str, str]] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    # urlset 형태
    for url_el in root.findall(".//sm:url", NS):
        loc = url_el.findtext("sm:loc", default="", namespaces=NS)
        if not loc:
            continue
        # press release / news 만 필터링
        if not re.search(r"/ifr-press-releases/", loc):
            continue
        lastmod = url_el.findtext("sm:lastmod", default="", namespaces=NS) or ""
        # news:publication_date도 시도
        if not lastmod:
            for child in url_el.iter():
                tag = child.tag.split("}")[-1]
                if tag == "publication_date" and child.text:
                    lastmod = child.text
                    break
        out.append((loc, lastmod))
    return out


_TEXT_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})\b",
    re.I,
)
_FULL_MONTH = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def parse_date_from_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    m = _TEXT_DATE_RE.search(text)
    if not m:
        return ""
    month_word = m.group(0).split()[0].lower().replace(".", "")[:3]
    mon = _FULL_MONTH.get(month_word, "")
    if not mon:
        return ""
    return f"{m.group(2)}-{mon}-{m.group(1).zfill(2)}"


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = date = ""
    el = soup.find("meta", property="og:title")
    if el and el.get("content"):
        title = re.sub(r"\s+", " ", el["content"]).strip()
    for prop in ["og:description", "description"]:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if el and el.get("content"):
            desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
            break
    for prop in ["article:published_time", "article:modified_time"]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            date = el["content"]
            break
    if not date:
        date = parse_date_from_text(html)
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc, date


async def build() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Archive Builder")
    print("=" * 60)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        all_pairs: dict[str, str] = {}
        for sm_url in SITEMAP_URLS:
            print(f"\n  [1/3] sitemap: {sm_url}")
            status, xml = await fetch(client, sm_url)
            if status != 200:
                print(f"  ⚠ sitemap 실패: HTTP {status}")
                continue
            pairs = parse_sitemap(xml)
            print(f"  → 발견: {len(pairs)}건")
            for u, lm in pairs:
                # news sitemap 우선 (먼저 들어감), 두 번째 sitemap은 lastmod만 보강
                if u not in all_pairs:
                    all_pairs[u] = lm
                elif lm and not all_pairs[u]:
                    all_pairs[u] = lm

        pairs_list = [(u, lm) for u, lm in all_pairs.items()]
        new_pairs = [(u, lm) for u, lm in pairs_list if u not in known_urls]
        skipped   = len(pairs_list) - len(new_pairs)
        print(f"\n  → 합산 {len(pairs_list)}건 / 신규 {len(new_pairs)}건 (기존 {skipped}건 스킵)")

        print(f"\n  [2/3] 기사 메타 fetch (신규 {len(new_pairs)}건)")
        sem = asyncio.Semaphore(CONCURRENCY)

        async def fetch_article(url: str, fallback_date: str):
            async with sem:
                st, body = await fetch(client, url)
                if st == 200:
                    title, desc, date = extract_meta(body)
                else:
                    title, desc, date = "", "", fallback_date
                if not date:
                    date = fallback_date
                if not title:
                    return None
                return {
                    "url":         url,
                    "title":       title,
                    "description": desc,
                    "lastmod":     date,
                    "source":      SOURCE_NAME,
                    "tier":        1,
                }

        results = await asyncio.gather(*[fetch_article(u, lm) for u, lm in new_pairs])
        new_entries = [r for r in results if r and r.get("title")]
        print(f"  → 완료: {len(new_entries)}건")

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

    print(f"\n  [3/3] 저장: {len(merged)}건 (신규 +{len(new_entries)})")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "sitemap_urls":     SITEMAP_URLS,
        "body_access":      "public",
        "entry_count":      len(merged),
        "newly_added":      len(new_entries),
        "previously_known": len(existing_entries),
        "entries":          merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {ARCHIVE_PATH}  ({ARCHIVE_PATH.stat().st_size/1024:.1f} KB)")
    print("=" * 60)
    return archive


if __name__ == "__main__":
    asyncio.run(build())
