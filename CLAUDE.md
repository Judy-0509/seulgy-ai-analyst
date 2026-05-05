# Research Helper — 프로젝트 가이드

스마트폰 시장 리서치 자동화 도구.  
Tier-1 리서치 기관(Omdia, Counterpoint, IDC 등) 아카이브를 기반으로 주제를 자동 선정하고, TOC 기반 보고서를 생성한다.

---

## 서버 실행

```bash
# 백엔드 + 프론트엔드 동시 실행 (권장)
python start.py

# 개별 실행
uvicorn src.server:app --host 127.0.0.1 --port 8000   # 백엔드
cd frontend && npm run dev                              # 프론트엔드
```

| URL | 내용 |
|-----|------|
| `http://localhost:5173/` | React 랜딩/추천 주제 화면 |
| `http://localhost:5173/app` | React 보고서 생성 파이프라인 UI |
| `http://localhost:5173/db` | React 아카이브 DB 화면 |
| `http://localhost:8000/` | React 앱 — Vite 빌드(`frontend/dist/`) 서빙 또는 API 안내 |
| `http://localhost:8000/dashboard` | 아카이브 빌드 대시보드 |
| `http://localhost:8000/reports/{파일명}` | 생성된 보고서 HTML 서빙 |

---

## 핵심 파이프라인

### 1. 보고서 생성 — `run_report.py`

```
A(영문 쿼리) → B(Archive 검색) → C(TOC 생성) → [GATE 1: 목차 확인]
→ D(섹션별 검색) → [GATE 2: 결과 확인] → E/F(분석+작성) → G(시사점) → 저장
```

```bash
# CLI (--auto 플래그로 GATE 자동 통과)
python run_report.py "분석 토픽"
python run_report.py --auto "분석 토픽"

# 웹 UI: React 메인 추천 주제 또는 /app에서 보고서 생성
```

출력: `reports/{slug}_report.md` + `reports/{slug}_report.html` + `reports/{slug}_process.json`

### 2. 주제 추천 — `run_suggest.py`

아카이브 DB에서 최근 기사를 분석해 GLM-4.7 Thinking 모드로 보고서 주제를 자동 선정.  
결과: `scripts/_topic_suggestions.json` — React 랜딩/홈 화면의 추천 주제 API가 사용

### 3. 아카이브 빌드

```bash
# 전체 빌드 (server.py 대시보드에서도 실행 가능)
python scripts/build_all_archives.py

# 개별 소스
python scripts/build_omdia_archive.py
python scripts/build_counterpoint_archive.py
# ... 등
```

---

## 파일 트리

```
22_Research Helper/
│
├── CLAUDE.md                       ← 이 파일
├── .env                            ← API 키 (`ZHIPU_API_KEY`, Qwen 선택 설정 등)
├── .env.example
├── pyproject.toml
│
├── start.py                        ← [개발 진입점] 백엔드+프론트 동시 실행 (python start.py)
├── run_report.py                   ← [진입점] TOC 보고서 생성 파이프라인
├── run_suggest.py                  ← [진입점] 주제 추천 생성
│
├── src/
│   ├── server.py                   ← FastAPI 서버 (포트 8000)
│   │                                  엔드포인트: /api/report/*, /api/archives/*, /api/topics/*
│   ├── state_machine.py            ← Phase0 분석 파이프라인 (AnalysisPipeline)
│   ├── models.py                   ← Pydantic 모델 (SearchResult, ResearchPlan 등)
│   ├── config.py                   ← 설정값
│   ├── prompts/
│   │   ├── system.py               ← ANALYST_SYSTEM_PROMPT
│   │   └── step_prompts.py         ← PRE_SEARCH_PROMPT, TOC_PROMPT, SECTION_REPORT_PROMPT, INSIGHTS_PROMPT
│   ├── services/
│   │   ├── llm.py                  ← LLMService (GLM-4.7 기본, Qwen 선택)
│   │   ├── search.py               ← SearchService (Archive→RSS→DDG 3-tier)
│   │   ├── body_fetcher.py         ← 본문 fetch (FETCHABLE_SOURCES)
│   │   ├── body_cache.py           ← SQLite 본문 캐시
│   │   └── citation.py             ← 인용 포맷팅
│   └── utils/
│       └── formatting.py
│
├── scripts/
│   ├── build_all_archives.py       ← 전체 아카이브 빌드 오케스트레이터 (server.py에서 subprocess 호출)
│   ├── build_counterpoint_archive.py
│   ├── build_omdia_archive.py
│   ├── build_idc_archive.py
│   ├── build_trendforce_archive.py
│   ├── build_morgan_stanley_archive.py
│   ├── build_gartner_archive.py
│   ├── build_reuters_archive.py
│   ├── build_yole_archive.py
│   ├── build_archive_viewer.py     ← archive_viewer.html 생성
│   ├── build_topic_html.py         ← 주제 HTML 빌드 유틸
│   ├── suggest_topics.py           ← GLM 기반 주제 추천 로직
│   └── clear_body_cache.py         ← 본문 캐시 초기화 유틸
│
├── data/
│   ├── archives/                   ← 소스별 아카이브 JSON (8개 기관)
│   ├── article_bodies.db           ← 본문 fetch 캐시 (SQLite, gitignore)
│   └── smartphone_keywords.json    ← 스마트폰 관련 필터링 키워드
│
├── reports/                        ← 생성된 보고서 (gitignore)
│   ├── *_report.html
│   ├── *_report.md
│   └── *_process.json
│
├── frontend/                       ← React + Vite 프론트엔드
│   ├── DESIGN_SYSTEM.md            ← 다른 기능 통합 시 참고할 디자인 규칙
│   ├── public/
│   │   └── logo-mark.png           ← Canopy 로고/favicon 소스
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LandingPage.jsx     ← 랜딩/추천 주제 화면
│   │   │   ├── AppPage.jsx         ← 홈/파이프라인 라우팅
│   │   │   └── DbPage.jsx          ← 아카이브 DB 화면
│   │   └── components/
│   │       └── PipelineScreen.jsx  ← 보고서 생성 파이프라인 뷰
│   ├── dist/                       ← Vite 빌드 산출물 (server.py가 / 에서 서빙)
│   └── package.json
│
├── web/
│   └── dashboard.html              ← 아카이브 빌드 대시보드
│
└── tests/                          ← pytest 테스트
    ├── test_state_machine.py
    ├── test_search_relaxed.py
    └── ...
```

