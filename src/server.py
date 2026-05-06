"""FastAPI server: serves the React UI and bridges to AnalysisPipeline via SSE."""
import asyncio
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.services.token_logger import read_all as read_token_log
from src.models import (
    PipelineState,
    ResearchPlan,
    Topic,
    DimensionProposal,
)
from src.news_api import router as news_router
from src.state_machine import AnalysisPipeline
from src.domains import load_domain

ROOT = Path(__file__).parent.parent
FRONTEND_DIST  = ROOT / "frontend" / "dist"
DASHBOARD_HTML = ROOT / "web" / "dashboard.html"
ARCHIVES_DIR   = ROOT / "data" / "archives"
ALL_ARCHIVES_SCRIPT = ROOT / "scripts" / "build_all_archives.py"

# UI 표시명 -> archive JSON 파일명 (build_all_archives.py와 동일 순서)
ARCHIVE_REGISTRY = [
    # Smartphone sources
    ("Counterpoint Research", "counterpoint.json"),
    ("TrendForce",            "trendforce.json"),
    ("Omdia",                 "omdia.json"),
    ("IDC",                   "idc.json"),
    ("Yole",                  "yole.json"),
    ("DigiTimes Asia",        "digitimes.json"),
    ("CCS Insight",           "ccs_insight.json"),
    # Humanoid / Robotics sources
    ("The Robot Report",           "robot_report.json"),
    ("IEEE Spectrum",              "ieee_spectrum_robotics.json"),
    ("TechCrunch Robotics",        "techcrunch_robotics.json"),
    ("MIT Technology Review",      "mit_tech_review.json"),
    ("Robotics & Automation News", "robotics_automation_news.json"),
    ("The Verge",                  "verge_robotics.json"),
    ("arXiv (cs.RO)",              "arxiv_robotics.json"),
    ("NVIDIA",                     "nvidia_news.json"),
    ("Boston Dynamics",            "boston_dynamics.json"),
    ("Figure AI",                  "figure_ai.json"),
    ("Unitree Robotics",           "unitree.json"),
    ("Apptronik",                  "apptronik.json"),
    ("Agility Robotics",           "agility_robotics.json"),
    ("1X Technologies",            "onex_technologies.json"),
    ("IFR",                        "ifr.json"),
]

app = FastAPI()
USER_ACTION_TIMEOUT_SECONDS = 600


@app.on_event("startup")
def _startup() -> None:
    from src.news_db import init_db
    from src.news_scheduler import start_scheduler
    init_db()
    start_scheduler()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(news_router)


@app.middleware("http")
async def no_cache_for_html_and_api(request: Request, call_next):
    response = await call_next(request)
    accept = request.headers.get("accept", "")
    if request.url.path.startswith("/api/") or "text/html" in accept:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# frontend/dist 빌드가 있으면 정적 파일 서빙 (npm run build 후 사용)
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


# Session management
class Session:
    def __init__(self, topic: str, domain_id: str = "smartphone"):
        self.id = str(uuid.uuid4())
        self.topic = topic
        self.pipeline = AnalysisPipeline(domain_id=domain_id)
        self.queue: asyncio.Queue = asyncio.Queue()
        self.plan: Optional[ResearchPlan] = None
        self.task: Optional[asyncio.Task] = None
        self.dim_feedback_event: asyncio.Event = asyncio.Event()
        self.dim_feedback: str = ""

    async def emit(self, **kwargs):
        await self.queue.put(kwargs)


SESSIONS: dict[str, Session] = {}


# Log -> event parser
def parse_log(text: str) -> Optional[dict]:
    """Convert pipeline log line to UI event."""
    stripped = text.strip()
    if not stripped:
        return None
    # Skip step headers / footers / bold markers
    if (
        stripped.startswith("[Step")
        or stripped.startswith("[완료]")
        or stripped.startswith("**[")
        or stripped.startswith("[")
    ):
        return None
    # Result counts: "└─ N개 결과" — skip for cleaner UI
    if "└─" in stripped:
        return None
    # Query lines: "  · {query}"  (leading bullet)
    m = re.match(r"^\s*·\s+(.+)$", text.rstrip("\n"))
    if m:
        content = m.group(1).strip()
        # Heuristic: action descriptions end with "중..." or "중"
        if content.endswith(("중...", "중", "중…")) or "변환" in content or "수립" in content:
            return {"type": "step_log", "text": content}
        return {"type": "step_query", "text": content}
    return {"type": "step_log", "text": stripped}


