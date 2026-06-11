"""Deutsche Bank Research Institute 아카이브 빌더 — 휴머노이드 / 로보틱스.

전략: dbresearch.com 의 robots.txt sitemap 이 404라(2026-06-11 확인) 섹션 리스팅
       페이지 6개를 직접 순회 → 문서 링크(anchor) 추출 → 제목에 humanoid/robot
       키워드가 있는 건만 저장.

robots.txt 확인 (2026-06-11): User-agent:* 는 /MAIL /REPO /api 등 비콘텐츠 경로만
차단, /PROD/ 콘텐츠는 허용. named-bot 차단 명단(anthropic-ai 등)은 해당 UA 한정.

주의: 문서가 대부분 PDF 링크라 og 메타데이터가 없음 → 리스팅 anchor 텍스트를
제목으로 사용, description 은 빈 값. lastmod 는 최초 발견 시점(first-seen).
현재(2026-06) Technology 섹션에 휴머노이드 기사 0건 — 향후 게재 시 수집 목적.

실행:
    python scripts/build_deutsche_bank_archive.py

산출:
    data/archives/deutsche_bank.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "deutsche_bank.json"
SOURCE_NAME  = "Deutsche Bank Research"
SITE_BASE    = "https://www.dbresearch.com"
LISTING_URLS = [
    "https://www.dbresearch.com/PROD/IE-PROD/Technolgy__Research_Institute/RI_TEC.alias",
    "https://www.dbresearch.com/PROD/IE-PROD/Macro__Research_Institute/RI_MAC.alias",
    "https://www.dbresearch.com/PROD/IE-PROD/Germany__Research_Institute/RI_GER.alias",
    "https://www.dbresearch.com/PROD/IE-PROD/Geopolitics__Research_Institute/RI_GEO.alias",
    "https://www.dbresearch.com/PROD/IE-PROD/Corporate_Landscape__Research_Institute/RI_COR.alias",
    "https://www.dbresearch.com/PROD/IE-PROD/Expert_Voices__Research_Institute/RI_EXP.alias",
]

TITLE_KEYWORDS = [
    "humanoid", "robot", "embodied", "physical ai",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 25

_DOC_HREF = re.compile(r"^/PROD/IE-PROD/PROD\d+/", re.IGNORECASE)


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        return entries, {e["url"] for e in entries if e.get("url")}
    except Exception:
        return [], set()


def is_humanoid_title(title: str) -> bool:
    low = title.lower()
    if "robotaxi" in low:
        return False
    return any(kw in low for kw in TITLE_KEYWORDS)


def extract_doc_links(html: str) -> list[tuple[str, str]]:
    """리스팅 페이지에서 (절대 URL, 제목) 추출. anchor 텍스트가 비면 URL 파일명 사용."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not _DOC_HREF.match(href):
            continue
        title = re.sub(r"\s+", " ", a.get_text()).strip()
        if not title:
            from urllib.parse import unquote
            stem = href.rsplit("/", 1)[-1]
            stem = re.sub(r"\.(pdf|xhtml)$", "", stem, flags=re.IGNORECASE)
            title = unquote(stem).replace("_", " ").strip()
        out.append((SITE_BASE + href, title))
    return out


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


async def build_async() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Archive Builder")
    print("=" * 60)
    existing, known_urls = load_existing()
    print(f"  [0/2] 기존 archive: {len(existing)}건")

    candidates: dict[str, str] = {}
    async with httpx.AsyncClient(headers=HEADERS, timeout=REQUEST_TIMEOUT,
                                 follow_redirects=True) as client:
        print(f"  [1/2] 리스팅 페이지 {len(LISTING_URLS)}개 순회 중...")
        for listing_url in LISTING_URLS:
            status, body = await fetch(client, listing_url)
            if status != 200 or body.startswith("ERR:"):
                print(f"        skip ({status}): {listing_url}")
                continue
            for url, title in extract_doc_links(body):
                if url not in candidates and is_humanoid_title(title):
                    candidates[url] = title

    print(f"        humanoid/robot 후보: {len(candidates)}건")
    now_iso = datetime.now().isoformat(timespec="seconds")
    new_entries = [
        {
            "url":         url,
            "title":       title,
            "description": "",
            "lastmod":     now_iso,
            "source":      SOURCE_NAME,
            "tier":        1,
        }
        for url, title in candidates.items()
        if url not in known_urls
    ]

    all_entries = existing + new_entries
    seen: set[str] = set()
    deduped = []
    for e in sorted(all_entries, key=lambda x: x.get("lastmod", ""), reverse=True):
        url = e.get("url", "")
        if url in seen:
            continue
        seen.add(url)
        deduped.append(e)

    out = {
        "source":            SOURCE_NAME,
        "site_base":         SITE_BASE,
        "built_at":          now_iso,
        "body_access":       "public_metadata",
        "body_note":         "리스팅 anchor 제목만 저장 (문서는 PDF, lastmod=first-seen)",
        "entry_count":       len(deduped),
        "newly_added":       len(new_entries),
        "previously_known":  len(existing),
        "entries":           deduped,
    }
    print(f"  [2/2] 저장: {len(deduped)}건 (신규 +{len(new_entries)})")
    print(f"  → {ARCHIVE_PATH}")
    print("=" * 60)
    return out


def main() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    out = asyncio.run(build_async())
    ARCHIVE_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                            encoding="utf-8")


if __name__ == "__main__":
    main()