---

## 주요 API 엔드포인트

| Method | Path | 역할 |
|--------|------|------|
| POST | `/api/report/start` | 보고서 생성 시작 → `{session_id}` 반환 |
| GET  | `/api/report/stream/{sid}` | SSE: 실시간 진행 로그 스트림 |
| POST | `/api/report/gate1` | GATE 1 확정 (목차/검색어) |
| POST | `/api/report/gate2` | GATE 2 확정 (검색결과, proceed 여부) |
| POST | `/api/start` | Phase0 분석 시작 (React 앱용) |
| GET  | `/api/stream/{sid}` | Phase0 SSE 스트림 |
| POST | `/api/confirm_dimensions` | Phase0 차원 확정 |
| GET  | `/api/topics/mine` | 최근 Tier-1 스마트폰 기사 목록 |
| GET  | `/api/topics/suggested` | `scripts/_topic_suggestions.json` 기반 추천 주제 |
| GET  | `/api/archives/status` | 아카이브 현황 |
| GET  | `/api/archives/entries` | 특정 소스 전체 기사 (키워드 필터 없음) |
| POST | `/api/archives/refresh` | 아카이브 전체 빌드 시작 |
| GET  | `/api/archives/stream/{job_id}` | 아카이브 빌드 로그 SSE |
| GET/PUT | `/api/keywords` | 스마트폰 필터링 키워드 조회/교체 |

---

## 검색 아키텍처 (SearchService)

```
Tier 0: Archive (data/archives/*.json)  ← 메인, 항상 실행
Tier 1: RSS 피드 (max 3건/소스)         ← 외부 검색 시
Tier 2: DuckDuckGo (SOURCE_TIER_MAP 도메인만)  ← 외부 검색 시
```

`search_archive_only()` — Tier 0만  
`search()` — 전체 3-tier

---

## 환경 변수 (.env)

```
LLM_BACKEND=glm          # 기본값: glm, 선택값: qwen
ZHIPU_API_KEY=...        # GLM-4.7

# Qwen 백엔드 사용 시
QWEN_API_KEY=...
QWEN_BASE_URL=...
QWEN_MODEL=qwen3-32b
QWEN_FAST_MODEL=qwen3-8b
```

---

## 테스트 실행

```bash
pytest
pytest tests/test_search_relaxed.py -v
```

프론트엔드 변경 시에는 관련 파일 중심으로 lint를 실행한다.

```bash
cd frontend
npm.cmd exec eslint -- src/pages/LandingPage.jsx src/pages/DbPage.jsx src/components/PipelineScreen.jsx
```

---

## 프론트엔드 디자인 규칙

다른 웹사이트나 기능을 합칠 때는 `frontend/DESIGN_SYSTEM.md`를 먼저 읽는다.

- 기본 앱/DB 화면은 `frontend/src/theme.js`의 `C` 토큰을 사용한다.
- 파이프라인 화면은 `PipelineScreen.jsx` 내부 `E` 토큰과 `gl()` helper를 유지한다.
- 브랜드 마크와 favicon은 `frontend/public/logo-mark.png`를 사용한다.
- API 기반 화면은 loading/empty/error/ready 상태를 분리한다.
