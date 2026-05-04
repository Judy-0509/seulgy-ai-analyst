"""네이버 증권 리서치 아카이브 빌더.

전략:
  - finance.naver.com/research/ 산업분석 + 기업분석 탭
  - httpx로 목록 페이지 파싱 (EUC-KR 인코딩)
  - PDF 직접 다운로드 → pdfplumber로 텍스트 추출
  - 증분 업데이트 (기존 archive 보존, 신규만 처리)
  - 기본 최대 50페이지/탭 (약 1000건) — MAX_PAGES 조정 가능

사용:
  python scripts/build_naver_research_archive.py

산출:
  data/archives/naver_research.json
"""
import asyncio
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pdfplumber
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ARCHIVE_DIR = Path("data/archives")
ARCHIVE_PATH = ARCHIVE_DIR / "naver_research.json"

SITE_BASE = "https://finance.naver.com"
TABS = {
    "industry": SITE_BASE + "/research/industry_list.naver",
    "company":  SITE_BASE + "/research/company_list.naver",
}

MAX_PAGES = 50       # 탭당 최대 수집 페이지 (약 20건/페이지 → 최대 1000건/탭)
PDF_MAX_CHARS = 3000  # PDF 텍스트 저장 한도
CONCURRENCY_LIST = 4  # 목록 페이지 동시 요청
CONCURRENCY_PDF  = 3  # PDF 동시 다운로드
REQUEST_DELAY    = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer": "https://finance.naver.com/research/",
}


# ── 날짜 ──────────────────────────────────────────────────────────────────────

def parse_date(raw: str) -> str:
    """'26.04.30' → '2026-04-30T00:00:00'"""
    raw = raw.strip()
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{2})", raw)
    if m:
        yy, mo, dd = m.groups()
        return f"20{yy}-{mo}-{dd}T00:00:00"
    return raw


# ── HTTP ──────────────────────────────────────────────────────────────────────

async def fetch_bytes(client: httpx.AsyncClient, url: str) -> tuple[int, bytes]:
    await asyncio.sleep(REQUEST_DELAY)
    try:
        r = await client.get(url, timeout=25)
        return r.status_code, r.content
    except Exception as e:
        return 0, f"ERR: {e}".encode()


# ── 목록 페이지 파싱 ──────────────────────────────────────────────────────────

def parse_list_page(html: str, tab: str) -> list[dict]:
    """목록 페이지 HTML → 엔트리 리스트."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="type_1")
    if not table:
        return []

    entries = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        # 산업분석: 분류 | 제목 | 증권사 | 파일 | 날짜 | 조회수
        # 기업분석: 종목명 | 제목 | 증권사 | 파일 | 날짜 | 조회수
        if tab == "industry":
            category_td = tds[0]
            title_td    = tds[1]
            broker_td   = tds[2]
            file_td     = tds[3]
            date_td     = tds[4]
        else:  # company
            category_td = tds[0]
            title_td    = tds[1]
            broker_td   = tds[2]
            file_td     = tds[3]
            date_td     = tds[4]

        # 제목 + 상세 링크
        title_a = title_td.find("a")
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        if not title:
            continue

        # PDF 링크
        file_a = file_td.find("a", href=True)
        if not file_a:
            continue
        pdf_href = file_a["href"]
        if not pdf_href.startswith("http"):
            pdf_href = SITE_BASE + pdf_href
        if not pdf_href.lower().endswith(".pdf"):
            continue

        brokerage = broker_td.get_text(strip=True)
        date_raw  = date_td.get_text(strip=True)
        date_iso  = parse_date(date_raw)
        category  = category_td.get_text(strip=True)

        entries.append({
            "url": pdf_href,
            "title": title,
            "description": "",   # PDF 텍스트로 채울 예정
            "brokerage": brokerage,
            "category": category,
            "lastmod": date_iso,
            "source": "Naver Research",
            "tab": tab,
            "tier": 2,
        })

    return entries


# ── PDF 텍스트 추출 ───────────────────────────────────────────────────────────

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """pdfplumber로 PDF → 텍스트 (PDF_MAX_CHARS 제한)."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            parts = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                parts.append(text)
                if sum(len(p) for p in parts) >= PDF_MAX_CHARS * 2:
                    break
            full = "\n".join(parts)
            full = re.sub(r"\s{3,}", "  ", full).strip()
            return full[:PDF_MAX_CHARS]
    except Exception:
        return ""


# ── 목록 수집 ─────────────────────────────────────────────────────────────────

