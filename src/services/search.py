import asyncio
import json
import random
import re
import time
from datetime import date
from pathlib import Path
import httpx
import feedparser
from bs4 import BeautifulSoup
from src.models import SearchResult, SearchResults
from src.config import RSS_SOURCES, SOURCE_TIER_MAP, JS_REQUIRED_DOMAINS, SEARCH_CONFIG, PAID_SOURCE_DOMAINS

ARCHIVES_DIR = Path(__file__).parent.parent.parent / "data" / "archives"


# 핵심 토픽어 분류용 사전들
ACTION_VERBS = {
    "launch", "release", "unveil", "reveal", "announce", "introduce",
    "debut", "rollout", "ship", "ships", "shipping", "start", "begin",
    "출시", "공개", "발표", "발매",
}
STOP_WORDS = {
    "the", "a", "an", "of", "in", "on", "at", "and", "or", "for", "to",
    "is", "are", "be", "with", "by", "as", "from", "this", "that",
    "vs", "via",
    # Publisher / research-firm names — PRE_SEARCH_PROMPT가 쿼리에 강제 주입하는
    # institutional source 이름들. eng_topic 추출 시 required term이 되면
    # archive 매칭 점수가 publisher 이름 포함 여부에 좌우되어 부작용 발생.
    "counterpoint", "idc", "gsmarena",
    "omdia", "trendforce", "yole",
    "scmp", "morgan", "stanley",
}
# 범용 명사 — required 대신 anchor로 강등하여 floor 점수에만 기여.
# 이 단어들이 required에 포함되면 "Display Production Tracker" 같은 무관 기사가
# production/market/supply 하나로 통과하는 오염 현상이 발생함.
GENERIC_NOUNS = {
    "production", "capacity", "supply", "chain", "market", "size", "growth",
    "shipment", "shipments", "forecast", "analysis", "tracker", "database",
    "report", "inventory", "price", "cost", "revenue", "share", "global",
    "demand", "outlook", "update", "data", "strategy", "trends", "trend",
    "overview", "insight", "latest", "new", "news",
}


def classify_core_terms(eng_topic: str, current_year: str | None = None) -> dict:
    """eng_topic을 required / anchor 로 분류.

    - action verb / stopword / 너무 짧은 토큰: drop
    - 숫자(연도) 또는 'latest': anchor
    - 그 외 (브랜드, 일반 명사): required (모두 매칭 시 통과)
    """
    tokens = re.findall(r"[A-Za-z]+", eng_topic or "")
    required: list[str] = []
    anchor: list[str] = []
    seen = set()
    for t in tokens:
        low = t.lower()
        if low in seen or len(low) < 2:
            continue
        seen.add(low)
        if low in ACTION_VERBS or low in STOP_WORDS:
            continue
        if low == "latest" or low in GENERIC_NOUNS:
            anchor.append(low)
        else:
            required.append(low)
    if current_year:
        anchor.append(str(current_year))
    return {"required": required, "anchor": anchor}


