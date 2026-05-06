"""DigiTimes Asia 아카이브 빌더.

전략:
  - DigiTimes는 sitemap 미제공 (HTML 응답)
  - /rss/daily.xml (RSS 2.0, ~50-60건/일, description = 본문 첫 문단)
  - 매일 실행해 누적 (증분)

사용:
  python scripts/build_digitimes_archive.py

산출:
  data/archives/digitimes.json
"""
import asyncio
import io
import json
import re
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "digitimes.json"
SITE_BASE = "https://www.digitimes.com"
RSS_URL = SITE_BASE + "/rss/daily.xml"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml,text/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_pubdate(s: str) -> str:
    try:
        return parsedate_to_datetime(s).isoformat(timespec="seconds")
    except Exception:
        return ""


def parse_rss(xml: str) -> list[dict]:
    soup = BeautifulSoup(xml, "xml")
    out = []
    for item in soup.find_all("item"):
        link_el = item.find("link")
        title_el = item.find("title")
        desc_el = item.find("description")
        pub_el = item.find("pubDate")
        if not link_el or not title_el:
            continue
        url = (link_el.text or "").strip()
        title = re.sub(r"\s+", " ", (title_el.text or "")).strip()
        desc_html = (desc_el.text or "") if desc_el else ""
        desc = re.sub(
            r"\s+", " ",
            BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)
        ).strip()
        lastmod = parse_pubdate(pub_el.text) if pub_el and pub_el.text else ""
        if not url:
            continue
        out.append({
            "url": url,
            "title": title,
            "description": desc,
            "lastmod": lastmod,
            "source": "DigiTimes Asia",
            "tier": 1,
        })
    return out


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        return entries, {e["url"] for e in entries if e.get("url")}
    except Exception:
        return [], set()


async def build() -> dict:
    print("=" * 76)
    print("  DigiTimes Asia Archive Builder")
    print(f"  source: {RSS_URL}")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/2] 기존 archive 로드: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as c:
        print("\n  [1/2] RSS fetch")
        r = await c.get(RSS_URL)
        if r.status_code != 200:
            print(f"  ! RSS HTTP {r.status_code} — abort")
            return {}
        items = parse_rss(r.text)
        print(f"  → RSS {len(items)}건 파싱")

    new_items = [e for e in items if e["url"] not in known_urls]
    print(f"  → 신규 {len(new_items)}건 (기존 {len(items) - len(new_items)}건 스킵)")

    all_entries = existing_entries + new_items
    seen: set[str] = set()
    merged: list[dict] = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    archive = {
        "source": "DigiTimes Asia",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(merged),
        "newly_added": len(new_items),
        "previously_known": len(existing_entries),
        "note": "RSS daily.xml only — run daily to accumulate (no historical sitemap)",
        "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"\n  [2/2] 저장: {ARCHIVE_PATH} ({size_kb:.1f} KB)")
    print("=" * 76)
    print(f"  완료. 총 {len(merged)}건 (신규 +{len(new_items)})")
    print("=" * 76)
    return archive


def show_samples(archive: dict, kw_list: list[str]):
    if not archive:
        return
    entries = archive.get("entries", [])
    print("\n  키워드별 매칭 샘플:")
    for kw in kw_list:
        kw_l = kw.lower()
        matched = [
            e for e in entries
            if kw_l in (e["title"] + " " + e.get("description", "")).lower()
        ]
        print(f"\n  · '{kw}' → {len(matched)}건")
        for e in matched[:3]:
            print(f"      [{(e.get('lastmod') or '')[:10]}] {e['title'][:80]}")


async def main():
    archive = await build()
    show_samples(
        archive,
        ["smartphone", "iPhone", "Samsung", "memory", "foldable", "AI"],
    )


if __name__ == "__main__":
    asyncio.run(main())
