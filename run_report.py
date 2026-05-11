"""
목차 기반 보고서 생성기
A→B→C→[USER GATE 1]→D→D'→[USER GATE 2]→E→F 워크플로우
출력: reports/{slug}_report.md + reports/{slug}_report.html
"""
import asyncio
import json
import os
import re
import time
import sys
from datetime import date, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

import markdown as md_lib

from src.services.llm import LLMService
from src.services.search import SearchService
from src.services.body_fetcher import fetch_or_cached, FETCHABLE_SOURCES
from src.prompts.system import ANALYST_SYSTEM_PROMPT
from src.prompts.step_prompts import PRE_SEARCH_PROMPT, TOC_PROMPT, SECTION_REPORT_PROMPT, INSIGHTS_PROMPT
from src.state_machine import _extract_json_block, _extract_json_array

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

MAX_REFINE_ROUNDS = 3  # D↔D' 루프 최대 횟수


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _year() -> int:
    return date.today().year


def _slug(topic: str) -> str:
    slug = re.sub(r"\s+", "_", topic.strip())
    slug = re.sub(r"[^\w가-힣]", "_", slug)
    return slug.strip("_")[:60]


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


async def _ainput(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


def _print_section(n: int, width: int = 60):
    print("\n" + "─" * width)
    print(f"  [{n}단계]")
    print("─" * width)


def _format_archive_context(results) -> str:
    lines = []
    for i, r in enumerate(results[:12], 1):
        title = (r.article_title or "")[:100]
        snippet = (r.content or "")[:200].replace("\n", " ")
        lines.append(f"[{i}] [{r.source_name}] {title}\n    {snippet}")
    return "\n".join(lines) if lines else "(archive 검색 결과 없음)"


def _format_evidence_block(results, bodies: dict | None = None) -> str:
    """SECTION_REPORT_PROMPT용 evidence 포맷. bodies dict {url→body} 있으면 우선."""
    bodies = bodies or {}
    lines = []
    for i, r in enumerate(results[:12], 1):
        title = (r.article_title or r.source_name or "")[:100]
        body = bodies.get(r.source_url, "")
        snippet = (r.content or "")[:1500].replace("\n", " ")
        text = (body[:2000] if body else snippet)
        date_str = f"    Date: {r.pub_date}\n" if r.pub_date else ""
        lines.append(
            f"[{i}] {title}\n"
            f"    URL: {r.source_url}\n"
            f"    Source: {r.source_name}\n"
            f"{date_str}"
            f"    {text}"
        )
    return "\n\n".join(lines) if lines else "(검색 결과 없음)"


# ---------------------------------------------------------------------------
# Stage A — 영문 쿼리 생성 (PRE_SEARCH_PROMPT 재사용)
# ---------------------------------------------------------------------------

_KOREAN_RE = re.compile(r"[가-힣]")


def _preview_text(text: str, limit: int = 700) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    return compact[:limit]


def _extract_search_queries(text: str) -> list[str]:
    queries = _extract_json_array(text) or []
    if queries:
        return queries

    obj = _extract_json_block(text)
    if isinstance(obj, dict):
        for key in ("queries", "search_queries", "english_queries", "pre_queries"):
            value = obj.get(key)
            if isinstance(value, list):
                queries = [q for q in value if isinstance(q, str)]
                if queries:
                    return queries[:8]

    lines = []
    for line in (text or "").splitlines():
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[\).])\s*", "", line).strip().strip('"')
        if len(cleaned.split()) >= 3 and not _KOREAN_RE.search(cleaned):
            lines.append(cleaned)
    return lines[:8]


async def stage_a(llm: LLMService, topic: str, progress_cb=None) -> tuple[list[str], str]:
    async def progress(step: str, text: str, **extra):
        if progress_cb:
            await progress_cb(step=step, text=text, **extra)

    print("[A] 영문 쿼리 생성...")
    t0 = time.time()
    await progress("topic_received", "한국어 분석 주제를 수신했습니다.", topic=topic)
    _analyst_type = os.getenv("GLM_ANALYST_TYPE", "senior smartphone market analyst")
    prompt = PRE_SEARCH_PROMPT.format(topic=topic, current_year=_year(), analyst_type=_analyst_type)
    _stage_a_model = os.getenv("GLM_ANALYSIS_MODEL", "glm-4.7-flashx")
    await progress("llm_request", "GLM에 영어 검색 쿼리 생성을 요청했습니다.", model=_stage_a_model)
    resp = await llm.complete(ANALYST_SYSTEM_PROMPT, prompt, max_tokens=2000, temperature=0.1,
                              model=_stage_a_model)
    raw = _strip_fence((resp.content or resp.reasoning or "").strip())
    await progress(
        "llm_response",
        "GLM 응답을 수신했습니다.",
        elapsed=round(time.time() - t0, 1),
        preview=_preview_text(raw),
    )
    queries = _extract_search_queries(raw)
    raw_count = len(queries or [])
    # 한국어 포함 쿼리 제거 — 영어 archive에서 검색 품질 저하 방지
    queries = [q for q in (queries or []) if not _KOREAN_RE.search(q)]
    await progress(
        "filter_queries",
        f"영어 아카이브 검색에 맞게 한국어 포함 쿼리를 제외했습니다. ({len(queries)}/{raw_count}개 유지)",
        raw_count=raw_count,
        kept_count=len(queries),
    )
    if not queries:
        # 재시도: 단순 번역 프롬프트
        await progress("retry_simple", "유효한 영어 쿼리가 없어 단순 번역 프롬프트로 재시도합니다.")
        simple_prompt = (
            f'Translate this topic into 4 English search queries. '
            f'Return ONLY a JSON array, no explanation: ["query1","query2","query3","query4"]\n'
            f'Topic: "{topic}"\nYear: {_year()}'
        )
        try:
            resp2 = await llm.complete(ANALYST_SYSTEM_PROMPT, simple_prompt, max_tokens=2000, temperature=0.1,
                                       model=_stage_a_model)
            raw2 = _strip_fence((resp2.content or resp2.reasoning or "").strip())
            retry_raw_queries = _extract_search_queries(raw2)
            queries = [q for q in retry_raw_queries if not _KOREAN_RE.search(q)]
            await progress(
                "retry_done",
                f"재시도 결과 영어 쿼리 {len(queries)}개를 확보했습니다.",
                kept_count=len(queries),
                preview=_preview_text(raw2),
            )
        except Exception:
            await progress("retry_failed", "재시도 요청이 실패했습니다. 키워드 폴백을 준비합니다.")
            pass

    if not queries:
        # 최종 폴백: 주제 키워드 기반 동적 쿼리
        await progress("fallback", "LLM 쿼리를 사용할 수 없어 주제 키워드 기반 폴백 쿼리를 생성합니다.")
        _KO_EN = {
            "폴더블": "foldable", "아이폰": "iPhone", "삼성": "Samsung",
            "스마트폰": "smartphone", "출시": "launch", "시장": "market",
            "영향": "impact", "가격": "price", "메모리": "memory",
            "반도체": "semiconductor", "공급": "supply", "수요": "demand",
            "점유율": "market share", "비용": "cost", "전략": "strategy",
            "갤럭시": "Galaxy", "화웨이": "Huawei", "중국": "China",
            "분석": "analysis", "성장": "growth", "위축": "decline",
            "온디바이스": "on-device", "온디바이스 AI": "on-device AI",
            "에이전트": "agent", "AI 에이전트": "AI agent",
            "로드맵": "roadmap", "소비자": "consumer", "수용도": "adoption",
            "실제": "actual", "괴리": "gap", "격차": "gap",
            "사용자": "user", "경험": "experience", "기기": "device",
        }
        eng = topic
        for ko, en in _KO_EN.items():
            eng = eng.replace(ko, en)
        eng = re.sub(r"[가-힣]+", "", eng).strip()
        eng_kw = " ".join(eng.split()[:5]) or "smartphone market"
        queries = [
            f"{eng_kw} {_year()}",
            f"{eng_kw} market impact {_year()}",
            f"{eng_kw} OEM strategy {_year()}",
        ]
        print(f"   [!] LLM이 영어 쿼리를 생성하지 못해 키워드 폴백 사용")
    eng_topic = " ".join(queries[0].split()[:6])
    await progress(
        "final_queries",
        f"최종 영어 검색 쿼리 {len(queries)}개를 확정했습니다.",
        queries=queries,
        eng_topic=eng_topic,
        elapsed=round(time.time() - t0, 1),
    )
    print(f"   → 쿼리 {len(queries)}개 생성 ({round(time.time()-t0,1)}s): {queries[0][:60]}...")
    return queries, eng_topic


