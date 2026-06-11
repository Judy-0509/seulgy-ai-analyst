# Research Helper — 프로젝트 가이드

스마트폰·휴머노이드·자동차·스페이스 데이터센터 시장 리서치 자동화 도구.  
Tier-1 리서치 기관 아카이브를 기반으로 주제를 자동 선정하고, 목차 기반 보고서를 생성한다.

| 도메인 | 소스 수 | 키워드 수 | 색상 |
|--------|---------|-----------|------|
| Smartphone | 7 | 73 | 초록 (`#10b981`) |
| Humanoid | 16 | 57 | 빨강 (`#b73745`) |
| Automotive | 26 | 168 | 파랑 (`#2563eb`) |
| Space Datacenter | 8 | 52 | 청록 (`#22d3a6`) |

> Humanoid는 16개 전용 빌더(IB 6: GS·MS·Barclays·BofA·JPMorgan·Deutsche Bank 포함) 외에 스마트폰 트래커 4개(Counterpoint·TrendForce·IDC·Omdia) + 추가 시장조사 4개(IDTechEx·ABI·Yano·IFR) + Humanoids Daily / RoboticsTomorrow 등이 합쳐져 실제로는 30개 소스를 사용 (전부 active).

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
| `http://localhost:5173/login` | Google 로그인 화면 (Supabase OAuth) |
| `http://localhost:5173/app` | 보고서 생성 파이프라인 UI (인증 필요) |
| `http://localhost:5173/db` | 아카이브 DB 화면 (인증 필요) |
| `http://localhost:5173/news` | 뉴스 피드 화면 (공개) |
| `http://localhost:5173/archive` | 과거 보고서 아카이브 (인증 필요) |
| `http://localhost:5173/archive/:slug` | 보고서 상세 뷰 (인증 필요) |
| `http://localhost:5173/keywords` | 도메인별 필터링 키워드 뷰어 (인증 필요) |
| `http://localhost:8000/` | React 앱 — Vite 빌드(`frontend/dist/`) 서빙 또는 API 안내 |
| `http://localhost:8000/dashboard` | 아카이브 빌드 대시보드 |
| `http://localhost:8000/reports/{파일명}` | 생성된 보고서 HTML 서빙 |

---

## 핵심 파이프라인

### 1. 보고서 생성 — `run_report.py`

```
A(영문 쿼리) → B(Archive 검색) → C(목차 생성) → [GATE 1: 목차 확인]
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
네 도메인 모두 메이저(30일) + Curiosity Pick(7일) 2-pass 구성 (둘 다 주 1회 실행 권장):

```bash
# 스마트폰
python scripts/suggest_smartphone_topics.py --days 30
python scripts/suggest_smartphone_emerging.py --days 7

# 휴머노이드
python scripts/suggest_humanoid_topics.py --days 30
python scripts/suggest_humanoid_emerging.py --days 7

# 자동차
python scripts/suggest_automotive_topics.py --days 30
python scripts/suggest_automotive_emerging.py --days 7

# 스페이스 데이터센터
python scripts/suggest_space_datacenter_topics.py --days 30
python scripts/suggest_space_datacenter_emerging.py --days 7

# 보고서 follow-up 추천 (별도 entrypoint)
python run_suggest.py
```

| 도메인 / 패스 | 출력 파일 | API |
|--------|-----------|-----|
| 스마트폰 메이저 (30일) | `scripts/_topic_suggestions.json` | `GET /api/topics/suggested?domain=smartphone` |
| 스마트폰 Curiosity (7일) | `scripts/_topic_suggestions_emerging.json` | `↑ 같은 응답에 합쳐짐 (criteria=Crit 3)` |
| 휴머노이드 메이저 (30일) | `scripts/_humanoid_topic_suggestions.json` | `GET /api/topics/suggested?domain=humanoid` |
| 휴머노이드 Curiosity (7일) | `scripts/_humanoid_topic_suggestions_emerging.json` | `↑ 같은 응답에 합쳐짐` |
| 자동차 메이저 (30일) | `scripts/_automotive_topic_suggestions.json` | `GET /api/topics/suggested?domain=automotive` |
| 자동차 Curiosity (7일) | `scripts/_automotive_topic_suggestions_emerging.json` | `↑ 같은 응답에 합쳐짐` |
| 스페이스 DC 메이저 (30일) | `scripts/_space_datacenter_topic_suggestions.json` | `GET /api/topics/suggested?domain=space_datacenter` |
| 스페이스 DC Curiosity (7일) | `scripts/_space_datacenter_topic_suggestions_emerging.json` | `↑ 같은 응답에 합쳐짐` |

> Emerging 토픽은 server.py가 응답에 자동 merge하며 모두 `criteria="Criterion 3"`으로 강제됨.
> Frontend의 "이번 주 새롭게 등장한 주제" 섹션이 Crit 3 토픽을 자동 분류해 노출.

### 3. 아카이브 빌드

```bash
# 전체 빌드 (server.py 대시보드에서도 실행 가능)
python scripts/build_all_archives.py

