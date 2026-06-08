import asyncio
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional


def _year() -> int:
    return date.today().year

from src.models import PipelineState, Topic, ResearchPlan, DimensionProposal
from src.services.search import SearchService
from src.services.body_fetcher import fetch_or_cached, FETCHABLE_SOURCES, BLOCKED_SOURCES
from src.services.llm import LLMService
from src.services.citation import CitationRegistry
from src.prompts.system import DOMAIN_ANALYST_TYPES
from src.domains import load_domain
from src.prompts.step_prompts import (
    PLANNING_DIMENSIONS_PROMPT,
    DIMENSION_FINALIZE_PROMPT,
    DIMENSION_DEDUP_PROMPT,
    PRE_SEARCH_PROMPT,
    DIMENSION_ANALYSIS_PROMPT,
    CROSS_DIMENSION_LINKAGE_PROMPT,
    KEY_QUESTIONS_PROMPT,
)
from src.models import SearchResult

REPORTS_DIR = Path("reports")
PLAN_DEBUG_LOG_PATH = REPORTS_DIR / "step0_plan_raw_debug.log"


def _log_plan_raw(label: str, text: str, reasoning: str = "") -> None:
    PLAN_DEBUG_LOG_PATH.parent.mkdir(exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with PLAN_DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 70}\n[{ts}] {label}\n{'=' * 70}\n")
        if reasoning:
            f.write(f"--- reasoning ---\n{reasoning}\n")
        f.write(f"--- content ---\n{text}\n")