# ---------------------------------------------------------------------------
# Stage B — Archive-first 검색 (소스 다양화)
# ---------------------------------------------------------------------------

_PRIORITY_SOURCES = ["TrendForce", "IDC", "Omdia", "Yole Group"]

# 부재 소스별 보완 쿼리 패턴 (eng_kw = 영문 핵심 키워드)
def _supplement_query(src: str, eng_kw: str, year: int) -> str:
    patterns = {
        "TrendForce": f"{eng_kw} DRAM NAND price supply chain {year}",
        "IDC":        f"{eng_kw} smartphone shipments market share quarterly {year}",
        "Omdia":      f"{eng_kw} semiconductor component forecast {year}",
        "Yole Group": f"{eng_kw} component technology manufacturing market {year}",
    }
    return patterns.get(src, f"{eng_kw} {src} {year}")


async def stage_b(search: SearchService, queries: list[str], eng_kw: str = "") -> list:
    from collections import Counter
    print("[B] Archive 사전 검색 (소스 다양화)...")
    t0 = time.time()
    seen_urls: set[str] = set()
    all_results = []

    for q in queries:
        sr = await search.search_archive_only(q, q.split())
        for r in sr.results:
            if r.source_url not in seen_urls:
                seen_urls.add(r.source_url)
                all_results.append(r)

    # 우선순위 소스 중 누락된 것에 보완 쿼리 실행
    represented = {r.source_name for r in all_results}
    missing = [s for s in _PRIORITY_SOURCES if s not in represented]
    kw = eng_kw or "smartphone memory"
    for src in missing:
        supp_q = _supplement_query(src, kw, _year())
        sr = await search.search_archive_only(supp_q, supp_q.split())
        added = 0
        for r in sr.results:
            if r.source_url not in seen_urls and r.source_name == src:
                seen_urls.add(r.source_url)
                all_results.append(r)
                added += 1
        if added:
            print(f"   >> {src}: +{added}건 보완")

    all_results = all_results[:25]
    dist = Counter(r.source_name for r in all_results)
    dist_str = ", ".join(f"{s}:{n}" for s, n in dist.most_common())
    print(f"   → archive {len(all_results)}건 [{dist_str}] ({round(time.time()-t0,1)}s)")
    return all_results


# ---------------------------------------------------------------------------
# Stage C — 목차 생성 (LLM)
# ---------------------------------------------------------------------------

STAGE_C_MIN_SECTIONS = 3            # TOC_PROMPT가 3-section 강제하므로 최소 3개
STAGE_C_MAX_RETRY = 3               # LLM 응답이 비정상이면 재시도


async def stage_c(llm: LLMService, topic: str, archive_results: list) -> list[dict]:
    """반환: [{"title": str, "queries": [str, ...], "included": [bool, ...]}, ...]

    가드레일: sections >= 3 AND 각 section의 queries non-empty 검증.
    실패 시 최대 3회 retry. retry 모두 실패면 RuntimeError로 abort
    (이전엔 smartphone hardcoded 폴백이 있었지만 도메인-agnostic하지 않아 제거).
    """
    print("[C] 목차 + 검색어 생성...")
    t0 = time.time()
    archive_ctx = _format_archive_context(archive_results)
    analyst_type = os.getenv("GLM_ANALYST_TYPE", "senior smartphone market analyst")
    prompt = TOC_PROMPT.format(
        topic=topic, current_year=_year(), archive_context=archive_ctx, analyst_type=analyst_type,
    )

    sections: list[dict] = []
    last_diagnostic = ""
    for attempt in range(1, STAGE_C_MAX_RETRY + 1):
        try:
            resp = await llm.complete(
                ANALYST_SYSTEM_PROMPT, prompt,
                max_tokens=3000,
                temperature=0.2 + (attempt - 1) * 0.1,  # 재시도마다 약간씩 다양성 ↑
                model=os.getenv("GLM_TOC_MODEL", "glm-5.1"),
            )
        except Exception as e:
            last_diagnostic = f"LLM 오류: {e}"
            print(f"   ⚠ Stage C attempt {attempt}/{STAGE_C_MAX_RETRY} — {last_diagnostic}")
            continue

        raw = _strip_fence(resp.content.strip())
        data = _extract_json_block(raw)
        sections = []
        if data and isinstance(data.get("sections"), list):
            for s in data["sections"][:5]:
                queries = [q for q in (s.get("queries") or []) if q and not _KOREAN_RE.search(q)][:5]
                if not queries:
                    continue
                sections.append({
                    "title": (s.get("title") or "")[:60],
                    "causal_role": s.get("causal_role", "analysis"),
                    "angle": s.get("angle", ""),
                    "queries": queries,
                    "included": [True] * len(queries),
                })

        # 가드레일 — 3개 미만 또는 빈 queries 섹션 있으면 retry
        if len(sections) >= STAGE_C_MIN_SECTIONS and all(s.get("queries") for s in sections):
            print(f"   → 목차 {len(sections)}개 ({round(time.time()-t0,1)}s, attempt {attempt})")
            return sections

        last_diagnostic = (
            f"sections={len(sections)} (요구: >={STAGE_C_MIN_SECTIONS}), "
            f"empty_queries={sum(1 for s in sections if not s.get('queries'))}"
        )
        print(f"   ⚠ Stage C attempt {attempt}/{STAGE_C_MAX_RETRY} — {last_diagnostic}, retry...")

    # 모든 retry 실패 → abort
    raise RuntimeError(
        f"[Stage C 가드레일] {STAGE_C_MAX_RETRY}회 재시도 후에도 유효한 {STAGE_C_MIN_SECTIONS}+ 목차 생성 실패. "
        f"마지막 진단: {last_diagnostic}. "
        f"원인 가능성: (1) 토픽이 너무 narrow하여 3-section 분기가 불가능, "
        f"(2) archive 결과가 한 출처에 몰려 다양성 부족, "
        f"(3) LLM 응답 품질 문제. 토픽을 더 구체화 또는 archive 보강 필요."
    )