# 개별 소스 — 스마트폰 (7개)
python scripts/build_counterpoint_archive.py
python scripts/build_trendforce_archive.py
python scripts/build_omdia_archive.py
python scripts/build_idc_archive.py
python scripts/build_yole_archive.py
python scripts/build_digitimes_archive.py        # RSS daily — 매일 실행해 누적
python scripts/build_ccs_insight_archive.py      # YOAST sitemap (carrier/EU 시장)

# 개별 소스 — 휴머노이드 (14개)
python scripts/build_robotics_automation_news_archive.py
python scripts/build_ieee_spectrum_robotics_archive.py
python scripts/build_robot_report_archive.py
python scripts/build_techcrunch_robotics_archive.py
python scripts/build_mit_tech_review_archive.py
python scripts/build_boston_dynamics_archive.py
python scripts/build_figure_ai_archive.py
python scripts/build_arxiv_robotics_archive.py
python scripts/build_nvidia_news_archive.py
python scripts/build_unitree_archive.py
python scripts/build_verge_robotics_archive.py
python scripts/build_goldman_sachs_archive.py     # IB Research — TAM/forecast 인용 1순위
python scripts/build_morgan_stanley_archive.py    # IB Research — Adam Jonas humanoid 시리즈
python scripts/build_bofa_institute_archive.py    # Physical AI / Humanoid 전용 hub
python scripts/build_jpmorgan_archive.py          # IB Research — US/en sitemap + humanoid slug 필터
python scripts/build_deutsche_bank_archive.py     # IB Research — RI 리스팅 6개 순회 (sitemap 404)

# 개별 소스 — 자동차 전용 빌더 (15개, 2026년만)
python scripts/build_jato_archive.py
python scripts/build_alixpartners_archive.py
python scripts/build_wardsauto_archive.py
python scripts/build_sae_archive.py
python scripts/build_vw_archive.py
python scripts/build_cox_automotive_archive.py
python scripts/build_automotive_dive_archive.py
python scripts/build_automotive_world_archive.py
python scripts/build_electrek_archive.py
python scripts/build_insideevs_archive.py
python scripts/build_toyota_archive.py
python scripts/build_cnevpost_archive.py        # 영문 중국 EV 매체
python scripts/build_carnewschina_archive.py    # 영문 중국 자동차 매체
python scripts/build_icct_archive.py            # 정책·배출 NGO
python scripts/build_acea_archive.py            # EU 제조사 협회
python scripts/build_bnef_archive.py            # BloombergNEF 무료 블로그 (자동차 키워드 필터)
python scripts/build_rmi_archive.py             # Rocky Mountain Institute (자동차 키워드 필터)
python scripts/build_te_archive.py              # Transport & Environment (EU NGO)
python scripts/build_irena_archive.py           # IRENA Transport (UN, 자동차 키워드 필터)

# 자동차는 추가로 스마트폰 트래커 7개도 자동 활용 (별도 빌드 불필요)
# Counterpoint / TrendForce / Omdia / IDC / Yole / DigiTimes Asia / CCS Insight
# — 자동차 키워드(168) 필터로 auto-relevant 콘텐츠만 통과

