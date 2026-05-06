# Smartphone 주제 선정 파이프라인 — 진단 & 개선 회고 (2026-05-07)

> 본 문서는 다른 에이전트/엔지니어가 컨텍스트 없이 들어와 현재 상태를 파악하고
> 후속 작업을 이어갈 수 있도록 작성된 self-contained 회고록입니다.
> 의사결정 근거(WHY) 위주로 기록하며, 코드/구조 자체는 `CLAUDE.md`와
> `docs/process_overview.html`을 참조하세요.

---

## 1. 출발점 — 무엇을 고민했나

스마트폰 도메인의 주간 추천 주제를 자동 선정하는 `scripts/suggest_smartphone_topics.py`가
**5개 출처**(Counterpoint, TrendForce, Omdia, IDC, Morgan Stanley)만 사용하고 있었음.

문제 의식:
- D2D 위성통신, 패널·부품, 공급망 leak 등 가치사슬 일부만 보도하는 신호가 누락됨
- 30일 윈도우에서 대부분 토픽이 Counterpoint × Omdia 2개 출처 합의로만 잡힘 — 단조로움
- 단일 트래커 layer만 보다 보니 "이 칩셋이 실제 양산되었나"
  ("패널 발주 → 디바이스 출하" 선행지표) 같은 cross-layer 신호를 놓침

가설: **출처 수를 늘리고 출처별 관점(레이어)을 명시한 prompt를 주면 토픽이 더 입체적이 될 것이다.**

---

## 2. 실험 설계 — 옵션 A vs 옵션 B

A/B 두 패스를 동일 30일 윈도우, 동일 LLM(GLM-4.7 thinking), 동일 키워드 필터(73개)로
실행하여 결과를 비교했다. **기존 보고서 EXCLUDE 룰은 양쪽 모두 비활성**(`--with-existing` off)
— 누적된 과거 보고서가 토픽 후보를 가리지 못하도록.

| 항목 | 옵션 A (baseline) | 옵션 B (확장 + taxonomy) |
|---|---|---|
| 출처 | 5개 (Counterpoint, TrendForce, Omdia, IDC, Morgan Stanley) | 10개 (A 5개 + Yole, DigiTimes Asia, TechInsights, UBI Research, CCS Insight) |
| Prompt | 기본 Crit 2/3 룰만 | 6개 layer (A·B·C·D·E·F) + cross-layer corroboration 룰 + 단독 출처 가중 차등 룰 |
| 출력 | `_topic_suggestions.json` | `_topic_suggestions_b.json` |

실험 산출물 (시점: 2026-05-07 01:15 ~ 01:36):
- A: `scripts/_history/smartphone_2026-05-07T01-15-42.json` (백업)
- B: 동일 디렉토리에 `smartphone-b_*` 형태로 보관

---

## 3. 정량 비교 결과

| 측면 | A | B |
|---|---|---|
| 코퍼스 (30일 키워드 필터 통과) | 157건 | **182건** (+15.9%) |
| Pass 1 thinking | 13,322자 | 14,597자 |
| 식별 토픽 수 | 6 | **8** |
| 평균 institution_count | 2.17 | **3.13** (+44%) |
| 평균 인용 기사/토픽 | 4.0 | **5.5** (+38%) |
| Cross-layer 인식 | A (Tracker) 단일 | A+C, A+D, A+E 등 다층 |
| Crit 2+3 토픽 | 0 | 1 (AI 글래스) |

**B가 잡고 A가 놓친 토픽**:
- "애플의 파운드리 공급망 다변화 (삼성·인텔 활용 검토)" — DigiTimes leak + TrendForce corroboration
- "AI 글래스 차세대 앰비언트 컴퓨팅" — A에서는 "AI 에이전트 vs 수용도" 묶음에 흡수되었던 것
- "폴더블 시장 구조 재편" — A는 "iPhone 17e + 북미 폴더블"로 좁게 인식, B는 시장 단위 재편으로 격상

**B의 약점 (실험 중 발견)**:
- LLM이 출력하는 `source_layers` 필드가 5/8 토픽에서 **잘못된 라벨**을 붙임
  (예: 실제 인용은 DigiTimes(E)+TrendForce(A)+Omdia(A)인데 LLM이 `["B","C"]`라 표기)

---

## 4. 출처별 커버리지 진단 (4번 작업)

10개 출처가 실제로 LLM 토픽에 얼마나 인용되는지를 측정.

| 출처 | total | last30d | kw 통과 | B 토픽 인용 | 상태 |
|---|---:|---:|---:|---:|---|
| Counterpoint Research | 265 | 65 | 32 | 6 | 정상 |
| TrendForce | 452 | 71 | 28 | 6 | 정상 |
| Omdia | 1,458 | 444 | 95 | 7 | 정상 |
| IDC | 183 | 40 | 2 | 1 | 매칭 빈약 |
| Morgan Stanley | 662 | 8 | **0** | **0** | 도메인 부적합 (거시경제만 수집) |
| Yole | 33 | 8 | 3 | 0 | archive 부실 |
| DigiTimes Asia | 58 | 58 | 10 | 5 | **B의 핵심 기여** |
| TechInsights | 52 | **0** | 0 | 0 | **빌더 작동 불능** |
| UBI Research | 880 | 17 | 9 | **0** | 일본어/한국어 제목으로 LLM이 영문 narrative 형성 시 회피 |
| CCS Insight | 2,640 | 11 | 3 | 0 | 신호 약함 |

