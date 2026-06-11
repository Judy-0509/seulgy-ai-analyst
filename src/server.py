"""FastAPI server: serves the React UI and bridges to the run_report.py report pipeline via SSE."""
import asyncio
import json
import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.auth import require_member, require_admin, require_admin_query, is_admin, require_team
import src.page_access as page_access
from src.roles import role_of, add_team, remove_team, list_team, request_team, list_requests, approve_request, reject_request, is_requested
from src.feedback_store import (
    add_feedback, list_mine, list_all, update_status,
    ALLOWED_TARGET_TYPE,
)

from src.services.token_logger import read_all as read_token_log
from src.services.en_summary import load_en_summary
from src.news_api import router as news_router
from src.domains import load_domain

ROOT = Path(__file__).parent.parent
FRONTEND_DIST  = ROOT / "frontend" / "dist"
DASHBOARD_HTML = ROOT / "web" / "dashboard.html"
ONBOARDING_HTML = ROOT / "onboarding.html"
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
    ("Humanoids Daily",            "humanoids_daily.json"),
    ("RoboticsTomorrow",           "robotics_tomorrow.json"),
    ("IDTechEx",                   "idtechex_humanoid.json"),
    ("ABI Research",               "abi_humanoid.json"),
    ("Yano Research",              "yano_humanoid.json"),
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
    ("Goldman Sachs Research",     "goldman_sachs.json"),
    ("Morgan Stanley Research",    "morgan_stanley.json"),
    ("Barclays Research",          "barclays.json"),
    ("Bank of America Institute",  "bofa_institute.json"),
    # Automotive sources
    ("WardsAuto",          "wardsauto.json"),
    ("Cox Automotive",     "cox_automotive.json"),
    ("AlixPartners",       "alixpartners.json"),
    ("SAE International",  "sae.json"),
    ("JATO Dynamics",      "jato.json"),
    ("Automotive Dive",    "automotive_dive.json"),
    ("Automotive World",   "automotive_world.json"),
    ("Electrek",           "electrek.json"),
    ("InsideEVs",          "insideevs.json"),
    ("VW Group",           "vw_group.json"),
    ("Toyota Newsroom",    "toyota.json"),
    ("CnEVPost",           "cnevpost.json"),
    ("CarNewsChina",       "carnewschina.json"),
    ("ICCT",               "icct.json"),
    ("ACEA",               "acea.json"),
    ("BloombergNEF",       "bnef.json"),
    ("RMI",                "rmi.json"),
    ("Transport & Environment", "transport_environment.json"),
    ("IRENA",              "irena.json"),
    # Space Datacenter sources
    ("SpaceNews",             "spacenews.json"),
    ("Space.com",             "spacecom.json"),
    ("IEEE Spectrum (Space)", "ieee_spectrum_space.json"),
    ("Data Center Knowledge", "datacenter_knowledge.json"),
    ("Data Center Frontier",  "datacenter_frontier.json"),
    ("TechCrunch (Space)",    "techcrunch_space.json"),
    ("arXiv (cs.DC)",         "arxiv_space.json"),
    # Smartglass sources
    ("UploadVR",        "uploadvr.json"),
    ("The Ghost Howls", "skarredghost.json"),
    ("Road to VR",      "roadtovr.json"),
    ("AR Insider",      "arinsider.json"),
    ("KGOnTech",        "kgontech.json"),
    ("Meta Newsroom",   "meta_newsroom.json"),
    ("Rokid",           "rokid.json"),
    ("Citi Research",   "citi.json"),
]

app = FastAPI()
USER_ACTION_TIMEOUT_SECONDS = 600


@app.on_event("startup")
def _startup() -> None:
    from src.news_db import init_db
    init_db()
    if os.getenv("ENABLE_MI_NEWS_SCHEDULER", "").lower() in {"1", "true", "yes", "on"}:
        from src.news_scheduler import start_scheduler
        start_scheduler()