# Pipeline runners
async def _run_phase0(sess: Session):
    pipeline = sess.pipeline

    async def cb(text: str):
        if text.startswith("§THINKING§"):
            await sess.emit(type="step_thinking", text=text[len("§THINKING§"):])
            return
        ev = parse_log(text)
        if ev:
            await sess.emit(**ev)

    await sess.emit(type="phase0_start", topic=sess.topic)
    try:
        # A->B->C: 5개 차원 제안
        proposal = await pipeline.plan_propose(sess.topic, progress_cb=cb)
        pre_urls = getattr(pipeline, '_pre_search_urls', [])
        await sess.emit(
            type="dimension_proposal",
            proposal=proposal.model_dump(),
            pre_urls=pre_urls,
        )

        # User action timeout: terminate instead of auto-progress.
        try:
            await asyncio.wait_for(sess.dim_feedback_event.wait(), timeout=USER_ACTION_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await sess.emit(type="error", text="차원 선택 대기 시간이 10분을 초과해 프로세스를 종료했습니다.")
            return
        feedback = sess.dim_feedback

        # 피드백 반영 -> 최종 ResearchPlan
        plan = await pipeline.plan_finalize(sess.topic, proposal, feedback, progress_cb=cb)
        sess.plan = plan
        eng = getattr(pipeline, '_eng_topic', sess.topic)
        pipeline.state = PipelineState(topic=Topic(title=sess.topic, eng_title=eng))
        plan_dict = plan.model_dump()

        # E->F->G->H: 차원별 분석
        mindmap = await pipeline.analyze_by_dimensions(sess.topic, plan, progress_cb=cb)

        await sess.emit(type="phase0_done", plan=plan_dict, pre_urls=pre_urls, mindmap=mindmap)
        await sess.emit(type="done")
    except asyncio.CancelledError:
        return
    except Exception as e:
        await sess.emit(type="error", text=f"Phase 0 오류: {e}")
    finally:
        SESSIONS.pop(sess.id, None)


# Endpoints
@app.get("/")
async def root():
    dist_index = FRONTEND_DIST / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)
    from fastapi.responses import JSONResponse
    return JSONResponse({
        "message": "Research Helper API",
        "frontend": "http://localhost:5173  (cd frontend && npm run dev)",
        "reports": "http://localhost:8000/reports/glm_topic_suggestions.html",
    })


@app.post("/api/start")
async def api_start(req: Request):
    body = await req.json()
    topic = (body.get("topic") or "").strip()
    if not topic:
        raise HTTPException(400, "topic required")
    sess = Session(topic)
    SESSIONS[sess.id] = sess
    sess.task = asyncio.create_task(_run_phase0(sess))
    return {"session_id": sess.id}


@app.post("/api/cancel")
async def api_cancel(req: Request):
    body = await req.json()
    sid = body.get("session_id")
    sess = SESSIONS.get(sid)
    if not sess:
        return {"ok": True}
    if sess.task:
        sess.task.cancel()
    await sess.emit(type="cancelled")
    SESSIONS.pop(sid, None)
    return {"ok": True}


@app.post("/api/confirm_dimensions")
async def api_confirm_dimensions(req: Request):
    body = await req.json()
    sid = body.get("session_id")
    feedback = (body.get("feedback") or "").strip()
    sess = SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    sess.dim_feedback = feedback
    sess.dim_feedback_event.set()
    return {"ok": True}


@app.get("/api/stream/{sid}")
async def api_stream(sid: str):
    sess = SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "session not found")

    async def gen():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(sess.queue.get(), timeout=20)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("done", "cancelled", "error"):
                    break
        except asyncio.CancelledError:
            return

    return StreamingResponse(gen(), media_type="text/event-stream")


# Archive Dashboard — DB 자동 수집 컨트롤

# job_id -> asyncio.Queue (SSE 라인 버퍼)
ARCHIVE_JOBS: dict[str, asyncio.Queue] = {}


