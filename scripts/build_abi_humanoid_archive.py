"""ABI Research humanoid robotics archive builder.

Collects public metadata from sitemap URLs containing humanoid/robot keywords.
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
ARCHIVE_PATH = ARCHIVE_DIR / "abi_humanoid.json"
SOURCE_NAME = "ABI Research"
SITE_BASE = "https://www.abiresearch.com"
SITEMAP_URL = SITE_BASE + "/sitemap.xml"

CONCURRENCY = 4
REQUEST_TIMEOUT = 20
KEYWORDS = (
    "humanoid", "humanoid robot", "humanoid robotics",
    # smartglass 도메인 공유 (2026-06-12)
    "smart glasses", "smart-glasses", "ar glasses", "ar-glasses",
    "ai glasses", "ai-glasses", "augmented reality", "wearable",
)
SEED_URLS = [
    SITE_BASE + "/news-resources/chart-data/humanoid-robot-installed-base",
]
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/xml,text/xml,text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
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
        if not loc:
            continue
        low = loc.lower()
        if any(k in low for k in KEYWORDS):
            lastmod = url_el.findtext("sm:lastmod", default="", namespaces=NS).strip()
            out.append((loc, lastmod))
    for url in SEED_URLS:
        out.insert(0, (url, ""))
    seen = set()
    deduped = []
    for url, lm in out:
        if url in seen:
            continue
        seen.add(url)
        deduped.append((url, lm))
    return deduped[:50]


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = date = ""
    el = soup.find("meta", property="og:title")
    if el and el.get("content"):
        title = re.sub(r"\s+", " ", el["content"]).strip()
    for prop in ("og:description", "description"):
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if el and el.get("content"):
            desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
            break
    for prop in ("article:published_time", "article:modified_time"):
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            date = el["content"].strip()
            break
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = re.sub(r"\s+", " ", h1.get_text(" ", strip=True))
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc, date


def relevant(title: str, desc: str, url: str) -> bool:
    text = f"{title} {desc} {url}".lower()
    return any(k in text for k in KEYWORDS)


async def build() -> dict:
    existing, known = load_existing()
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        status, xml = await fetch(client, SITEMAP_URL)
        if status != 200:
            raise RuntimeError(f"sitemap fetch failed: HTTP {status}")
        pairs = parse_sitemap(xml)
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
        if not relevant(e.get("title", ""), e.get("description", ""), url):
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
