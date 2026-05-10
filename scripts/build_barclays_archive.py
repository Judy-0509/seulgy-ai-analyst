"""Barclays Research archive builder for humanoid robotics / Physical AI.

This stores public metadata only. Barclays research reports are generally gated,
so the builder uses official/public press-release pages and extracts title,
description, and publication date.

Run:
    python scripts/build_barclays_archive.py

Output:
    data/archives/barclays.json
"""
import json
import re
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup


ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "barclays.json"
SOURCE_NAME = "Barclays Research"
SITE_BASE = "https://home.barclays"

SEED_URLS = [
    "https://www.businesswire.com/news/home/20260114100182/en/",
]

FALLBACK_ENTRIES = {
    "https://www.businesswire.com/news/home/20260114100182/en/": {
        "url": "https://www.businesswire.com/news/home/20260114100182/en/",
        "title": "Barclays Research Finds Humanoid Robotics On Track to Become a $200 Billion Market by 2035",
        "description": (
            "Barclays Research released the Impact Series report The Future of Work: AI Gets Physical, "
            "estimating that the global humanoid robotics market could grow from $2-3 billion "
            "today to $200 billion by 2035 under optimistic scenarios."
        ),
        "lastmod": "2026-01-14",
        "source": SOURCE_NAME,
        "tier": 1,
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
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


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    desc = ""
    pub = ""

    for prop, attr in [
        ("og:title", "title"),
        ("twitter:title", "title"),
        ("og:description", "desc"),
        ("twitter:description", "desc"),
        ("article:published_time", "pub"),
    ]:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if not el or not el.get("content"):
            continue
        value = clean(el["content"])
        if attr == "title" and not title:
            title = value
        elif attr == "desc" and not desc:
            desc = value
        elif attr == "pub" and not pub:
            pub = value[:19]

    if not title:
        h1 = soup.find("h1")
        if h1:
            title = clean(h1.get_text(" ", strip=True))
    if not desc:
        ps = [
            clean(p.get_text(" ", strip=True))
            for p in soup.find_all("p")
            if len(clean(p.get_text(" ", strip=True))) > 80
        ]
        desc = " ".join(ps[:2])[:700]
    if not pub:
        text = soup.get_text(" ", strip=True)
        m = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}",
            text,
        )
        if m:
            pub = m.group(0)

    return title, desc, pub


def fetch_entry(url: str) -> dict | None:
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
            response = client.get(url)
        if response.status_code != 200:
            return None
        title, desc, pub = extract_meta(response.text)
        if not title:
            return None
        return {
            "url": url,
            "title": title,
            "description": desc,
            "lastmod": pub or datetime.now().isoformat(timespec="seconds"),
            "source": SOURCE_NAME,
            "tier": 1,
        }
    except Exception:
        return None


def main() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    existing, known_urls = load_existing()
    new_entries = []
    for url in SEED_URLS:
        if url in known_urls:
            continue
        entry = fetch_entry(url)
        if not entry:
            entry = FALLBACK_ENTRIES.get(url)
        if entry:
            new_entries.append(entry)

    all_entries = existing + new_entries
    seen = set()
    merged = []
    for entry in sorted(all_entries, key=lambda x: x.get("lastmod", ""), reverse=True):
        url = entry.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append(entry)

    out = {
        "source": SOURCE_NAME,
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "body_access": "public_metadata",
        "body_note": "Official/public press-release metadata only; full Barclays report may be gated.",
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "previously_known": len(existing),
        "entries": merged,
    }
    ARCHIVE_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{SOURCE_NAME}: saved {len(merged)} entries (+{len(new_entries)}) -> {ARCHIVE_PATH}")


if __name__ == "__main__":
    main()
