"""MIT Technology Review 아카이브 빌더.

전략: sitemap XML 36개 순회 + robotics/AI 키워드 필터링.
⚠ 본문: 유료 구독 페이월. og:description(요약)만 수집.

실행:
    python scripts/build_mit_tech_review_archive.py         # 최근 6개월
    python scripts/build_mit_tech_review_archive.py 12      # 최근 12개월

산출:
    data/archives/mit_tech_review.json
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
ARCHIVE_PATH = ARCHIVE_DIR / "mit_tech_review.json"
SOURCE_NAME  = "MIT Technology Review"
SITE_BASE    = "https://www.technologyreview.com"
# 3단계 중첩: sitemap.xml → sitemap-index-2.xml → sitemap-index-1.xml → sitemap-N.xml
# sitemap-index-1.xml을 직접 사용 (36개 기사 sitemap 포함)
SITEMAP_INDEX = SITE_BASE + "/sitemap-index-1.xml"

DEFAULT_MONTHS = 6
CONCURRENCY    = 4
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

ROBOTICS_KEYWORDS = {
    "robot", "humanoid", "bipedal", "locomotion", "autonomous vehicle",
    "boston dynamics", "figure ai", "optimus", "agility robotics",
    "unitree", "dexterous", "embodied ai", "physical ai", "manipulation",
    "warehouse robot", "industrial robot", "robotics", "robotic arm",
    "nvidia isaac", "gr00t",
}


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


def parse_sitemap_index(xml: str) -> list[str]:
    soup = BeautifulSoup(xml, "xml")
    return [loc.text.strip() for loc in soup.find_all("loc")]


def parse_sitemap(xml: str, cutoff: str) -> tuple[list[tuple[str, str]], bool]:
    soup = BeautifulSoup(xml, "xml")
    out = []
    has_recent = False
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm  = u.find("lastmod")
        if not loc:
            continue
        url    = loc.text.strip()
        lm_str = lm.text.strip()[:10] if lm else ""
        if lm_str >= cutoff:
            has_recent = True
        if lm_str and lm_str < cutoff:
            continue
        # /topic/ 과 /author/ 등 비기사 URL 제외
        if any(x in url for x in ["/author/", "/topic/", "/tag/", "/feed/"]):
            continue
        out.append((url, lm_str))
    return out, has_recent


def is_robotics(title: str, desc: str) -> bool:
    combined = (title + " " + desc).lower()
    return any(kw in combined for kw in ROBOTICS_KEYWORDS)


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
    print("=" * 70)
    print(f"  {SOURCE_NAME} Archive Builder")
    print(f"  기간: 최근 {months}개월 (cutoff: {cutoff})")
    print("=" * 70)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        print(f"\n  [1/3] sitemap index 수집: {SITEMAP_INDEX}")
        st, xml = await fetch(client, SITEMAP_INDEX)
        if st != 200:
            print(f"  ⚠ sitemap 접근 실패: HTTP {st}")
            return {}

        sitemap_urls = parse_sitemap_index(xml)
        # 기사 sitemap만 (post-sitemap 포함)
        sitemap_urls = [u for u in sitemap_urls if "sitemap" in u.lower()]
        print(f"  → sitemap {len(sitemap_urls)}개")

        all_pairs: list[tuple[str, str]] = []
        for i, sm_url in enumerate(sitemap_urls):
            st, xml = await fetch(client, sm_url)
            if st != 200:
                continue
            pairs, has_recent = parse_sitemap(xml, cutoff)
            all_pairs.extend(pairs)
            print(f"    [{i+1:2d}] {len(pairs):4d}건 (cutoff 내)  {sm_url.split('/')[-1]}")
            # 이 sitemap에 최근 항목이 전혀 없으면 이후 sitemaps도 오래된 데이터
            if not has_recent and i > 5:
                print("    → 최근 항목 없음 → 나머지 sitemaps 스킵")
                break

        # 중복 제거
        seen_u: set[str] = set()
        unique = []
        for u, d in all_pairs:
            if u not in seen_u:
                seen_u.add(u)
                unique.append((u, d))
        print(f"  → 중복 제거 후: {len(unique)}건")

        new_pairs = [(u, d) for u, d in unique if u not in known_urls]
        print(f"  → 신규: {len(new_pairs)}건 (기존 {len(unique)-len(new_pairs)}건 스킵)")

        # 신규 URL 메타 fetch + 키워드 필터
        print(f"\n  [2/3] 기사 메타 fetch + robotics 필터 (신규 {len(new_pairs)}건, 동시 {CONCURRENCY})")
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
                if not is_robotics(title, desc):
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

    print("\n  [3/3] 저장")
    archive = {
        "source":           SOURCE_NAME,
        "site_base":        SITE_BASE,
        "built_at":         datetime.now().isoformat(timespec="seconds"),
        "months":           months,
        "cutoff_date":      cutoff,
        "body_access":      "paywall",
        "body_note":        "구독 필요. og:description 요약만 활용 가능.",
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
