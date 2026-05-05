"""The Verge 아카이브 빌더 (robotics 키워드 필터).

RSS 기반 수집 (전체 피드에서 robotics 관련 기사 필터링). 본문 접근 가능 (공개).

실행:
    python scripts/build_verge_robotics_archive.py

산출:
    data/archives/verge_robotics.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "verge_robotics.json"
SOURCE_NAME  = "The Verge"
SITE_BASE    = "https://www.theverge.com"
RSS_URL      = "https://www.theverge.com/rss/index.xml"


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


ROBOTICS_KEYWORDS = {
    "robot", "humanoid", "bipedal", "locomotion", "autonomous vehicle",
    "boston dynamics", "figure ai", "optimus", "agility", "unitree",
    "dexterous", "embodied", "warehouse robot", "industrial robot",
    "robotics", "robotic", "manipulation", "robot arm",
}


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_relevant(title: str, desc: str) -> bool:
    combined = (title + " " + desc).lower()
    return any(kw in combined for kw in ROBOTICS_KEYWORDS)


def build() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Robots Archive Builder")
    print("=" * 60)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/2] 기존 archive: {len(existing_entries)}건")

    print(f"\n  [1/2] RSS 수집: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    print(f"  → 피드 항목: {len(feed.entries)}건")

    new_entries: list[dict] = []
    filtered = 0
    for entry in feed.entries:
        url = entry.get("link", "").strip()
        if not url or url in known_urls:
            continue
        title = strip_html(entry.get("title", ""))
        desc  = strip_html(entry.get("summary", ""))[:500]
        if not is_relevant(title, desc):
            filtered += 1
            continue
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

    if filtered:
        print(f"  → robotics 필터링: {filtered}건 제외")
    print(f"\n  [2/2] 저장: {len(merged)}건 (신규 +{len(new_entries)})")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "rss_url":          RSS_URL,
        "body_access":      "public",
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
