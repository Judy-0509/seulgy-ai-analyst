# Research Helper

> Tier-1 리서치 기관 아카이브 기반 스마트폰 시장 자동 분석 도구

GLM-4.7 Thinking 모드를 활용해 Counterpoint Research, Omdia, TrendForce, IDC 등 주요 기관의 아카이브를 검색하고, 추천 주제 선정부터 TOC(목차) 기반 심층 보고서 생성까지 React UI에서 실행합니다.

---

## 주요 기능

- **주제 자동 추천** — 최신 아카이브 동향을 분석해 보고서 주제를 자동 선정하고 메인 화면에 표시
- **TOC 기반 보고서 생성** — 섹션별 검색 → 본문 분석 → Executive Summary 자동 작성
- **실시간 React 파이프라인 UI** — 8단계 진행 상황을 단계별로 시각화
- **GATE 시스템** — 목차 확정(GATE 1), 검색결과 검토(GATE 2) 단계에서 사용자 개입
- **멀티 소스 아카이브** — 8개 Tier-1 기관 데이터 통합 검색 및 DB 화면 조회

---

## 아키텍처

```
Step 01  영문 쿼리 생성        GLM이 주제를 분석해 최적화된 검색어 생성
Step 02  아카이브 사전 검색     8개 기관 아카이브에서 관련 리포트 스캔
Step 03  목차 생성             수집 메타데이터 기반으로 GLM이 보고서 목차 설계
Step 04  GATE 1               목차 검토 및 확정
Step 05  섹션별 검색            확정된 목차별로 아카이브 심층 검색
Step 06  GATE 2               검색결과 검토 및 추가 검색 여부 결정
Step 07  본문 분석             섹션별 본문 fetch → GLM 분석 → 내용 작성
Step 08  Executive Summary    전체 내용 종합 → 핵심 시사점 도출
```

**지원 소스**: Counterpoint Research · TrendForce · Omdia · IDC · Reuters · Yole · Gartner · Morgan Stanley

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| LLM | GLM-4.7 Thinking (기본), Qwen3 선택 |
| 백엔드 | Python 3.10+, FastAPI, uvicorn |
| 프론트엔드 | React 19, Vite, react-router-dom v7 |
| 실시간 통신 | Server-Sent Events (SSE) |
| 검색 | 3-tier: Archive → RSS → DuckDuckGo |
| 데이터 | SQLite (본문 캐시), JSON (아카이브) |

---

## 시작하기

### 1. 사전 요구사항

- Python 3.10 이상
- Node.js 18 이상
- Zhipu AI API 키 (`ZHIPU_API_KEY`)
- Qwen 호환 API 키/URL (선택, `LLM_BACKEND=qwen` 사용 시)

### 2. 설치

```bash
# 저장소 클론
git clone <repo-url>
cd research-helper

# Python 의존성 설치
pip install -e .

# 프론트엔드 의존성 설치
cd frontend && npm install && cd ..
```

### 3. 환경 변수 설정

`.env.example`을 복사해 `.env` 파일을 생성하고 API 키를 입력합니다.

```bash
cp .env.example .env
```

```env
LLM_BACKEND=glm
ZHIPU_API_KEY=your_zhipu_api_key_here

# 선택: Qwen 백엔드
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3-32b
QWEN_FAST_MODEL=qwen3-8b
```

### 4. 서버 실행

```bash
# 백엔드(:8000) + 프론트엔드(:5173) 동시 실행 (권장)
python start.py
```

개별 실행:

```bash
uvicorn src.server:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

| 주소 | 내용 |
|------|------|
| `http://localhost:5173/` | 주제 추천 랜딩 화면 |
| `http://localhost:5173/app` | 보고서 생성 파이프라인 UI |
| `http://localhost:5173/db` | 아카이브 DB 화면 |
| `http://localhost:8000/dashboard` | 아카이브 빌드 대시보드 |

---

## 아카이브 빌드

아카이브는 각 기관 사이트에서 기사 메타데이터를 수집한 JSON 파일입니다.
저장소에 포함된 아카이브(`data/archives/`)를 그대로 사용하거나, 최신 데이터로 갱신할 수 있습니다.

```bash
# 전체 아카이브 갱신
python scripts/build_all_archives.py

# 특정 소스만 갱신
python scripts/build_counterpoint_archive.py
python scripts/build_omdia_archive.py
# ... 등
```

---

## 보고서 생성 (CLI)

웹 UI 외에 CLI로도 보고서를 생성할 수 있습니다.

```bash
# 대화형 (GATE 단계에서 사용자 입력)
python run_report.py "분석 주제"

# 자동 모드 (GATE 자동 통과)
python run_report.py --auto "분석 주제"
```

출력: `reports/{slug}_report.html`, `reports/{slug}_report.md`

---

## 주제 추천 갱신

```bash
python run_suggest.py
```

최근 아카이브 동향을 분석해 보고서 주제 목록을 자동 생성합니다.
결과는 `scripts/_topic_suggestions.json`에 저장되고 React 메인 화면이 이를 읽습니다.

---

## 프로젝트 구조

```
research-helper/
├── src/                    # 백엔드 코어
│   ├── server.py           # FastAPI 서버
│   ├── state_machine.py    # 분석 파이프라인
│   ├── services/           # LLM, 검색, 캐시
│   └── prompts/            # GLM 프롬프트
├── frontend/               # React 프론트엔드
│   ├── DESIGN_SYSTEM.md    # 디자인 규칙
│   ├── public/logo-mark.png
│   └── src/
│       ├── pages/          # LandingPage, AppPage, DbPage
│       └── components/     # PipelineScreen 등
├── scripts/                # 아카이브 빌드 스크립트
├── data/archives/          # 기관별 아카이브 JSON (8개 소스)
├── reports/                # 생성된 보고서 (gitignore)
├── tests/                  # pytest 테스트
├── run_report.py           # 보고서 생성 진입점
├── run_suggest.py          # 주제 추천 진입점
└── start.py                # 개발 서버 동시 실행
```

---

## 테스트

```bash
pytest
pytest tests/test_search_relaxed.py -v
```

프론트엔드 변경 시:

```bash
cd frontend
npm run lint
```

---

## 프론트엔드 디자인 규칙

새 화면/기능을 추가할 때는 `frontend/DESIGN_SYSTEM.md`를 먼저 참고합니다.
공통 토큰은 `frontend/src/theme.js`, 브랜드 마크는 `frontend/public/logo-mark.png`를 사용합니다.

---

## 라이선스

이 프로젝트는 개인 연구 목적으로 개발되었습니다.
