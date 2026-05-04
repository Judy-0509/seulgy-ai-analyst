# Research Helper

> Tier-1 리서치 기관 아카이브 기반 스마트폰 시장 자동 분석 도구

GLM-4.7 Thinking 모드를 활용해 Counterpoint Research, Omdia, TrendForce, IDC 등 주요 기관의 아카이브를 검색하고, TOC(목차) 기반 심층 보고서를 자동 생성합니다.

---

## 주요 기능

- **주제 자동 추천** — 최신 아카이브 동향을 분석해 보고서 주제를 자동 선정
- **TOC 기반 보고서 생성** — 섹션별 검색 → 본문 분석 → Executive Summary 자동 작성
- **실시간 파이프라인 UI** — 8단계 진행 상황을 단계별로 시각화
- **GATE 시스템** — 목차 확정(GATE 1), 검색결과 검토(GATE 2) 단계에서 사용자 개입
- **멀티 소스 아카이브** — 9개 Tier-1 기관 데이터 통합 검색

---

## 아키텍처

```
Step 01  영문 쿼리 생성        GLM이 주제를 분석해 최적화된 검색어 생성
Step 02  아카이브 사전 검색     9개 기관 아카이브에서 관련 리포트 스캔
Step 03  목차 생성             수집 메타데이터 기반으로 GLM이 보고서 목차 설계
Step 04  GATE 1               목차 검토 및 확정
Step 05  섹션별 검색            확정된 목차별로 아카이브 심층 검색
Step 06  GATE 2               검색결과 검토 및 추가 검색 여부 결정
Step 07  본문 분석             섹션별 본문 fetch → GLM 분석 → 내용 작성
Step 08  Executive Summary    전체 내용 종합 → 핵심 시사점 도출
```

**지원 소스**: Counterpoint Research · TrendForce · Omdia · IDC · Reuters · Yole · Gartner · Morgan Stanley · Naver Research

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| LLM | GLM-4.7 Thinking (주), Claude (서브) |
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
- GLM API 키 ([Zhipu AI](https://open.bigmodel.cn/) 에서 발급)
- Anthropic API 키 (선택)

### 2. 설치

```bash
# 저장소 클론
git clone https://github.com/Judy-0509/spark.git
cd spark

# Python 의존성 설치
pip install -e .

# 프론트엔드 의존성 설치
cd frontend
npm install
cd ..
```

### 3. 환경 변수 설정

`.env.example`을 복사해 `.env` 파일을 생성합니다.

```bash
cp .env.example .env
```

`.env` 파일을 열고 API 키를 입력합니다.

```env
GLM_API_KEY=your_glm_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here   # 선택
```

### 4. 서버 실행

**백엔드와 프론트엔드를 각각 실행합니다.**

```bash
# 터미널 1 — 백엔드 (FastAPI)
uvicorn src.server:app --host 127.0.0.1 --port 8000

# 터미널 2 — 프론트엔드 (Vite dev server)
cd frontend
npm run dev
```

| 주소 | 내용 |
|------|------|
| `http://localhost:5173` | React 앱 (메인 UI) |
| `http://localhost:8000/reports/glm_topic_suggestions.html` | 주제 추천 + 보고서 생성 |
| `http://localhost:8000/dashboard` | 아카이브 빌드 대시보드 |

---

## 아카이브 빌드

아카이브는 각 기관 사이트에서 기사 메타데이터를 수집한 JSON 파일입니다.  
기존 아카이브(`data/archives/`)가 포함되어 있으며, 최신 데이터로 갱신하려면 아래 명령어를 실행합니다.

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

출력 파일: `reports/{slug}_report.html`, `reports/{slug}_report.md`

---

## 주제 추천 생성

```bash
python run_suggest.py
```

최근 아카이브 동향을 분석해 보고서 주제 목록을 자동 생성합니다.  
결과: `reports/glm_topic_suggestions.html`

---

## 프로젝트 구조

```
spark/
├── src/                    # 백엔드 코어
│   ├── server.py           # FastAPI 서버
│   ├── state_machine.py    # 분석 파이프라인
│   ├── services/           # LLM, 검색, 캐시
│   └── prompts/            # GLM 프롬프트
├── frontend/               # React 프론트엔드
│   └── src/
│       └── components/
│           └── PipelineScreen.jsx  # 메인 UI
├── scripts/                # 아카이브 빌드 스크립트
├── data/archives/          # 기관별 아카이브 JSON
├── reports/                # 생성된 보고서
├── tests/                  # pytest 테스트
├── run_report.py           # 보고서 생성 진입점
└── run_suggest.py          # 주제 추천 진입점
```

---

## 테스트

```bash
pytest
pytest tests/test_search_relaxed.py -v
```

---

## 라이선스

이 프로젝트는 개인 연구 목적으로 개발되었습니다.