def _archive_status_one(name: str, json_name: str) -> dict:
    """단일 archive JSON의 메타데이터를 읽어 카드용 dict 반환."""
    p = ARCHIVES_DIR / json_name
    info = {
        "name": name,
        "json_name": json_name,
        "exists": p.exists(),
        "size_bytes": 0,
        "entry_count": 0,
        "built_at": None,
        "latest_entry": None,
    }
    if not p.exists():
        return info
    try:
        info["size_bytes"] = p.stat().st_size
        data = json.loads(p.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        info["entry_count"] = len(entries)
        info["built_at"]    = data.get("built_at")
        # 가장 최근 lastmod 추출
        lms = [e.get("lastmod") for e in entries if e.get("lastmod")]
        if lms:
            info["latest_entry"] = max(lms)
    except Exception as e:
        info["error"] = str(e)
    return info


@app.get("/dashboard")
async def dashboard():
    if not DASHBOARD_HTML.exists():
        raise HTTPException(404, "dashboard.html not found")
    return FileResponse(DASHBOARD_HTML)


@app.get("/api/archives/status")
async def api_archives_status():
    archives = [_archive_status_one(n, j) for n, j in ARCHIVE_REGISTRY]
    return {
        "archives": archives,
        "total_entries": sum(a["entry_count"] for a in archives),
        "ts": datetime.now().isoformat(),
    }


async def _run_archive_orchestrator(job_id: str):
    """build_all_archives.py를 subprocess로 띄우고 stdout 줄을 큐에 넣음."""
    q = ARCHIVE_JOBS[job_id]
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-u", str(ALL_ARCHIVES_SCRIPT),
            cwd=str(ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if not text:
                continue
            # JSON 라인이면 그대로, 아니면 fatal 로그로 래핑
            try:
                json.loads(text)
                await q.put(text)
            except Exception:
                await q.put(json.dumps(
                    {"type": "log", "text": text}, ensure_ascii=False))
        await proc.wait()
    except Exception as e:
        await q.put(json.dumps(
            {"type": "fatal", "error": str(e)}, ensure_ascii=False))
    finally:
        await q.put("__END__")


@app.post("/api/archives/refresh")
async def api_archives_refresh():
    job_id = uuid.uuid4().hex[:8]
    ARCHIVE_JOBS[job_id] = asyncio.Queue()
    asyncio.create_task(_run_archive_orchestrator(job_id))
    return {"job_id": job_id}


@app.get("/api/archives/stream/{job_id}")
async def api_archives_stream(job_id: str):
    q = ARCHIVE_JOBS.get(job_id)
    if q is None:
        raise HTTPException(404, "job not found")

    async def gen():
        try:
            while True:
                try:
                    line = await asyncio.wait_for(q.get(), timeout=30)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if line == "__END__":
                    break
                yield f"data: {line}\n\n"
        finally:
            ARCHIVE_JOBS.pop(job_id, None)

    return StreamingResponse(gen(), media_type="text/event-stream")


# Topic Analysis — DB 기반 주제 자동 선정

TIER1_SOURCES = {"Counterpoint Research", "TrendForce", "Omdia", "IDC", "Morgan Stanley"}

_KW_PATH = ROOT / "data" / "smartphone_keywords.json"
SMARTPHONE_KW: list[str] = json.loads(_KW_PATH.read_text(encoding="utf-8"))["keywords"]

def _is_smartphone(entry: dict) -> bool:
    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
    return any(kw in text for kw in SMARTPHONE_KW)


@app.get("/api/keywords")
async def api_keywords_get(domain: str = "smartphone"):
    """도메인별 필터링 키워드 목록 반환."""
    cfg = load_domain(domain)
    kw_path = ROOT / cfg["keywords_file"]
    data = json.loads(kw_path.read_text(encoding="utf-8"))
    return {"keywords": data["keywords"], "count": len(data["keywords"]), "domain": domain}


@app.put("/api/keywords")
async def api_keywords_put(req: Request, domain: str = "smartphone"):
    """키워드 목록 전체 교체. add/remove 대신 전체 리스트를 전달."""
    body = await req.json()
    keywords = body.get("keywords")
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        raise HTTPException(400, "keywords must be a list of strings")
    keywords = [k.strip().lower() for k in keywords if k.strip()]
    if not keywords:
        raise HTTPException(400, "keywords list cannot be empty")
    cfg = load_domain(domain)
    kw_path = ROOT / cfg["keywords_file"]
    data = json.loads(kw_path.read_text(encoding="utf-8"))
    data["keywords"] = keywords
    kw_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    load_domain.cache_clear()
    if domain == "smartphone":
        global SMARTPHONE_KW
        SMARTPHONE_KW = keywords
    return {"ok": True, "count": len(keywords), "domain": domain}


@app.get("/api/topics/mine")
async def api_topics_mine(days: int = 30, domain: str = "smartphone"):
    """최근 N일 Tier-1 소스의 도메인 관련 기사를 소스별로 묶어 반환."""
    import re as _re
    from datetime import timedelta

    cutoff = datetime.now(tz=__import__("datetime").timezone.utc) - timedelta(days=days)
    all_entries: list[dict] = []

    for _, json_name in ARCHIVE_REGISTRY:
        p = ARCHIVES_DIR / json_name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for e in data.get("entries", []):
                all_entries.append(e)
        except Exception:
            continue

    # Tier-1 + 기간 필터
    recent: list[dict] = []
    for e in all_entries:
        if e.get("source") not in TIER1_SOURCES:
            continue
        lm = e.get("lastmod", "")
        try:
            dt = datetime.fromisoformat(lm.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=__import__("datetime").timezone.utc)
            if dt >= cutoff:
                recent.append(e)
        except Exception:
            continue

    # 도메인 관련 기사만
    domain_kw = load_domain(domain)["keywords"]
    sm = [e for e in recent if any(kw in (e.get("title","") + " " + e.get("description","")).lower() for kw in domain_kw)]

    # 소스별 그룹핑
    groups: dict[str, list] = {}
    for src in TIER1_SOURCES:
        items = sorted(
            [e for e in sm if e.get("source") == src],
            key=lambda x: x.get("lastmod", ""),
            reverse=True,
        )
        if items:
            groups[src] = [
                {
                    "title":       e.get("title", ""),
                    "date":        e.get("lastmod", "")[:10],
                    "description": _re.sub(r"<[^>]+>", "", e.get("description", ""))[:200],
                    "url":         e.get("url", ""),
                }
                for e in items
            ]

    return {
        "days": days,
        "cutoff": cutoff.isoformat(),
        "total": len(sm),
        "groups": groups,
        "ts": datetime.now().isoformat(),
    }


@app.get("/api/archives/entries")
async def api_archives_entries(source: str, limit: int = 300):
    """특정 소스의 전체 아카이브 기사 반환. 키워드 필터 없음."""
    import re as _re

    for _, json_name in ARCHIVE_REGISTRY:
        p = ARCHIVES_DIR / json_name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("source") != source:
                continue
            entries = data.get("entries", [])
            entries_sorted = sorted(entries, key=lambda x: x.get("lastmod", ""), reverse=True)
            items = [
                {
                    "title": e.get("title", ""),
                    "date":  e.get("lastmod", "")[:10],
                    "url":   e.get("url", ""),
                    "description": _re.sub(r"<[^>]+>", "", e.get("description", ""))[:200],
                }
                for e in entries_sorted[:limit]
            ]
            return {"source": source, "total": len(entries), "items": items}
        except Exception:
            continue

    return {"source": source, "total": 0, "items": []}


# Report Generation — run_report.py pipeline UI bridge

class ReportSession:
    def __init__(self, topic: str, domain_id: str = "smartphone"):
        self.id = str(uuid.uuid4())
        self.topic = topic
        self.domain_id = domain_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.task: Optional[asyncio.Task] = None
        self.ext_event: asyncio.Event = asyncio.Event()
        self.ext_use_external: bool = False
        self.gate1_event: asyncio.Event = asyncio.Event()
        self.gate1_data: Optional[list] = None
        self.gate2_event: asyncio.Event = asyncio.Event()
        self.gate2_data: Optional[tuple] = None  # (proceed: bool, sections: list)

    async def emit(self, **kwargs):
        await self.queue.put(kwargs)


REPORT_SESSIONS: dict[str, "ReportSession"] = {}


def _sec_to_dict(sec: dict) -> dict:
    """GATE 1용 섹션 직렬화. results 미포함."""
    return {
        "title": sec.get("title", ""),
        "causal_role": sec.get("causal_role", "analysis"),
        "angle": sec.get("angle", ""),
        "queries": list(sec.get("queries", [])),
        "included": list(sec.get("included", [])),
    }


def _sec_with_results_to_dict(sec: dict) -> dict:
    """GATE 2용 섹션 직렬화. results 포함."""
    d = _sec_to_dict(sec)
    d["results"] = [
        {
            "source": r.source_name,
            "title": (r.article_title or r.source_url or "")[:100],
            "url": r.source_url,
        }
        for r in sec.get("results", [])
    ]
    return d


def _merge_sec(confirmed: dict, orig: dict) -> dict:
    """브라우저 응답 dict를 원본 섹션에 병합. results는 보존."""
    sec = dict(orig)
    queries = list(confirmed.get("queries", orig.get("queries", [])))
    included = list(confirmed.get("included", [True] * len(queries)))
    while len(included) < len(queries):
        included.append(True)
    sec["queries"] = queries
    sec["included"] = included[:len(queries)]
    sec["title"] = confirmed.get("title", orig.get("title", ""))
    return sec


def _topic_to_report_slug(topic: str) -> str:
    slug = re.sub(r"\s+", "_", str(topic or "").strip())
    slug = re.sub(r"[^\w가-힣]", "_", slug)
    return slug.strip("_")[:60]


def _remember_topic_report_slug(domain_id: str, topic: str, slug: str) -> None:
    try:
        suggested_path = ROOT / load_domain(domain_id)["suggested_path"]
        if not suggested_path.exists():
            return
        data = json.loads(suggested_path.read_text(encoding="utf-8"))
        changed = False
        for item in data.get("topics", []):
            if isinstance(item, dict) and str(item.get("title") or "").strip() == str(topic or "").strip():
                item["report_slug"] = slug
                changed = True
        if changed:
            suggested_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


async def _run_report(sess: ReportSession):
    import sys as _sys
    _root = str(ROOT)
    if _root not in _sys.path:
        _sys.path.insert(0, _root)

    from run_report import (
        stage_a, stage_b, stage_c, stage_d, stage_ef, stage_g,
        _save_report, _warn_section_overlap, _year,
        user_gate_1, user_gate_2,
    )
    from src.services.llm import LLMService
    from src.services.search import SearchService
    from datetime import datetime as _dt

    search = None
    try:
        llm = LLMService()
        search = SearchService()
        run_ts = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        topic = sess.topic

        await sess.emit(type="report_log", text="보고서 생성 시작")

        # A
        await sess.emit(type="report_log", text="영문 쿼리 생성 중...")

        async def stage_a_progress(**event):
            await sess.emit(type="report_step_a_trace", **event)

        pre_queries, eng_topic = await stage_a(llm, topic, progress_cb=stage_a_progress)
        search.set_core_terms(eng_topic, current_year=str(_year()))
        await sess.emit(type="report_step_a", queries=pre_queries, eng_topic=eng_topic)
        await sess.emit(type="report_log", text=f"쿼리 {len(pre_queries)}개 생성")

        # B
        await sess.emit(type="report_log", text="Archive 검색 중...")
        archive_results = await stage_b(search, pre_queries, eng_kw=eng_topic)
        by_source: dict[str, list] = {}
        for r in archive_results:
            by_source.setdefault(r.source_name, []).append({
                "title": r.article_title or "",
                "url": r.source_url,
            })
        await sess.emit(type="report_step_b", by_source=by_source, total=len(archive_results))
        await sess.emit(type="report_log", text=f"Archive {len(archive_results)}건 수집")

        # External search decision: terminate on 10-minute inactivity.
        sess.ext_event.clear()
        try:
            await asyncio.wait_for(sess.ext_event.wait(), timeout=USER_ACTION_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await sess.emit(type="report_error", text="외부 검색 진행 여부를 10분 동안 선택하지 않아 프로세스를 종료했습니다.")
            await sess.emit(type="done")
            return

        use_external = sess.ext_use_external

        if use_external:
            await sess.emit(type="report_log", text="외부 검색 실행 중...")
            ext_by_source: dict[str, list] = {}
            seen = {r.source_url for r in archive_results}
            for pq in pre_queries:
                sr = await search.search(pq, pq.split())
                for r in sr.results:
                    if r.source_url not in seen:
                        archive_results.append(r)
                        seen.add(r.source_url)
                        ext_by_source.setdefault(r.source_name, []).append({
                            "title": r.article_title or "",
                            "url": r.source_url,
                        })
            ext_total = sum(len(v) for v in ext_by_source.values())
            await sess.emit(
                type="report_step_b_ext",
                queries=pre_queries,
                by_source=ext_by_source,
                total=ext_total,
            )
            await sess.emit(type="report_log", text=f"외부 검색 {ext_total}건 추가")

        # C
        await sess.emit(type="report_step_c")
        await sess.emit(type="report_log", text="목차 생성 중...")
        sections = await stage_c(llm, topic, archive_results)
        _warn_section_overlap(sections)
        await sess.emit(type="report_log", text=f"목차 {len(sections)}개 생성")

        # GATE 1
        sess.gate1_event.clear()
        sess.gate1_data = None

        async def gate1_cb(secs):
            await sess.emit(type="report_gate1", sections=[_sec_to_dict(s) for s in secs])
            try:
                await asyncio.wait_for(sess.gate1_event.wait(), timeout=USER_ACTION_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                raise RuntimeError("GATE 1 목차 확인을 10분 동안 진행하지 않아 프로세스를 종료했습니다.")
            confirmed = sess.gate1_data or []
            result = []
            for i, orig in enumerate(secs):
                cd = confirmed[i] if i < len(confirmed) else {}
                result.append(_merge_sec(cd, orig) if cd else orig)
            return result

        sections = await user_gate_1(sections, auto=False, gate_cb=gate1_cb)
        await sess.emit(type="report_log", text="목차 확정")

        # D -> query/search refinement loop
        refine_round = 0
        max_rounds = 3
        while refine_round < max_rounds:
            await sess.emit(type="report_log", text="검색 실행 중...")
            await sess.emit(type="report_step_d", sections=[{"title": s["title"]} for s in sections])

            async def d_progress(si, total, title, _sess=sess):
                await _sess.emit(type="report_step_d_progress", idx=si, total=total, title=title)

            sections = await stage_d(search, sections, use_external=use_external, progress=d_progress)
            total_r = sum(len(s.get("results", [])) for s in sections)
            await sess.emit(type="report_log", text=f"검색 완료: {total_r}건")

            if refine_round >= max_rounds - 1:
                break

            sess.gate2_event.clear()
            sess.gate2_data = None

            async def gate2_cb(secs, _ev=sess.gate2_event):
                await sess.emit(type="report_gate2", sections=[_sec_with_results_to_dict(s) for s in secs])
                try:
                    await asyncio.wait_for(_ev.wait(), timeout=USER_ACTION_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    raise RuntimeError("GATE 2 검색 결과 확인을 10분 동안 진행하지 않아 프로세스를 종료했습니다.")
                proceed, updated = sess.gate2_data or (True, [])
                if proceed:
                    return True, secs
                merged = []
                for i, orig in enumerate(secs):
                    u = updated[i] if i < len(updated) else {}
                    merged.append(_merge_sec(u, orig) if u else orig)
                return False, merged

            proceed, sections = await user_gate_2(sections, auto=False, gate_cb=gate2_cb)
            if proceed:
                break
            refine_round += 1
            await sess.emit(type="report_log", text=f"쿼리 보완 재검색 (라운드 {refine_round + 1})")

        # E+F
        await sess.emit(type="report_log", text="목차별 분석 시작...")

        async def ef_progress(si, total, title):
            await sess.emit(type="report_step_ef_progress", si=si, total=total, title=title)

        sections = await stage_ef(llm, topic, sections, progress_cb=ef_progress)

        # G
        await sess.emit(type="report_log", text="시사점 생성 중...")
        meta = await stage_g(llm, topic, sections)

        # 저장
        await sess.emit(type="report_log", text="저장 중...")
        md_path, html_path = _save_report(topic, sections, run_ts, archive_results, pre_queries, meta)
        slug = html_path.name.removesuffix("_report.html")
        _remember_topic_report_slug(sess.domain_id, topic, slug)

        await sess.emit(type="report_done", report_url=f"/archive/{slug}")
        await sess.emit(type="done")

    except asyncio.CancelledError:
        return
    except Exception as e:
        import traceback
        await sess.emit(type="report_error", text=f"{e}\n{traceback.format_exc()[:400]}")
        await sess.emit(type="done")
    finally:
        if search:
            await search.close()
        REPORT_SESSIONS.pop(sess.id, None)


@app.get("/api/topics/suggested")
async def api_topics_suggested(domain: str = "smartphone"):
    """도메인별 GLM 선정 주제 반환."""
    p = ROOT / load_domain(domain)["suggested_path"]
    topics: list[dict] = []
    generated_at = None
    days = 30
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            topics = list(data.get("topics", []))
            generated_at = data.get("generated_at")
            days = data.get("days", 30)
        except Exception:
            pass

    # Merge emerging "Curiosity Pick" topics (weekly pass — smartphone & humanoid).
    # All emerging topics carry criteria="Criterion 3" so frontend's existing
    # Crit2/Crit3 split surfaces them in the "이번 주 새롭게 등장한 주제" section.
    EMERGING_PATHS = {
        "smartphone": "scripts/_topic_suggestions_emerging.json",
        "humanoid":   "scripts/_humanoid_topic_suggestions_emerging.json",
    }
    em_rel = EMERGING_PATHS.get(domain)
    if em_rel:
        emerging_path = ROOT / em_rel
        if emerging_path.exists():
            try:
                em_data = json.loads(emerging_path.read_text(encoding="utf-8"))
                for t in em_data.get("topics", []):
                    if not isinstance(t, dict):
                        continue
                    t["criteria"] = "Criterion 3"  # force, regardless of LLM output
                    t.setdefault("source", "emerging")
                    topics.append(t)
            except Exception:
                pass

    for topic in topics:
        if not isinstance(topic, dict):
            continue
        title = str(topic.get("title") or "").strip()
        slug = str(topic.get("report_slug") or "").strip() or _topic_to_report_slug(title)
        if slug and (ROOT / "reports" / f"{slug}_report.md").exists():
            topic["report_slug"] = slug
        else:
            topic.pop("report_slug", None)
    return {
        "topics": topics,
        "generated_at": generated_at,
        "days": days,
    }


@app.get("/api/usage")
async def api_usage():
    """GLM 토큰 사용량 및 비용 집계."""
    from collections import defaultdict
    raw_entries = read_token_log()
    entries = []
    for e in raw_entries:
        try:
            prompt_tokens = int(e.get("prompt_tokens") or 0)
            completion_tokens = int(e.get("completion_tokens") or 0)
            cost_cny = float(e.get("cost_cny") or 0)
        except (TypeError, ValueError):
            continue
        try:
            total_tokens = int(e.get("total_tokens") or prompt_tokens + completion_tokens)
        except (TypeError, ValueError):
            total_tokens = prompt_tokens + completion_tokens
        entries.append({
            "ts": str(e.get("ts") or ""),
            "model": str(e.get("model") or "unknown"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_cny": cost_cny,
            "caller": str(e.get("caller") or ""),
        })
    if not entries:
        return {"summary": {}, "by_model": [], "by_day": [], "recent": []}

    total_prompt = sum(e["prompt_tokens"] for e in entries)
    total_completion = sum(e["completion_tokens"] for e in entries)
    total_cost = sum(e["cost_cny"] for e in entries)

    by_model: dict = defaultdict(lambda: {"prompt_tokens": 0, "completion_tokens": 0, "cost_cny": 0.0, "calls": 0})
    by_day:   dict = defaultdict(lambda: {"prompt_tokens": 0, "completion_tokens": 0, "cost_cny": 0.0, "calls": 0})
    for e in entries:
        m = by_model[e["model"]]
        m["prompt_tokens"]     += e["prompt_tokens"]
        m["completion_tokens"] += e["completion_tokens"]
        m["cost_cny"]          += e["cost_cny"]
        m["calls"]             += 1
        day = e["ts"][:10] or "unknown"
        d = by_day[day]
        d["prompt_tokens"]     += e["prompt_tokens"]
        d["completion_tokens"] += e["completion_tokens"]
        d["cost_cny"]          += e["cost_cny"]
        d["calls"]             += 1

    return {
        "summary": {
            "total_prompt_tokens":     total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens":            total_prompt + total_completion,
            "total_cost_cny":          round(total_cost, 4),
            "call_count":              len(entries),
        },
        "by_model": [{"model": k, **v, "cost_cny": round(v["cost_cny"], 4)} for k, v in sorted(by_model.items())],
        "by_day":   [{"day": k,   **v, "cost_cny": round(v["cost_cny"], 4)} for k, v in sorted(by_day.items(), reverse=True)],
        "recent":   list(reversed(entries[-50:])),
    }


def _extract_metrics(*texts: str) -> list[str]:
    joined = " ".join(t for t in texts if t)
    patterns = [
        r"\d+(?:\.\d+)?\s?~\s?\d+(?:\.\d+)?\s?%",
        r"\d+(?:\.\d+)?\s?%",
        r"\d+(?:\.\d+)?\s?(?:배|건|년|개월|분기|조|억|만|달러|원)",
        r"Q[1-4]\s?\d{2,4}",
        r"YoY|QoQ",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, joined, flags=re.IGNORECASE):
            item = match.strip()
            if item and item not in found:
                found.append(item)
    return found[:8]


_HUMANOID_SOURCES = {
    "Robotics & Automation News", "TechCrunch Robotics", "IEEE Spectrum Robotics",
    "IEEE Spectrum", "The Robot Report", "Boston Dynamics", "Figure AI",
    "arXiv (cs.RO)", "MIT Technology Review", "Unitree Robotics", "NVIDIA", "The Verge",
}

_AUTOMOTIVE_SOURCES = {
    "JATO Dynamics", "AlixPartners", "WardsAuto", "SAE International",
    "VW Group", "Mercedes-Benz Media", "Cox Automotive", "Automotive Dive",
    "Automotive World", "Electrek", "InsideEVs", "Toyota Newsroom",
}

_SMARTPHONE_SOURCES = {
    "Counterpoint Research", "TrendForce", "Omdia", "IDC",
    "Yole", "Yole Group", "DigiTimes Asia", "Digitimes", "CCS Insight",
}

def _detect_domain(process_data: dict | None) -> str:
    """Majority-vote 기반 도메인 판정.

    한 보고서가 여러 도메인 출처를 섞어 인용할 수 있으므로 (예: D2D 위성통신 토픽이
    스마트폰 + 자동차 출처를 모두 인용), 단일 매칭 대신 가장 많이 인용된 도메인을 채택.
    동률·미매칭이거나 smartphone이 최다이면 smartphone fallback.
    """
    if not process_data:
        return "smartphone"
    counts = {"smartphone": 0, "humanoid": 0, "automotive": 0}
    for src in process_data.get("archive_sources", []):
        name = src.get("source_name")
        if name in _HUMANOID_SOURCES:
            counts["humanoid"] += 1
        elif name in _AUTOMOTIVE_SOURCES:
            counts["automotive"] += 1
        elif name in _SMARTPHONE_SOURCES:
            counts["smartphone"] += 1
    if counts["humanoid"] > counts["automotive"] and counts["humanoid"] > counts["smartphone"]:
        return "humanoid"
    if counts["automotive"] > counts["humanoid"] and counts["automotive"] > counts["smartphone"]:
        return "automotive"
    return "smartphone"


def _parse_report_markdown(md_text: str, process_data: dict | None = None) -> dict:
    lines = md_text.splitlines()
    topic = lines[0].lstrip("# ").strip() if lines else ""
    run_ts = ""
    for line in lines[:8]:
        if line.startswith("생성일시:"):
            run_ts = line.split(":", 1)[1].strip()
            break

    exec_summary = ""
    exec_match = re.search(r"## Executive Summary\s+(.*?)(?:\n---\n|\n##\s+\d+\.)", md_text, re.S)
    if exec_match:
        exec_summary = exec_match.group(1).strip()

    insights = []
    insights_match = re.search(r"##\s+[^\n]*Market Insights[^\n]*\n(.*)$", md_text, re.S)
    report_body = md_text[:insights_match.start()] if insights_match else md_text
    if insights_match:
        for match in re.finditer(r"###\s+\d+\.\s*(.*?)\n\n(.*?)(?=\n###\s+\d+\.|\Z)", insights_match.group(1), re.S):
            insights.append({"title": match.group(1).strip(), "body": match.group(2).strip()})

    def split_source_block(body: str) -> tuple[str, str]:
        for marker in ("**출처**", "**Sources**"):
            if marker in body:
                before, after = body.split(marker, 1)
                return before, after
        return body, ""

    sections = []
    for match in re.finditer(r"(?:^|\n)##\s+(\d+)\.\s*(.*?)\n(.*?)(?=\n##\s+\d+\.|\n---\n|\Z)", report_body, re.S):
        idx = int(match.group(1))
        title = match.group(2).strip()
        body = match.group(3).strip()
        headline = ""
        headline_match = re.search(r"\*\*(.*?)\*\*", body, re.S)
        if headline_match:
            headline = headline_match.group(1).strip()

        before_sources, source_block = split_source_block(body)
        bullets = [
            line.strip().lstrip("-*•ㆍ· ").strip()
            for line in before_sources.splitlines()
            if line.strip().startswith(("-", "*", "•", "ㆍ", "·"))
        ]
        narrative = re.sub(r"\*\*.*?\*\*", "", before_sources, count=1, flags=re.S)
        narrative = "\n".join(
            line.strip()
            for line in narrative.splitlines()
            if line.strip() and not line.strip().startswith(("-", "*", "•", "ㆍ", "·"))
        )

        sources = []
        source_re = re.compile(
            r"\[(\d+)\]\s+\[(.*?)(?:\s+(?:—|--)\s*\"(.*?)\")?\]\((.*?)\)(?:\s+\((.*?)\))?"
        )
        for src_match in source_re.finditer(source_block):
            source_name = src_match.group(2).strip()
            source_title = (src_match.group(3) or "").strip()
            url = src_match.group(4).strip()
            date_str = (src_match.group(5) or "").strip()
            detail = ""
            for bullet in bullets:
                if source_title and (source_title[:36] in bullet or bullet[:36] in source_title):
                    detail = bullet
                    break
            if not detail:
                detail = source_title or source_name
            sources.append({
                "num": src_match.group(1),
                "source_name": source_name,
                "title": source_title,
                "url": url,
                "date": date_str,
                "detail": detail,
                "metrics": _extract_metrics(source_title, detail),
            })

        sections.append({
            "index": idx,
            "title": title,
            "headline": headline,
            "narrative": narrative,
            "bullets": bullets,
            "sources": sources,
        })

    if process_data:
        for section, process_section in zip(sections, process_data.get("sections", [])):
            section["angle"] = process_section.get("angle", "")
            known_urls = {src["url"] for src in section.get("sources", [])}
            for result in process_section.get("results", [])[:8]:
                if result.get("url") in known_urls:
                    continue
                section.setdefault("supporting_results", []).append({
                    "source_name": result.get("source_name", ""),
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "detail": result.get("title", ""),
                    "metrics": _extract_metrics(result.get("title", "")),
                })

    references = []
    for section in sections:
        for source in section.get("sources", []):
            references.append({**source, "section": section["title"], "section_index": section["index"]})

    research_background = ""
    if process_data:
        research_background = (process_data.get("meta") or {}).get("research_background", "")

    return {
        "topic": topic,
        "run_ts": run_ts,
        "research_background": research_background,
        "executive_summary": exec_summary,
        "sections": sections,
        "insights": insights,
        "references": references,
    }


@app.get("/api/reports")
async def api_reports_list():
    reports_dir = ROOT / "reports"
    items = []
    for md_path in sorted(reports_dir.glob("*_report.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        slug = md_path.name.removesuffix("_report.md")
        process_path = reports_dir / f"{slug}_process.json"
        process_data = None
        if process_path.exists():
            try:
                process_data = json.loads(process_path.read_text(encoding="utf-8"))
            except Exception:
                process_data = None

        try:
            report = _parse_report_markdown(md_path.read_text(encoding="utf-8"), process_data)
        except Exception:
            report = {"topic": slug, "run_ts": "", "executive_summary": "", "sections": [], "references": []}

        stat = md_path.stat()
        metric_tags = []
        for ref in report.get("references", []):
            for metric in ref.get("metrics", []):
                if metric not in metric_tags:
                    metric_tags.append(metric)
        items.append({
            "slug": slug,
            "topic": report.get("topic") or slug,
            "run_ts": report.get("run_ts", ""),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "summary": (report.get("executive_summary") or "").strip(),
            "section_count": len(report.get("sections", [])),
            "reference_count": len(report.get("references", [])),
            "metric_tags": metric_tags[:8],
            "domain": _detect_domain(process_data),
        })

    return {"reports": items}


@app.get("/api/reports/{slug}")
async def api_report_detail(slug: str):
    safe_slug = Path(slug).name
    md_path = ROOT / "reports" / f"{safe_slug}_report.md"
    process_path = ROOT / "reports" / f"{safe_slug}_process.json"
    if not md_path.exists() or not md_path.is_file():
        raise HTTPException(404, "report not found")

    process_data = None
    if process_path.exists():
        try:
            process_data = json.loads(process_path.read_text(encoding="utf-8"))
        except Exception:
            process_data = None

    report = _parse_report_markdown(md_path.read_text(encoding="utf-8"), process_data)
    return {"slug": safe_slug, "domain": _detect_domain(process_data), **report}


@app.delete("/api/reports/{slug}")
async def api_report_delete(slug: str):
    safe_slug = Path(slug).name
    reports_dir = ROOT / "reports"
    deleted = []
    for suffix in ("_report.md", "_report.html", "_process.json"):
        path = reports_dir / f"{safe_slug}{suffix}"
        if path.exists() and path.is_file():
            path.unlink()
            deleted.append(path.name)
    if not deleted:
        raise HTTPException(404, "report not found")
    return {"deleted": deleted}


@app.get("/reports/{filename}")
async def serve_report_file(filename: str):
    path = ROOT / "reports" / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(path)


@app.post("/api/report/start")
async def api_report_start(req: Request):
    body = await req.json()
    topic = (body.get("topic") or "").strip()
    if not topic:
        raise HTTPException(400, "topic required")
    domain_id = body.get("domain", "smartphone")
    sess = ReportSession(topic, domain_id=domain_id)
    REPORT_SESSIONS[sess.id] = sess
    sess.task = asyncio.create_task(_run_report(sess))
    return {"session_id": sess.id}


@app.get("/api/report/stream/{sid}")
async def api_report_stream(sid: str):
    sess = REPORT_SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "session not found")

    async def gen():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(sess.queue.get(), timeout=20)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") == "done":
                    break
        except asyncio.CancelledError:
            return

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/report/cancel/{sid}")
async def api_report_cancel(sid: str):
    sess = REPORT_SESSIONS.pop(sid, None)
    if sess and sess.task and not sess.task.done():
        sess.task.cancel()
    return {"ok": True}


@app.post("/api/report/ext_decision")
async def api_report_ext_decision(req: Request):
    body = await req.json()
    sid = body.get("session_id")
    sess = REPORT_SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    sess.ext_use_external = bool(body.get("use_external", False))
    sess.ext_event.set()
    return {"ok": True}


@app.post("/api/report/gate1")
async def api_report_gate1(req: Request):
    body = await req.json()
    sid = body.get("session_id")
    sess = REPORT_SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    sess.gate1_data = body.get("sections", [])
    sess.gate1_event.set()
    return {"ok": True}


@app.post("/api/report/gate2")
async def api_report_gate2(req: Request):
    body = await req.json()
    sid = body.get("session_id")
    sess = REPORT_SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    proceed = bool(body.get("proceed", True))
    sections = body.get("sections", [])
    sess.gate2_data = (proceed, sections)
    sess.gate2_event.set()
    return {"ok": True}


# SPA fallback — must be registered LAST so API routes take priority
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
