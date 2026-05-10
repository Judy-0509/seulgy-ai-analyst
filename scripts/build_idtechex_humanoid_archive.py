"""IDTechEx humanoid robotics archive builder.

Uses a conservative seed-list approach because a public sitemap was not found.
Stores public page metadata only.
"""
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
ARCHIVE_PATH = ARCHIVE_DIR / "idtechex_humanoid.json"
SOURCE_NAME = "IDTechEx"
SITE_BASE = "https://www.idtechex.com"

SEED_URLS = [
    "https://www.idtechex.com/en/research-article/humanoid-robots-to-reach-nearly-us-30-billion-by-2036/34443",
    "https://www.idtechex.com/en/research-report/humanoid-robots-2026-2036-technologies-markets-and-opportunities/1094",
]

FALLBACK_ENTRIES = {
    "https://www.idtechex.com/en/research-report/humanoid-robots-2026-2036-technologies-markets-and-opportunities/1094": {
        "url": "https://www.idtechex.com/en/research-report/humanoid-robots-2026-2036-technologies-markets-and-opportunities/1094",
        "title": "Humanoid Robots 2026-2036: Technologies, Markets and Opportunities",
        "description": "IDTechEx market report covering humanoid robot technologies, market opportunities, components, and commercialization outlook through 2036.",
        "lastmod": "2025-04-16",
        "source": SOURCE_NAME,
        "tier": 1,
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*",
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
    return "humanoid" in text and "fusion energy" not in text


def build() -> dict:
    existing, known = load_existing()
    new_entries = []
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
        for url in SEED_URLS:
            if url in known:
                continue
            try:
                r = client.get(url)
            except Exception:
                continue
            if r.status_code != 200:
                continue
            title, desc, date = extract_meta(r.text)
            if not title or not relevant(title, desc, url):
                fallback = FALLBACK_ENTRIES.get(url)
                if fallback:
                    new_entries.append(fallback)
                continue
            new_entries.append({
                "url": url,
                "title": title,
                "description": desc,
                "lastmod": date,
                "source": SOURCE_NAME,
                "tier": 1,
            })

    seen = set()
    merged = []
    for e in existing + new_entries:
        url = e.get("url")
        if not url or url in seen:
            continue
        if not relevant(e.get("title", ""), e.get("description", ""), url):
            fallback = FALLBACK_ENTRIES.get(url)
            if not fallback:
                continue
            e = fallback
        seen.add(url)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    archive = {
        "source": SOURCE_NAME,
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "seed_urls": SEED_URLS,
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
    build()