class AnalysisPipeline:
    def __init__(self, domain_id: str = "smartphone", on_data_gap: Callable = None):
        self.search = SearchService()
        self.llm = LLMService()
        self.registry = CitationRegistry()
        self.on_data_gap = on_data_gap
        self.state: Optional[PipelineState] = None
        self._domain = load_domain(domain_id)
        self._sys = self._domain["system_prompt"]
        self._analyst_type = DOMAIN_ANALYST_TYPES.get(domain_id, "senior smartphone market analyst")
        self._player_examples = self._domain.get("player_examples", "Samsung, Apple, Xiaomi, Huawei")
        self._example_topic = self._domain.get("example_topic", "foldable smartphones")

    def _make_step(self, cls, progress_cb=None, **kwargs):
        return cls(self.search, self.llm, self.registry, progress_cb=progress_cb, **kwargs)

    def _topic_slug(self, title: str) -> str:
        return re.sub(r"[^a-zA-Z0-9가-힣]", "_", title)[:50]

    def _state_path(self, slug: str) -> Path:
        REPORTS_DIR.mkdir(exist_ok=True)
        return REPORTS_DIR / f"{slug}_state.json"

    def save_state(self) -> None:
        if self.state and self.state.topic:
            path = self._state_path(self._topic_slug(self.state.topic.title))
            data = self.state.model_dump()
            path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")

    def load_state(self, topic_title: str) -> Optional[PipelineState]:
        path = self._state_path(self._topic_slug(topic_title))
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return PipelineState.model_validate(data)
        return None

    async def plan_propose(self, topic_title: str, progress_cb=None) -> DimensionProposal:
        """Phase 0 A~C: 영문 키워드 → 사전 검색 → 5개 차원 제안."""
        # A: 토픽 → 영문 검색 쿼리
        if progress_cb:
            await progress_cb("영문 키워드 변환 중...\n")
        kw_raw = (await self.llm.complete(
            self._sys,
            PRE_SEARCH_PROMPT.format(topic=topic_title, current_year=_year(), analyst_type=self._analyst_type,
                                     player_examples=self._player_examples, example_topic=self._example_topic),
            max_tokens=2000,
            temperature=0.1,
        )).content.strip()
        if kw_raw.startswith("```"):
            kw_raw = re.sub(r"^```[a-z]*\n?", "", kw_raw)
            kw_raw = re.sub(r"\n?```$", "", kw_raw)
        pre_queries = _extract_json_array(kw_raw)
        if pre_queries:
            eng_topic = " ".join(pre_queries[0].split()[:6])
        else:
            eng_topic = topic_title
        self._eng_topic = eng_topic
        self._pre_queries = pre_queries  # [REV4-M3] defensive secondary capture
        self.search.set_core_terms(eng_topic, current_year=str(_year()))

        if not pre_queries:
            pre_queries = [
                f"{eng_topic} {_year()}",
                f"{eng_topic} {self._domain['fallback_query_suffix']}",
                f"{eng_topic} latest news",
            ]

        # B (REV4): archive-first → 결과 < 5건이면 user Y/N (asyncio.to_thread) → optional external
        if progress_cb:
            await progress_cb("Archive 사전 검색 중...\n")

        archive_results: list = []
        archive_url_set: set[str] = set()
        for q in pre_queries:
            if progress_cb:
                await progress_cb(f"  · {q} (archive only)\n")
            try:
                sr = await self.search.search_archive_only(q)
                for r in sr.results:
                    if not r.source_url or r.source_url in archive_url_set:
                        continue
                    archive_url_set.add(r.source_url)
                    archive_results.append(r)
            except Exception:
                continue

        archive_count = len(archive_url_set)
        use_external = False  # 스펙 line 29: ≥5 archive only

        if archive_count < 5:
            if progress_cb:
                await progress_cb(
                    f"\n  ⚠️  Archive 매칭 결과: {archive_count}건 (5건 미만)\n"
                    f"     외부 검색(RSS/DuckDuckGo) 진행 시 추가 데이터 확보 가능.\n"
                )
            # input() async-safe: 메인 스레드에서 사용자 입력 대기 (event loop 블로킹 방지)
            ans = (await asyncio.to_thread(
                input, "     외부 검색 진행할까요? [Y/n]: "
            )).strip().lower()
            use_external = ans in ("", "y", "yes")
            if not use_external and progress_cb:
                await progress_cb(f"  → archive 결과만으로 진행 (총 {archive_count}건)\n")
        elif progress_cb:
            await progress_cb(f"  ✓ Archive 매칭 충분 ({archive_count}건) — archive only 진행\n")

        # B-2: optional external (사용자 승인 시)
        all_pre_results = list(archive_results)
        if use_external:
            for q in pre_queries:
                if progress_cb:
                    await progress_cb(f"  · {q} (external)\n")
                try:
                    sr = await self.search.search_external_only(q, fetched=archive_url_set)
                    if hasattr(self, 'registry') and self.registry:
                        self.registry.add_fetched_urls(sr.fetched_urls)
                    for r in sr.results:
                        if not r.source_url or r.source_url in archive_url_set:
                            continue
                        archive_url_set.add(r.source_url)
                        all_pre_results.append(r)
                except Exception:
                    continue

        # pipeline state — E단계 분기용
        self._use_external = use_external

        # 기존 pre_search_context 구성 로직 유지
        pre_parts: list[str] = []
        pre_url_data: list[dict] = []
        for r in all_pre_results:
            excerpt = re.sub(r"\s+", " ", (r.content or "")).strip()[:500]
            source_label = (r.source_name or r.source_url).strip()
            art_title = (r.article_title or "").strip()
            display_title = f"{source_label} — {art_title[:70]}" if art_title else source_label
            pre_parts.append(f"[{source_label}] {excerpt}")
            pre_url_data.append({
                "url": r.source_url,
                "title": display_title,
                "summary": excerpt,
                "query": "(archive)" if not use_external else "(mixed)",
                "tier": r.tier,
            })
        self._pre_search_urls = pre_url_data[:30]
        pre_search_context = "\n\n".join(pre_parts[:30]) or "(검색 결과 없음)"

        # C: 5개 차원 제안 (D 흡수)
        if progress_cb:
            await progress_cb("핵심차원 5개 제안 중...\n")
        dim_prompt = PLANNING_DIMENSIONS_PROMPT.format(
            topic=topic_title, pre_search_context=pre_search_context, current_year=_year(),
            player_examples=self._player_examples, example_topic=self._example_topic,
        )
        dim_response = await self.llm.complete(
            self._sys, dim_prompt,
            max_tokens=8000, thinking=True, temperature=0.4,
        )
        dim_raw = dim_response.content.strip()
        _log_plan_raw("PASS1 DIMENSIONS+QUERIES", dim_raw, dim_response.reasoning)
        if dim_raw.startswith("```"):
            dim_raw = re.sub(r"^```[a-z]*\n?", "", dim_raw)
            dim_raw = re.sub(r"\n?```$", "", dim_raw)

        dim_data = _extract_json_block(dim_raw) or {}
        try:
            if not dim_data:
                dim_data = json.loads(dim_raw)
        except Exception:
            pass

        proposed_dimensions = dim_data.get("key_dimensions") or []
        dimension_rationale = dim_data.get("dimension_rationale") or {}
        dimension_queries_grouped = dim_data.get("dimension_queries_grouped") or []
        analysis_rationale = dim_data.get("analysis_rationale") or f"{eng_topic} {self._domain['fallback_query_suffix']} analysis"

        # 길이 정합 보정
        while len(dimension_queries_grouped) < len(proposed_dimensions):
            i = len(dimension_queries_grouped)
            dim_eng = proposed_dimensions[i] if i < len(proposed_dimensions) else eng_topic
            dimension_queries_grouped.append([
                f"{eng_topic} {dim_eng} news {_year()}",
                f"{eng_topic} {dim_eng} player response",
                f"{eng_topic} {dim_eng} market data",
            ])

        if not proposed_dimensions:
            proposed_dimensions = ["시장 영향 (Build/Sell-in/Sell-through)", "주요 플레이어 대응",
                                   "소비자 수요 및 Sell-through 변화", "공급망 현황", "경쟁 구도 변화"]
            dimension_rationale = {d: "" for d in proposed_dimensions}
            dimension_queries_grouped = [
                [f"{eng_topic} {self._domain['fallback_query_suffix']} {_year()}", f"{eng_topic} supply chain {_year()}", f"{eng_topic} market share forecast"],
                [f"{eng_topic} Samsung response", f"{eng_topic} Apple strategy", f"{eng_topic} Chinese OEM"],
                [f"{eng_topic} consumer demand {_year()}", f"{eng_topic} price sensitivity", f"{eng_topic} sell-through retail"],
                [f"{eng_topic} supply chain {_year()}", f"{eng_topic} component shortage", f"{eng_topic} production forecast"],
                [f"{eng_topic} competition {_year()}", f"{eng_topic} market share shift", f"{eng_topic} competitor response"],
            ]

        return DimensionProposal(
            analysis_rationale=analysis_rationale,
            eng_topic=eng_topic,
            pre_queries=pre_queries,  # [REV4-M3] NEW
            proposed_dimensions=proposed_dimensions,
            dimension_rationale=dimension_rationale,
            dimension_queries_grouped=dimension_queries_grouped,
        )

    async def plan_refine(
        self,
        topic_title: str,
        proposal: DimensionProposal,
        user_feedback: str,
        progress_cb=None,
    ) -> DimensionProposal:
        """피드백 1회 반영 → 새 DimensionProposal 반환 (반복 호출 가능)."""
        if progress_cb:
            await progress_cb("사용자 피드백 반영 중...\n")
        proposed_list = "\n".join(
            f"{i+1}. {dim}: {proposal.dimension_rationale.get(dim, '')}"
            for i, dim in enumerate(proposal.proposed_dimensions)
        )
        finalize_prompt = DIMENSION_FINALIZE_PROMPT.format(
            topic=topic_title,
            analysis_rationale=proposal.analysis_rationale,
            proposed_list=proposed_list,
            feedback=user_feedback,
            current_year=_year(),
            prev_excluded_perspectives=json.dumps(proposal.excluded_perspectives, ensure_ascii=False),
            prev_excluded_topics=json.dumps(proposal.excluded_topics, ensure_ascii=False),
        )
        resp = await self.llm.complete(
            self._sys, finalize_prompt,
            max_tokens=4000, thinking=False, temperature=0.3,
        )
        raw = resp.content.strip()
        _log_plan_raw("REFINE DIMENSIONS", raw)
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        data = _extract_json_block(raw) or {}
        try:
            if not data:
                data = json.loads(raw)
        except Exception:
            pass

        key_dimensions = data.get("key_dimensions") or proposal.proposed_dimensions
        dimension_rationale = {**proposal.dimension_rationale, **(data.get("dimension_rationale") or {})}
        dimension_queries_grouped = data.get("dimension_queries_grouped") or proposal.dimension_queries_grouped

        # excluded 추출: LLM이 누적 결과를 반환하면 그대로, 비어 있으면 이전 누적 유지
        VALID_PERSPS = {"build", "sell_in", "sell_through"}
        new_persps = data.get("excluded_perspectives")
        if isinstance(new_persps, list):
            excluded_perspectives = [
                p.strip().lower().replace("-", "_")
                for p in new_persps if isinstance(p, str)
            ]
            excluded_perspectives = [p for p in excluded_perspectives if p in VALID_PERSPS]
        else:
            excluded_perspectives = list(proposal.excluded_perspectives)

        new_topics = data.get("excluded_topics")
        if isinstance(new_topics, list):
            excluded_topics = [t.strip() for t in new_topics if isinstance(t, str) and t.strip()]
        else:
            excluded_topics = list(proposal.excluded_topics)

        while len(dimension_queries_grouped) < len(key_dimensions):
            i = len(dimension_queries_grouped)
            eng_base = getattr(self, "_eng_topic", "") or topic_title
            dimension_queries_grouped.append([
                f"{eng_base} {key_dimensions[i]} news {_year()}",
                f"{eng_base} {key_dimensions[i]} player response",
                f"{eng_base} {key_dimensions[i]} market data",
            ])

        return DimensionProposal(
            analysis_rationale=proposal.analysis_rationale,
            eng_topic=proposal.eng_topic,
            pre_queries=proposal.pre_queries,  # [REV4-M3] inherit unchanged
            proposed_dimensions=key_dimensions,
            dimension_rationale=dimension_rationale,
            dimension_queries_grouped=dimension_queries_grouped,
            excluded_perspectives=excluded_perspectives,
            excluded_topics=excluded_topics,
        )

    async def plan_finalize(
        self,
        topic_title: str,
        proposal: DimensionProposal,
        user_feedback: str = "",
        progress_cb=None,
    ) -> ResearchPlan:
        """사용자 피드백 → 최종 ResearchPlan.
        빈 피드백 / 승인이면 proposal 그대로. 피드백이 있으면 plan_refine 1회 후 확정.
        반복 피드백은 호출자(app/server/debug)에서 plan_refine을 직접 루프하고
        최종 승인 시 이 함수를 빈 피드백으로 호출하세요.
        """
        APPROVE_TOKENS = {"", "ok", "승인", "yes", "y", "확인", "좋아", "진행", "ㅇㅋ", "네", "ㅇ"}
        if user_feedback.strip().lower() not in APPROVE_TOKENS:
            proposal = await self.plan_refine(topic_title, proposal, user_feedback, progress_cb)
        return ResearchPlan(
            analysis_rationale=proposal.analysis_rationale,
            key_dimensions=proposal.proposed_dimensions,
            dimension_rationale=proposal.dimension_rationale,
            dimension_queries_grouped=proposal.dimension_queries_grouped,
            pre_queries=proposal.pre_queries,  # [REV4-M3]
            excluded_perspectives=proposal.excluded_perspectives,
            excluded_topics=proposal.excluded_topics,
        )

    async def plan(self, topic_title: str, progress_cb=None) -> ResearchPlan:
        """Backward-compatible: propose + auto-approve (no user feedback)."""
        proposal = await self.plan_propose(topic_title, progress_cb)
        return await self.plan_finalize(topic_title, proposal, "", progress_cb)

    async def analyze_by_dimensions(
        self,
        topic_title: str,
        plan: ResearchPlan,
        progress_cb=None,
        max_chars: int = 200000,
        max_tokens: int = 8000,
    ) -> dict:
        """Phase 0 (E~H): 차원별 검색 → 차원 분석 → 차원 간 연계 → 핵심 질문 도출."""
        if self.state is None:
            self.state = PipelineState(
                topic=Topic(title=topic_title, eng_title=getattr(self, "_eng_topic", "")),
            )

        dimensions = list(plan.key_dimensions)
        grouped = list(plan.dimension_queries_grouped or [])
        excluded_perspectives = list(getattr(plan, "excluded_perspectives", []) or [])
        excluded_topics = list(getattr(plan, "excluded_topics", []) or [])
        active_perspectives = [
            p for p in ("build", "sell_in", "sell_through")
            if p not in excluded_perspectives
        ] + ["composite"]

        # 부족한 그룹은 기본 쿼리로 채움
        while len(grouped) < len(dimensions):
            i = len(grouped)
            eng_base = getattr(self, "_eng_topic", "") or topic_title
            grouped.append([
                f"{eng_base} {dimensions[i]} news {_year()}",
                f"{eng_base} {dimensions[i]} player response",
                f"{eng_base} {dimensions[i]} market data",
            ])

        # Sell-through 관점이 누락된 경우 소비자/채널 차원 자동 추가
        # 단, 사용자가 sell_through 제외를 명시했다면 자동 추가하지 않음
        consumer_keywords = {"소비자", "consumer", "demand", "수요", "구매", "purchase",
                             "sell-through", "sell through", "채널", "channel"}
        has_demand_dim = any(
            any(kw in dim.lower() for kw in consumer_keywords)
            for dim in dimensions
        )
        if not has_demand_dim and "sell_through" not in excluded_perspectives:
            eng_base = getattr(self, "_eng_topic", "") or topic_title
            demand_dim_name = "소비자 수요 및 Sell-through 변화"
            dimensions.append(demand_dim_name)
            grouped.append([
                f"{eng_base} consumer demand sell-through {_year()}",
                f"{eng_base} consumer price sensitivity willingness to pay",
                f"{eng_base} channel sell-through retail share",
            ])
            plan.dimension_rationale[demand_dim_name] = (
                "소비자의 구매 의향, 가격 수용성, 유통 채널의 sell-through 변화를 파악하여 최종 판매 측면을 분석하기 위함."
            )

        dim_analyses: list[dict] = []
        self._phase0_search_results: list[SearchResult] = []

        # E + F: 차원별 검색 + GLM 분석
        for idx, (dim_name, queries) in enumerate(zip(dimensions, grouped), start=1):
            if progress_cb:
                await progress_cb(f"\n**[차원 {idx}/{len(dimensions)}] {dim_name}**\n")

            # E (REV4): 차원별 검색 — use_external 플래그에 따라 archive_only 또는 full search
            dim_results: list[SearchResult] = []
            seen_urls: set[str] = set()
            use_external = getattr(self, "_use_external", True)  # 기본값 True (B에서 설정 안된 경우 호환)
            for q in queries:
                if progress_cb:
                    await progress_cb(f"  · {q}\n")
                try:
                    sr = await (self.search.search_archive_only(q) if not use_external
                                else self.search.search(q))
                    self.registry.add_fetched_urls(sr.fetched_urls)
                    for r in sr.results:
                        if not r.source_url or r.source_url in seen_urls:
                            continue
                        seen_urls.add(r.source_url)
                        # F-stage body fetch: FETCHABLE는 직접, BLOCKED는 Wayback 시도
                        if r.source_name in FETCHABLE_SOURCES or r.source_name in BLOCKED_SOURCES:
                            body = await asyncio.to_thread(
                                fetch_or_cached, r.source_url, r.source_name
                            )
                            if body:
                                r.content = body
                        dim_results.append(r)
                except Exception as e:
                    _log_plan_raw(f"DIM {idx} SEARCH ERROR ({q})", repr(e))
                    continue
            if progress_cb:
                await progress_cb(f"    └─ unique 결과 {len(dim_results)}건\n")
            self._phase0_search_results.extend(dim_results)

            content = _format_results_unlimited(dim_results, max_chars=max_chars)

            # F: GLM 분석 (B/SI/ST perspective 명시)
            if progress_cb:
                await progress_cb("  · GLM-4.7 분석 중...\n")
            rationale = plan.dimension_rationale.get(dim_name, "")
            prompt = DIMENSION_ANALYSIS_PROMPT.format(
                topic=topic_title,
                dimension_name=dim_name,
                dimension_rationale=rationale,
                search_results=content,
                excluded_perspectives=json.dumps(excluded_perspectives, ensure_ascii=False) or "[]",
                excluded_topics=json.dumps(excluded_topics, ensure_ascii=False) or "[]",
            )
            try:
                response = await self.llm.complete(
                    self._sys,
                    prompt,
                    max_tokens=max_tokens,
                    thinking=False,
                    temperature=0.1,
                )
                _log_plan_raw(f"DIM {idx} RAW", response.content, response.reasoning)
                if progress_cb and response.reasoning:
                    await progress_cb(f"§THINKING§{response.reasoning}")
            except Exception as e:
                _log_plan_raw(f"DIM {idx} LLM ERROR", repr(e))
                response = None

            dim_data = _extract_json_block(response.content) if response else None
            if not dim_data:
                if progress_cb:
                    await progress_cb("  ! JSON 파싱 실패 — 폴백 사용\n")
                dim_data = {
                    "dimension": dim_name,
                    "headline": f"{dim_name}: 분석 결과 파싱 실패",
                    "subtopics": [],
                }

            # URL 화이트리스트 검증 (anti-hallucination)
            valid_urls = seen_urls | set(self.registry._known_urls)
            for sub in dim_data.get("subtopics", []) or []:
                clean_evidence = []
                for e in sub.get("evidence", []) or []:
                    url = (e.get("source_url") or "").strip()
                    if url and url in valid_urls:
                        clean_evidence.append(e)
                sub["evidence"] = clean_evidence
                # perspective 정합성 보정
                p = (sub.get("perspective") or "").strip().lower().replace("-", "_")
                if p not in ("build", "sell_in", "sell_through", "composite"):
                    p = "composite"
                sub["perspective"] = p

            # 사용자 제외 항목 강제 필터 (LLM이 무시했을 경우 대비)
            if excluded_perspectives or excluded_topics:
                kept_subs = []
                for sub in dim_data.get("subtopics", []) or []:
                    if sub.get("perspective") in excluded_perspectives:
                        continue
                    label_lower = (sub.get("label") or "").lower()
                    if any(t.lower() in label_lower for t in excluded_topics if t):
                        continue
                    kept_subs.append(sub)
                dim_data["subtopics"] = kept_subs
            dim_data["dimension"] = dim_name

            dim_analyses.append(dim_data)
            if progress_cb:
                await progress_cb(f"  ✓ {dim_name} 완료 ({len(dim_data.get('subtopics', []))}개 subtopic)\n")

        # G: 차원 간 연계 분석 (thinking ON)
        linkages: list[dict] = []
        if len(dim_analyses) >= 2:
            if progress_cb:
                await progress_cb("\n**[차원 연계 분석]** 인과 관계 도출 중...\n")
            dim_summaries_text = "\n\n".join(
                f"### 차원: {da.get('dimension', '')}\n"
                f"핵심 발견: {da.get('headline', '')}\n"
                f"주요 소주제: {', '.join(s.get('label', '') for s in da.get('subtopics', []))}"
                for da in dim_analyses
            )
            linkage_prompt = CROSS_DIMENSION_LINKAGE_PROMPT.format(
                topic=topic_title,
                dimension_summaries=dim_summaries_text,
                excluded_perspectives=json.dumps(excluded_perspectives, ensure_ascii=False) or "[]",
                excluded_topics=json.dumps(excluded_topics, ensure_ascii=False) or "[]",
            )
            try:
                linkage_resp = await self.llm.complete(
                    self._sys, linkage_prompt,
                    max_tokens=8000, thinking=True, temperature=0.4,
                )
                _log_plan_raw("LINKAGE RAW", linkage_resp.content, linkage_resp.reasoning)
                linkage_data = _extract_json_block(linkage_resp.content)
                linkages = linkage_data.get("linkages", []) if linkage_data else []
                # 제외 관점 linkage 필터
                if excluded_perspectives or excluded_topics:
                    filtered = []
                    for l in linkages:
                        p = (l.get("perspective") or "").strip().lower().replace("-", "_")
                        if p in excluded_perspectives:
                            continue
                        text_blob = (
                            (l.get("relationship") or "") + " "
                            + (l.get("causal_chain") or "")
                        ).lower()
                        if any(t.lower() in text_blob for t in excluded_topics if t):
                            continue
                        filtered.append(l)
                    linkages = filtered
            except Exception as e:
                _log_plan_raw("LINKAGE ERROR", repr(e))
            if progress_cb:
                await progress_cb(f"  ✓ 연계 {len(linkages)}개 도출\n")

        # H: 핵심 질문 5개 도출 (thinking ON, max_tokens 8000)
        time_horizon: dict = {}
        scenarios: list[dict] = []
        key_questions: list[dict] = []

        if dim_analyses:
            if progress_cb:
                await progress_cb("\n**[핵심 질문 도출]** 5개 핵심 질문 생성 중...\n")
            dim_summaries_full = "\n\n".join(
                f"### 차원: {da.get('dimension', '')}\n"
                f"핵심 발견: {da.get('headline', '')}\n"
                f"소주제 ({len(da.get('subtopics', []))}개): "
                + "; ".join(
                    f"{s.get('label', '')} [{s.get('perspective', 'composite')}]"
                    for s in da.get("subtopics", [])
                )
                for da in dim_analyses
            )
            linkages_text = (
                "\n".join(
                    f"- {l.get('from_dim', '')} → {l.get('to_dim', '')}: "
                    f"{l.get('relationship', '')} ({l.get('causal_chain', '')})"
                    for l in linkages
                )
                if linkages else "(연계 없음)"
            )

            kq_prompt = KEY_QUESTIONS_PROMPT.format(
                topic=topic_title,
                analysis_rationale=plan.analysis_rationale,
                dimension_summaries=dim_summaries_full,
                linkages_text=linkages_text,
                excluded_perspectives=json.dumps(excluded_perspectives, ensure_ascii=False) or "[]",
                excluded_topics=json.dumps(excluded_topics, ensure_ascii=False) or "[]",
                active_perspectives=json.dumps(active_perspectives, ensure_ascii=False),
            )
            try:
                kq_resp = await self.llm.complete(
                    self._sys, kq_prompt,
                    max_tokens=8000, thinking=True, temperature=0.4,
                )
                _log_plan_raw("KEY_QUESTIONS RAW", kq_resp.content, kq_resp.reasoning)
                kq_data = _extract_json_block(kq_resp.content) or {}
                time_horizon = kq_data.get("time_horizon") or {}
                scenarios = kq_data.get("scenarios") or []
                key_questions = kq_data.get("key_questions") or []
                # perspective 정합성 보정
                for q in key_questions:
                    p = (q.get("perspective") or "").strip().lower().replace("-", "_")
                    if p not in ("build", "sell_in", "sell_through", "composite"):
                        p = "composite"
                    q["perspective"] = p

                # 사용자 제외 항목 강제 필터 (LLM이 무시했을 경우 대비)
                if excluded_perspectives or excluded_topics:
                    filtered_qs = []
                    for q in key_questions:
                        if q.get("perspective") in excluded_perspectives:
                            continue
                        text_blob = (
                            (q.get("question") or "") + " "
                            + (q.get("rationale") or "")
                        ).lower()
                        if any(t.lower() in text_blob for t in excluded_topics if t):
                            continue
                        filtered_qs.append(q)
                    key_questions = filtered_qs
                    # 시나리오의 제외 관점 impact 필드 비우기
                    for sc in scenarios:
                        if "build" in excluded_perspectives:
                            sc["build_impact"] = ""
                        if "sell_in" in excluded_perspectives:
                            sc["sell_in_impact"] = ""
                        if "sell_through" in excluded_perspectives:
                            sc["sell_through_impact"] = ""
            except Exception as e:
                _log_plan_raw("KEY_QUESTIONS ERROR", repr(e))
            if progress_cb:
                await progress_cb(f"  ✓ 핵심 질문 {len(key_questions)}개 도출\n")

        # 마인드맵 묶기 + 저장
        mindmap = {
            "topic": topic_title,
            "rationale": plan.analysis_rationale,
            # [REV3-U1 / REV4-M3] persisted English anchors for Phase 1 refinement search
            "eng_topic": getattr(self, "_eng_topic", "") or topic_title,
            "pre_queries": list(getattr(plan, "pre_queries", []) or []),
            "excluded_perspectives": excluded_perspectives,
            "excluded_topics": excluded_topics,
            "dimensions": dim_analyses,
            "linkages": linkages,
            "time_horizon": time_horizon,
            "scenarios": scenarios,
            "key_questions": key_questions,
        }
        REPORTS_DIR.mkdir(exist_ok=True)
        slug = self._topic_slug(topic_title)
        mindmap_path = REPORTS_DIR / f"{slug}_mindmap.json"
        mindmap_path.write_text(
            json.dumps(mindmap, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if progress_cb:
            await progress_cb(f"\n[저장] {mindmap_path}\n")
        return mindmap


def _format_results_unlimited(results: list, max_chars: int = 200000) -> str:
    """차원 분석용: 검색 결과 전체를 LLM 프롬프트에 그대로 전달 (max_chars 사실상 무제한)."""
    lines = []
    total = 0
    for r in results:
        entry = (
            f"[출처: {r.source_name} (Tier {r.tier}), URL: {r.source_url}]\n"
            f"{r.content}\n"
        )
        if total + len(entry) > max_chars:
            break
        lines.append(entry)
        total += len(entry)
    return "\n---\n".join(lines)


def _safe_json_loads(text: str) -> Optional[dict]:
    """표준 json.loads 실패 시 json-repair로 LLM 출력의 흔한 오류(미닫힘 괄호,
    이스케이프 누락 따옴표, trailing comma 등)를 복구해 dict 반환."""
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    try:
        from json_repair import loads as _repair_loads
        data = _repair_loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _extract_json_block(text: str) -> Optional[dict]:
    """LLM 응답에서 JSON 객체 추출.
    1) ```json ... ``` 펜스 블록 우선
    2) 가장 큰 {} 블록 백업
    3) 표준 파싱 실패 시 json-repair로 복구
    실패 시 None.
    """
    if not text:
        return None
    fenced = re.findall(r"```(?:json)?\s*(\{[\s\S]+?\})\s*```", text, flags=re.IGNORECASE)
    if fenced:
        data = _safe_json_loads(fenced[-1])
        if data:
            return data
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        data = _safe_json_loads(m.group())
        if data:
            return data
    return _safe_json_loads(text)


def _extract_json_array(text: str) -> list[str]:
    """텍스트에서 JSON 배열 추출 (전체 또는 부분)."""
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [q for q in data if isinstance(q, str)][:4]
    except Exception:
        pass
    m = re.search(r"\[[\s\S]+?\]", text)
    if m:
        try:
            data = json.loads(m.group())
            if isinstance(data, list):
                return [q for q in data if isinstance(q, str)][:4]
        except Exception:
            pass
    return []