_cors = os.environ.get(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://localhost:8000,http://127.0.0.1:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(news_router)


# 모든 응답에 적용하는 보안 헤더. CSP는 frame-ancestors만 지정(인라인 스타일 다수라
# strict CSP는 UI를 깨뜨릴 수 있어 클릭재킹 방어 범위로 한정). HSTS는 HTTPS에서만 효력.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


@app.middleware("http")
async def security_and_cache_headers(request: Request, call_next):
    response = await call_next(request)
    for _k, _v in SECURITY_HEADERS.items():
        response.headers.setdefault(_k, _v)
    accept = request.headers.get("accept", "")
    if request.url.path.startswith("/api/") or "text/html" in accept:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# frontend/dist 빌드가 있으면 정적 파일 서빙 (npm run build 후 사용)
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


# (2026-05-30 제거) 레거시 Phase0 dimension-proposal 흐름:
#   Session/SESSIONS, parse_log, _run_phase0 및 /api/start·/api/cancel·
#   /api/confirm_dimensions·/api/stream 엔드포인트를 제거했다. frontend는 더 이상 호출하지 않으며,
#   활성 보고서 경로는 ReportSession + /api/report/* (run_report.py stage_a~g)다.
#   state_machine.AnalysisPipeline 클래스는 tests에서 계속 사용하므로 보존.


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


@app.get("/onboarding")
async def onboarding():
    if not ONBOARDING_HTML.exists():
        raise HTTPException(404, "onboarding.html not found")
    return FileResponse(ONBOARDING_HTML)


@app.get("/api/archives/status")
async def api_archives_status():
    archives = [_archive_status_one(n, j) for n, j in ARCHIVE_REGISTRY]
    return {
        "archives": archives,
        "total_entries": sum(a["entry_count"] for a in archives),
        "ts": datetime.now().isoformat(),
    }


@app.get("/api/me")
async def api_me(user: dict = Depends(require_member)):
    """현재 로그인 사용자의 이메일, 관리자 여부, 부여된 페이지 목록을 반환."""
    email = user.get("email", "")
    admin = is_admin(user)
    pages = list(page_access.VALID_PAGES) if admin else page_access.granted_pages(email)
    return {"email": email, "is_admin": admin, "pages": pages, "role": role_of(user), "role_requested": is_requested(email)}


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
async def api_archives_refresh(_user: dict = Depends(require_admin)):
    job_id = uuid.uuid4().hex[:8]
    ARCHIVE_JOBS[job_id] = asyncio.Queue()
    asyncio.create_task(_run_archive_orchestrator(job_id))
    return {"job_id": job_id}


@app.get("/api/archives/stream/{job_id}")
async def api_archives_stream(job_id: str, _user: dict = Depends(require_admin_query)):
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
async def api_keywords_get(domain: str = "smartphone", _user: dict = Depends(require_team)):
    """도메인별 필터링 키워드 목록 반환."""
    cfg = load_domain(domain)
    kw_path = ROOT / cfg["keywords_file"]
    data = json.loads(kw_path.read_text(encoding="utf-8"))
    return {"keywords": data["keywords"], "count": len(data["keywords"]), "domain": domain}


@app.put("/api/keywords")
async def api_keywords_put(req: Request, domain: str = "smartphone", _user: dict = Depends(require_admin)):
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
async def api_topics_mine(days: int = 30, domain: str = "smartphone", _user: dict = Depends(require_team)):
    """최근 N일 Tier-1 소스의 도메인 관련 기사를 소스별로 묶어 반환."""
    import re as _re

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
async def api_archives_entries(source: str, limit: int = 300, _user: dict = Depends(require_team)):
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


# Page Access — 권한 신청 / 승인 엔드포인트

@app.post("/api/access/request")
async def api_access_request(req: Request, user: dict = Depends(require_member)):
    """멤버가 특정 페이지의 접근 권한을 신청한다."""
    body = await req.json()
    pg = (body.get("page") or "").strip().lower()
    if pg not in page_access.VALID_PAGES:
        raise HTTPException(400, f"유효하지 않은 페이지입니다. 허용값: {sorted(page_access.VALID_PAGES)}")
    email = (user.get("email") or "").strip().lower()
    page_access.request_access(email, pg)
    return {"ok": True}


@app.get("/api/access/requests")
async def api_access_requests(_user: dict = Depends(require_admin)):
    """관리자: 대기 중인 권한 신청 목록을 반환한다."""
    return {"requests": page_access.list_requests("pending")}


@app.post("/api/access/approve")
async def api_access_approve(req: Request, _user: dict = Depends(require_admin)):
    """관리자: 권한 신청을 승인한다."""
    body = await req.json()
    email = (body.get("email") or "").strip().lower()
    pg = (body.get("page") or "").strip().lower()
    if not email or pg not in page_access.VALID_PAGES:
        raise HTTPException(400, "email 과 유효한 page 가 필요합니다")
    page_access.approve(email, pg)
    return {"ok": True}


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
    from src.prompts.system import DOMAIN_SYSTEM_PROMPTS, DOMAIN_ANALYST_TYPES, ANALYST_SYSTEM_PROMPT
    from datetime import datetime as _dt

    search = None
    try:
        llm = LLMService()
        search = SearchService(domain=sess.domain_id)
        run_ts = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        topic = sess.topic
        # 도메인 페르소나/시스템 프롬프트를 요청 단위로 해석해 stage에 인자로 전달
        # (전역 상태 미사용 → 동시 멀티도메인 보고서 교차 오염 방지)
        _sys_prompt = DOMAIN_SYSTEM_PROMPTS.get(sess.domain_id, ANALYST_SYSTEM_PROMPT)
        _analyst_type = DOMAIN_ANALYST_TYPES.get(sess.domain_id, "senior smartphone market analyst")
        _dom_cfg = load_domain(sess.domain_id)
        _player_examples = _dom_cfg.get("player_examples", "Samsung, Apple, Xiaomi, Huawei")
        _example_topic = _dom_cfg.get("example_topic", "foldable smartphones")

        await sess.emit(type="report_log", text="보고서 생성 시작")

        # A
        await sess.emit(type="report_log", text="영문 쿼리 생성 중...")

        async def stage_a_progress(**event):
            await sess.emit(type="report_step_a_trace", **event)

        pre_queries, eng_topic = await stage_a(llm, topic, progress_cb=stage_a_progress,
                                               system_prompt=_sys_prompt, analyst_type=_analyst_type,
                                               player_examples=_player_examples, example_topic=_example_topic)
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

        # Humanoid reports should always include current web context. The
        # domain archive is intentionally broad, but source depth is uneven.
        if sess.domain_id == "humanoid":
            use_external = True
            sess.ext_use_external = True
            await sess.emit(type="report_log", text="Humanoid 도메인: 외부 검색을 자동으로 포함합니다.")
        else:
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
        sections = await stage_c(llm, topic, archive_results,
                                 system_prompt=_sys_prompt, analyst_type=_analyst_type,
                                 player_examples=_player_examples, example_topic=_example_topic)
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

        sections = await stage_ef(llm, topic, sections, progress_cb=ef_progress,
                                  system_prompt=_sys_prompt, analyst_type=_analyst_type,
                                  player_examples=_player_examples, example_topic=_example_topic)

        # G
        await sess.emit(type="report_log", text="시사점 생성 중...")
        meta = await stage_g(llm, topic, sections,
                             system_prompt=_sys_prompt, analyst_type=_analyst_type,
                             player_examples=_player_examples, example_topic=_example_topic)

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
    if not (ROOT / "data" / "domains" / f"{domain}.json").exists():
        return {"topics": [], "generated_at": None, "days": 30, "history_by_week": []}
    domain_cfg = load_domain(domain)
    p = ROOT / domain_cfg["suggested_path"]
    topics: list[dict] = []
    generated_at = None
    days = 30
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            topics = [t for t in data.get("topics", []) if isinstance(t, dict)]
            generated_at = data.get("generated_at")
            days = data.get("days", 30)
        except Exception:
            pass

    def _latest_article_date(t: dict, fallback: str = "") -> str:
        dates = [a.get("date", "") for a in t.get("articles", []) if a.get("date")]
        return max(dates) if dates else fallback

    # Sort current topics by trend rank when available; older files fall back to recency.
    cur_fallback = (generated_at or "")[:10]
    if any((t.get("trend") or {}).get("rank") for t in topics if isinstance(t, dict)):
        topics.sort(key=lambda t: (t.get("trend") or {}).get("rank") or 9999)
    else:
        topics.sort(key=lambda t: _latest_article_date(t, cur_fallback), reverse=True)

    # Load history files: scripts/_history/{domain}_*.json (up to 8 previous weeks)
    hist_dir = p.parent / "_history"
    history_by_week: list[dict] = []
    current_week = cur_fallback
    if hist_dir.exists():
        seen_weeks: set[str] = set()
        for hf in sorted(hist_dir.glob(f"{domain}_*.json"), reverse=True):
            try:
                hdata = json.loads(hf.read_text(encoding="utf-8"))
                week_of = (hdata.get("generated_at") or "")[:10]
                if not week_of or week_of == current_week or week_of in seen_weeks:
                    continue
                seen_weeks.add(week_of)
                week_topics = list(hdata.get("topics", []))
                # orig_crit2: original rank order from the file (before UI re-sort)
                orig_crit2 = [t for t in week_topics if isinstance(t, dict) and t.get("criteria") != "Criterion 3"]
                week_topics.sort(key=lambda t: _latest_article_date(t, week_of), reverse=True)
                history_by_week.append({"week_of": week_of, "topics": week_topics, "orig_crit2": orig_crit2})
                if len(history_by_week) >= 8:
                    break
            except Exception:
                pass
        history_by_week.sort(key=lambda w: w["week_of"], reverse=True)

    # Merge emerging "Curiosity Pick" topics (weekly pass — smartphone, humanoid, automotive).
    # All emerging topics carry criteria="Criterion 3" so frontend's existing
    # Crit2/Crit3 split surfaces them in the "이번 주 새롭게 등장한 주제" section.
    EMERGING_PATHS = {
        "smartphone":      "scripts/_topic_suggestions_emerging.json",
        "humanoid":        "scripts/_humanoid_topic_suggestions_emerging.json",
        "automotive":      "scripts/_automotive_topic_suggestions_emerging.json",
        "space_datacenter": "scripts/_space_datacenter_topic_suggestions_emerging.json",
        "smartglass":      "scripts/_smartglass_topic_suggestions_emerging.json",
    }
    em_rel = EMERGING_PATHS.get(domain)
    if em_rel:
        emerging_path = ROOT / em_rel
        if emerging_path.exists():
            try:
                em_data = json.loads(emerging_path.read_text(encoding="utf-8"))
                em_generated = (em_data.get("generated_at") or "")[:10]
                em_days = em_data.get("days", 7)
                # clamp article dates: LLM sometimes hallucinates old pub dates.
                # Any supporting article older than em_days*2 from generated_at
                # gets its date replaced with generated_at to avoid stale "N일 전" display.
                try:
                    _gen_date = date.fromisoformat(em_generated) if em_generated else date.today()
                except ValueError:
                    _gen_date = date.today()
                _max_age = timedelta(days=em_days * 2)
                for t in em_data.get("topics", []):
                    if not isinstance(t, dict):
                        continue
                    t["criteria"] = "Criterion 3"
                    t.setdefault("source", "emerging")
                    for art in t.get("articles", []):
                        try:
                            art_date = date.fromisoformat(art.get("date", "")[:10])
                            if (_gen_date - art_date) > _max_age:
                                art["date"] = em_generated
                        except (ValueError, TypeError):
                            pass
                    topics.append(t)
            except Exception:
                pass

    def _apply_report_slug(topic_list: list[dict]) -> None:
        for topic in topic_list:
            if not isinstance(topic, dict):
                continue
            title = str(topic.get("title") or "").strip()
            slug = str(topic.get("report_slug") or "").strip() or _topic_to_report_slug(title)
            if slug and (ROOT / "reports" / f"{slug}_report.md").exists():
                topic["report_slug"] = slug
            else:
                topic.pop("report_slug", None)

    _apply_report_slug(topics)
    for week in history_by_week:
        _apply_report_slug(week["topics"])

    # Assign rank + rank_change to Crit 2 topics.
    # rank_change = prev_rank - cur_rank  (positive → moved up, negative → dropped)
    # rank_change = None → topic is new (no prior history match)
    crit2 = [t for t in topics if isinstance(t, dict) and t.get("criteria") != "Criterion 3"]
    for i, t in enumerate(crit2):
        t["rank"] = i + 1

    def _title_tokens(title: str) -> set[str]:
        """핵심 키워드 추출 — 영한 회사명 정규화 + 조사 제거."""
        import re as _re
        _EN_KO = {
            "huawei": "화웨이", "samsung": "삼성", "apple": "애플",
            "tsmc": "tsmc", "nvidia": "엔비디아", "qualcomm": "퀄컴",
            "mediatek": "미디어텍", "arm": "arm",
        }
        _JOSA = re.compile(r"(을|를|이|가|은|는|에|의|와|과|도|로|으로|에서|까지|부터|만|들)$")
        normalized = title.lower()
        for en, ko in _EN_KO.items():
            normalized = normalized.replace(en, ko)
        words = _re.split(r"[\s\(\)·/,·\-\·\.'\"]+", normalized)
        tokens = set()
        for w in words:
            w = _JOSA.sub("", w)
            if len(w) >= 2:
                tokens.add(w)
        return tokens

    def _best_prev_rank(title: str, prev_list: list[dict]) -> int | None:
        cur_tokens = _title_tokens(title)
        if not cur_tokens:
            return None
        best_score, best_rank = 0.0, None
        for i, pt in enumerate(prev_list):
            pt_tokens = _title_tokens(str(pt.get("title") or ""))
            if not pt_tokens:
                continue
            overlap = len(cur_tokens & pt_tokens) / len(cur_tokens | pt_tokens)
            if overlap > best_score:
                best_score, best_rank = overlap, i + 1
        # 20% 이상 겹치면 같은 주제로 판단
        return best_rank if best_score >= 0.2 else None

    prev_crit2: list[dict] = []
    if history_by_week:
        # Use orig_crit2 (pre-sort order = original rank order from the file)
        prev_crit2 = history_by_week[0].get("orig_crit2", [])
        if not prev_crit2:
            prev_crit2 = [
                t for t in history_by_week[0].get("topics", [])
                if isinstance(t, dict) and t.get("criteria") != "Criterion 3"
            ]

    for t in crit2:
        title = str(t.get("title") or "").strip()
        prev = _best_prev_rank(title, prev_crit2)
        t["rank_change"] = (prev - t["rank"]) if prev is not None else None

    # Assign rank + rank_change to each history week's Crit 2 topics
    for week_idx, week in enumerate(history_by_week):
        week_orig = week.get("orig_crit2", [])
        # Build a fast title→rank map from original order
        orig_rank_map = {str(t.get("title") or "").strip(): i + 1 for i, t in enumerate(week_orig)}
        # The week before this one (for rank_change)
        older_crit2: list[dict] = []
        if week_idx + 1 < len(history_by_week):
            older_crit2 = history_by_week[week_idx + 1].get("orig_crit2", [])
        for t in week.get("topics", []):
            if not isinstance(t, dict) or t.get("criteria") == "Criterion 3":
                continue
            title = str(t.get("title") or "").strip()
            # rank: original position in this week's file
            t["rank"] = orig_rank_map.get(title, None)
            # rank_change: vs the week before this one
            if older_crit2:
                prev_r = _best_prev_rank(title, older_crit2)
                cur_r = t["rank"]
                t["rank_change"] = (prev_r - cur_r) if (prev_r is not None and cur_r is not None) else None
            else:
                t["rank_change"] = None

    return {
        "topics": topics,
        "history_by_week": history_by_week,
        "generated_at": generated_at,
        "days": days,
    }


@app.get("/api/usage")
async def api_usage(_user: dict = Depends(require_admin)):
    """GLM 토큰 사용량 및 비용 집계 (USD primary, CNY backward-compat)."""
    from collections import defaultdict
    from src.services.token_logger import _price_for
    raw_entries = read_token_log()
    entries = []
    for e in raw_entries:
        try:
            prompt_tokens = int(e.get("prompt_tokens") or 0)
            completion_tokens = int(e.get("completion_tokens") or 0)
        except (TypeError, ValueError):
            continue
        # cost_usd 우선, 없으면 PRICING 으로 fallback 계산 (구 entry 호환)
        cost_usd = e.get("cost_usd")
        if cost_usd is None:
            price = _price_for(str(e.get("model") or "unknown"))
            cost_usd = (prompt_tokens * price["input"] + completion_tokens * price["output"]) / 1_000_000
        try:
            cost_usd = float(cost_usd)
        except (TypeError, ValueError):
            cost_usd = 0.0
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
            "cost_usd": cost_usd,
            "cost_cny": 0.0,  # legacy field, deprecated (값 0)
            "caller": str(e.get("caller") or ""),
        })
    if not entries:
        return {"summary": {}, "by_model": [], "by_day": [], "recent": []}

    total_prompt = sum(e["prompt_tokens"] for e in entries)
    total_completion = sum(e["completion_tokens"] for e in entries)
    total_cost_usd = sum(e["cost_usd"] for e in entries)

    by_model: dict = defaultdict(lambda: {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "calls": 0})
    by_day:   dict = defaultdict(lambda: {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "calls": 0})
    for e in entries:
        m = by_model[e["model"]]
        m["prompt_tokens"]     += e["prompt_tokens"]
        m["completion_tokens"] += e["completion_tokens"]
        m["cost_usd"]          += e["cost_usd"]
        m["calls"]             += 1
        day = e["ts"][:10] or "unknown"
        d = by_day[day]
        d["prompt_tokens"]     += e["prompt_tokens"]
        d["completion_tokens"] += e["completion_tokens"]
        d["cost_usd"]          += e["cost_usd"]
        d["calls"]             += 1

    return {
        "summary": {
            "total_prompt_tokens":     total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens":            total_prompt + total_completion,
            "total_cost_usd":          round(total_cost_usd, 6),
            "total_cost_cny":          0.0,  # legacy, deprecated
            "call_count":              len(entries),
        },
        "by_model": [{"model": k, **v, "cost_usd": round(v["cost_usd"], 6)} for k, v in sorted(by_model.items())],
        "by_day":   [{"day": k,   **v, "cost_usd": round(v["cost_usd"], 6)} for k, v in sorted(by_day.items(), reverse=True)],
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
    "Humanoids Daily", "RoboticsTomorrow", "IDTechEx", "ABI Research", "Yano Research",
    "Apptronik", "Agility Robotics",
    "1X Technologies", "IFR", "NVIDIA News", "Unitree",
    "Goldman Sachs Research", "Morgan Stanley Research", "Barclays Research",
    "Bank of America Institute",
}

