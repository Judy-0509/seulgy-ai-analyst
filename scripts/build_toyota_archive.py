"""Toyota Newsroom 아카이브 빌더.

전략: RSS 피드 수집. 주기적 실행으로 점진 누적.

실행:
    python scripts/build_toyota_archive.py

산출:
    data/archives/toyota.json
"""
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import feedparser

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "toyota.json"
SOURCE_NAME  = "Toyota Newsroom"
SITE_BASE    = "https://pressroom.toyota.com"
RSS_URL      = "https://pressroom.toyota.com/feed/"


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data    = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        return entries, {e["url"] for e in entries if e.get("url")}
    except Exception:
        return [], set()


def parse_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6]).isoformat(timespec="seconds")
            except Exception:
                pass
    return ""


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Archive Builder")
    print("=" * 60)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/2] 기존 archive: {len(existing_entries)}건")

    print(f"\n  [1/2] RSS 수집: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    print(f"  → 피드 항목: {len(feed.entries)}건")

    new_entries: list[dict] = []
    for entry in feed.entries:
        url = entry.get("link", "").strip()
        if not url or url in known_urls:
            continue
        title = strip_html(entry.get("title", ""))
        desc  = strip_html(entry.get("summary", ""))[:500]
        new_entries.append({
            "url":         url,
            "title":       title,
            "description": desc,
            "lastmod":     parse_date(entry),
            "source":      SOURCE_NAME,
            "tier":        1,
        })

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

    print(f"\n  [2/2] 저장: {len(merged)}건 (신규 +{len(new_entries)})")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "rss_url":          RSS_URL,
        "entry_count":      len(merged),
        "newly_added":      len(new_entries),
        "previously_known": len(existing_entries),
        "entries":          merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"  → {ARCHIVE_PATH}  ({size_kb:.1f} KB)")
    print("=" * 60)
    return archive


if __name__ == "__main__":
    build()
