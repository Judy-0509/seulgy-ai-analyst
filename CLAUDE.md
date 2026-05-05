# Research Helper — 프로젝트 가이드

스마트폰 및 휴머노이드 로봇 시장 리서치 자동화 도구.  
Tier-1 리서치 기관 아카이브(스마트폰)와 로보틱스 미디어 아카이브(휴머노이드)를 기반으로  
주제를 자동 선정하고, TOC 기반 보고서를 생성한다.

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
| `http://localhost:5173/` | 랜딩/도메인 선택/추천 주제 화면 (공개) |
| `http://localhost:5173/login` | PIN 로그인 화면 |
| `http://localhost:5173/app` | 보고서 생성 파이프라인 UI (인증 필요) |
| `http://localhost:5173/db` | 아카이브 DB 화면 (인증 필요) |
| `http://localhost:5173/news` | 뉴스 피드 화면 (공개) |
| `http://localhost:5173/archive` | 과거 보고서 아카이브 (인증 필요) |
| `http://localhost:5173/archive/:slug` | 보고서 상세 뷰 (인증 필요) |
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

# 웹 UI: React 랜딩 추천 주제 클릭 또는 /app에서 직접 입력
```

출력: `reports/{slug}_report.md` + `reports/{slug}_report.html` + `reports/{slug}_process.json`

### 2. 주제 추천

아카이브 DB에서 최근 기사를 분석해 GLM-4.7 Thinking 모드로 보고서 주제를 자동 선정.

```bash
python run_suggest.py                        # 스마트폰 (기본)
python scripts/suggest_smartphone_topics.py  # 스마트폰 명시
python scripts/suggest_humanoid_topics.py    # 휴머노이드
```

| 도메인 | 출력 파일 | API |
|--------|-----------|-----|
| 스마트폰 | `scripts/_topic_suggestions.json` | `GET /api/topics/suggested?domain=smartphone` |
| 휴머노이드 | `scripts/_humanoid_topic_suggestions.json` | `GET /api/topics/suggested?domain=humanoid` |

### 3. 아카이브 빌드

```bash
# 전체 빌드 (server.py 대시보드에서도 실행 가능)
python scripts/build_all_archives.py

# 개별 소스 — 스마트폰
python scripts/build_counterpoint_archive.py
python scripts/build_omdia_archive.py
python scripts/build_idc_archive.py
# ... 등

