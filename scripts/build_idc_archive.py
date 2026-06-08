"""IDC (idc.com) 아카이브 빌더.

수집 대상:
  1. post-sitemap.xml  → /resource-center/blog/{slug}/ 기사 (cutoff 이후)
  2. promo-sitemap.xml → /promo/{name}/ 마켓 트래커 13개 (전부)

접근 방식:
  - WAF/JS 챌린지 없음 → httpx 직접 사용
  - og:title + og:description 추출
  - 증분 업데이트 (기존 archive 보존, 신규만 fetch)

사용:
  python scripts/build_idc_archive.py               # 2026-01-01 이후
  python scripts/build_idc_archive.py 2025-01-01    # 2025 포함

산출:
  data/archives/idc.json
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

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "idc.json"

SITE_BASE = "https://www.idc.com"
POST_SITEMAP   = SITE_BASE + "/post-sitemap.xml"
PROMO_SITEMAP  = SITE_BASE + "/promo-sitemap.xml"

DEFAULT_CUTOFF = "2026-01-01"
CONCURRENCY    = 8
REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR: {e}"


def parse_sitemap(xml: str) -> list[tuple[str, str]]:
    """(loc, lastmod) 리스트 반환."""
    soup = BeautifulSoup(xml, "xml")
    out = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        lm  = u.find("lastmod")
        if loc:
            out.append((loc.text.strip(), (lm.text if lm else "").strip()))
    return out


def extract_meta(html: str) -> tuple[str, str, str]:
    """og:title + og:description + 실제 발행일 추출.

    발행일 우선순위:
      1. <meta property="article:published_time">  (WordPress 표준)
      2. JSON-LD datePublished / dateCreated
      3. <time datetime="...">
      사이트맵 lastmod는 사이트맵 재생성일을 반영하므로 사용하지 않음.
    """
    soup = BeautifulSoup(html, "html.parser")
    title, desc, pub_date = "", "", ""

    el_t = soup.find("meta", property="og:title")
    if el_t and el_t.get("content"):
        title = re.sub(r"\s+", " ", el_t["content"]).strip()
    el_d = soup.find("meta", property="og:description")
    if el_d and el_d.get("content"):
        desc = re.sub(r"\s+", " ", el_d["content"]).strip()
    if not title:
        t = soup.find("title")
        if t:
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True))

    # 1) article:published_time
    el_pt = soup.find("meta", property="article:published_time")
    if el_pt and el_pt.get("content"):
        pub_date = el_pt["content"].strip()

    # 2) JSON-LD datePublished / dateCreated
    if not pub_date:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string or "")
                candidates = [ld] if isinstance(ld, dict) else (ld if isinstance(ld, list) else [])
                for item in candidates:
                    if isinstance(item, dict):
                        pub_date = item.get("datePublished") or item.get("dateCreated") or ""
                        if pub_date:
                            break
            except Exception:
                pass
            if pub_date:
                break

    # 3) <time datetime="..."> fallback
    if not pub_date:
        el_time = soup.find("time", {"datetime": True})
        if el_time:
            pub_date = el_time["datetime"].strip()

    return title, desc, pub_date


def load_existing() -> tuple[list[dict], set[str]]:
    if not ARCHIVE_PATH.exists():
        return [], set()
    try:
        data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        urls = {e["url"] for e in entries if e.get("url")}
        return entries, urls
    except Exception:
        return [], set()


async def collect_urls(client: httpx.AsyncClient, cutoff: str) -> list[tuple[str, str]]:
    """post-sitemap + promo-sitemap에서 (url, lastmod) 수집."""
    print(f"\n  [1/3] sitemap 수집 (cutoff: {cutoff})")
    pairs: list[tuple[str, str]] = []

    # 1) post-sitemap — cutoff 이후 기사만
    s, xml = await fetch(client, POST_SITEMAP)
    if s == 200:
        posts = parse_sitemap(xml)
        filtered = [(u, lm) for u, lm in posts if lm >= cutoff]
        pairs.extend(filtered)
        print(f"    post-sitemap: 전체 {len(posts)}건 → cutoff 이후 {len(filtered)}건")
    else:
        print(f"    post-sitemap: [{s}] 실패")

    # 2) promo-sitemap — 전부 (마켓 트래커, 날짜 필터 없음)
    s, xml = await fetch(client, PROMO_SITEMAP)
    if s == 200:
        promos = parse_sitemap(xml)
        pairs.extend(promos)
        print(f"    promo-sitemap: {len(promos)}건 (전부 포함)")
    else:
        print(f"    promo-sitemap: [{s}] 실패")

    # 중복 제거 (lastmod 최신 우선)
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for u, lm in sorted(pairs, key=lambda x: x[1], reverse=True):
        if u not in seen:
            seen.add(u)
            deduped.append((u, lm))

    print(f"  → 총 {len(deduped)}건")
    return deduped


async def fetch_meta_all(
    client: httpx.AsyncClient, url_dates: list[tuple[str, str]]
) -> list[dict]:
    """동시성 제한 하에 og:meta 추출."""
    print(f"\n  [2/3] og:meta 추출 ({len(url_dates)}건, concurrency {CONCURRENCY})")
    sem = asyncio.Semaphore(CONCURRENCY)
    ok_cnt = 0
    fail_cnt = 0

    async def _one(idx: int, url: str, lm: str):
        nonlocal ok_cnt, fail_cnt
        async with sem:
            s, html = await fetch(client, url)
            if s != 200:
                fail_cnt += 1
                return None
            title, desc, pub_date = extract_meta(html)
            if not title and not desc:
                fail_cnt += 1
                return None
            ok_cnt += 1
            if (idx + 1) % 30 == 0:
                print(f"    진행: {idx+1}/{len(url_dates)} (ok {ok_cnt}, fail {fail_cnt})")
            return {
                "url": url,
                "title": title,
                "description": desc,
                "lastmod": pub_date or lm,  # 실제 발행일 우선, 없으면 사이트맵 lastmod
                "source": "IDC",
                "tier": 1,
            }

    tasks = [_one(i, u, lm) for i, (u, lm) in enumerate(url_dates)]
    results = await asyncio.gather(*tasks)
    entries = [r for r in results if r]
    print(f"  → 메타 추출 완료: {len(entries)}건 (실패 {fail_cnt}건)")
    return entries


async def build(cutoff: str) -> dict:
    print("=" * 76)
    print("  IDC Archive Builder")
    print(f"  cutoff: {cutoff}, concurrency: {CONCURRENCY}")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing_entries)}건")

    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True
    ) as client:
        all_pairs = await collect_urls(client, cutoff)

        new_pairs = [(u, lm) for u, lm in all_pairs if u not in known_urls]
        skipped = len(all_pairs) - len(new_pairs)
        print(f"  → 신규: {len(new_pairs)}건 (기존 {skipped}건 스킵)")

        new_entries = await fetch_meta_all(client, new_pairs) if new_pairs else []

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

    print("\n  [3/3] 아카이브 저장")
    archive = {
        "source": "IDC",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "cutoff_date": cutoff,
        "entry_count": len(merged),
        "newly_added": len(new_entries),
        "previously_known": len(existing_entries),
        "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"  → 저장: {ARCHIVE_PATH}  ({size_kb:.1f} KB)")
    print("\n" + "=" * 76)
    print(f"  완료. 총 {len(merged)}건 (신규 +{len(new_entries)}, 기존 {len(existing_entries)})")
    print("=" * 76)
    return archive


def show_samples(archive: dict, kw_list: list[str]):
    entries = archive.get("entries", [])
    if not entries:
        return
    print("\n  키워드별 매칭 샘플:")
    for kw in kw_list:
        kw_l = kw.lower()
        matched = [
            e for e in entries
            if kw_l in (e["title"] + " " + e["description"]).lower()
        ]
        print(f"\n  · '{kw}' → {len(matched)}건")
        for e in matched[:3]:
            print(f"      [{e['lastmod'][:10]}] {e['title'][:80]}")


async def redate(batch: int = 20):
    """기존 아카이브 전체를 재방문해 실제 발행일로 lastmod를 교정.

    사이트맵 lastmod가 오늘 날짜로 오염된 기존 기사들에 적용.
    사용: python scripts/build_idc_archive.py --redate [--batch N]

    batch: 동시 요청 수 (기본 20, 서버 부하 고려해 조절)
    """
    existing_entries, _ = load_existing()
    if not existing_entries:
        print("  아카이브가 비어 있습니다.")
        return

    print("=" * 76)
    print(f"  IDC Redate — 기존 {len(existing_entries)}건 실제 발행일 교정")
    print(f"  (concurrency {batch})")
    print("=" * 76)

    sem = asyncio.Semaphore(batch)
    updated = 0
    failed = 0

    async def _fix(idx: int, entry: dict):
        nonlocal updated, failed
        url = entry.get("url", "")
        async with sem:
            async with httpx.AsyncClient(
                headers=HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT
            ) as client:
                s, html = await fetch(client, url)
            if s != 200:
                failed += 1
                return entry
            _, _, pub_date = extract_meta(html)
            if pub_date:
                entry = {**entry, "lastmod": pub_date}
                updated += 1
            else:
                failed += 1  # 날짜 추출 실패 — 기존 값 유지
            if (idx + 1) % 20 == 0:
                print(f"    진행: {idx+1}/{len(existing_entries)} (교정 {updated}, 미발견 {failed})")
            return entry

    tasks = [_fix(i, e) for i, e in enumerate(existing_entries)]
    fixed_entries = await asyncio.gather(*tasks)
    fixed_entries = [e for e in fixed_entries if e]
    fixed_entries.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    archive_data = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    archive_data["entries"] = fixed_entries
    archive_data["built_at"] = datetime.now().isoformat(timespec="seconds")
    archive_data["entry_count"] = len(fixed_entries)
    ARCHIVE_PATH.write_text(
        json.dumps(archive_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  완료. 교정 {updated}건 / 날짜 미발견(기존 유지) {failed}건")
    print("=" * 76)


def parse_args():
    """(mode, cutoff, batch) 반환.

    mode: 'build' | 'redate'
    사용법:
      python scripts/build_idc_archive.py                  # 기본 빌드
      python scripts/build_idc_archive.py 2025-01-01       # cutoff 지정
      python scripts/build_idc_archive.py --redate         # 기존 기사 날짜 교정
      python scripts/build_idc_archive.py --redate --batch 10
    """
    args = sys.argv[1:]
    if "--redate" in args:
        batch = 20
        if "--batch" in args:
            bi = args.index("--batch")
            try:
                batch = int(args[bi + 1])
            except (IndexError, ValueError):
                pass
        return "redate", DEFAULT_CUTOFF, batch

    cutoff = DEFAULT_CUTOFF
    date_args = [a for a in args if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a)]
    if date_args:
        cutoff = date_args[0]
    elif args:
        print(f"사용법: python {sys.argv[0]} [YYYY-MM-DD | --redate [--batch N]]")
        sys.exit(1)
    return "build", cutoff, 20


async def main():
    mode, cutoff, batch = parse_args()
    if mode == "redate":
        await redate(batch)
    else:
        archive = await build(cutoff)
        show_samples(
            archive,
            ["smartphone", "foldable", "iPhone", "Samsung", "OLED",
             "memory", "DRAM", "AI", "market share", "shipment"],
        )


if __name__ == "__main__":
    asyncio.run(main())