_AUTOMOTIVE_SOURCES = {
    "JATO Dynamics", "AlixPartners", "WardsAuto", "SAE International",
    "VW Group", "Mercedes-Benz Media", "Cox Automotive", "Automotive Dive",
    "Automotive World", "Electrek", "InsideEVs", "Toyota Newsroom",
    "CnEVPost", "CarNewsChina", "ICCT", "ACEA",
    "BloombergNEF", "RMI", "Transport & Environment", "IRENA",
    # 스마트폰 트래커는 _SMARTPHONE_SOURCES에 그대로 — 도메인 판정 majority vote 보존
}

_SMARTPHONE_SOURCES = {
    "Counterpoint Research", "TrendForce", "Omdia", "IDC",
    "Yole", "Yole Group", "DigiTimes Asia", "Digitimes", "CCS Insight",
}

def _detect_domain(process_data: dict | None) -> str:
    """도메인 판정: process.json에 domain 필드가 있으면 그것을 우선 사용.
    없으면 archive_sources majority-vote fallback.
    """
    if not process_data:
        return "smartphone"
    stored = process_data.get("domain", "")
    if stored in ("smartphone", "humanoid", "automotive", "space_datacenter", "smartglass"):
        return stored
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

    references_by_key = {}
    for section in sections:
        for source in section.get("sources", []):
            key = (source.get("url") or "").strip()
            if not key:
                key = f"{source.get('source_name', '')}|{source.get('title', '')}"

            if key not in references_by_key:
                references_by_key[key] = {
                    **source,
                    "section": section["title"],
                    "section_index": section["index"],
                    "section_indices": [],
                    "sections": [],
                }

            reference = references_by_key[key]
            section_index = section["index"]
            if section_index not in reference["section_indices"]:
                reference["section_indices"].append(section_index)
            if section["title"] not in reference["sections"]:
                reference["sections"].append(section["title"])

            existing_metrics = reference.setdefault("metrics", [])
            for metric in source.get("metrics", []):
                if metric not in existing_metrics:
                    existing_metrics.append(metric)

    references = list(references_by_key.values())
    # 오래된 기사가 참고문헌 상단에 노출되지 않도록 최신순 정렬.
    # 날짜 없는 항목은 최하단, 동일 날짜는 다인용(여러 섹션 인용) 우선.
    references.sort(
        key=lambda r: (r.get("date") or "", len(r.get("section_indices") or [])),
        reverse=True,
    )

    research_background = ""
    quick_brief: dict = {}
    korea_impact: dict = {}
    if process_data:
        meta = process_data.get("meta") or {}
        research_background = meta.get("research_background", "")
        qb = meta.get("quick_brief") or {}
        if isinstance(qb, dict):
            quick_brief = qb
        ki = meta.get("korea_impact") or {}
        if isinstance(ki, dict):
            korea_impact = ki

    return {
        "topic": topic,
        "run_ts": run_ts,
        "research_background": research_background,
        "executive_summary": exec_summary,
        "sections": sections,
        "insights": insights,
        "references": references,
        "quick_brief": quick_brief,
        "korea_impact": korea_impact,
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
        en_data = load_en_summary(reports_dir, slug) or {}
        items.append({
            "slug": slug,
            "topic": report.get("topic") or slug,
            "run_ts": report.get("run_ts", ""),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "summary": (report.get("executive_summary") or "").strip(),
            "summary_en": en_data.get("executive_summary_en", ""),
            "topic_en": en_data.get("topic_en", ""),
            "section_count": len(report.get("sections", [])),
            "reference_count": len(report.get("references", [])),
            "metric_tags": metric_tags[:8],
            "domain": _detect_domain(process_data),
        })

    return {"reports": items}


@app.get("/api/reports/{slug}")
async def api_report_detail(slug: str, _user: dict = Depends(require_member)):
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
    result = {"slug": safe_slug, "domain": _detect_domain(process_data), **report}
    en_data = load_en_summary(ROOT / "reports", safe_slug)
    if en_data:
        result["topic_en"] = en_data.get("topic_en", "")
        result["executive_summary_en"] = en_data.get("executive_summary_en", "")
    return result


@app.delete("/api/reports/{slug}")
async def api_report_delete(slug: str, _user: dict = Depends(require_admin)):
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
async def serve_report_file(filename: str, _user: dict = Depends(require_member)):
    reports_dir = (ROOT / "reports").resolve()
    path = (reports_dir / filename).resolve()
    # Prevent path traversal (e.g. encoded ../) escaping the reports directory.
    if reports_dir not in path.parents or not path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(path)


@app.post("/api/report/start")
async def api_report_start(req: Request, _user: dict = Depends(require_admin)):
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
async def api_report_stream(sid: str, _user: dict = Depends(require_admin_query)):
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
async def api_report_cancel(sid: str, _user: dict = Depends(require_admin_query)):
    sess = REPORT_SESSIONS.pop(sid, None)
    if sess and sess.task and not sess.task.done():
        sess.task.cancel()
    return {"ok": True}


@app.post("/api/report/ext_decision")
async def api_report_ext_decision(req: Request, _user: dict = Depends(require_admin)):
    body = await req.json()
    sid = body.get("session_id")
    sess = REPORT_SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    sess.ext_use_external = bool(body.get("use_external", False))
    sess.ext_event.set()
    return {"ok": True}


@app.post("/api/report/gate1")
async def api_report_gate1(req: Request, _user: dict = Depends(require_admin)):
    body = await req.json()
    sid = body.get("session_id")
    sess = REPORT_SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    sess.gate1_data = body.get("sections", [])
    sess.gate1_event.set()
    return {"ok": True}


@app.post("/api/report/gate2")
async def api_report_gate2(req: Request, _user: dict = Depends(require_admin)):
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


# ── Feedback endpoints ──────────────────────────────────────────────────────

@app.post("/api/feedback")
async def api_feedback_create(req: Request, user: dict = Depends(require_team)):
    body = await req.json()
    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "message required")
    target_type = body.get("target_type") or "general"
    if target_type not in ALLOWED_TARGET_TYPE:
        target_type = "general"
    domain = body.get("domain") or ""
    target_ref = body.get("target_ref") or ""
    meta = user.get("user_metadata", {})
    email = (user.get("email") or "").lower()
    name = meta.get("full_name") or meta.get("name") or (email.split("@")[0] if email else "")
    row = add_feedback(
        user_id=user.get("id") or "",
        email=email,
        name=name,
        domain=domain,
        target_type=target_type,
        target_ref=target_ref,
        message=message,
    )
    return row


