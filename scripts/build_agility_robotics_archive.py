"""Agility Robotics 프레스 릴리즈 아카이브 빌더.

전략:
  - agilityrobotics.com/press-releases 인덱스 페이지에서 카드 목록 파싱
  - 개별 기사는 /content/<slug> 패턴
  - 각 기사 페이지의 og 메타로 보강

실행:
    python scripts/build_agility_robotics_archive.py

산출:
    data/archives/agility_robotics.json
"""
import asyncio
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

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "agility_robotics.json"
SOURCE_NAME  = "Agility Robotics"
SITE_BASE    = "https://agilityrobotics.com"
INDEX_URLS   = [
    "https://agilityrobotics.com/press-releases",
    "https://agilityrobotics.com/latest-press",
]

CONCURRENCY     = 3
REQUEST_TIMEOUT = 20

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
        data    = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
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


def parse_index(html: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"^/content/[a-z0-9\-]+", href):
            continue
        url = href if href.startswith("http") else SITE_BASE + href
        if url in seen:
            continue
        seen.add(url)
        title = ""
        h = a.find(["h1", "h2", "h3", "h4"])
        if h:
            title = h.get_text(" ", strip=True)
        if not title:
            title = a.get_text(" ", strip=True)[:160].strip()
        date = ""
        parent = a.parent
        for _ in range(4):
            if parent is None:
                break
            time_el = parent.find("time")
            if time_el:
                date = time_el.get("datetime") or time_el.get_text(strip=True)
                break
            parent = parent.parent
        if title:
            results.append((url, title, date))
    return results


_TEXT_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})\b",
    re.I,
)
_FULL_MONTH = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def parse_date_from_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    m = _TEXT_DATE_RE.search(text)
    if not m:
        return ""
    month_word = m.group(0).split()[0].lower().replace(".", "")[:3]
    mon = _FULL_MONTH.get(month_word, "")
    if not mon:
        return ""
    return f"{m.group(2)}-{mon}-{m.group(1).zfill(2)}"


def slug_to_title(url: str) -> str:
    m = re.search(r"/content/([a-z0-9\-]+)", url)
    if not m:
        return ""
    return m.group(1).replace("-", " ").title()


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = date = ""
    el = soup.find("meta", property="og:title")
    if el and el.get("content"):
        title = re.sub(r"\s+", " ", el["content"]).strip()
    for prop in ["og:description", "description"]:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if el and el.get("content"):
            desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
            break
    for prop in ["article:published_time", "article:modified_time"]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            date = el["content"]
            break
    if not date:
        time_el = soup.find("time")
        if time_el:
            date = time_el.get("datetime") or time_el.get_text(strip=True)
    if not date:
        date = parse_date_from_text(html)
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = re.sub(r"\s+", " ", h1.get_text(" ", strip=True))
        if not title:
            t = soup.find("title")
            if t:
                title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc, date


async def build() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Archive Builder")
    print("=" * 60)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        all_pairs: list[tuple[str, str, str]] = []
        for idx_url in INDEX_URLS:
            print(f"\n  [1/3] 인덱스 수집: {idx_url}")
            status, html = await fetch(client, idx_url)
            if status != 200:
                print(f"  ⚠ 인덱스 실패: HTTP {status}")
                continue
            ps = parse_index(html)
            print(f"  → 발견: {len(ps)}건")
            all_pairs.extend(ps)

        # 중복 제거
        uniq: dict[str, tuple[str, str, str]] = {}
        for u, t, d in all_pairs:
            uniq.setdefault(u, (u, t, d))
        pairs = list(uniq.values())

        new_pairs = [(u, t, d) for u, t, d in pairs if u not in known_urls]
        skipped   = len(pairs) - len(new_pairs)
        print(f"\n  → 인덱스 합산 {len(pairs)}건 / 신규 {len(new_pairs)}건 (기존 {skipped}건 스킵)")

        print(f"\n  [2/3] 기사 메타 fetch (신규 {len(new_pairs)}건)")
        sem = asyncio.Semaphore(CONCURRENCY)

        async def fetch_article(url: str, fallback_title: str, fallback_date: str):
            async with sem:
                st, body = await fetch(client, url)
                if st == 200:
                    title, desc, date = extract_meta(body)
                else:
                    title, desc, date = fallback_title, "", fallback_date
                if not title:
                    title = fallback_title or slug_to_title(url)
                if not date:
                    date = fallback_date
                return {
                    "url":         url,
                    "title":       title,
                    "description": desc,
                    "lastmod":     date,
                    "source":      SOURCE_NAME,
                    "tier":        1,
                }

        results = await asyncio.gather(*[fetch_article(u, t, d) for u, t, d in new_pairs])
        new_entries = [r for r in results if r and r.get("title")]
        print(f"  → 완료: {len(new_entries)}건")

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

    print(f"\n  [3/3] 저장: {len(merged)}건 (신규 +{len(new_entries)})")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "index_urls":       INDEX_URLS,
        "body_access":      "public",
        "entry_count":      len(merged),
        "newly_added":      len(new_entries),
        "previously_known": len(existing_entries),
        "entries":          merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {ARCHIVE_PATH}  ({ARCHIVE_PATH.stat().st_size/1024:.1f} KB)")
    print("=" * 60)
    return archive


if __name__ == "__main__":
    asyncio.run(build())
