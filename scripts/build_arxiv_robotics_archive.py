"""arXiv cs.RO (Robotics) 아카이브 빌더.

전략: arXiv API (Atom feed) 사용. 최근 6개월 humanoid/robotics 논문 수집.
      cs.RO 전체 + humanoid 관련 cs.AI 논문 포함.
      증분 업데이트: 기존 URL 재fetch 없음.

실행:
    python scripts/build_arxiv_robotics_archive.py         # 최근 6개월
    python scripts/build_arxiv_robotics_archive.py 12      # 최근 12개월

산출:
    data/archives/arxiv_robotics.json
"""
import io
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import feedparser

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "arxiv_robotics.json"
SOURCE_NAME  = "arXiv (cs.RO)"
SITE_BASE    = "https://arxiv.org"
API_BASE     = "https://export.arxiv.org/api/query"

DEFAULT_MONTHS = 6
BATCH_SIZE     = 200   # arXiv API 최대 권장
CRAWL_DELAY    = 3.0   # arXiv robots.txt: 15s 권장, 3s는 배치 간 간격

# 수집할 쿼리 목록 (각각 독립 수집 후 merge)
QUERIES = [
    # cs.RO 전체 (로봇공학)
    "cat:cs.RO",
    # humanoid/embodied AI 관련 cs.AI/cs.LG 논문
    (
        "cat:cs.AI AND ("
        "ti:humanoid OR ti:bipedal OR ti:locomotion OR ti:legged "
        "OR ti:manipulation OR ti:dexterous OR ti:embodied"
        ")"
    ),
]


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


def parse_arxiv_date(entry) -> str:
    """arXiv published 날짜 파싱."""
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


def collect_query(query: str, cutoff: str, known_urls: set[str]) -> list[dict] | None:
    """단일 쿼리에 대해 arXiv API 페이지네이션으로 최근 데이터 수집.
    429 rate limit 시 None 반환."""
    entries: list[dict] = []
    start = 0
    stop_flag = False

    while not stop_flag:
        params = {
            "search_query": query,
            "start":        start,
            "max_results":  BATCH_SIZE,
            "sortBy":       "submittedDate",
            "sortOrder":    "descending",
        }
        url = f"{API_BASE}?{urlencode(params)}"
        feed = feedparser.parse(url)

        # 429 Rate Limit 감지
        status = getattr(feed, "status", 200)
        if status == 429:
            print(f"  ⚠ arXiv API 429 Rate Limit — IP 쿨다운 필요. 수 시간 후 재시도.")
            return None

        if not feed.entries:
            # bozo_exception 으로 오류 여부 확인
            exc = getattr(feed, "bozo_exception", None)
            if exc:
                print(f"  ⚠ feedparser 오류: {exc}")
            break

        for entry in feed.entries:
            link = entry.get("link", "").strip()
            if not link or link in known_urls:
                continue
            pub_date = parse_arxiv_date(entry)
            if pub_date and pub_date[:10] < cutoff:
                stop_flag = True
                continue
            title = strip_html(entry.get("title", ""))
            # arXiv summary = abstract
            desc = strip_html(entry.get("summary", ""))[:800]
            known_urls.add(link)
            entries.append({
                "url":         link,
                "title":       title,
                "description": desc,
                "lastmod":     pub_date,
                "source":      SOURCE_NAME,
                "tier":        1,
            })

        print(f"    start={start:5d}: {len(feed.entries)}건, 누계 {len(entries)}건")
        if len(feed.entries) < BATCH_SIZE:
            break
        start += BATCH_SIZE
        time.sleep(CRAWL_DELAY)

    return entries


def build(months: int) -> dict:
    cutoff = cutoff_date(months)
    print("=" * 70)
    print(f"  {SOURCE_NAME} Archive Builder")
    print(f"  기간: 최근 {months}개월 (cutoff: {cutoff})")
    print(f"  arXiv crawl delay: {CRAWL_DELAY}s/batch")
    print("=" * 70)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/2] 기존 archive: {len(existing_entries)}건")

    new_entries: list[dict] = []
    rate_limited = False
    for i, query in enumerate(QUERIES, 1):
        print(f"\n  [1/2] 쿼리 {i}/{len(QUERIES)}: {query[:60]}...")
        batch = collect_query(query, cutoff, known_urls)
        if batch is None:
            rate_limited = True
            print(f"  → 쿼리 {i} 중단 (rate limit)")
            break
        new_entries.extend(batch)
        print(f"  → 쿼리 {i} 수집: {len(batch)}건")
        if i < len(QUERIES):
            time.sleep(CRAWL_DELAY)

    if rate_limited and not new_entries:
        print("\n  ⚠ arXiv API rate limit으로 수집 중단. 기존 archive 유지.")
        return {}

    # Merge + dedup + 정렬
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
        "queries":          QUERIES,
        "body_access":      "public",
        "body_note":        "논문 PDF 공개. arxiv.org/abs/{id} → arxiv.org/pdf/{id}",
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