@app.get("/api/feedback/mine")
async def api_feedback_mine(user: dict = Depends(require_team)):
    email = (user.get("email") or "").lower()
    return list_mine(email)


@app.get("/api/feedback")
async def api_feedback_list(
    domain: str = "",
    status: str = "",
    user: dict = Depends(require_admin),
):
    return list_all(domain=domain or None, status=status or None)


@app.patch("/api/feedback/{fid}")
async def api_feedback_patch(fid: int, req: Request, user: dict = Depends(require_admin)):
    body = await req.json()
    new_status = (body.get("status") or "").strip()
    from src.feedback_store import ALLOWED_STATUS
    if new_status not in ALLOWED_STATUS:
        raise HTTPException(400, f"status must be one of: {', '.join(sorted(ALLOWED_STATUS))}")
    ok = update_status(fid, new_status)
    if not ok:
        raise HTTPException(404, "feedback item not found")
    return {"ok": True}


# ── Role management endpoints ────────────────────────────────────────────────

@app.get("/api/roles/team")
async def api_roles_team_list(user: dict = Depends(require_admin)):
    return {"team": list_team()}


@app.post("/api/roles/team")
async def api_roles_team_add(req: Request, user: dict = Depends(require_admin)):
    body = await req.json()
    email = (body.get("email") or "").strip()
    if not email:
        raise HTTPException(400, "email required")
    name = (body.get("name") or "").strip()
    add_team(email, name)
    return {"team": list_team()}


