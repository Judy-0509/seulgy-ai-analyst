"""Morgan Stanley Insights / Ideas 아카이브 빌더 — 휴머노이드 / 로보틱스 / Physical AI.

전략: sitemap.xml 수집 → /insights/ 또는 /ideas/ 경로 + humanoid/robot 키워드 URL 필터
       → og:title + og:description + lastmod 수집.

robots.txt 확인 (2026-05): /insights/ 및 /ideas/ 경로 허용. /content/, /pub/ 차단.

실행:
    python scripts/build_morgan_stanley_archive.py

산출:
    data/archives/morgan_stanley.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "morgan_stanley.json"
SOURCE_NAME  = "Morgan Stanley Research"
SITE_BASE    = "https://www.morganstanley.com"
SITEMAP_URLS = [
    "https://www.morganstanley.com/sitemap.xml",
]

URL_KEYWORDS = [
    "humanoid", "robot", "robotics", "physical-ai", "automation",
    "ai-tech", "embodied", "industrial-ai",
]

# 허용 경로 prefix (robots.txt 정합성 + 메타데이터 풍부한 페이지만)
ALLOWED_PREFIXES = ("/insights/", "/ideas/")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

CONCURRENCY     = 4
REQUEST_TIMEOUT = 20


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        return entries, {e["url"] for e in entries if e.get("url")}
    except Exception:
        return [], set()


def is_humanoid_url(url: str) -> bool:
    path = url.replace(SITE_BASE, "")
    if not any(path.startswith(p) for p in ALLOWED_PREFIXES):
        return False
    if url.endswith(".pdf"):
        return False
    low = url.lower()
    return any(kw in low for kw in URL_KEYWORDS)


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


async def collect_sitemap_urls(client: httpx.AsyncClient) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sm_url in SITEMAP_URLS:
        status, body = await fetch(client, sm_url)
        if status != 200:
            continue
        for url, lm in re.findall(
            r"<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]*)</lastmod>)?", body
        ):
            url = url.strip()
            if url in seen:
                continue
            seen.add(url)
            if is_humanoid_url(url):
                out.append((url, (lm or "").strip()))
    return out


def extract_meta(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title, desc = "", ""
    for prop, slot in [("og:title", "title"), ("og:description", "desc")]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            content = re.sub(r"\s+", " ", el["content"]).strip()
            if slot == "title":
                title = content
            else:
                desc = content
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = re.sub(r"\s+", " ", h1.get_text()).strip()
    return title, desc


async def fetch_one(client: httpx.AsyncClient, sem: asyncio.Semaphore,
                    url: str, lastmod: str) -> dict | None:
    async with sem:
        status, body = await fetch(client, url)
        if status != 200 or body.startswith("ERR:"):
            return None
        title, desc = extract_meta(body)
        if not title:
            return None
        return {
            "url":         url,
            "title":       title,
            "description": desc,
            "lastmod":     lastmod or datetime.now().isoformat(timespec="seconds"),
            "source":      SOURCE_NAME,
            "tier":        1,
        }


async def build_async() -> dict:
    print("=" * 60)
    print(f"  {SOURCE_NAME} Archive Builder")
    print("=" * 60)
    existing, known_urls = load_existing()
    print(f"  [0/3] 기존 archive: {len(existing)}건")

    async with httpx.AsyncClient(headers=HEADERS, timeout=REQUEST_TIMEOUT,
                                 follow_redirects=True) as client:
        print("  [1/3] sitemap 수집 중...")
        url_pairs = await collect_sitemap_urls(client)
        print(f"        humanoid/robot 후보 URL: {len(url_pairs)}건")

        new_urls = [(u, lm) for u, lm in url_pairs if u not in known_urls]
        print(f"  [2/3] 신규 fetch 대상: {len(new_urls)}건")

        sem = asyncio.Semaphore(CONCURRENCY)
        results = await asyncio.gather(
            *(fetch_one(client, sem, u, lm) for u, lm in new_urls)
        )

    new_entries = [r for r in results if r]
    all_entries = existing + new_entries
    seen: set[str] = set()
    deduped = []
    for e in sorted(all_entries, key=lambda x: x.get("lastmod", ""), reverse=True):
        if e["url"] in seen:
            continue
        seen.add(e["url"])
        deduped.append(e)

    out = {
        "source":            SOURCE_NAME,
        "site_base":         SITE_BASE,
        "built_at":          datetime.now().isoformat(timespec="seconds"),
        "body_access":       "public_metadata",
        "body_note":         "og:title / og:description 만 저장 (full report 는 paywall)",
        "entry_count":       len(deduped),
        "newly_added":       len(new_entries),
        "previously_known":  len(existing),
        "entries":           deduped,
    }
    print(f"  [3/3] 저장: {len(deduped)}건 (신규 +{len(new_entries)})")
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