**진단 도구**: `scripts/_diag_source_coverage.py` (남겨둠. 차후 같은 분석 반복 가능).

**핵심 발견**:
- B의 실질 이득은 **DigiTimes Asia 단독으로부터** 나온다.
  나머지 4개(UBI, Yole, TechInsights, CCS)는 데드 웨이트.
- TechInsights는 30일 동안 한 건도 추가되지 않았음 — sitemap/CDN 변경 가능성 (이전 회의에서 CDN cache로 어렵게 해결한 적 있음).
- Morgan Stanley는 archive에 거시경제 보고서만 모이고 스마트폰 키워드 매칭이 0건. 도메인 부적합.
- UBI Research는 일본어/한국어 제목이 코퍼스에 다수 포함되어 LLM이 인용을 꺼리는 듯.

---

## 5. 결정 — 무엇을 채택했나

### 5.1 옵션 B를 main으로 승격
- `scripts/suggest_smartphone_topics.py`를 옵션 B 코드로 전체 교체
- 단, `domain_label`은 `smartphone`(원래대로), 출력 경로도 `_topic_suggestions.json`(원래대로) 유지
- 기존 `suggest_smartphone_topics_b.py` 삭제, `_topic_suggestions_b.json` 삭제

### 5.2 `source_layers` 자동 채움 (post-process)
- LLM 출력에 의존하지 않고, 인용 출처 이름 → `SOURCE_TAXONOMY` dict로 코드가 자동 매핑
- 구현: `scripts/_suggest_core.py:run_pipeline()`에 `source_taxonomy` 파라미터 추가
  → 마지막 단계에서 `topic["source_layers"]` 덮어씀
- 이번 마이그레이션에서 5/8 토픽의 라벨 오류가 100% 교정됨

### 5.3 Dead-weight 3개 출처 영구 제거 (사용자 결정)
**제거 대상**: TechInsights, Morgan Stanley, UBI Research

**제거 범위**:
- `scripts/build_techinsights_archive.py`, `build_morgan_stanley_archive.py`, `build_ubi_research_archive.py` 삭제
- `data/archives/techinsights.json`, `morgan_stanley.json`, `ubi_research.json` 삭제
- `scripts/build_all_archives.py` BUILDERS 목록에서 제외
- `scripts/suggest_smartphone_topics.py` ARCHIVE_REGISTRY / SOURCE_TAXONOMY / SOURCE_LABEL / SYSTEM_PROMPT taxonomy 섹션 / USER_PROMPT_TEMPLATE cross-layer 룰에서 제외
- `src/server.py` ARCHIVE_REGISTRY에서 제외
- `src/services/body_fetcher.py` FETCHABLE_SOURCES (Morgan Stanley) / METADATA_ONLY_SOURCES (TechInsights, UBI Research)에서 제외
- `frontend/src/theme.js` SRC_COLOR_MAP에서 제외
- `CLAUDE.md` 도메인 표 / 빌드 스크립트 목록 / 파일 트리 동기화

**남은 7개 활성 출처**:
| Layer | 출처 |
|---|---|
| A · Tracker | Counterpoint Research, TrendForce, Omdia, IDC |
| C · Component | Yole |
| E · Asian Supply | DigiTimes Asia |
| F · Carrier/EU | CCS Insight |

> Yole(33 entries)과 CCS Insight(낮은 인용률)은 **현재로서는 약한 신호**지만 단독 시그널 가치가 있어
> 보존. 향후 7-day emerging 패스에서 더 적극적으로 활용될 가능성을 위해 남김.

---

## 6. 미해결 이슈

### 6.1 Criterion 3 부족
30일 윈도우에서는 단독 출처 신호가 corroborate되어 모두 Crit 2로 흡수됨.
B 결과 8개 토픽 중 순수 Crit 3 = 0개, Crit 2+3 = 1개.

→ **별도 7일 또는 14일 윈도우로 emerging 패스를 분리 운영**할 것을 권장 (다음 항목 참고).

### 6.2 7일 Curiosity Pick 패스 — 구현 완료 (2026-05-07 후속)
사용자 인터뷰 결과 4가지 흥미 패턴(a/b/e/g)으로 정의:
- (a) 마이너 OEM의 strategic movement
- (b) 메이저 narrative와 반대되는 contrarian signal
- (e) 단발성 기술 fact / 부품 leak (Tier-1 출처 단독)
- (g) 대형 OEM(Apple/Samsung/Huawei)의 off-trend behavior