# ---------------------------------------------------------------------------
# USER GATE 1 — 검색어 add/remove
# ---------------------------------------------------------------------------

def _display_sections(sections: list[dict]):
    print()
    for si, sec in enumerate(sections, 1):
        print(f"  [목차 {si}] {sec['title']}")
        for qi, (q, inc) in enumerate(zip(sec["queries"], sec["included"]), 1):
            mark = "[O]" if inc else "[X]"
            print(f"    [{si}.{qi}] {mark} {q}")
    print()


def _warn_section_overlap(sections: list[dict]) -> None:
    """두 목차 제목 간 키워드 중복이 높으면 경고."""
    titles = [s["title"] for s in sections]
    stopwords = {"및", "의", "에", "에서", "와", "과", "이", "가", "을", "를", "로", "으로", "한", "하는", "관련", "현황"}
    tokenized = [set(t for t in re.split(r"\s+", title) if t not in stopwords) for title in titles]
    for i in range(len(tokenized)):
        for j in range(i + 1, len(tokenized)):
            a, b = tokenized[i], tokenized[j]
            if not a or not b:
                continue
            overlap = len(a & b) / min(len(a), len(b))
            if overlap >= 0.5:
                print(f"  [!] 목차 중복 경고: [{i+1}] '{titles[i]}' vs [{j+1}] '{titles[j]}' (겹침 {int(overlap*100)}%)")


async def user_gate_1(sections: list[dict], auto: bool = False, gate_cb=None) -> list[dict]:
    print("\n" + "=" * 60)
    print("  [USER GATE 1] 목차 + 검색어 확인")
    print("=" * 60)
    _display_sections(sections)
    if auto:
        total = sum(s["included"].count(True) for s in sections)
        print(f"  [AUTO] 목차 {len(sections)}개, 검색어 {total}개 자동 확정")
        return sections
    if gate_cb is not None:
        return await gate_cb(sections)
    print("  명령어:")
    print("    +{섹션번호} {새 검색어}    : 검색어 추가  (예: +1 EU penalty enforcement 2026)")
    print("    -{섹션번호}.{쿼리번호}     : 검색어 제외  (예: -1.2)")
    print("    Enter (빈 줄)             : 확정")
    print()

    while True:
        try:
            line = (await _ainput("  > ")).strip()
        except EOFError:
            break
        if not line:
            break

        # +N query text
        m_add = re.match(r"^\+(\d+)\s+(.+)$", line)
        if m_add:
            si = int(m_add.group(1)) - 1
            q_text = m_add.group(2).strip()
            if 0 <= si < len(sections):
                sections[si]["queries"].append(q_text)
                sections[si]["included"].append(True)
                print(f"    → [{si+1}.{len(sections[si]['queries'])}] 추가: {q_text}")
                _display_sections(sections)
            else:
                print(f"    ! 섹션 번호 {si+1} 없음")
            continue

        # -N.M
        m_del = re.match(r"^-(\d+)\.(\d+)$", line)
        if m_del:
            si = int(m_del.group(1)) - 1
            qi = int(m_del.group(2)) - 1
            if 0 <= si < len(sections) and 0 <= qi < len(sections[si]["included"]):
                sections[si]["included"][qi] = not sections[si]["included"][qi]
                status = "제외" if not sections[si]["included"][qi] else "포함"
                print(f"    → [{si+1}.{qi+1}] {status} 토글")
                _display_sections(sections)
            else:
                print(f"    ! [{si+1}.{qi+1}] 없음")
            continue

        print("    ! 인식 불가 명령. '+N 쿼리' 또는 '-N.M' 형식 사용")

    # 확정된 쿼리 출력
    total = sum(s["included"].count(True) for s in sections)
    print(f"\n  확정: 목차 {len(sections)}개, 검색어 {total}개")
    return sections


# ---------------------------------------------------------------------------
# Stage D — 검색 실행
# ---------------------------------------------------------------------------

STAGE_D_FALLBACK_THRESHOLD = 5  # 섹션당 archive 결과가 이보다 적으면 외부 검색 자동 보강


