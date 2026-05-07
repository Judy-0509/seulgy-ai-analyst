"""SpaceNews 아카이브 빌더.

전략: RSS 피드 페이지네이션 (feedparser). space datacenter 키워드 필터 적용.
      증분 업데이트: 기존 URL 재fetch 없음.

실행:
    python scripts/build_spacenews_archive.py         # 최근 6개월
    python scripts/build_spacenews_archive.py 12      # 최근 12개월

산출:
    data/archives/spacenews.json
"""
import io
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import feedparser

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "spacenews.json"
SOURCE_NAME  = "SpaceNews"
SITE_BASE    = "https://spacenews.com"
RSS_BASE     = "https://spacenews.com/feed/"

DEFAULT_MONTHS = 6
MAX_PAGES      = 50
CRAWL_DELAY    = 1.5

KW_PATH = Path("data/space_datacenter_keywords.json")


def load_keywords() -> list[str]:
    try:
        return json.loads(KW_PATH.read_text(encoding="utf-8")).get("keywords", [])
    except Exception:
        return []


def is_relevant(title: str, desc: str, keywords: list[str]) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in keywords)


def cutoff_date(months: int) -> str:
    d = date.today() - timedelta(days=months * 30)
    return d.strftime("%Y-%m-%d")


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data    = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        return entries, {e["url"] for e in entries if e.get("url")}
    except Exception:
        return [], set()


def parse_entry_date(entry) -> str:
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


def build(months: int) -> dict:
    cutoff = cutoff_date(months)
    print("=" * 70)
    print(f"  {SOURCE_NAME} Archive Builder")
    print(f"  기간: 최근 {months}개월 (cutoff: {cutoff})")
    print("=" * 70)

    keywords = load_keywords()
    existing_entries, known_urls = load_existing()
    print(f"\n  [0/2] 기존 archive: {len(existing_entries)}건")
    print(f"\n  [1/2] RSS 피드 수집 (최대 {MAX_PAGES}페이지)")

    new_entries: list[dict] = []
    stop_flag = False

    for page in range(1, MAX_PAGES + 1):
        if stop_flag:
            break
        url = RSS_BASE if page == 1 else f"{RSS_BASE}?paged={page}"
        feed = feedparser.parse(url)

        if not feed.entries:
            print(f"    page {page}: 기사 없음 → 종료")
            break

        page_new = 0
        for entry in feed.entries:
            link = entry.get("link", "").strip()
            if not link:
                continue
            pub_date = parse_entry_date(entry)
            if pub_date and pub_date[:10] < cutoff:
                stop_flag = True
                continue
            if link in known_urls:
                continue
            title = strip_html(entry.get("title", ""))
            desc  = strip_html(entry.get("summary", "") or entry.get("description", ""))[:500]
            if not is_relevant(title, desc, keywords):
                continue
            known_urls.add(link)
            new_entries.append({
                "url":         link,
                "title":       title,
                "description": desc,
                "lastmod":     pub_date,
                "source":      SOURCE_NAME,
                "tier":        1,
            })
            page_new += 1

        print(f"    page {page}: {len(feed.entries)}건, 신규 관련 {page_new}건")
        if stop_flag:
            print(f"    → cutoff {cutoff} 도달")
        time.sleep(CRAWL_DELAY)

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
        "months":           months,
        "cutoff_date":      cutoff,
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
    print(f"  완료. 총 {len(merged)}건 (신규 +{len(new_entries)}, 기존 {len(existing_entries)})")
    print("=" * 70)
    return archive


def main():
    months = DEFAULT_MONTHS
    if len(sys.argv) > 1:
        try:
            months = int(sys.argv[1])
        except ValueError:
            print(f"사용법: python {sys.argv[0]} [개월수]")
            sys.exit(1)
    build(months)


if __name__ == "__main__":
    main()
