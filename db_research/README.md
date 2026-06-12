# db_research/ — 도메인별 소스 후보 조사 자료

각 도메인의 아카이브 소스를 추가/검토할 때 사용한 **외부 조사 결과**를 보관합니다.
어떤 기관이 가장 자주 인용되는지, 어떤 데이터를 발행하는지, 크롤링 가능 여부 (robots.txt) 등
구조적 의사결정 자료를 도메인별로 누적합니다.

코드 변경(아카이브 빌더, suggest 스크립트, server.py)은 별도 디렉터리에서 진행하고,
이 폴더는 **결정의 근거**만 남기는 reference 자료입니다.

---

## 폴더 구조

```
db_research/
├── README.md                              ← 이 파일
├── _template.md                           ← 신규 도메인 조사용 템플릿
└── <domain>/                              ← 도메인별 조사 문서 (로컬 전용 — 공개 repo 비노출)
    └── YYYY-MM-DD_<topic>.md
```

도메인 폴더 명: `smartphone/`, `humanoid/`, `automotive/`, `smartglass/` 등 ID와 일치.
파일명: `YYYY-MM-DD_<topic>.md` 형식.

---

## 조사 워크플로우

### 1. Gap 식별
- 현재 아카이브 소스 목록 확인
- 도메인별 suggest 스크립트가 잘 동작하는지, Crit 2 다중 소스 교차가 충분히 나오는지 점검
- 부족한 영역 (Tier-1 정량 데이터, 정책/NGO, 학술, OEM 발표 등) 식별

### 2. 외부 조사 (web search)
- "{domain} most cited research firm"
- "{domain} Tier-1 analyst report"
- "{domain} 'according to' OR 'predicts' news article"
- 후보 firm/source 리스트업, 인용 빈도 평가

### 3. 접근성 확인
- 각 후보 사이트의 `robots.txt` 확인 (User-agent: *)
- sitemap 존재 여부, 구조 확인
- 무료 공개 여부 (paywall 검증)
- og:meta 등 메타데이터 풍부도 확인

### 4. 빌더 작성 패턴
- 기존 빌더 (`scripts/build_*_archive.py`) 패턴 차용
- 표준 스키마: `url / title / description / lastmod / source / tier`
- sitemap 기반 → URL 키워드 필터 → og:meta 수집

### 5. 오케스트레이션 등록
다음 4곳을 동기화:
- `scripts/build_all_archives.py` 의 `BUILDERS` 리스트
- `src/server.py` 의 `ARCHIVE_REGISTRY`
- `scripts/suggest_<domain>_topics.py` 의 `ARCHIVE_REGISTRY`, `SOURCE_LABEL`, `SOURCE_TAXONOMY`, `keyword_filter`
- `CLAUDE.md` 의 도메인 표 / 빌더 명령

---

## 작성된 조사 문서

| 도메인 | 파일 | 내용 |
|---|---|---|
| Humanoid | [humanoid/2026-05-07_tier1_ib_research.md](humanoid/2026-05-07_tier1_ib_research.md) | Goldman Sachs · Morgan Stanley · BofA Institute 추가 근거 |
| Humanoid | [humanoid/2026-06-11_analyst_feedback_ab_test.md](humanoid/2026-06-11_analyst_feedback_ab_test.md) | 애널리스트 피드백 반영 (JPM·DB·Omdia 추가, 키워드 5종) + 가중치 A/B 테스트 결과 |
| Smartglass | [smartglass/2026-06-11_smartglass_sources.md](smartglass/2026-06-11_smartglass_sources.md) | 신규 도메인 Tier-1 소스 선정 — 재활용 10 + 신규 8 (18개 소스), Display Daily·Xreal·DSCC 등 제외 근거 |

---

## 신규 도메인 조사용 템플릿

[_template.md](_template.md) 사용. 필드:
- 조사 일자
- 현재 아카이브 상태 진단
- Gap 식별 근거
- 후보 소스 리스트 (인용 빈도 / 데이터 유형 / 접근성)
- robots.txt 검토 결과
- 추가 결정 (선정 / 보류 / 제외) 및 이유
- 빌더 구현 메모
