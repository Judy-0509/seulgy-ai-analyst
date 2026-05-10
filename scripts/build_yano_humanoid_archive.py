"""Yano Research humanoid robotics archive builder.

Collects public press-release metadata from Yano's sitemap and press pages.
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

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "yano_humanoid.json"
SOURCE_NAME = "Yano Research"
SITE_BASE = "https://www.yanoresearch.com"
SITEMAP_URL = SITE_BASE + "/sitemap.xml"

CONCURRENCY = 3
REQUEST_TIMEOUT = 20
KEYWORDS = ("humanoid", "robot", "robotics", "ロボット", "ヒューマノイド")
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/xml,text/xml,text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
}


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
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
    out = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    for url_el in root.findall(".//sm:url", NS):
        loc = url_el.findtext("sm:loc", default="", namespaces=NS).strip()
        if not loc or "/press/" not in loc:
            continue
        lastmod = url_el.findtext("sm:lastmod", default="", namespaces=NS).strip()
        out.append((loc, lastmod))
    # Ensure the known 2026 humanoid release is always checked.
    out.insert(0, (SITE_BASE + "/press/press.php/4111", "2026-04-30"))
    return out


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = date = ""
    el = soup.find("meta", property="og:title")
    if el and el.get("content"):
        title = re.sub(r"\s+", " ", el["content"]).strip()
    el = soup.find("meta", property="og:description")
    if el and el.get("content"):
        desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
    if not title:
        h1 = soup.find("h1", class_="press-title") or soup.find("h1")
        if h1:
            title = re.sub(r"\s+", " ", h1.get_text(" ", strip=True))
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    date_el = soup.find(class_="press-release-date")
    if date_el:
        raw = date_el.get_text(" ", strip=True)
        m = re.search(r"(\d{2})/(\d{2})/(\d{2,4})", raw)
        if m:
            y = m.group(3)
            y = "20" + y if len(y) == 2 else y
            date = f"{y}-{m.group(1)}-{m.group(2)}"
    return title, desc, date


def relevant(title: str, desc: str, url: str) -> bool:
    text = f"{title} {desc} {url}".lower()
    return any(k.lower() in text for k in KEYWORDS)


async def build() -> dict:
    existing, known = load_existing()
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        status, xml = await fetch(client, SITEMAP_URL)
        if status != 200:
            raise RuntimeError(f"sitemap fetch failed: HTTP {status}")
        pairs = parse_sitemap(xml)
        seen_pairs = set()
        pairs = [(u, lm) for u, lm in pairs if not (u in seen_pairs or seen_pairs.add(u))]
        new_pairs = [(u, lm) for u, lm in pairs if u not in known]

        sem = asyncio.Semaphore(CONCURRENCY)

        async def fetch_one(url: str, fallback_date: str):
            async with sem:
                st, body = await fetch(client, url)
                if st != 200:
                    return None
                title, desc, date = extract_meta(body)
                if not title or not relevant(title, desc, url):
                    return None
                return {
                    "url": url,
                    "title": title,
                    "description": desc,
                    "lastmod": date or fallback_date,
                    "source": SOURCE_NAME,
                    "tier": 1,
                }

        results = await asyncio.gather(*[fetch_one(u, lm) for u, lm in new_pairs])
        new_entries = [r for r in results if r]

    seen = set()
    merged = []
    for e in existing + new_entries:
        url = e.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    archive = {
        "source": SOURCE_NAME,
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "sitemap_url": SITEMAP_URL,
        "body_access": "metadata_only",
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "previously_known": len(existing),
        "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {ARCHIVE_PATH} ({len(merged)} entries, +{len(new_entries)})")
    return archive


if __name__ == "__main__":
    asyncio.run(build())