# 개별 소스 — 스페이스 데이터센터 전용 빌더 (7개)
python scripts/build_spacenews_archive.py           # RSS — 주 1회
python scripts/build_spacecom_archive.py            # RSS — 주 1회
python scripts/build_ieee_spectrum_space_archive.py # Sitemap + space kw 필터
python scripts/build_datacenter_knowledge_archive.py # RSS — 주 1회
python scripts/build_datacenter_frontier_archive.py  # RSS — 주 1회
python scripts/build_techcrunch_space_archive.py    # 페이지 크롤 + space kw 필터
python scripts/build_arxiv_space_archive.py         # arXiv API (cs.DC + cs.NI)
# + NVIDIA (nvidia_news.json) — humanoid 빌더와 공유, 별도 빌드 불필요
```

---

## 파일 트리

```
22_Research Helper/
│
├── CLAUDE.md                       ← 이 파일
├── .env                            ← API 키 (gitignore)
├── .env.example                    ← 키 템플릿
├── pyproject.toml
│
├── start.py                        ← [개발 진입점] 백엔드+프론트 동시 실행
├── run_report.py                   ← [진입점] 목차 보고서 생성 파이프라인
├── run_suggest.py                  ← [진입점] 스마트폰 주제 추천 생성
│
├── src/
│   ├── server.py                   ← FastAPI 서버 (포트 8000)
│   ├── state_machine.py            ← Phase0 분석 파이프라인 (AnalysisPipeline)
│   ├── models.py                   ← Pydantic 모델
│   ├── config.py                   ← 설정값
│   ├── domains.py                  ← 도메인 설정 로더 (smartphone / humanoid / automotive)
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
│   ├── build_all_archives.py       ← 전체 아카이브 빌드 오케스트레이터 (29개 소스)
│   │
│   │   # 스마트폰 아카이브 (7개) — 2026-05-07 옵션 B 정식 채택 + dead-weight 3개 제거
│   ├── build_counterpoint_archive.py
│   ├── build_trendforce_archive.py
│   ├── build_omdia_archive.py
│   ├── build_idc_archive.py
│   ├── build_yole_archive.py             ← 반도체 패키징·광학 부품 (sitemap)
│   ├── build_digitimes_archive.py        ← Asia 공급망 (RSS daily)
│   ├── build_ccs_insight_archive.py      ← UK/EU 통신사·소비자 (sitemap)
│   │
│   │   # 휴머노이드 아카이브 (11개)
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
│   ├── build_goldman_sachs_archive.py             ← Goldman Sachs Insights (humanoid kw 필터)
│   ├── build_morgan_stanley_archive.py            ← Morgan Stanley Insights/Ideas (humanoid kw 필터)
│   ├── build_bofa_institute_archive.py            ← BofA Institute /transformation/ (humanoid kw 필터)
│   ├── build_jpmorgan_archive.py                  ← JPMorgan Insights (humanoid slug 필터)
│   ├── build_deutsche_bank_archive.py             ← DB Research Institute 리스팅 (humanoid kw 필터)
│   │
│   │   # 자동차 아카이브 (19개 전용 빌더 + 7개 스마트폰 트래커 재활용 = 26개 소스)
│   ├── build_jato_archive.py
│   ├── build_alixpartners_archive.py
│   ├── build_wardsauto_archive.py
│   ├── build_sae_archive.py
│   ├── build_vw_archive.py
│   ├── build_cox_automotive_archive.py
│   ├── build_automotive_dive_archive.py
│   ├── build_automotive_world_archive.py
│   ├── build_electrek_archive.py
│   ├── build_insideevs_archive.py
│   ├── build_toyota_archive.py
│   ├── build_cnevpost_archive.py        ← 영문 중국 EV (2026년만)
│   ├── build_carnewschina_archive.py    ← 영문 중국 자동차 (2026년만)
│   ├── build_icct_archive.py            ← 정책·배출 NGO (2026년만)
│   ├── build_acea_archive.py            ← EU 제조사 협회 (2026년만)
│   ├── build_bnef_archive.py            ← BloombergNEF 블로그 (auto kw 필터)
│   ├── build_rmi_archive.py             ← Rocky Mountain Institute (auto kw 필터)
│   ├── build_te_archive.py              ← Transport & Environment EU NGO
│   ├── build_irena_archive.py           ← UN 재생에너지기구 Transport
│   ├── _auto_research_helper.py        ← 컨설팅·정책 빌더 공통 헬퍼
│   │
│   ├── build_archive_viewer.py     ← archive_viewer.html 생성
│   ├── build_topic_html.py         ← 주제 HTML 빌드 유틸
│   └── clear_body_cache.py         ← 본문 캐시 초기화 유틸
│
├── data/
│   ├── archives/                   ← 소스별 아카이브 JSON (스마트폰 7 + 휴머노이드 11 + 자동차 26)
│   ├── domains/
│   │   ├── smartphone.json         ← 스마트폰 도메인 설정
│   │   ├── humanoid.json           ← 휴머노이드 도메인 설정
│   │   └── automotive.json         ← 자동차 도메인 설정
│   ├── smartphone_keywords.json    ← 스마트폰 필터링 키워드 (42개)
│   ├── humanoid_keywords.json      ← 휴머노이드 필터링 키워드 (57개)
│   ├── automotive_keywords.json    ← 자동차 필터링 키워드 (168개)
│   └── article_bodies.db           ← 본문 fetch 캐시 (SQLite, gitignore)
│
├── db_research/                    ← 도메인별 소스 후보 조사 자료 (의사결정 근거)
│   ├── README.md                   ← 워크플로우 + 작성된 조사 인덱스
│   ├── _template.md                ← 신규 도메인 조사용 템플릿
│   └── humanoid/
│       └── 2026-05-07_tier1_ib_research.md  ← GS·MS·BofA 추가 근거
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
│   │   ├── smartphone-bg-v3-desktop.webp       ← 스마트폰 도메인 배경 이미지
│   │   ├── humanoid-bg-v2-desktop.webp         ← 휴머노이드 도메인 배경 이미지
│   │   └── automotive-bg-v2-desktop.webp       ← 자동차 도메인 배경 이미지
│   └── src/
│       ├── App.jsx                 ← 라우터 + ProtectedRoute
│       ├── theme.js                ← C 토큰, SRC_COLOR_MAP (도메인별 기관 색상)
│       ├── contexts/
│       │   ├── AuthContext.jsx     ← Supabase Google OAuth 인증 + 역할(role) 제공
│       │   └── DomainContext.jsx   ← 도메인 상태 (smartphone / humanoid / automotive)
│       ├── components/
│       │   ├── Sidebar.jsx         ← 홈 전용 사이드바 (도메인 전환)
│       │   └── PipelineScreen.jsx  ← 보고서 생성 파이프라인 뷰
│       └── pages/
│           ├── LandingPage.jsx     ← 랜딩/도메인 선택/추천 주제
│           ├── LoginPage.jsx       ← Google 로그인 화면 (Supabase OAuth)
│           ├── AppPage.jsx         ← 파이프라인 라우팅
│           ├── DbPage.jsx          ← 아카이브 DB 화면
│           ├── NewsPage.jsx        ← 뉴스 피드 화면
│           ├── KeywordsPage.jsx    ← 도메인별 필터링 키워드 뷰어
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
| GET  | `/api/topics/mine` | 최근 기사 목록 (`?domain=smartphone\|humanoid\|automotive`) |
| GET  | `/api/topics/suggested` | 추천 주제 (`?domain=smartphone\|humanoid\|automotive`) |
| GET  | `/api/reports` | 보고서 목록 (domain 필드 포함) |
| GET  | `/api/reports/{slug}` | 보고서 상세 (domain 필드 포함) |
| DELETE | `/api/reports/{slug}` | 보고서 삭제 (.md + .html + _process.json) |
| GET  | `/api/archives/status` | 아카이브 현황 |
| GET  | `/api/archives/entries` | 특정 소스 전체 기사 |
| POST | `/api/archives/refresh` | 아카이브 전체 빌드 시작 |
| GET  | `/api/archives/stream/{job_id}` | 아카이브 빌드 로그 SSE |
| GET  | `/api/keywords` | 도메인별 필터링 키워드 조회 (`?domain=smartphone\|humanoid\|automotive`) |
| PUT  | `/api/keywords` | 도메인별 필터링 키워드 교체 (`?domain=...`) |

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
# Supabase (Google OAuth 로그인 — Vite 빌드에 포함, VITE_ 접두사 필수)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key-here