async def collect_tab_entries(
    client: httpx.AsyncClient,
    tab: str,
    known_urls: set[str],
) -> list[dict]:
    """한 탭의 목록 페이지들을 순회해 신규 엔트리 수집."""
    base_url = TABS[tab]
    sem = asyncio.Semaphore(CONCURRENCY_LIST)
    all_new: list[dict] = []
    stop_flag = False

    async def _fetch_page(page_num: int) -> list[dict]:
        nonlocal stop_flag
        if stop_flag:
            return []
        async with sem:
            url = f"{base_url}?&page={page_num}"
            s, content = await fetch_bytes(client, url)
            if s != 200:
                return []
            html = content.decode("euc-kr", errors="replace")
            entries = parse_list_page(html, tab)

            new_entries = [e for e in entries if e["url"] not in known_urls]

            # 이 페이지의 모든 항목이 이미 알려진 경우 → 중단 신호
            if entries and not new_entries:
                stop_flag = True

            return new_entries

    for page_num in range(1, MAX_PAGES + 1):
        if stop_flag:
            print(f"    [{tab}] p{page_num-1}에서 기존 항목만 발견 → 중단")
            break
        results = await _fetch_page(page_num)
        all_new.extend(results)
        if (page_num) % 10 == 0:
            print(f"    [{tab}] {page_num}페이지 완료, 신규 {len(all_new)}건")

    return all_new


# ── PDF 텍스트 채우기 ─────────────────────────────────────────────────────────

async def fill_pdf_texts(
    client: httpx.AsyncClient,
    entries: list[dict],
) -> None:
    """entries의 description 필드를 PDF 텍스트로 채운다 (in-place)."""
    if not entries:
        return
    print(f"\n  PDF 텍스트 추출 ({len(entries)}건, concurrency {CONCURRENCY_PDF})")
    sem = asyncio.Semaphore(CONCURRENCY_PDF)
    ok_cnt = 0
    fail_cnt = 0

    async def _one(idx: int, entry: dict):
        nonlocal ok_cnt, fail_cnt
        async with sem:
            s, data = await fetch_bytes(client, entry["url"])
            if s != 200 or len(data) < 100:
                fail_cnt += 1
                return
            text = extract_pdf_text(data)
            entry["description"] = text
            ok_cnt += 1
            if (idx + 1) % 50 == 0:
                print(f"    PDF 진행: {idx+1}/{len(entries)} (ok {ok_cnt}, fail {fail_cnt})")

    await asyncio.gather(*[_one(i, e) for i, e in enumerate(entries)])
    print(f"  → PDF 추출 완료: ok {ok_cnt}, fail {fail_cnt}")


# ── 기존 archive 로드 ─────────────────────────────────────────────────────────

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


# ── 메인 빌드 ─────────────────────────────────────────────────────────────────

async def build() -> dict:
    print("=" * 76)
    print("  Naver Research Archive Builder")
    print(f"  tabs: 산업분석 + 기업분석 | max {MAX_PAGES}페이지/탭 | PDF 텍스트 추출")
    print("=" * 76)

    existing_entries, known_urls = load_existing()
    print(f"\n  [0/3] 기존 archive 로드: {len(existing_entries)}건")

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        # 1. 목록 수집
        print("\n  [1/3] 목록 페이지 수집")
        all_new: list[dict] = []
        for tab in ("industry", "company"):
            print(f"  → [{tab}] 수집 시작 (max {MAX_PAGES}p)")
            tab_entries = await collect_tab_entries(client, tab, known_urls)
            print(f"  → [{tab}] 신규 {len(tab_entries)}건")
            all_new.extend(tab_entries)
            known_urls.update(e["url"] for e in tab_entries)

        print(f"\n  → 전체 신규: {len(all_new)}건")

        # 2. PDF 텍스트 추출
        print("\n  [2/3] PDF 텍스트 추출")
        await fill_pdf_texts(client, all_new)

    # 3. Merge + dedup + 정렬
    all_entries = existing_entries + all_new
    seen: set[str] = set()
    merged: list[dict] = []
    for e in all_entries:
        u = e.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        merged.append(e)
    merged.sort(key=lambda e: e.get("lastmod") or "", reverse=True)

    print(f"\n  [3/3] 아카이브 저장")
    archive = {
        "source": "Naver Research",
        "site_base": SITE_BASE,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(merged),
        "newly_added": len(all_new),
        "previously_known": len(existing_entries),
        "tabs": ["industry", "company"],
        "entries": merged,
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    size_kb = ARCHIVE_PATH.stat().st_size / 1024
    print(f"  → 저장: {ARCHIVE_PATH}  ({size_kb:.1f} KB)")
    print("\n" + "=" * 76)
    print(f"  완료. 총 {len(merged)}건 (신규 +{len(all_new)}, 기존 {len(existing_entries)})")
    print("=" * 76)
    return archive


def show_samples(archive: dict, kw_list: list[str]):
    entries = archive.get("entries", [])
    if not entries:
        return
    print("\n  키워드별 매칭 샘플:")
    for kw in kw_list:
        kw_l = kw.lower()
        matched = [e for e in entries if kw_l in (e["title"] + " " + e.get("description", "")).lower()]
        print(f"\n  · '{kw}' → {len(matched)}건")
        for e in matched[:2]:
            snippet = e.get("description", "")[:80].replace("\n", " ")
            print(f"      [{e['lastmod'][:10]}] {e['title'][:60]}")
            if snippet:
                print(f"        → {snippet}…")


async def main():
    archive = await build()
    show_samples(archive, ["반도체", "AI", "스마트폰", "디스플레이", "배터리", "삼성", "TSMC"])


if __name__ == "__main__":
    asyncio.run(main())
