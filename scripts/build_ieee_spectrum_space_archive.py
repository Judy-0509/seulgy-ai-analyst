"""IEEE Spectrum Space Datacenter 아카이브 빌더.

전략:
  - 번호형 sitemap 직접 순회 (sitemap_1 = 최신).
  - 미디어 파일(/media-library/) 제외, lastmod >= cutoff만 수집.
  - 기사 fetch 후 title/description space datacenter 키워드 필터.
⚠ 본문: 일부 기사 IEEE 회원 전용. og:description 요약만 수집.

실행:
    python scripts/build_ieee_spectrum_space_archive.py         # 최근 6개월
    python scripts/build_ieee_spectrum_space_archive.py 12      # 최근 12개월

산출:
    data/archives/ieee_spectrum_space.json
"""
import asyncio
import io
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR  = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "ieee_spectrum_space.json"
SOURCE_NAME  = "IEEE Spectrum"
SITE_BASE    = "https://spectrum.ieee.org"
SITEMAP_FMT   = SITE_BASE + "/feeds/sitemaps/sitemap_{n}.xml"
MAX_SITEMAP_N = 20

DEFAULT_MONTHS = 6
CONCURRENCY    = 4
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

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


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def is_media(url: str) -> bool:
    return "/media-library/" in url or bool(re.search(r"\.(jpg|png|gif|jpeg|webp|svg)\?", url))


def parse_sitemap(xml: str, cutoff: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(xml, "xml")
    out = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm  = u.find("lastmod")
        if not loc:
            continue
        url    = loc.text.strip()
        lm_str = lm.text.strip()[:10] if lm else ""
        if is_media(url):
            continue
        if lm_str and lm_str < cutoff:
            continue
        out.append((url, lm_str))
    return out


def extract_meta(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = desc = pub_date = ""
    el = soup.find("meta", property="og:title")
    if el and el.get("content"):
        title = re.sub(r"\s+", " ", el["content"]).strip()
    for prop in ["og:description", "description"]:
        el = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if el and el.get("content"):
            desc = re.sub(r"\s+", " ", el["content"]).strip()[:500]
            break
    el = soup.find("meta", property="article:published_time")
    if el and el.get("content"):
        pub_date = el["content"]
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))
    return title, desc, pub_date


async def build(months: int) -> dict:
    cutoff = cutoff_date(months)
    keywords = load_keywords()
    print("=" * 70)
    print(f"  {SOURCE_NAME} Space Archive Builder")
    print(f"  기간: 최근 {months}개월 (cutoff: {cutoff})")
    print(f"  sitemap 범위: sitemap_1 ~ sitemap_{MAX_SITEMAP_N}")
    print("=" * 70)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        print("\n  [1/3] sitemap 수집")
        all_pairs: list[tuple[str, str]] = []

        for n in range(1, MAX_SITEMAP_N + 1):
            sm_url = SITEMAP_FMT.format(n=n)
            st, xml = await fetch(client, sm_url)
            if st != 200:
                print(f"    sitemap_{n}: skip (HTTP {st})")
                continue
            pairs = parse_sitemap(xml, cutoff)
            all_pairs.extend(pairs)
            print(f"    sitemap_{n}: {len(pairs):4d}건 (cutoff 이후, 미디어 제외)")

        seen_u: set[str] = set()
        unique = []
        for u, d in all_pairs:
            if u not in seen_u:
                seen_u.add(u)
                unique.append((u, d))
        new_pairs = [(u, d) for u, d in unique if u not in known_urls]
        print(f"  → 중복 제거: {len(unique)}건, 신규: {len(new_pairs)}건 (기존 {len(unique)-len(new_pairs)}건 스킵)")

        print(f"\n  [2/3] 기사 fetch + space datacenter 필터 ({len(new_pairs)}건, 동시 {CONCURRENCY})")
        sem = asyncio.Semaphore(CONCURRENCY)
        ok = err = skipped_kw = 0

        async def fetch_meta(url: str, lm: str):
            nonlocal ok, err, skipped_kw
            async with sem:
                st, html = await fetch(client, url)
                if st != 200:
                    err += 1
                    return None
                title, desc, pub_date = extract_meta(html)
                if not title:
                    err += 1
                    return None
                if not is_relevant(title, desc, keywords):
                    skipped_kw += 1
                    return None
                ok += 1
                lm_val = pub_date or lm
                if len(lm_val) == 10:
                    lm_val += "T00:00:00"
                return {
                    "url":         url,
                    "title":       title,
                    "description": desc,
                    "lastmod":     lm_val,
                    "source":      SOURCE_NAME,
                    "tier":        1,
                }

        tasks   = [fetch_meta(u, d) for u, d in new_pairs]
        results = await asyncio.gather(*tasks)
        new_entries = [r for r in results if r]
        print(f"  → 완료: {ok}건, 실패: {err}건, 키워드 필터: {skipped_kw}건")

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

    print("\n  [3/3] 저장")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "months":           months,
        "cutoff_date":      cutoff,
        "body_access":      "partial_paywall",
        "body_note":        "일부 기사 IEEE 회원 전용. og:description 요약만 수집.",
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


async def main():
    months = DEFAULT_MONTHS
    if len(sys.argv) > 1:
        try:
            months = int(sys.argv[1])
        except ValueError:
            print(f"사용법: python {sys.argv[0]} [개월수]")
            sys.exit(1)
    await build(months)


if __name__ == "__main__":
    asyncio.run(main())
