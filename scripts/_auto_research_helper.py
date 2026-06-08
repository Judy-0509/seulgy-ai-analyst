"""자동차 연구·정책 소스 빌더 공통 헬퍼.

McKinsey/BCG/IRENA/T&E (sitemap+URL 필터)
BNEF/RMI (RSS+키워드 필터)
공통 — 2026년 발행 + 자동차 키워드(168) 통과 기사만 보존.
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

import feedparser
import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "data/archives"

# 자동차 키워드 — 168개 중 핵심 매칭 키워드 (대소문자 무관 부분일치)
_AUTO_KW_CACHE = None


def _load_auto_keywords() -> list[str]:
    global _AUTO_KW_CACHE
    if _AUTO_KW_CACHE is not None:
        return _AUTO_KW_CACHE
    kw_path = ROOT / "data" / "automotive_keywords.json"
    data = json.loads(kw_path.read_text(encoding="utf-8"))
    _AUTO_KW_CACHE = [k.lower() for k in data.get("keywords", [])]
    return _AUTO_KW_CACHE


def is_auto_relevant(title: str, desc: str = "") -> bool:
    """기사 제목/요약이 자동차 키워드 하나라도 매칭하면 True."""
    text = (title + " " + desc).lower()
    kw = _load_auto_keywords()
    return any(k in text for k in kw)


def is_year_2026(lastmod: str) -> bool:
    return bool(lastmod) and lastmod.startswith("2026")


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_rss_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6]).isoformat(timespec="seconds")
            except Exception:
                pass
    return ""


def load_existing(archive_path: Path) -> tuple[list[dict], set[str]]:
    if not archive_path.exists():
        return [], set()
    try:
        d = json.loads(archive_path.read_text(encoding="utf-8"))
        es = d.get("entries") or []
        return es, {e["url"] for e in es if e.get("url")}
    except Exception:
        return [], set()


HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                  "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url)
        return r.status_code, r.text
    except Exception as e:
        return 0, str(e)


def parse_sitemap(xml_body: str) -> tuple[list[str], list[tuple[str, str]]]:
    soup = BeautifulSoup(xml_body, "xml")
    sub_sitemaps = [loc.text.strip() for sm in soup.find_all("sitemap")
                    if (loc := sm.find("loc"))]
    pairs = []
    for u in soup.find_all("url"):
        loc = u.find("loc"); lm = u.find("lastmod")
        if loc:
            pairs.append((loc.text.strip(), lm.text.strip() if lm else ""))
    return sub_sitemaps, pairs


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = pub = ""
    for prop, key in [("og:title", "t"), ("og:description", "d")]:
        el = soup.find("meta", property=prop)
        if el and el.get("content"):
            v = re.sub(r"\s+", " ", el["content"]).strip()
            if key == "t": title = v
            else: desc = v
    if not title:
        t = soup.find("title")
        if t: title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    pt = soup.find("meta", property="article:published_time")
    if pt and pt.get("content"):
        pub = pt["content"][:19]
    return title, desc, pub


async def build_rss_only(*, source_name: str, site_base: str, rss_url: str,
                         archive_path: Path, require_auto_keyword: bool = True,
                         year_filter: bool = True, tier: int = 2) -> dict:
    """RSS 한 곳만 보는 단순 빌더 (BNEF/RMI 같이 broad RSS)."""
    print("=" * 60); print(f"  {source_name} Archive Builder"); print("=" * 60)
    existing, known = load_existing(archive_path)
    print(f"\n  [0/2] 기존 archive: {len(existing)}건")

    print(f"\n  [1/2] RSS 수집: {rss_url}")
    feed = feedparser.parse(rss_url, agent=HEADERS_BROWSER["User-Agent"])
    new_entries = []
    skip_yr = skip_kw = added = 0
    for e in feed.entries:
        url = e.get("link", "").strip()
        if not url or url in known:
            continue
        lm = parse_rss_date(e)
        if year_filter and not is_year_2026(lm):
            skip_yr += 1; continue
        title = strip_html(e.get("title", ""))
        desc  = strip_html(e.get("summary", ""))[:500]
        if require_auto_keyword and not is_auto_relevant(title, desc):
            skip_kw += 1; continue
        new_entries.append({
            "url": url, "title": title, "description": desc,
            "lastmod": lm, "source": source_name, "tier": tier,
        })
        known.add(url); added += 1
    print(f"      RSS 항목 {len(feed.entries)}개 → 신규 +{added} (year skip {skip_yr}, kw skip {skip_kw})")

    return _save(existing, new_entries, archive_path, source_name, site_base, rss_url=rss_url)


async def build_sitemap(*, source_name: str, site_base: str, sitemap_url: str,
                        archive_path: Path, url_includes: list[str],
                        url_excludes: list[str] | None = None,
                        sub_include_keywords: list[str] | None = None,
                        require_auto_keyword: bool = False,
                        year_filter: bool = True,
                        max_articles: int = 400,
                        concurrency: int = 5,
                        tier: int = 1,
                        rss_url: str | None = None) -> dict:
    """sitemap 기반 빌더. URL 패턴 필터 + og:meta 추출 + 자동차 키워드 필터(옵션)."""
    print("=" * 60); print(f"  {source_name} Archive Builder"); print("=" * 60)
    existing, known = load_existing(archive_path)
    print(f"\n  [0/3] 기존 archive: {len(existing)}건")

    new_entries = []

    async with httpx.AsyncClient(timeout=90, follow_redirects=True, headers=HEADERS_BROWSER) as client:
        # Optional RSS first
        if rss_url:
            print(f"\n  [pre/3] RSS 수집: {rss_url}")
            feed = feedparser.parse(rss_url, agent=HEADERS_BROWSER["User-Agent"])
            rss_added = 0
            for e in feed.entries:
                url = e.get("link", "").strip()
                if not url or url in known: continue
                lm = parse_rss_date(e)
                if year_filter and not is_year_2026(lm): continue
                title = strip_html(e.get("title", ""))
                desc = strip_html(e.get("summary", ""))[:500]
                if require_auto_keyword and not is_auto_relevant(title, desc): continue
                new_entries.append({
                    "url": url, "title": title, "description": desc,
                    "lastmod": lm, "source": source_name, "tier": tier,
                })
                known.add(url); rss_added += 1
            print(f"      RSS 신규 {rss_added}건")

        print(f"\n  [1/3] sitemap 수집: {sitemap_url}")
        st, body = await fetch(client, sitemap_url)
        if st != 200:
            print(f"      sitemap 실패 [{st}]")
            return _save(existing, new_entries, archive_path, source_name, site_base,
                          sitemap_url=sitemap_url, rss_url=rss_url)

        sub_sitemaps, pairs = parse_sitemap(body)

        # If sitemap is index, drill down into sub-sitemaps
        if sub_sitemaps:
            if sub_include_keywords:
                use_subs = [s for s in sub_sitemaps if any(k in s for k in sub_include_keywords)]
            else:
                use_subs = sub_sitemaps
            print(f"      sub-sitemap: 전체 {len(sub_sitemaps)}, 사용 {len(use_subs)}")
            for sm_url in use_subs:
                sm_url2 = sm_url.replace("http://", "https://")
                s, b = await fetch(client, sm_url2)
                if s == 200:
                    _, more = parse_sitemap(b)
                    pairs.extend(more)

        # Filter pairs
        def url_ok(u):
            if not any(inc in u for inc in url_includes):
                return False
            if url_excludes and any(exc in u for exc in url_excludes):
                return False
            return True

        filtered = [(u, lm) for u, lm in pairs if url_ok(u)]
        if year_filter:
            filtered = [(u, lm) for u, lm in filtered if is_year_2026(lm)]
        # Dedupe
        seen = set(); pairs2 = []
        for u, lm in sorted(filtered, key=lambda x: x[1] or "", reverse=True):
            if u not in seen and u not in known:
                seen.add(u); pairs2.append((u, lm))
        pairs2 = pairs2[:max_articles]
        print(f"      URL 패턴+년도 필터 통과 {len(pairs2)}건")

        if pairs2:
            print(f"\n  [2/3] og:meta 추출 ({len(pairs2)}건, 동시 {concurrency})")
            sem = asyncio.Semaphore(concurrency)
            ok_cnt = 0

            async def fetch_meta(idx, url, lm):
                nonlocal ok_cnt
                async with sem:
                    s, html = await fetch(client, url)
                    if s != 200: return None
                    title, desc, pub = extract_meta(html)
                    if not title: return None
                    if require_auto_keyword and not is_auto_relevant(title, desc):
                        return None
                    ok_cnt += 1
                    if (idx + 1) % 25 == 0:
                        print(f"      진행: {idx+1}/{len(pairs2)} (ok {ok_cnt})")
                    return {"url": url, "title": title, "description": desc,
                            "lastmod": pub or lm, "source": source_name, "tier": tier}

            results = await asyncio.gather(*[fetch_meta(i, u, lm) for i, (u, lm) in enumerate(pairs2)])
            for r in results:
                if r and (not year_filter or is_year_2026(r["lastmod"])):
                    new_entries.append(r)
            print(f"      추출 완료 (auto-relevant): {sum(1 for r in results if r)}")

    return _save(existing, new_entries, archive_path, source_name, site_base,
                  sitemap_url=sitemap_url, rss_url=rss_url)


def _save(existing, new_entries, archive_path, source_name, site_base,
          sitemap_url=None, rss_url=None) -> dict:
    all_e = existing + new_entries
    seen = set(); merged = []
    for e in all_e:
        u = e.get("url")
        if not u or u in seen: continue
        if not is_year_2026(e.get("lastmod", "")): continue
        seen.add(u); merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)
    print(f"\n  [save] 저장: {len(merged)}건 (신규 +{len(new_entries)})")
    archive = {
        "source": source_name, "site_base": site_base,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "year_filter": "2026",
        "entry_count": len(merged), "newly_added": len(new_entries),
        "previously_known": len(existing), "entries": merged,
    }
    if sitemap_url: archive["sitemap_url"] = sitemap_url
    if rss_url:     archive["rss_url"] = rss_url
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {archive_path}  ({archive_path.stat().st_size/1024:.1f} KB)")
    print("=" * 60)
    return archive