class SearchService:
    _edge_driver = None  # shared singleton

    def __init__(self):
        self._httpx_client = httpx.AsyncClient(
            timeout=SEARCH_CONFIG["httpx_timeout"],
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True,
        )
        self.core_terms: dict | None = None  # {"required": [...], "anchor": [...]}
        self._archives: list[dict] = self._load_archives()  # Tier 0: institutional archive

    @staticmethod
    def _load_archives() -> list[dict]:
        """data/archives/*.json 모두 로드.

        각 archive 파일 형식: {entries: [{url, title, description, lastmod, source, tier}]}
        반환: 모든 entry를 평탄화한 리스트 (archive 키 보존: source, tier).
        """
        if not ARCHIVES_DIR.exists():
            return []
        flat: list[dict] = []
        for f in sorted(ARCHIVES_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for e in (data.get("entries") or []):
                    if not e.get("url"):
                        continue
                    flat.append({
                        "url": e["url"],
                        "title": e.get("title") or "",
                        "description": e.get("description") or "",
                        "lastmod": e.get("lastmod") or "",
                        "source": e.get("source") or data.get("source") or "Archive",
                        "tier": e.get("tier") if e.get("tier") is not None else data.get("tier", 1),
                    })
            except Exception:
                continue
        return flat

    def set_core_terms(self, eng_topic: str, current_year: str | None = None) -> None:
        self.core_terms = classify_core_terms(eng_topic, current_year)

    def _score_text(self, text: str) -> tuple[float, bool]:
        """(score, passes_floor) 반환. core_terms 미설정 시 (1.0, True).

        REV4 매칭 완화 룰:
          - required·anchor 가중치는 3.0 / 0.5
          - 모든 required 매치 시 1.5× 보너스 (정밀 일치 우선)
          - passes_floor = score >= 0.5 — anchor만 매칭돼도 통과시켜 회수율 확보
        """
        if not self.core_terms:
            return 1.0, True
        low = (text or "").lower()
        required = self.core_terms["required"]
        anchor = self.core_terms["anchor"]
        if not required:
            return 1.0, True
        req_match = sum(1 for t in required if t in low)
        anc_match = sum(1 for t in anchor if t in low)
        score = req_match * 3.0 + anc_match * 0.5
        # 모든 required 매치 시 보너스 (정밀 일치 우선)
        if req_match == len(required):
            score *= 1.5
        passes_floor = score >= 0.5
        return score, passes_floor

    def _search_archive(self, query: str, keywords: list[str]) -> list[tuple[float, SearchResult]]:
        """Tier 0: institutional archive (Counterpoint 등) — 메모리 검색, 즉시 응답.

        scoring 규칙:
          - core_terms 있으면 _score_text() 통과한 것만 (주제 관련성 게이트)
          - 통과 후 섹션 쿼리 키워드 매칭 보너스 추가 → 섹션별 차별화
          - core_terms 없으면 query keyword 부분문자열 매칭
          - tier 1 archive entry는 점수 × 3.0 보너스 → 상위 노출
        """
        if not self._archives:
            return []
        kw_lower = [k.lower() for k in (keywords or [])]
        scored: list[tuple[float, SearchResult]] = []
        for entry in self._archives:
            text = (entry["title"] + " " + entry["description"]).strip()
            if not text:
                continue
            low = text.lower()
            if self.core_terms:
                score, passes = self._score_text(text)
                if not passes:
                    continue
                # 섹션 쿼리 키워드 매칭 보너스 — 섹션별 랭킹 차별화
                if kw_lower:
                    kw_match = sum(1 for k in kw_lower if k in low)
                    score += kw_match * 1.5
            else:
                if not kw_lower or not any(k in low for k in kw_lower):
                    continue
                score = 1.0
            # Tier 1 institutional 보너스 — RSS의 1.5× 보너스를 능가하도록
            if (entry.get("tier") or 1) == 1:
                score *= 3.0
            sr = SearchResult(
                source_url=entry["url"],
                final_url=entry["url"],
                content=text[:2000],  # title + description (LLM evidence)
                tier=entry.get("tier", 1),
                source_name=entry.get("source", "Archive"),
                article_title=entry["title"],
            )
            scored.append((score, sr))
        # 점수 순 정렬 후 합리적 cap (RSS·httpx와 경쟁 가능하도록)
        scored.sort(key=lambda x: -x[0])
        return scored[:15]

    async def search(self, query: str, keywords: list[str] = None) -> SearchResults:
        keywords = keywords or query.split()
        all_scored: list[tuple[float, SearchResult]] = []
        all_urls: set[str] = set()

        # Tier 0: institutional archive (즉시 응답, API 호출 없음)
        archive_scored = self._search_archive(query, keywords)
        for score, r in archive_scored:
            all_scored.append((score, r))
            all_urls.update([r.source_url, r.final_url])

        # Tier 1: RSS (scored, per-source quota)
        rss_scored = await self._search_rss(query, keywords)
        for score, r in rss_scored:
            if r.source_url in all_urls:
                continue  # archive와 중복되면 archive 우선 (이미 등록됨)
            all_scored.append((score, r))
            all_urls.update([r.source_url, r.final_url])

        cap = SEARCH_CONFIG["max_results_per_query"] * 2

        # Tier 2: httpx fallback — RSS 결과가 cap의 절반 미만일 때만
        if len(all_scored) < cap // 2:
            httpx_results = await self._search_httpx(query, keywords, fetched=all_urls)
            for r in httpx_results:
                txt = (r.source_name or "") + " " + (r.content or "")
                score, all_req = self._score_text(txt)
                # core_terms가 있을 땐 required AND-매칭 통과한 것만
                if self.core_terms and not all_req:
                    continue
                all_scored.append((score, r))
                all_urls.update([r.source_url, r.final_url])

        # 점수 desc 정렬 후 cap 적용
        all_scored.sort(key=lambda x: -x[0])
        results = [r for _, r in all_scored[:cap]]
        return SearchResults(
            results=results,
            fetched_urls=frozenset(u for u in all_urls if u),
        )

    async def search_archive_only(self, query: str, keywords: list[str] | None = None) -> SearchResults:
        """Tier 0 (archive) 만 사용. 외부 호출 0회. fallback UX용.

        Cap 동작: `_search_archive()` 자체가 line 161 에서 [:15] 절단 적용.
        여기서 추가로 config_cap 적용 → effective_cap = min(15, config_cap).
        """
        keywords = keywords or query.split()
        archive_scored = self._search_archive(query, keywords)  # 이미 [:15] 적용됨
        archive_scored.sort(key=lambda x: -x[0])
        cap = SEARCH_CONFIG["max_results_per_query"] * 2
        results = [r for _, r in archive_scored[:cap]]
        urls = {r.source_url for r in results}
        return SearchResults(results=results, fetched_urls=frozenset(urls))

    async def search_external_only(
        self,
        query: str,
        keywords: list[str] | None = None,
        fetched: set[str] | None = None,
    ) -> SearchResults:
        """Tier 1 (RSS) + Tier 2 (DDG) 만. archive 제외. fetched 는 dedup용 URL set."""
        keywords = keywords or query.split()
        fetched = fetched or set()
        all_scored: list[tuple[float, SearchResult]] = []
        all_urls: set[str] = set(fetched)

        rss_scored = await self._search_rss(query, keywords)
        for score, r in rss_scored:
            if r.source_url in all_urls:
                continue
            all_scored.append((score, r))
            all_urls.update([r.source_url, r.final_url])

        cap = SEARCH_CONFIG["max_results_per_query"] * 2
        if len(all_scored) < cap // 2:
            httpx_results = await self._search_httpx(query, keywords, fetched=all_urls)
            for r in httpx_results:
                txt = (r.source_name or "") + " " + (r.content or "")
                score, all_req = self._score_text(txt)
                if self.core_terms and not all_req:
                    continue
                all_scored.append((score, r))
                all_urls.update([r.source_url, r.final_url])

        all_scored.sort(key=lambda x: -x[0])
        new_urls = all_urls - set(fetched)
        results = [r for _, r in all_scored[:cap]]
        return SearchResults(
            results=results,
            fetched_urls=frozenset(u for u in new_urls if u),
        )

    async def _search_rss(self, query: str, keywords: list[str]) -> list[tuple[float, SearchResult]]:
        """모든 소스를 병렬 패치 → 소스별 쿼터 적용 → (score, SearchResult) 리스트 반환."""
        kw_lower = [k.lower() for k in keywords]
        max_per_source = SEARCH_CONFIG.get("max_per_source", 3)
        max_entries = SEARCH_CONFIG.get("max_entries_per_feed", 30)
        rss_timeout = SEARCH_CONFIG.get("rss_feed_timeout", 8.0)
        loop = asyncio.get_running_loop()

        async def _fetch_one(source: dict) -> list[tuple[float, SearchResult]]:
            try:
                feed = await asyncio.wait_for(
                    loop.run_in_executor(None, feedparser.parse, source["url"]),
                    timeout=rss_timeout,
                )
                source_scored: list[tuple[float, SearchResult]] = []
                for entry in feed.entries[:max_entries]:
                    title = getattr(entry, "title", "")
                    summary = getattr(entry, "summary", "")
                    text = (title or "") + " " + (summary or "")

                    if self.core_terms:
                        score, passes = self._score_text(text)
                        if not passes:
                            continue
                    else:
                        low = text.lower()
                        if not any(k in low for k in kw_lower):
                            continue
                        score = 1.0

                    content = summary or (
                        getattr(entry, "content", [{}])[0].get("value", "")
                        if getattr(entry, "content", None) else ""
                    )
                    link = getattr(entry, "link", "")
                    source_scored.append((score, SearchResult(
                        source_url=link,
                        final_url=link,
                        content=BeautifulSoup(content, "html.parser").get_text()[:2000],
                        tier=source["tier"],
                        source_name=source["name"],
                        article_title=title or "",
                    )))

                source_scored.sort(key=lambda x: -x[0])
                return source_scored[:max_per_source]
            except Exception:
                return []

        per_source = await asyncio.gather(*[_fetch_one(s) for s in RSS_SOURCES])
        all_collected: list[tuple[float, SearchResult]] = []
        for results in per_source:
            all_collected.extend(results)
        return all_collected

    async def _search_httpx(self, query: str, keywords: list[str], fetched: set) -> list[SearchResult]:
        results = []
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            resp = await self._httpx_client.get(search_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            for link_tag in soup.select(".result__url")[:10]:
                url = link_tag.get_text(strip=True)
                if not url.startswith("http"):
                    url = "https://" + url
                domain = url.split("/")[2] if "/" in url else url
                if url in fetched:
                    continue
                tier = SOURCE_TIER_MAP.get(domain, 4)
                if tier <= 3:
                    try:
                        page_resp = await self._httpx_client.get(url)
                        text = BeautifulSoup(page_resp.text, "html.parser").get_text()[:2000]
                        results.append(SearchResult(
                            source_url=url,
                            final_url=str(page_resp.url),
                            content=text,
                            tier=tier,
                            source_name=domain,
                        ))
                    except Exception:
                        continue
        except Exception:
            pass
        return results

    async def fetch_url(self, url: str) -> SearchResult | None:
        domain = url.split("/")[2] if "/" in url else url
        if any(js_d in domain for js_d in JS_REQUIRED_DOMAINS):
            return await asyncio.to_thread(self._fetch_with_selenium, url)
        try:
            resp = await self._httpx_client.get(url)
            text = BeautifulSoup(resp.text, "html.parser").get_text()[:3000]
            tier = SOURCE_TIER_MAP.get(domain, 4)
            return SearchResult(
                source_url=url,
                final_url=str(resp.url),
                content=text,
                tier=tier,
                source_name=domain,
            )
        except Exception:
            return None

    def _fetch_with_selenium(self, url: str) -> SearchResult | None:
        try:
            from selenium import webdriver
            if SearchService._edge_driver is None:
                _args = ["--headless", "--no-sandbox", "--disable-dev-shm-usage"]
                # Edge → Chrome → Firefox 순으로 시도 (OS별 설치 환경 차이 대응)
                driver_instance = None
                try:
                    from selenium.webdriver.edge.options import Options as EdgeOptions
                    opts = EdgeOptions()
                    for a in _args:
                        opts.add_argument(a)
                    driver_instance = webdriver.Edge(options=opts)
                except Exception:
                    pass
                if driver_instance is None:
                    try:
                        from selenium.webdriver.chrome.options import Options as ChromeOptions
                        opts = ChromeOptions()
                        for a in _args:
                            opts.add_argument(a)
                        driver_instance = webdriver.Chrome(options=opts)
                    except Exception:
                        pass
                if driver_instance is None:
                    return None
                SearchService._edge_driver = driver_instance
            driver = SearchService._edge_driver
            driver.get(url)
            time.sleep(random.uniform(1, 3))
            soup = BeautifulSoup(driver.page_source, "html.parser")
            text = soup.get_text()[:3000]
            domain = url.split("/")[2]
            tier = SOURCE_TIER_MAP.get(domain, 4)
            return SearchResult(
                source_url=url,
                final_url=driver.current_url,
                content=text,
                tier=tier,
                source_name=domain,
            )
        except Exception:
            return None

    async def close(self):
        await self._httpx_client.aclose()
        if SearchService._edge_driver:
            SearchService._edge_driver.quit()
            SearchService._edge_driver = None
