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
| `http://localhost:5173` | React 앱 — Vite dev server (개발 시 메인 진입점) |
| `http://localhost:8000/` | React 앱 — Vite 빌드(`frontend/dist/`) 서빙 (빌드 후) |
| `http://localhost:8000/reports/glm_topic_suggestions.html` | 주제 선정 + **레포트 생성 UI** |
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

# 웹 UI: reports/glm_topic_suggestions.html에서 "레포트 생성" 버튼 클릭
```

출력: `reports/{slug}_report.md` + `reports/{slug}_report.html` + `reports/{slug}_process.json`

### 2. 주제 추천 — `run_suggest.py`

아카이브 DB에서 최근 기사를 분석해 GLM-4.7 Thinking 모드로 보고서 주제를 자동 선정.  
결과: `reports/glm_topic_suggestions.html`

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
├── .env                            ← API 키 (GLM, Anthropic 등)
├── .env.example
├── pyproject.toml
│
├── start.py                        ← [개발 진입점] 백엔드+프론트 동시 실행 (python start.py)
├── run_report.py                   ← [진입점] TOC 보고서 생성 파이프라인
├── run_suggest.py                  ← [진입점] 주제 추천 생성
│
├── src/
│   ├── server.py                   ← FastAPI 서버 (포트 8000)
│   │                                  엔드포인트: /api/start, /api/report/*, /api/archives/*, /api/topics/mine
│   ├── state_machine.py            ← Phase0 분석 파이프라인 (AnalysisPipeline)
│   ├── models.py                   ← Pydantic 모델 (SearchResult, ResearchPlan 등)
│   ├── config.py                   ← 설정값
│   ├── app.py                      ← Chainlit 앱 (미사용)
│   ├── prompts/
│   │   ├── system.py               ← ANALYST_SYSTEM_PROMPT
│   │   └── step_prompts.py         ← PRE_SEARCH_PROMPT, TOC_PROMPT, SECTION_REPORT_PROMPT, INSIGHTS_PROMPT
│   ├── services/
│   │   ├── llm.py                  ← LLMService (GLM-4.7 + Claude 래퍼)
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
│   ├── build_naver_research_archive.py
│   ├── build_gartner_archive.py
│   ├── build_reuters_archive.py
│   ├── build_yole_archive.py
│   ├── build_archive_viewer.py     ← archive_viewer.html 생성
│   ├── build_topic_html.py         ← 주제 HTML 빌드 유틸
│   ├── suggest_topics.py           ← GLM 기반 주제 추천 로직
│   └── clear_body_cache.py         ← 본문 캐시 초기화 유틸
│
├── data/
│   ├── archives/                   ← 소스별 아카이브 JSON (omdia.json, counterpoint.json 등)
│   ├── article_bodies.db           ← 본문 fetch 캐시 (SQLite)
│   └── smartphone_keywords.json    ← 스마트폰 관련 필터링 키워드
│
├── reports/                        ← 생성된 보고서 + UI
│   ├── glm_topic_suggestions.html  ← [메인 UI] 주제 선정 + 레포트 생성 버튼
│   ├── archive_viewer.html         ← 아카이브 뷰어
│   ├── *_report.html               ← 생성된 보고서 (HTML)
│   ├── *_report.md                 ← 생성된 보고서 (Markdown)
│   └── *_process.json              ← 파이프라인 메타데이터 (HTML 재생성용)
│
├── frontend/                       ← React + Vite 프론트엔드
│   ├── src/
│   │   └── components/
│   │       └── PipelineScreen.jsx  ← 메인 UI (보고서 생성 파이프라인 뷰)
│   ├── dist/                       ← Vite 빌드 산출물 (server.py가 / 에서 서빙)
│   └── package.json
│
├── web/
│   └── dashboard.html              ← 아카이브 빌드 대시보드
│
├── tests/                          ← pytest 테스트
│   ├── test_state_machine.py
│   ├── test_search_relaxed.py
│   └── ...
│
└── ETC/                            ← 개발/디버그용 파일 (운영 불필요)
    ├── scripts_dev/                ← 1회성 분석 스크립트
    ├── reports_dev/                ← 디버그 보고서, 구 state 파일
    └── docs_old/                   ← 구 설계 문서, .chainlit 등
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
| GET  | `/api/archives/status` | 아카이브 현황 |
| POST | `/api/archives/refresh` | 아카이브 전체 빌드 시작 |

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
GLM_API_KEY=...          # GLM-4.7 (주 LLM)
ANTHROPIC_API_KEY=...    # Claude (서브)
```

---

## 테스트 실행

```bash
pytest
pytest tests/test_search_relaxed.py -v
```
