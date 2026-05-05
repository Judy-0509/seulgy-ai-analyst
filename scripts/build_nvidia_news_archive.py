"""NVIDIA News (Isaac / Robotics) 아카이브 빌더.

전략:
  - NVIDIA 공식 뉴스룸 RSS + NVIDIA Technical Blog RSS 두 피드 수집
  - humanoid / robotics / Isaac 관련 키워드로 필터링
  - 본문 접근 가능 (공개)

실행:
    python scripts/build_nvidia_news_archive.py

산출:
    data/archives/nvidia_news.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "nvidia_news.json"
SOURCE_NAME  = "NVIDIA"
SITE_BASE    = "https://nvidianews.nvidia.com"
RSS_URLS = [
    "https://nvidianews.nvidia.com/news-releases.rss",
    "https://blogs.nvidia.com/feed/",
]

NVIDIA_KEYWORDS = {
    "robot", "humanoid", "isaac", "embodied", "locomotion", "manipulation",
    "dexterous", "bipedal", "foundation model", "physical ai", "gr00t",
    "jetson", "digits", "warehouse", "industrial automation",
}


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


def is_relevant(title: str, desc: str) -> bool:
    combined = (title + " " + desc).lower()
    return any(kw in combined for kw in NVIDIA_KEYWORDS)


def build() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Robotics Archive Builder")
    print("=" * 60)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/2] 기존 archive: {len(existing_entries)}건")

    new_entries: list[dict] = []
    for rss_url in RSS_URLS:
        print(f"\n  [1/2] RSS 수집: {rss_url}")
        feed = feedparser.parse(rss_url)
        print(f"  → 피드 항목: {len(feed.entries)}건")
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
            known_urls.add(url)
            new_entries.append({
                "url":         url,
                "title":       title,
                "description": desc,
                "lastmod":     parse_date(entry),
                "source":      SOURCE_NAME,
                "tier":        1,
            })
        if filtered:
            print(f"  → robotics 필터링: {filtered}건 제외")

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
        "rss_urls":         RSS_URLS,
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