**구현**: `scripts/suggest_smartphone_emerging.py` (신규).
- 7일 윈도우, Tier-1 7개 출처 그대로 사용
- 출력: `scripts/_topic_suggestions_emerging.json`
- 모든 토픽 `criteria="Criterion 3"` 강제
- Server.py `/api/topics/suggested`가 메이저 응답에 자동 merge
- Frontend "이번 주 새롭게 등장한 주제" 섹션이 Crit 3 분류로 자동 노출
- 권장 빈도: 메이저와 동일하게 **주 1회** (요일 미정)

### 6.3 IDC 키워드 매칭 빈약
IDC는 30일 40건 중 키워드 통과가 2건뿐. 키워드 필터가 IDC의 일반적 표제(Quarterly Tracker 등)와
잘 맞지 않음. 향후 IDC 전용 키워드 보강 또는 source-specific 필터 도입 고려.

### 6.4 codex가 별도로 비활성화한 4개 출처
Reuters, Gartner, Nikkei Asia, Bloomberg는 robots.txt/AI 봇 차단 정책으로 codex가 BUILDERS에서
제외했지만 `data/archives/{reuters,gartner,nikkei_asia,bloomberg}.json` 파일은 여전히 디렉토리에 잔존.
이번 작업에서는 사용자가 명시적으로 지목한 3개 (TechInsights, Morgan Stanley, UBI)만 정리.
4개 codex 잔존 JSON은 별도 결정 필요 (보존 vs 삭제).

---

## 7. 후속 에이전트 인계 노트

### 7.1 핵심 산출물 위치
| 파일 | 역할 |
|---|---|
| `scripts/suggest_smartphone_topics.py` | **현재 main 파이프라인 (옵션 B 정식 채택판)** |
| `scripts/_suggest_core.py` | 도메인 공통 엔진 — `source_taxonomy` 파라미터 사용 |
| `scripts/_topic_suggestions.json` | UI에 노출되는 최신 결과 (현재 8 토픽) |
| `scripts/_topic_suggestions.json.pre-b-migration.bak` | 옵션 A 결과 백업 |
| `scripts/_history/smartphone-b_*.json` | 옵션 B raw 결과 백업 |
| `scripts/_diag_source_coverage.py` | 출처별 커버리지 진단 도구 (재사용 가능) |
| `docs/topic_pipeline_review_2026-05-07.md` | 본 문서 |
| `docs/process_overview.html` | 발표용 시각 자료 |

### 7.2 재실행 방법
```bash
# 30일 main 패스 (현재 활성, 매일 또는 주간 권장)
python scripts/suggest_smartphone_topics.py --days 30

# 7일 단기 패스 (테스트용)
python scripts/suggest_smartphone_topics.py --days 7
```

출력:
- `scripts/_topic_suggestions.json` (덮어씀, 이전 버전은 `scripts/_history/`에 자동 보관)
- 콘솔에 토픽 요약 + 인용 출처 + key_data 출력
- 평균 실행 시간: 12~15분 (Pass 1 + N개 enrichment, GLM-4.7 thinking 모드)

### 7.3 자주 만나는 함정
1. **`source_layers` 라벨**: 이제 코드가 자동 채움. LLM 응답 라벨은 무시되니 신뢰하지 말 것.
2. **enriched_count vs topics 길이**: enrichment 단계에서 추가 기사가 0건인 토픽도 있으니
   둘이 다를 수 있음. UI는 모든 토픽을 표시.
3. **cp949 / BOM 문제**: Windows 환경에서 `Read` 도구가 한글 주석을 mojibake로 반환하는 경우가 있음.
   직접 utf-8 read/write로 처리하거나 `_strip_bom.py` 패턴 참고.
4. **GLM-4.7 동시성**: 현재 `glm_limiter.py`로 file-lock 기반 직렬화. 동시성 상한 미측정.
   `scripts/probe_glm_concurrency.py` 미실행 (todo 항목).

### 7.4 다음 우선순위
| 우선순위 | 항목 | 비고 |
|---|---|---|
| HIGH | 7일 emerging 설계 — 사용자 인터뷰 진행 | "흥미 관점" 정의 명확화 필요 |
| MID | IDC 전용 키워드 보강 | 매칭률 2/40 → 개선 |
| MID | codex가 비활성화한 4개 출처(Reuters/Gartner/Nikkei/Bloomberg) JSON 파일 정리 결정 | |
| LOW | GLM 동시성 상한 측정 | `scripts/probe_glm_concurrency.py` 실행 |
| LOW | `data/source_policy.json` 정책 파일 도입 (`todo.md` 항목 1) | |

---

## 8. 근거 / 참고

- 옵션 A 결과 raw: `scripts/_history/smartphone_2026-05-07T01-15-42.json`
- 옵션 B 결과 raw: `scripts/_history/smartphone-b_*` (동일 시점 파일)
- robots.txt 정책: `docs/crawling_robots_review.md` (codex 작성)
- 기존 todo: `todo.md` (3개 항목 — source_policy.json, identifiable UA, robots 분기 재점검)

> **이 문서를 갱신해야 하는 시점**:
> - 출처 추가/제거 시 (5장 표 갱신)
> - 7-day emerging 설계 확정 후 (6.2 결과 반영)
> - 2026 Q3 분기 robots.txt 재점검 후 (4.codex 잔존 출처 결정)
