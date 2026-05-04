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

from src.models import (
    PipelineState,
    ResearchPlan,
    Topic,
    DimensionProposal,
)
from src.state_machine import AnalysisPipeline

ROOT = Path(__file__).parent.parent
INDEX_HTML     = ROOT / "index.html"
DASHBOARD_HTML = ROOT / "web" / "dashboard.html"
ARCHIVES_DIR   = ROOT / "data" / "archives"
ALL_ARCHIVES_SCRIPT = ROOT / "scripts" / "build_all_archives.py"

# UI 표시명 → archive JSON 파일명 (build_all_archives.py와 동일 순서)
ARCHIVE_REGISTRY = [
    ("Counterpoint Research", "counterpoint.json"),
    ("TrendForce",            "trendforce.json"),
    ("Omdia",                 "omdia.json"),
    ("IDC",                   "idc.json"),
    ("Reuters",               "reuters.json"),
    ("Yole",                  "yole.json"),
    ("Gartner",               "gartner.json"),
    ("Morgan Stanley",        "morgan_stanley.json"),
    ("Naver Research",        "naver_research.json"),
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Session management ─────────────────────────────────────────────────────
class Session:
    def __init__(self, topic: str):
        self.id = str(uuid.uuid4())
        self.topic = topic
        self.pipeline = AnalysisPipeline()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.plan: Optional[ResearchPlan] = None
        self.task: Optional[asyncio.Task] = None
        self.dim_feedback_event: asyncio.Event = asyncio.Event()
        self.dim_feedback: str = ""

    async def emit(self, **kwargs):
        await self.queue.put(kwargs)


SESSIONS: dict[str, Session] = {}


# ── Log → event parser ─────────────────────────────────────────────────────
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


# ── Pipeline runners ───────────────────────────────────────────────────────
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
        # A→B→C: 5개 차원 제안
        proposal = await pipeline.plan_propose(sess.topic, progress_cb=cb)
        pre_urls = getattr(pipeline, '_pre_search_urls', [])
        await sess.emit(
            type="dimension_proposal",
            proposal=proposal.model_dump(),
            pre_urls=pre_urls,
        )

        # 사용자 피드백 대기 (최대 5분)
        try:
            await asyncio.wait_for(sess.dim_feedback_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            await sess.emit(type="error", text="차원 선택 대기 시간 초과 (5분)")
            return
        feedback = sess.dim_feedback

        # 피드백 반영 → 최종 ResearchPlan
        plan = await pipeline.plan_finalize(sess.topic, proposal, feedback, progress_cb=cb)
        sess.plan = plan
        eng = getattr(pipeline, '_eng_topic', sess.topic)
        pipeline.state = PipelineState(topic=Topic(title=sess.topic, eng_title=eng))
        plan_dict = plan.model_dump()

        # E→F→G→H: 차원별 분석
        mindmap = await pipeline.analyze_by_dimensions(sess.topic, plan, progress_cb=cb)

        await sess.emit(type="phase0_done", plan=plan_dict, pre_urls=pre_urls, mindmap=mindmap)
        await sess.emit(type="done")
    except asyncio.CancelledError:
        return
    except Exception as e:
        await sess.emit(type="error", text=f"Phase 0 오류: {e}")


# ── Endpoints ──────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return FileResponse(INDEX_HTML)


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


# ══════════════════════════════════════════════════════════════════════════
# Archive Dashboard — DB 자동 수집 컨트롤
# ══════════════════════════════════════════════════════════════════════════

# job_id → asyncio.Queue (SSE 라인 버퍼)
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
    """build_all_archives.py 를 subprocess로 띄우고 stdout 줄을 큐에 넣음."""
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


# ══════════════════════════════════════════════════════════════════════════
# Topic Analysis — DB 기반 주제 자동 선정
# ══════════════════════════════════════════════════════════════════════════

TIER1_SOURCES = {"Counterpoint Research", "TrendForce", "Omdia", "IDC", "Morgan Stanley"}

_KW_PATH = ROOT / "data" / "smartphone_keywords.json"
SMARTPHONE_KW: list[str] = json.loads(_KW_PATH.read_text(encoding="utf-8"))["keywords"]

def _is_smartphone(entry: dict) -> bool:
    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
    return any(kw in text for kw in SMARTPHONE_KW)


@app.get("/api/keywords")
async def api_keywords_get():
    """현재 스마트폰 필터링 키워드 목록 반환."""
    data = json.loads(_KW_PATH.read_text(encoding="utf-8"))
    return {"keywords": data["keywords"], "count": len(data["keywords"])}


@app.put("/api/keywords")
async def api_keywords_put(req: Request):
    """키워드 목록 전체 교체 (add/remove 후 전체 리스트 전달)."""
    body = await req.json()
    keywords = body.get("keywords")
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        raise HTTPException(400, "keywords must be a list of strings")
    keywords = [k.strip().lower() for k in keywords if k.strip()]
    if not keywords:
        raise HTTPException(400, "keywords list cannot be empty")
    data = json.loads(_KW_PATH.read_text(encoding="utf-8"))
    data["keywords"] = keywords
    _KW_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # 서버 메모리도 즉시 반영
    global SMARTPHONE_KW
    SMARTPHONE_KW = keywords
    return {"ok": True, "count": len(keywords)}


@app.get("/api/topics/mine")
async def api_topics_mine(days: int = 30):
    """최근 N일 Tier-1 소스 스마트폰 관련 기사를 소스별로 묶어 반환."""
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

    # 스마트폰 관련 기사만
    sm = [e for e in recent if _is_smartphone(e)]

    # 소스별 그룹화
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
                    "title":       e.get("title", "").replace("‑", "-").replace("’", "'"),
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


# ══════════════════════════════════════════════════════════════════════════
# Report Generation — run_report.py 파이프라인 웹 UI 브릿지
# ══════════════════════════════════════════════════════════════════════════

class ReportSession:
    def __init__(self, topic: str):
        self.id = str(uuid.uuid4())
        self.topic = topic
        self.queue: asyncio.Queue = asyncio.Queue()
        self.task: Optional[asyncio.Task] = None
        self.gate1_event: asyncio.Event = asyncio.Event()
        self.gate1_data: Optional[list] = None
        self.gate2_event: asyncio.Event = asyncio.Event()
        self.gate2_data: Optional[tuple] = None  # (proceed: bool, sections: list)

    async def emit(self, **kwargs):
        await self.queue.put(kwargs)


REPORT_SESSIONS: dict[str, "ReportSession"] = {}


def _sec_to_dict(sec: dict) -> dict:
    """GATE 1용 섹션 직렬화 (results 미포함)."""
    return {
        "title": sec.get("title", ""),
        "causal_role": sec.get("causal_role", "analysis"),
        "angle": sec.get("angle", ""),
        "queries": list(sec.get("queries", [])),
        "included": list(sec.get("included", [])),
    }


def _sec_with_results_to_dict(sec: dict) -> dict:
    """GATE 2용 섹션 직렬화 (results 포함)."""
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
    """브라우저 응답 dict를 원본 섹션에 병합 (results 등 보존)."""
    sec = dict(orig)
    queries = list(confirmed.get("queries", orig.get("queries", [])))
    included = list(confirmed.get("included", [True] * len(queries)))
    while len(included) < len(queries):
        included.append(True)
    sec["queries"] = queries
    sec["included"] = included[:len(queries)]
    sec["title"] = confirmed.get("title", orig.get("title", ""))
    return sec


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
        await sess.emit(type="report_log", text="[A] 영문 쿼리 생성 중...")
        pre_queries, eng_topic = await stage_a(llm, topic)
        search.set_core_terms(eng_topic, current_year=str(_year()))
        await sess.emit(type="report_step_a", queries=pre_queries, eng_topic=eng_topic)
        await sess.emit(type="report_log", text=f"쿼리 {len(pre_queries)}개 생성")

        # B
        await sess.emit(type="report_log", text="[B] Archive 검색 중...")
        archive_results = await stage_b(search, pre_queries, eng_kw=eng_topic)
        by_source: dict[str, list] = {}
        for r in archive_results:
            by_source.setdefault(r.source_name, []).append({
                "title": r.article_title or "",
                "url": r.source_url,
            })
        await sess.emit(type="report_step_b", by_source=by_source, total=len(archive_results))
        await sess.emit(type="report_log", text=f"Archive {len(archive_results)}건 수집")

        use_external = False

        # C
        await sess.emit(type="report_step_c")
        await sess.emit(type="report_log", text="[C] 목차 생성 중...")
        sections = await stage_c(llm, topic, archive_results)
        _warn_section_overlap(sections)
        await sess.emit(type="report_log", text=f"목차 {len(sections)}개 생성")

        # GATE 1
        sess.gate1_event.clear()
        sess.gate1_data = None

        async def gate1_cb(secs):
            await sess.emit(type="report_gate1", sections=[_sec_to_dict(s) for s in secs])
            try:
                await asyncio.wait_for(sess.gate1_event.wait(), timeout=600)
            except asyncio.TimeoutError:
                await sess.emit(type="report_log", text="GATE 1 타임아웃 — 자동 확정")
                return secs
            confirmed = sess.gate1_data or []
            result = []
            for i, orig in enumerate(secs):
                cd = confirmed[i] if i < len(confirmed) else {}
                result.append(_merge_sec(cd, orig) if cd else orig)
            return result

        sections = await user_gate_1(sections, auto=False, gate_cb=gate1_cb)
        await sess.emit(type="report_log", text="목차 확정")

        # D↔D' 루프
        refine_round = 0
        max_rounds = 3
        while refine_round < max_rounds:
            await sess.emit(type="report_log", text="[D] 검색 실행 중...")
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
                    await asyncio.wait_for(_ev.wait(), timeout=600)
                except asyncio.TimeoutError:
                    await sess.emit(type="report_log", text="GATE 2 타임아웃 — 분석 진행")
                    return True, secs
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
            await sess.emit(type="report_log", text=f"쿼리 보완 후 재검색 (라운드 {refine_round + 1})")

        # E+F
        await sess.emit(type="report_log", text="[E/F] 목차별 분석 시작...")

        async def ef_progress(si, total, title):
            await sess.emit(type="report_log", text=f"  [{si}/{total}] {title} 분석 중...")

        sections = await stage_ef(llm, topic, sections, progress_cb=ef_progress)

        # G
        await sess.emit(type="report_log", text="[G] 시사점 생성 중...")
        meta = await stage_g(llm, topic, sections)

        # 저장
        await sess.emit(type="report_log", text="저장 중...")
        md_path, html_path = _save_report(topic, sections, run_ts, archive_results, pre_queries, meta)

        await sess.emit(type="report_done", report_url=f"/reports/{html_path.name}")
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
    sess = ReportSession(topic)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