async def stage_d(search: SearchService, sections: list[dict], use_external: bool, progress=None) -> list[dict]:
    """각 섹션별 검색 실행. sections에 'results' 키 추가.

    use_external=True → 처음부터 archive + 외부(RSS/DDG) 통합 검색.
    use_external=False → archive only로 검색 후, 섹션 결과가 STAGE_D_FALLBACK_THRESHOLD 미만인
    섹션만 자동으로 외부 검색을 추가 호출 (안전망). 휴머노이드처럼 archive depth가 토픽별 편차가
    큰 도메인에서 quality 보장.
    """
    if use_external:
        mode_label = "archive + 외부"
    else:
        mode_label = f"archive only (희소 시 자동 fallback @ <{STAGE_D_FALLBACK_THRESHOLD}건)"
    print(f"\n[D] 검색 실행 ({mode_label})...")
    t0 = time.time()
    fallback_count = 0

    for i, sec in enumerate(sections):
        if progress:
            await progress(i, len(sections), sec["title"])
        seen: set[str] = set()
        sec_results = []
        for q, inc in zip(sec["queries"], sec["included"]):
            if not inc:
                continue
            if use_external:
                sr = await search.search(q, q.split())
            else:
                sr = await search.search_archive_only(q, q.split())
            for r in sr.results:
                if r.source_url not in seen:
                    seen.add(r.source_url)
                    sec_results.append(r)

        # 자동 fallback — archive only 모드에서 섹션 결과 희소 시 외부 검색 보강
        if not use_external and len(sec_results) < STAGE_D_FALLBACK_THRESHOLD:
            print(f"   ⚠ 섹션 {i+1} archive {len(sec_results)}건 — 외부 fallback 실행")
            for q, inc in zip(sec["queries"], sec["included"]):
                if not inc:
                    continue
                sr = await search.search(q, q.split())
                for r in sr.results:
                    if r.source_url not in seen:
                        seen.add(r.source_url)
                        sec_results.append(r)
            fallback_count += 1

        sec["results"] = sec_results[:20]

    total = sum(len(s.get("results", [])) for s in sections)
    fb_msg = f", auto-fallback {fallback_count}회" if fallback_count else ""
    print(f"   → 전체 {total}건 ({round(time.time()-t0,1)}s){fb_msg}")
    return sections


# ---------------------------------------------------------------------------
# Stage D' — 검색 결과 review
# ---------------------------------------------------------------------------

def _display_results(sections: list[dict]):
    print()
    n = 1
    for si, sec in enumerate(sections, 1):
        results = sec.get("results", [])
        print(f"  >> [목차 {si}] {sec['title']} ({len(results)}건)")
        for r in results:
            title = (r.article_title or r.source_name or "")[:70]
            snippet = (r.content or "")[:120].replace("\n", " ")
            print(f"    [{n}] [{r.source_name}] {title}")
            print(f"         {snippet}")
            n += 1
    print()


async def user_gate_2(sections: list[dict], auto: bool = False, gate_cb=None) -> tuple[bool, list[dict]]:
    """반환: (proceed, sections). proceed=False → 사용자가 추가 검색어 입력."""
    print("\n" + "=" * 60)
    print("  [USER GATE 2] 검색 결과 review")
    print("=" * 60)
    _display_results(sections)
    if auto:
        total = sum(len(s.get("results", [])) for s in sections)
        print(f"  [AUTO] {total}건 결과 자동 확정, 분석 진행")
        return True, sections
    if gate_cb is not None:
        return await gate_cb(sections)
    print("  분석 진행: Enter (빈 줄)")
    print("  추가 검색어: '+{섹션번호} {검색어}' 입력 후 Enter")
    print()

    while True:
        try:
            line = (await _ainput("  > ")).strip()
        except EOFError:
            return True, sections
        if not line:
            return True, sections

        m_add = re.match(r"^\+(\d+)\s+(.+)$", line)
        if m_add:
            si = int(m_add.group(1)) - 1
            q_text = m_add.group(2).strip()
            if 0 <= si < len(sections):
                sections[si]["queries"].append(q_text)
                sections[si]["included"].append(True)
                print(f"    → [{si+1}.{len(sections[si]['queries'])}] 추가: {q_text}")
            else:
                print(f"    ! 섹션 {si+1} 없음")
            return False, sections  # D 단계로 복귀

        print("    ! '+N 검색어' 형식으로 추가하거나 Enter로 분석 진행")


# ---------------------------------------------------------------------------
# Stage E+F — 목차별 분석 + 보고서 작성
# ---------------------------------------------------------------------------