# 개별 소스 — 휴머노이드
python scripts/build_robotics_automation_news_archive.py
python scripts/build_ieee_spectrum_robotics_archive.py
python scripts/build_robot_report_archive.py
# ... 등
```

---

## 파일 트리

```
22_Research Helper/
│
├── CLAUDE.md                       ← 이 파일
├── .env                            ← API 키 + PIN (gitignore)
├── .env.example                    ← 키 템플릿
├── pyproject.toml
│
├── start.py                        ← [개발 진입점] 백엔드+프론트 동시 실행
├── run_report.py                   ← [진입점] TOC 보고서 생성 파이프라인
├── run_suggest.py                  ← [진입점] 스마트폰 주제 추천 생성
│
├── src/
│   ├── server.py                   ← FastAPI 서버 (포트 8000)
│   ├── state_machine.py            ← Phase0 분석 파이프라인 (AnalysisPipeline)
│   ├── models.py                   ← Pydantic 모델
│   ├── config.py                   ← 설정값
│   ├── domains.py                  ← 도메인 설정 로더 (smartphone / humanoid)
│   ├── news_api.py                 ← 뉴스 피드 API 헬퍼
│   ├── prompts/
│   │   ├── system.py               ← ANALYST_SYSTEM_PROMPT
│   │   └── step_prompts.py         ← TOC_PROMPT, SECTION_REPORT_PROMPT 등
│   ├── services/
│   │   ├── llm.py                  ← LLMService (GLM-4.7 기본, Qwen 선택)
│   │   ├── search.py               ← SearchService (Archive→RSS→DDG 3-tier)
│   │   ├── body_fetcher.py         ← 본문 fetch
│   │   ├── body_cache.py           ← SQLite 본문 캐시
│   │   └── citation.py             ← 인용 포맷팅
│   └── utils/
│       └── formatting.py
│
├── scripts/
│   ├── _suggest_core.py            ← 주제 추천 공통 엔진 (run_pipeline 등)
│   ├── suggest_smartphone_topics.py← 스마트폰 주제 선정 → _topic_suggestions.json
│   ├── suggest_humanoid_topics.py  ← 휴머노이드 주제 선정 → _humanoid_topic_suggestions.json
│   ├── suggest_topics.py           ← 하위 호환 shim → suggest_smartphone_topics.py 위임
│   │
│   ├── build_all_archives.py       ← 전체 아카이브 빌드 오케스트레이터
│   │
│   │   # 스마트폰 아카이브
│   ├── build_counterpoint_archive.py
│   ├── build_omdia_archive.py
│   ├── build_idc_archive.py
│   ├── build_trendforce_archive.py
│   ├── build_morgan_stanley_archive.py
│   ├── build_gartner_archive.py
│   ├── build_reuters_archive.py
│   ├── build_yole_archive.py
│   │
│   │   # 휴머노이드 아카이브
│   ├── build_robotics_automation_news_archive.py
│   ├── build_techcrunch_robotics_archive.py
│   ├── build_ieee_spectrum_robotics_archive.py
│   ├── build_robot_report_archive.py
│   ├── build_mit_tech_review_archive.py
│   ├── build_boston_dynamics_archive.py
│   ├── build_figure_ai_archive.py
│   ├── build_arxiv_robotics_archive.py
│   ├── build_nvidia_news_archive.py
│   ├── build_unitree_archive.py
│   ├── build_verge_robotics_archive.py
│   │
│   ├── build_archive_viewer.py     ← archive_viewer.html 생성
│   ├── build_topic_html.py         ← 주제 HTML 빌드 유틸
│   └── clear_body_cache.py         ← 본문 캐시 초기화 유틸
│
├── data/
│   ├── archives/                   ← 소스별 아카이브 JSON (스마트폰 8 + 휴머노이드 11)
│   ├── domains/
│   │   ├── smartphone.json         ← 스마트폰 도메인 설정
│   │   └── humanoid.json           ← 휴머노이드 도메인 설정
│   ├── smartphone_keywords.json    ← 스마트폰 필터링 키워드
│   ├── humanoid_keywords.json      ← 휴머노이드 필터링 키워드
│   └── article_bodies.db           ← 본문 fetch 캐시 (SQLite, gitignore)
│
├── reports/                        ← 생성된 보고서 (gitignore)
│   ├── *_report.html
│   ├── *_report.md
│   └── *_process.json
│
├── frontend/                       ← React + Vite 프론트엔드
│   ├── DESIGN_SYSTEM.md            ← 디자인 규칙 (기능 추가 전 필독)
│   ├── vite.config.js              ← envDir: '..' — 루트 .env에서 VITE_* 변수 읽음
│   ├── public/
│   │   ├── logo-mark.png           ← Canopy 로고/favicon
│   │   ├── smartphone-bg.png       ← 스마트폰 도메인 배경 이미지
│   │   └── humanoid-bg.png         ← 휴머노이드 도메인 배경 이미지
│   └── src/
│       ├── App.jsx                 ← 라우터 + ProtectedRoute
│       ├── theme.js                ← C 토큰, SRC_COLOR_MAP (도메인별 기관 색상)
│       ├── contexts/
│       │   ├── AuthContext.jsx     ← PIN 기반 인증 (VITE_PIN_KEY)
│       │   └── DomainContext.jsx   ← 도메인 상태 (smartphone / humanoid)
│       ├── components/
│       │   ├── Sidebar.jsx         ← 홈 전용 사이드바
│       │   └── PipelineScreen.jsx  ← 보고서 생성 파이프라인 뷰
│       └── pages/
│           ├── LandingPage.jsx     ← 랜딩/도메인 선택/추천 주제
│           ├── LoginPage.jsx       ← PIN 로그인 화면
│           ├── AppPage.jsx         ← 파이프라인 라우팅
│           ├── DbPage.jsx          ← 아카이브 DB 화면
│           ├── NewsPage.jsx        ← 뉴스 피드 화면
│           ├── ReportPage.jsx      ← 보고서 상세 뷰 (도메인 색상 자동)
│           └── ReportsArchivePage.jsx ← 과거 보고서 목록 + 삭제
│
├── web/
│   └── dashboard.html              ← 아카이브 빌드 대시보드
│
└── tests/
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
| GET  | `/api/topics/mine` | 최근 기사 목록 (`?domain=smartphone\|humanoid`) |
| GET  | `/api/topics/suggested` | 추천 주제 (`?domain=smartphone\|humanoid`) |
| GET  | `/api/reports` | 보고서 목록 (domain 필드 포함) |
| GET  | `/api/reports/{slug}` | 보고서 상세 (domain 필드 포함) |
| DELETE | `/api/reports/{slug}` | 보고서 삭제 (.md + .html + _process.json) |
| GET  | `/api/archives/status` | 아카이브 현황 |
| GET  | `/api/archives/entries` | 특정 소스 전체 기사 |
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
# 프론트엔드 PIN (Vite 빌드에 포함 — VITE_ 접두사 필수)
VITE_PIN_KEY=your_pin_here   # /app, /db, /archive 접근 시 요구

# LLM 백엔드
LLM_BACKEND=glm              # 기본값: glm, 선택값: qwen
ZHIPU_API_KEY=...            # GLM-4.7

# Qwen 백엔드 사용 시
QWEN_API_KEY=...
QWEN_BASE_URL=...
QWEN_MODEL=qwen3-32b
QWEN_FAST_MODEL=qwen3-8b
```

> `vite.config.js`에 `envDir: '..'` 설정으로 루트 `.env`를 Vite가 직접 읽음.  
> `VITE_` 접두사가 없는 변수(ZHIPU_API_KEY 등)는 브라우저 번들에 노출되지 않음.

---

## 인증 구조

- **PIN 기반** — 아이디/비밀번호 없이 단일 PIN으로 접근 제어
- **공개 라우트**: `/`, `/news`, `/login`
- **보호 라우트**: `/app`, `/db`, `/archive`, `/archive/:slug`
- PIN은 `localStorage`에 세션 저장, 로그아웃 시 삭제

---

## 테스트 실행

```bash
pytest
pytest tests/test_search_relaxed.py -v
```

프론트엔드 변경 시:

```bash
cd frontend
npm.cmd exec eslint -- src/pages/LandingPage.jsx src/pages/DbPage.jsx src/components/PipelineScreen.jsx
```

---

## 프론트엔드 디자인 규칙

기능 추가 전 `frontend/DESIGN_SYSTEM.md`를 먼저 읽는다.

- 일반 앱/DB/News/Archive 화면은 `frontend/src/theme.js`의 `C` 토큰 사용
- 파이프라인 화면은 `PipelineScreen.jsx` 내부 `E` 토큰과 `gl()` helper 유지
- 브랜드 마크와 favicon은 `frontend/public/logo-mark.png` 사용
- API 기반 화면은 loading/empty/error/ready 상태를 분리
- 도메인별 기관 색상은 `theme.js`의 `SRC_COLOR_MAP` 참조 (스마트폰=초록, 휴머노이드=빨강)
