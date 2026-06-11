"""스마트글래스 소스 빌더 공통 헬퍼.

8개 신규 빌더(UploadVR/Ghost Howls/RoadtoVR/ARInsider/KGOnTech/Meta/Rokid/Citi)가
공유하는 sitemap 기반 증분 아카이브 빌드 + word-boundary 키워드 매칭.
패턴 출처: scripts/_auto_research_helper.py (자동차 컨설팅·정책 빌더 헬퍼).

키워드는 부분일치가 아닌 word-boundary 정규식으로 매칭한다
(db_research/smartglass/2026-06-11_smartglass_sources.md §7: "Envision production" 오탐 방지).
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

# Windows CP949 콘솔 인코딩 우회
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "data" / "archives"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 20
DATE_FLOOR_DEFAULT = "2025-01-01"

# ── word-boundary 키워드 매처 ────────────────────────────────────────────────

_KW_PATTERNS: list[re.Pattern] | None = None


def _load_patterns() -> list[re.Pattern]:
    global _KW_PATTERNS
    if _KW_PATTERNS is None:
        kw_path = ROOT / "data" / "smartglass_keywords.json"
        kws = json.loads(kw_path.read_text(encoding="utf-8")).get("keywords", [])
        pats = []
        for k in kws:
            esc = re.escape(k.lower())
            # 공백/하이픈은 상호 호환: "micro-led" ↔ "micro led", URL 슬러그 "ai-glasses"
            # re.escape(" ") → r"\ ", re.escape("-") → r"\-"
            # 두 치환을 순차 적용하면 첫 번째 치환 결과의 \- 가 두 번째에 의해 오염되므로
            # re.sub 한 번으로 양쪽을 동시에 치환한다.
            esc = re.sub(r"\\ |\\-", r"[\\s\\-]+", esc)
            pats.append(re.compile(rf"(?<![a-z0-9]){esc}(?![a-z0-9])"))
        _KW_PATTERNS = pats
    return _KW_PATTERNS


def is_smartglass_relevant(title: str, desc: str = "", url: str = "") -> bool:
    """제목/요약/URL이 smartglass 키워드와 word-boundary 매칭하면 True."""
    text = f"{title} {desc} {url}".lower()
    return any(p.search(text) for p in _load_patterns())


# ── 공통 fetch/파싱 ──────────────────────────────────────────────────────────

async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url)
        return r.status_code, r.text
    except Exception as e:
        return 0, str(e)


def parse_sitemap(xml_body: str) -> tuple[list[str], list[tuple[str, str]]]:
    """(서브 sitemap loc 리스트, (url, lastmod) 페어 리스트)."""
    soup = BeautifulSoup(xml_body, "xml")
    subs = [loc.text.strip() for sm in soup.find_all("sitemap") if (loc := sm.find("loc"))]
    pairs = []
    for u in soup.find_all("url"):
        loc = u.find("loc"); lm = u.find("lastmod")
        if loc:
            pairs.append((loc.text.strip(), lm.text.strip() if lm else ""))
    return subs, pairs


def extract_meta(html: str) -> tuple[str, str, str]:
    """(og:title, og:description, article:published_time[:19])."""
    soup = BeautifulSoup(html, "html.parser")
    title = desc = pub = ""
    for prop, key in [("og:title", "t"), ("og:description", "d")]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            v = re.sub(r"\s+", " ", el["content"]).strip()
            if key == "t":
                title = v
            else:
                desc = v
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    pt = soup.find("meta", property="article:published_time")
    if pt and pt.get("content"):
        pub = pt["content"][:19]
    return title, desc, pub


def extract_nextdata_publish_date(html: str) -> str:
    """Citi(Next.js) 전용: __NEXT_DATA__ JSON에서 publishDate 추출."""
    m = re.search(r'"publishDate"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    return m.group(1) if m else ""


def load_existing(archive_path: Path) -> tuple[list[dict], set[str]]:
    if not archive_path.exists():
        return [], set()
    try:
        d = json.loads(archive_path.read_text(encoding="utf-8"))
        es = d.get("entries") or []
        return es, {e["url"] for e in es if e.get("url")}
    except Exception:
        return [], set()


# ── 범용 sitemap 빌더 ────────────────────────────────────────────────────────

async def build_sitemap_archive(
    *,
    source_name: str,
    site_base: str,
    archive_filename: str,
    sitemap_index: str | None = None,
    sitemaps: list[str] | None = None,
    sub_include: str | None = None,        # 서브 sitemap loc 필터 (부분일치, 예: "post-sitemap")
    url_include_re: str | None = None,     # 기사 URL 정규식 필터 (예: r"global\.rokid\.com/blogs/news/")
    apply_keyword_filter: bool = True,
    date_floor: str = DATE_FLOOR_DEFAULT,
    tier: int = 2,
    concurrency: int = 6,
    delay_sec: float = 0.0,                # robots.txt Crawl-delay 준수용 (AR Insider=10)
    date_from_nextdata: bool = False,      # Citi: __NEXT_DATA__ publishDate 사용
) -> dict:
    archive_path = ARCHIVE_DIR / archive_filename
    print("=" * 76)
    print(f"  {source_name} Archive Builder (smartglass)")
    print("=" * 76)

    existing_entries, known_urls = load_existing(archive_path)
    print(f"  [0/3] 기존 archive: {len(existing_entries)}건")

    url_re = re.compile(url_include_re) if url_include_re else None

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT, follow_redirects=True, headers=HEADERS
    ) as client:
        # 1) sitemap 수집 (index → 서브 1단계)
        target_maps = list(sitemaps or [])
        if sitemap_index:
            status, body = await fetch(client, sitemap_index)
            if status == 200:
                subs, direct_pairs = parse_sitemap(body)
                if sub_include:
                    subs = [s for s in subs if sub_include in s]
                target_maps.extend(subs)
            else:
                print(f"  [WARN] sitemap index {status}: {sitemap_index}")
                direct_pairs = []
        else:
            direct_pairs = []

        pairs: list[tuple[str, str]] = list(direct_pairs)
        for sm_url in target_maps:
            status, body = await fetch(client, sm_url)
            if status != 200:
                print(f"    [{status}] skip {sm_url}")
                continue
            _, p = parse_sitemap(body)
            pairs.extend(p)
            print(f"    [200] {sm_url}: {len(p)}건")
            if delay_sec:
                await asyncio.sleep(delay_sec)

        # 2) URL 필터 + 날짜 floor + 증분 스킵
        seen: set[str] = set()
        cand: list[tuple[str, str]] = []
        for u, lm in pairs:
            if u in seen:
                continue
            seen.add(u)
            if url_re and not url_re.search(u):
                continue
            if lm and lm[:10] < date_floor:
                continue
            if u in known_urls:
                continue
            cand.append((u, lm))
        print(f"  [1/3] 신규 후보 URL: {len(cand)}건 (전체 {len(seen)}건)")

        # 3) og:meta 수집 + 키워드 필터
        sem = asyncio.Semaphore(1 if delay_sec else concurrency)

        async def fetch_one(u: str, lm: str):
            async with sem:
                if delay_sec:
                    await asyncio.sleep(delay_sec)
                status, html = await fetch(client, u)
                if status != 200:
                    return None
                title, desc, pub = extract_meta(html)
                if date_from_nextdata:
                    nd = extract_nextdata_publish_date(html)
                    if nd:
                        pub = nd
                if not title:
                    return None
                lastmod = pub or lm
                if lastmod and lastmod[:10] < date_floor:
                    return None
                if apply_keyword_filter and not is_smartglass_relevant(title, desc, u):
                    return None
                return {
                    "url": u, "title": title, "description": desc,
                    "lastmod": lastmod, "source": source_name, "tier": tier,
                }

        results = await asyncio.gather(*[fetch_one(u, lm) for u, lm in cand])
        new_entries = [r for r in results if r]
        print(f"  [2/3] 신규 채택: {len(new_entries)}건 (후보 {len(cand)}건 중)")

    # 4) merge + save
    all_entries = existing_entries + new_entries
    seen_url: set[str] = set()
    merged = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen_url:
            continue
        seen_url.add(u)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    archive = {
        "source": source_name,
        "site_base": site_base,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [3/3] 저장: {archive_path} (총 {len(merged)}건, 신규 +{len(new_entries)})")
    return archive