@app.post("/api/roles/team/remove")
async def api_roles_team_remove(req: Request, user: dict = Depends(require_admin)):
    body = await req.json()
    email = (body.get("email") or "").strip()
    if not email:
        raise HTTPException(400, "email required")
    remove_team(email)
    return {"team": list_team()}


@app.post("/api/roles/request")
async def api_roles_request(user: dict = Depends(require_member)):
    email = (user.get("email") or "").lower()
    name = user.get("name") or user.get("user_metadata", {}).get("full_name", "") if isinstance(user.get("user_metadata"), dict) else (user.get("name") or "")
    status = request_team(email, name)
    return {"status": status}


@app.get("/api/roles/requests")
async def api_roles_requests(_user: dict = Depends(require_admin)):
    return {"requests": list_requests()}


@app.post("/api/roles/approve")
async def api_roles_approve(req: Request, _user: dict = Depends(require_admin)):
    body = await req.json()
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "email required")
    approve_request(email)
    return {"team": list_team(), "requests": list_requests()}


@app.post("/api/roles/reject")
async def api_roles_reject(req: Request, _user: dict = Depends(require_admin)):
    body = await req.json()
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(400, "email required")
    reject_request(email)
    return {"requests": list_requests()}


@app.get("/api/auth/users")
async def api_auth_users(_user: dict = Depends(require_admin)):
    import os
    import httpx
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    base = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
    if not service_key or not base:
        raise HTTPException(503, "Supabase service_role 키가 설정되지 않았습니다")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{base}/auth/v1/admin/users",
                params={"per_page": 200},
                headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
            )
    except Exception:
        raise HTTPException(502, "Supabase 사용자 조회 중 오류가 발생했습니다")
    if resp.status_code != 200:
        raise HTTPException(502, f"Supabase 사용자 조회 실패 ({resp.status_code})")
    payload = resp.json()
    raw = payload.get("users", payload) if isinstance(payload, dict) else payload
    users = []
    for u in raw or []:
        email = (u.get("email") or "").lower()
        if not email:
            continue
        users.append({
            "id": u.get("id"),
            "email": email,
            "last_sign_in_at": u.get("last_sign_in_at"),
            "role": role_of({"email": email}),  # 'admin' | 'team' | 'other'
        })
    users.sort(key=lambda x: x.get("last_sign_in_at") or "", reverse=True)
    return {"users": users}


# SPA fallback — serves static files if they exist, otherwise index.html for React Router
if FRONTEND_DIST.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        dist = FRONTEND_DIST.resolve()
        candidate = (dist / full_path).resolve()
        # Only serve files that stay within the built frontend dir (no ../ escape);
        # anything else falls back to index.html for client-side routing.
        if candidate.is_file() and dist in candidate.parents:
            return FileResponse(str(candidate))
        return FileResponse(str(dist / "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