# 관리자 이메일 (콤마 구분) — 이 주소로 로그인하면 Admin 권한
ADMIN_EMAILS=owner@example.com

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

- **Supabase Google OAuth** — 이메일/비밀번호 없이 Google 계정으로 로그인
- **역할 4단계**: 비로그인 → 로그인(member) → 애널리스트(team) → 관리자(admin). 역할은 `data/roles.json` + `ADMIN_EMAILS` 환경변수로 결정
- **공개 라우트**: `/`, `/news`, `/login`
- **로그인 필요 (MemberRoute)**: `/archive/:slug`, `/feedback`
- **애널리스트 (TeamRoute)**: `/db`, `/keywords`
- **관리자 (AdminRoute)**: `/app`, `/usage`
- 백엔드는 Supabase 액세스 토큰을 검증하는 `require_member` / `require_team` / `require_admin` 의존성으로 API를 게이팅

---

## 테스트 실행

```bash
pytest
pytest tests/test_search_relaxed.py -v
```

프론트엔드 변경 시:

```bash
cd frontend
npm.cmd exec eslint -- src/pages/LandingPage.jsx src/pages/DbPage.jsx src/pages/KeywordsPage.jsx src/components/PipelineScreen.jsx
```

---

## 프론트엔드 디자인 규칙

기능 추가 전 `frontend/DESIGN_SYSTEM.md`를 먼저 읽는다.

- 일반 앱/DB/News/Archive/Keywords 화면은 `frontend/src/theme.js`의 `C` 토큰 사용
- 파이프라인 화면은 `PipelineScreen.jsx` 내부 `E` 토큰과 `gl()` helper 유지
- 브랜드 마크와 favicon은 `frontend/public/logo-mark.png` 사용
- API 기반 화면은 loading/empty/error/ready 상태를 분리
- 도메인별 기관 색상은 `theme.js`의 `SRC_COLOR_MAP` 참조 (스마트폰=초록, 휴머노이드=빨강, 자동차=파랑)