async def _fetch_bodies(sections: list[dict]) -> dict:
    """FETCHABLE_SOURCES 본문을 비동기 fetch. 반환: {url: body_text}."""
    tasks = []
    urls_sources = []
    seen: set[str] = set()
    for sec in sections:
        for r in sec.get("results", []):
            if r.source_name in FETCHABLE_SOURCES and r.source_url not in seen:
                tasks.append(asyncio.to_thread(fetch_or_cached, r.source_url, r.source_name))
                urls_sources.append(r.source_url)
                seen.add(r.source_url)

    if not tasks:
        return {}
    print(f"   본문 fetch: {len(tasks)}건...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    bodies: dict = {}
    for url, body in zip(urls_sources, results):
        if isinstance(body, str) and body:
            bodies[url] = body
    return bodies


async def stage_ef(llm: LLMService, topic: str, sections: list[dict], progress_cb=None) -> list[dict]:
    """각 섹션 분석. sections에 'report' 키 추가."""
    print("\n[E/F] 목차별 분석 및 보고서 작성...")
    bodies = await _fetch_bodies(sections)

    all_titles = [s["title"] for s in sections]
    cited_bullets: list[str] = []  # 이전 섹션에서 인용된 bullet 누적
    analyst_type = os.getenv("GLM_ANALYST_TYPE", "senior smartphone market analyst")

    for si, sec in enumerate(sections, 1):
        print(f"   [{si}/{len(sections)}] {sec['title']}...")
        if progress_cb:
            await progress_cb(si, len(sections), sec["title"])
        t0 = time.time()
        evidence = _format_evidence_block(sec.get("results", []), bodies)
        other_sections = ", ".join(t for t in all_titles if t != sec["title"]) or "없음"
        already_cited = "\n".join(f"- {b}" for b in cited_bullets) if cited_bullets else "없음 (첫 번째 섹션)"
        prompt = SECTION_REPORT_PROMPT.format(
            topic=topic,
            section_title=sec["title"],
            angle=sec.get("angle", ""),
            current_date=date.today().isoformat(),
            causal_role=sec.get("causal_role", "analysis"),
            other_sections=other_sections,
            already_cited=already_cited,
            evidence_block=evidence,
            analyst_type=analyst_type,
        )
        resp = await llm.complete(
            ANALYST_SYSTEM_PROMPT, prompt,
            max_tokens=6000, temperature=0.3,
            response_format={"type": "json_object"},
            thinking="disabled",
        )
        raw = _strip_fence(resp.content.strip())
        data = _extract_json_block(raw)

        # 가드레일 #3 — SECTION_REPORT_PROMPT의 insufficient_evidence fail-safe 처리.
        # LLM이 evidence 부족을 인식하고 자기 차단 응답을 보낸 경우, 그 섹션을 omit하고 다음 섹션으로.
        # fabricate된 출처(예: 가짜 Reuters 인용) 차단의 마지막 안전망.
        if data and data.get("insufficient_evidence"):
            reason = (data.get("reason") or "")[:200]
            print(f"      ⚠ 섹션 omit (insufficient_evidence): {reason}")
            sec["report"] = {"insufficient_evidence": True, "reason": reason}
            continue

        # 폴백: 최소 구조
        if not data:
            data = {
                "headline": f"{sec['title']} — 데이터 부족으로 분석 제한",
                "narrative": "(검색 결과가 부족하여 서술형 분석을 생성하지 못했습니다.)",
                "bullets": ["• 데이터 부족 [N/A, -]"],
                "footnotes": [],
            }

        # headline 길이 체크 (>80자 경고)
        hl = data.get("headline", "")
        if len(hl) > 80:
            data["headline"] = hl[:77] + "..."

        # 정량 fact 80% 검증
        bullets = data.get("bullets", [])
        if bullets:
            numeric = sum(1 for b in bullets if re.search(r"\d", b))
            ratio = numeric / len(bullets)
            if ratio < 0.8:
                print(f"      [!] 정량 fact {numeric}/{len(bullets)} ({int(ratio*100)}%) — 목표 80% 미달")
            cited_bullets.extend(bullets)  # 다음 섹션에 전달

        sec["report"] = data
        print(f"      → 완료 ({round(time.time()-t0,1)}s)")

    # 가드레일 — valid 섹션 비율 체크 (insufficient_evidence omit이 너무 많으면 abort)
    valid_sections = [s for s in sections if s.get("report") and not (s["report"] or {}).get("insufficient_evidence")]
    omitted_sections = [s for s in sections if (s.get("report") or {}).get("insufficient_evidence")]
    min_valid = max(2, (len(sections) + 1) // 2)  # 최소 2개 또는 절반 이상
    if len(valid_sections) < min_valid:
        omit_reasons = "; ".join((s["report"].get("reason") or "")[:80] for s in omitted_sections)
        raise RuntimeError(
            f"[Stage E/F 가드레일] {len(omitted_sections)}/{len(sections)} 섹션이 evidence 부족으로 omit됨. "
            f"valid {len(valid_sections)}/{len(sections)}, 최소 {min_valid} 필요. "
            f"omit 이유: {omit_reasons}. 보고서 생성 중단."
        )
    if omitted_sections:
        print(f"\n  [!] {len(omitted_sections)}/{len(sections)} 섹션 omit (insufficient_evidence) — 나머지로 보고서 생성")

    return sections


# ---------------------------------------------------------------------------
# Stage G — Executive Summary + Insights 생성
# ---------------------------------------------------------------------------

def _format_report_summary(sections: list[dict]) -> str:
    lines = []
    for i, sec in enumerate(sections, 1):
        rep = sec.get("report", {})
        lines.append(f"[섹션 {i}] {sec['title']} (causal_role: {sec.get('causal_role','analysis')})")
        lines.append(f"핵심 결론: {rep.get('headline', '')}")
        narrative = (rep.get("narrative", "") or "")[:400]
        lines.append(f"분석: {narrative}")
        for b in (rep.get("bullets", []) or [])[:4]:
            lines.append(f"  {b}")
        lines.append("")
    return "\n".join(lines)


async def stage_g(llm: LLMService, topic: str, sections: list[dict]) -> dict:
    """Executive Summary + 시사점(Insights) 생성.

    품질이 가장 중요한 단계라 GLM-5.1 사용 (4.7 대비 hallucination -56%, AA-Omniscience +35pt).
    A/B 테스트 결과: Investor Takeaway 라벨링·구체적 회사명·actionable 권고 우위.
    추가 비용: 보고서당 +¥0.04~0.08 (~₩10).
    """
    print("\n[G] Executive Summary + 시사점 + 한국 시장 영향 생성 (GLM-5.1)...")
    t0 = time.time()
    summary = _format_report_summary(sections)
    analyst_type = os.getenv("GLM_ANALYST_TYPE", "senior smartphone market analyst")
    prompt = INSIGHTS_PROMPT.format(
        topic=topic,
        report_summary=summary,
        current_date=date.today().isoformat(),
        analyst_type=analyst_type,
    )
    resp = await llm.complete(
        ANALYST_SYSTEM_PROMPT, prompt,
        model=os.getenv("GLM_FINAL_MODEL", "glm-5.1"),
        max_tokens=6000, temperature=0.3,
        response_format={"type": "json_object"},
        thinking="disabled",
    )
    raw = _strip_fence(resp.content.strip())
    data = _extract_json_block(raw) or {}
    insights = data.get("insights", [])
    exec_summary = data.get("executive_summary", "")
    research_background = data.get("research_background", "")
    quick_brief = data.get("quick_brief") or {}
    if not isinstance(quick_brief, dict):
        quick_brief = {}
    korea_impact = data.get("korea_impact") or {}
    if not isinstance(korea_impact, dict):
        korea_impact = {}
    print(f"   → 시사점 {len(insights)}개, quick_brief {'✓' if quick_brief.get('headline') else '×'}, korea_impact {'✓' if korea_impact.get('body') else '×'} ({round(time.time()-t0,1)}s)")
    return {
        "research_background": research_background,
        "executive_summary": exec_summary,
        "insights": insights,
        "quick_brief": quick_brief,
        "korea_impact": korea_impact,
    }


# ---------------------------------------------------------------------------
# 보고서 조립 — Markdown
# ---------------------------------------------------------------------------

def _build_markdown(topic: str, sections: list[dict], run_ts: str, meta: dict | None = None) -> str:
    meta = meta or {}
    lines = [
        f"# {topic}",
        f"",
        f"생성일시: {run_ts}",
        f"",
    ]

    # Executive Summary
    exec_summary = meta.get("executive_summary", "")
    if exec_summary:
        lines.append("## Executive Summary")
        lines.append(f"")
        lines.append(exec_summary)
        lines.append(f"")
        lines.append("---")
        lines.append(f"")

    # 가드레일 #3로 omit된 섹션은 markdown에서 제외
    valid_sections = [s for s in sections if not (s.get("report") or {}).get("insufficient_evidence")]
    for si, sec in enumerate(valid_sections, 1):
        rep = sec.get("report", {})
        headline = rep.get("headline", sec["title"])
        narrative = rep.get("narrative", "")
        bullets = rep.get("bullets", [])
        footnotes = rep.get("footnotes", [])

        lines.append(f"## {si}. {sec['title']}")
        lines.append(f"")
        lines.append(f"**{headline}**")
        lines.append(f"")

        for para in (narrative or "").split("\n\n"):
            para = para.strip()
            if para:
                lines.append(para)
                lines.append(f"")

        if bullets:
            for b in bullets:
                lines.append(b if b.startswith("•") else f"• {b}")
            lines.append(f"")

        if footnotes:
            lines.append("**출처**")
            lines.append(f"")
            for fn in footnotes:
                num = fn.get("num", "")
                url = fn.get("url", "")
                src = fn.get("source", url)
                title = fn.get("title", "")
                date_str = fn.get("date", "")
                if title and date_str:
                    lines.append(f"[{num}] [{src} — \"{title}\"]({url}) ({date_str})")
                elif title:
                    lines.append(f"[{num}] [{src} — \"{title}\"]({url})")
                else:
                    lines.append(f"[{num}] [{src}]({url})")
            lines.append(f"")

        lines.append(f"")

    # Insights
    insights = meta.get("insights", [])
    if insights:
        lines.append("---")
        lines.append(f"")
        lines.append("## 시사점 (Market Insights)")
        lines.append(f"")
        for i, ins in enumerate(insights, 1):
            lines.append(f"### {i}. {ins.get('title', '')}")
            lines.append(f"")
            lines.append(ins.get("body", ""))
            lines.append(f"")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 보고서 조립 — HTML (Markdown → HTML 변환)
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family: 'Apple SD Gothic Neo', -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', sans-serif; max-width: 960px; margin: 40px auto; padding: 0 24px; background: #f7f6f3; color: #2a2826; line-height: 1.75; }}
  h1 {{ font-size: 1.6rem; border-bottom: 2px solid #10b981; padding-bottom: 8px; margin-bottom: 4px; letter-spacing: -0.01em; }}
  h2 {{ font-size: 1.2rem; margin-top: 2.5rem; color: #047857; border-left: 4px solid #10b981; padding-left: 10px; }}
  p {{ margin: 0.6em 0; }}
  strong {{ color: #1f2933; }}
  ul, ol {{ padding-left: 1.4em; }}
  li {{ margin: 0.3em 0; }}
  a {{ color: #059669; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .meta {{ color: #6b7280; font-size: 0.85rem; margin-bottom: 2rem; }}
  h3 {{ font-size: 1rem; margin-top: 1.2rem; color: #047857; }}
  hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 2rem 0; }}

  /* ── 수행 과정 섹션 ── */
  .process-wrap {{ background: #f0f4ff; border-radius: 12px; padding: 24px 28px; margin-bottom: 2.5rem; }}
  .process-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 18px; }}
  .process-header h2 {{ margin: 0; border: none; padding: 0; font-size: 1rem; color: #4b5563; text-transform: uppercase; letter-spacing: 0.06em; }}
  .process-grid {{ display: grid; grid-template-columns: 1fr 1.4fr; gap: 16px; margin-bottom: 16px; }}
  .step-box {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 16px; }}
  .step-label {{ font-size: 0.78rem; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px; }}
  .source-row {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .src-badge {{ display: inline-flex; align-items: center; gap: 4px; background: #dbeafe; color: #1e40af; border-radius: 20px; padding: 3px 10px; font-size: 0.78rem; }}
  .src-badge b {{ color: #1d4ed8; }}
  .chain-wrap {{ display: flex; flex-direction: column; gap: 0; }}
  .chain-card {{ background: #fff; border-radius: 8px; padding: 12px 16px; border-left: 4px solid #ccc; position: relative; }}
  .chain-card + .chain-card {{ margin-top: 8px; }}
  .chain-arrow {{ text-align: center; font-size: 1.1rem; color: #9ca3af; line-height: 1; margin: 2px 0; }}
  .chain-role {{ font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em; margin-bottom: 3px; }}
  .chain-title {{ font-weight: 700; font-size: 0.92rem; }}
  .chain-meta {{ font-size: 0.72rem; color: #9ca3af; margin-top: 2px; }}
  .chain-qs {{ margin: 6px 0 0 0; padding-left: 14px; }}
  .chain-qs li {{ font-size: 0.72rem; color: #4b5563; font-family: monospace; margin: 1px 0; }}
  .results-wrap details {{ margin-bottom: 6px; }}
  .results-wrap summary {{ cursor: pointer; font-size: 0.82rem; padding: 6px 10px; background: #f9fafb; border-radius: 6px; color: #374151; list-style: none; }}
  .results-wrap summary::-webkit-details-marker {{ display: none; }}
  .results-list {{ margin: 4px 0 0 0; padding-left: 16px; }}
  .results-list li {{ font-size: 0.78rem; color: #374151; margin: 2px 0; }}
  .src-tag {{ color: #2563eb; font-weight: 600; margin-right: 4px; }}
  .query-list {{ margin: 4px 0 0 0; padding-left: 16px; }}
  .query-list li {{ font-size: 0.78rem; color: #374151; font-family: monospace; margin: 2px 0; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _build_process_html(
    sections: list[dict],
    archive_results: list | None = None,
    pre_queries: list[str] | None = None,
) -> str:
    """파이프라인 수행 과정 HTML 블록."""
    from collections import Counter

    # [A] 쿼리
    if pre_queries:
        q_items = "".join(f"<li>{q}</li>" for q in pre_queries)
        queries_html = f'<ul class="query-list">{q_items}</ul>'
    else:
        queries_html = "<p style='color:#9ca3af;font-size:0.8rem'>정보 없음</p>"

    # [B] 소스 분포
    if archive_results:
        dist = Counter(r.source_name for r in archive_results)
        badges = "".join(
            f'<span class="src-badge">{s} <b>{n}</b></span>'
            for s, n in dist.most_common()
        )
        sources_html = f'<div class="source-row">{badges}</div>'
    else:
        sources_html = "<p style='color:#9ca3af;font-size:0.8rem'>정보 없음</p>"

    # [C] 목차 인과 사슬
    role_cfg = {
        "structural_cause": ("[1] 구조적 원인", "#ef4444"),
        "direct_impact":    ("[2] 직접 영향",   "#f97316"),
        "market_outcome":   ("[3] 시장 결과",   "#10b981"),
        "analysis":         ("[?] 분석",        "#6b7280"),
    }
    chain_cards = []
    for i, sec in enumerate(sections):
        role = sec.get("causal_role", "analysis")
        label, color = role_cfg.get(role, ("[?]", "#6b7280"))
        qs = [q for q, inc in zip(sec["queries"], sec["included"]) if inc]
        qs_html = "".join(f"<li>{q}</li>" for q in qs)
        src_count = len(sec.get("results", []))
        if i > 0:
            chain_cards.append('<div class="chain-arrow">&#8595;</div>')
        chain_cards.append(
            f'<div class="chain-card" style="border-left-color:{color}">'
            f'<div class="chain-role" style="color:{color}">{label}</div>'
            f'<div class="chain-title">{sec["title"]}</div>'
            f'<div class="chain-meta">검색 결과 {src_count}건</div>'
            f'<ul class="chain-qs">{qs_html}</ul>'
            f'</div>'
        )
    chain_html = "\n".join(chain_cards)

    # [D] 섹션별 검색 결과
    results_details = []
    for i, sec in enumerate(sections, 1):
        results = sec.get("results", [])
        items = "".join(
            f'<li><span class="src-tag">[{r.source_name}]</span>'
            f'{(r.article_title or r.source_url)[:80]}</li>'
            for r in results[:10]
        )
        results_details.append(
            f'<details><summary>목차 {i}: {sec["title"]} ({len(results)}건)</summary>'
            f'<ul class="results-list">{items}</ul></details>'
        )
    results_html = "\n".join(results_details)

    return (
        '<div class="process-wrap">'
        '<div class="process-header"><h2>&#128203; 생성 과정 (파이프라인)</h2></div>'
        '<div class="process-grid">'
        '<div>'
        f'<div class="step-box" style="margin-bottom:12px"><div class="step-label">[A] 영문 검색 쿼리</div>{queries_html}</div>'
        f'<div class="step-box"><div class="step-label">[B] Archive 소스 분포</div>{sources_html}</div>'
        '</div>'
        f'<div class="step-box"><div class="step-label">[C] 목차 — 인과 사슬</div><div class="chain-wrap">{chain_html}</div></div>'
        '</div>'
        f'<div class="step-box results-wrap" style="margin-top:12px"><div class="step-label">[D] 섹션별 검색 결과</div>{results_html}</div>'
        '</div><hr>'
    )


def _build_html(
    topic: str,
    sections: list[dict],
    run_ts: str,
    archive_results: list | None = None,
    pre_queries: list[str] | None = None,
    meta: dict | None = None,
) -> str:
    md_text = _build_markdown(topic, sections, run_ts, meta)
    report_html = md_lib.markdown(md_text, extensions=["tables", "nl2br"])
    return HTML_TEMPLATE.format(title=topic, body=report_html)


# ---------------------------------------------------------------------------
# 저장
# ---------------------------------------------------------------------------

def _save_report(
    topic: str,
    sections: list[dict],
    run_ts: str,
    archive_results: list | None = None,
    pre_queries: list[str] | None = None,
    meta: dict | None = None,
):
    slug = _slug(topic)
    md_text = _build_markdown(topic, sections, run_ts, meta)
    html_text = _build_html(topic, sections, run_ts, archive_results, pre_queries, meta)

    md_path = REPORTS_DIR / f"{slug}_report.md"
    html_path = REPORTS_DIR / f"{slug}_report.html"

    # 프로세스 데이터 저장 (HTML 재생성용)
    process_data = {
        "topic": topic,
        "domain": domain,
        "run_ts": run_ts,
        "pre_queries": pre_queries or [],
        "meta": meta or {},
        "archive_sources": (
            [{"source_name": r.source_name, "url": r.source_url, "title": r.article_title}
             for r in (archive_results or [])]
        ),
        "sections": [
            {
                "title": s["title"],
                "causal_role": s.get("causal_role", "analysis"),
                "angle": s.get("angle", ""),
                "queries": s["queries"],
                "included": s["included"],
                "results": [
                    {"source_name": r.source_name, "url": r.source_url, "title": r.article_title}
                    for r in s.get("results", [])
                ],
            }
            for s in sections
        ],
    }
    process_path = REPORTS_DIR / f"{slug}_process.json"
    process_path.write_text(json.dumps(process_data, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")

    print(f"\n  [OK] Markdown: {md_path}")
    print(f"  [OK] HTML:     {html_path}")
    print(f"  [OK] Process:  {process_path}")
    return md_path, html_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(topic: str, auto: bool = False, gate1_cb=None, gate2_cb=None, domain: str = "smartphone"):
    llm = LLMService()
    search = SearchService()
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 60)
    print("  목차 기반 보고서 생성")
    print(f"  주제: {topic}")
    print(f"  시각: {run_ts}")
    print("=" * 60)

    # A: 영문 쿼리 생성
    pre_queries, eng_topic = await stage_a(llm, topic)
    search.set_core_terms(eng_topic, current_year=str(_year()))

    # B: Archive 사전 검색
    archive_results = await stage_b(search, pre_queries, eng_kw=eng_topic)

    # B 결과 부족 시 외부 검색 제안
    # 환경변수 STAGE_D_EXTERNAL_DEFAULT=true 면 default ON (휴머노이드처럼 archive depth 얕은 도메인용)
    external_default = os.getenv("STAGE_D_EXTERNAL_DEFAULT", "").strip().lower() in {"1", "true", "yes", "on"}
    use_external = external_default
    if len(archive_results) < 3:
        print(f"\n  [!] Archive 결과 {len(archive_results)}건 — 외부 검색(RSS/DDG)으로 보완할까요?")
        if auto:
            if external_default:
                print("  [AUTO] STAGE_D_EXTERNAL_DEFAULT=true → 외부 검색 활성화")
                ans = "y"
            else:
                print("  [AUTO] 외부 검색 건너뜀")
                ans = "n"
        else:
            default_label = "Y/n" if external_default else "y/N"
            ans = (await _ainput(f"  외부 검색 허용? [{default_label}] > ")).strip().lower()
            if not ans:
                ans = "y" if external_default else "n"
        use_external = ans == "y"
        if use_external:
            seen = {r.source_url for r in archive_results}
            for pq in pre_queries:
                sr = await search.search(pq, pq.split())
                for r in sr.results:
                    if r.source_url not in seen:
                        archive_results.append(r)
                        seen.add(r.source_url)
            print(f"   → 보완 후 {len(archive_results)}건")

    # C: LLM 목차 생성
    sections = await stage_c(llm, topic, archive_results)

    # 목차 중복 경고
    _warn_section_overlap(sections)

    # USER GATE 1: 검색어 add/remove
    sections = await user_gate_1(sections, auto=auto, gate_cb=gate1_cb)

    # D↔D' 루프 (최대 MAX_REFINE_ROUNDS)
    refine_round = 0
    while refine_round < MAX_REFINE_ROUNDS:
        sections = await stage_d(search, sections, use_external=use_external)

        # D' + USER GATE 2
        if refine_round == MAX_REFINE_ROUNDS - 1:
            # 마지막 round — 강제 진행
            _display_results(sections)
            print(f"\n  [!] 최대 보완 {MAX_REFINE_ROUNDS}회 도달 — 분석을 진행합니다.")
            break

        if refine_round == MAX_REFINE_ROUNDS - 2:
            print(f"\n  [!] 이미 {refine_round+1}회 보완했습니다. 이번이 마지막 보완 기회입니다.")

        proceed, sections = await user_gate_2(sections, auto=auto, gate_cb=gate2_cb)
        if proceed:
            break
        refine_round += 1

    # 가드레일 — Stage D evidence threshold
    # 전체 결과 너무 적거나 섹션당 평균 너무 낮으면 보고서 생성 abort.
    # evidence 0건/극히 부족 상태에서 Stage E/F가 LLM 자체 지식으로 fabricate하는 path 차단.
    STAGE_D_MIN_TOTAL = 10
    STAGE_D_MIN_AVG_PER_SECTION = 3
    total_evidence = sum(len(s.get("results", [])) for s in sections)
    avg_per_section = total_evidence / len(sections) if sections else 0
    if total_evidence < STAGE_D_MIN_TOTAL or avg_per_section < STAGE_D_MIN_AVG_PER_SECTION:
        msg = (
            f"\n  [⚠ Stage D 가드레일] Evidence 부족 — 전체 {total_evidence}건 (요구 ≥{STAGE_D_MIN_TOTAL}), "
            f"섹션당 평균 {avg_per_section:.1f}건 (요구 ≥{STAGE_D_MIN_AVG_PER_SECTION})."
        )
        print(msg)
        print(f"  evidence 부족 시 LLM이 자체 지식으로 fabricate하는 위험 → 보고서 생성 중단 권장.")
        print(f"  대응: archive 보강 / STAGE_D_EXTERNAL_DEFAULT=true / 토픽 재정의.")
        if auto:
            raise RuntimeError(
                f"[Stage D 가드레일] Evidence {total_evidence}건 — auto 모드에서 abort. "
                f"보고서 신뢰도 보호."
            )
        else:
            ans = (await _ainput("  그래도 진행하시겠습니까? [y/N] > ")).strip().lower()
            if ans != "y":
                raise RuntimeError("[Stage D 가드레일] 사용자가 evidence 부족으로 보고서 생성 중단을 선택.")

    # E+F: 목차별 분석 + 보고서 작성
    sections = await stage_ef(llm, topic, sections)

    # G: Executive Summary + 시사점
    meta = await stage_g(llm, topic, sections)

    # 저장
    print("\n[저장 중...]")
    md_path, html_path = _save_report(topic, sections, run_ts, archive_results, pre_queries, meta)

    print("\n" + "=" * 60)
    print("  보고서 생성 완료")
    print(f"  주제: {topic}")
    print(f"  목차: {len(sections)}개")
    total_bullets = sum(len(s.get("report", {}).get("bullets", [])) for s in sections)
    print(f"  정량 fact: {total_bullets}건")
    print("=" * 60)

    await search.close()
    return md_path, html_path


def rebuild_html_from_process(process_json_path: str):
    """저장된 _process.json으로 HTML만 재생성 (LLM 재호출 없음)."""
    p = Path(process_json_path)
    if not p.exists():
        print(f"[!] 파일 없음: {p}")
        sys.exit(1)
    data = json.loads(p.read_text(encoding="utf-8"))
    topic = data["topic"]
    run_ts = data["run_ts"]

    # 보고서 markdown 읽기
    slug = _slug(topic)
    md_path = REPORTS_DIR / f"{slug}_report.md"
    if not md_path.exists():
        print(f"[!] Markdown 보고서 없음: {md_path}")
        sys.exit(1)
    md_text = md_path.read_text(encoding="utf-8")

    # archive_results 복원 (source_name, source_url, article_title 만 필요)
    from src.models import SearchResult
    archive_results = [
        SearchResult(
            source_url=e["url"], final_url=e["url"],
            content="", tier=0,
            source_name=e["source_name"],
            article_title=e.get("title", ""),
        )
        for e in data.get("archive_sources", [])
    ]

    # sections 복원 (results 포함)
    sections = []
    for s in data.get("sections", []):
        results = [
            SearchResult(
                source_url=r["url"], final_url=r["url"],
                content="", tier=0,
                source_name=r["source_name"],
                article_title=r.get("title", ""),
            )
            for r in s.get("results", [])
        ]
        sections.append({
            "title": s["title"],
            "causal_role": s.get("causal_role", "analysis"),
            "angle": s.get("angle", ""),
            "queries": s["queries"],
            "included": s["included"],
            "results": results,
            "report": {},
        })

    pre_queries = data.get("pre_queries", [])
    meta = data.get("meta", {})
    # 저장된 markdown 재사용 (이미 executive summary + insights 포함)
    report_html = md_lib.markdown(md_text, extensions=["tables", "nl2br"])
    html_text = HTML_TEMPLATE.format(title=topic, body=report_html)

    html_path = REPORTS_DIR / f"{slug}_report.html"
    html_path.write_text(html_text, encoding="utf-8")
    print(f"[OK] HTML 재생성 완료: {html_path}")


if __name__ == "__main__":
    import argparse as _ap
    _parser = _ap.ArgumentParser(add_help=False)
    _parser.add_argument("--auto", action="store_true")
    _parser.add_argument("--domain", default="smartphone")
    _parser.add_argument("--rebuild", default=None)
    _known, _rest = _parser.parse_known_args()

    if _known.rebuild:
        rebuild_html_from_process(_known.rebuild)
    elif not _rest:
        print("사용법:")
        print("  python run_report.py \"분석 토픽\"")
        print("  python run_report.py --auto \"분석 토픽\"   # 게이트 자동 통과")
        print("  python run_report.py --domain humanoid \"분석 토픽\"")
        print("  python run_report.py --rebuild reports/{slug}_process.json")
        sys.exit(1)
    else:
        topic_arg = " ".join(_rest)
        asyncio.run(main(topic_arg, auto=_known.auto, domain=_known.domain))
