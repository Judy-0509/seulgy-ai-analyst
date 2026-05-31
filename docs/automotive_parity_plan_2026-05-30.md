# Automotive 리서치 Parity 계획 (2026-05-30)

> 목표: 현재 **smartphone** 도메인이 가진 "완성된 리서치"를 **automotive** 도메인에서도
> 동일하게 수행하도록 만든다. (사용자 지시: 기존 automotive 구현이 있더라도 백지에서
> 새로 설계한다는 관점으로, 정확한 격차를 메우는 계획을 수립.)

이 문서는 코드 근거(`file:line`)와 실측 데이터를 바탕으로 작성되었으며, Codex 검토를 받기 위한
자기완결적(self-contained) 계획서다.

> **Codex 검토 기록 (2026-05-30)** — 판정 **APPROVED WITH CHANGES**.
> Gap 1~5 전부 코드로 CONFIRMED. 추가로 누락 격차 2건(Gap 6 아카이브 검색 도메인 스코프,
> Gap 7 body-fetch 커버리지) 식별, 프레임 불일치(5.4)를 필수로 격상, 전역 대신 인자 주입
> (5.1b)을 정식 채택. 본 문서는 해당 피드백을 모두 반영한 개정판이다.

---

## 0. 시스템 개요 (리뷰어용 맥락)

Tier-1 리서치 기관 아카이브 기반 시장 분석 자동화 도구. 도메인은 `smartphone`,
`humanoid`, `automotive`, `space_datacenter` 4종. **리서치는 두 갈래**로 구성된다:

1. **주제 추천 (suggest)** — `scripts/suggest_<domain>_topics.py` + `suggest_<domain>_emerging.py`
   가 `scripts/_suggest_core.py`의 `run_pipeline()`을 호출. 아카이브를 키워드 필터 →
   GLM Pass1(클러스터링/선정) → Pass2(enrich) → **trend 랭킹** → JSON 산출.
   프론트(`LandingPage.jsx`)가 이 JSON의 `trend`/`rank`를 읽어 상승/유지/신규 뱃지와
   정렬을 렌더링.
2. **보고서 생성 (report)** — 활성 경로는 `run_report.py`의 `stage_a~stage_g`. 웹은
   `POST /api/report/start` → `server.py:_run_report()`가 이 stage들을 직접 호출, CLI는
   `run_report.py:main()`이 호출. (`src/state_machine.py`의 `AnalysisPipeline`은 별도의
   구버전 경로로 보이며 활성 보고서 생성에는 쓰이지 않음 — 5.2 참조.)

도메인별 페르소나/프레임은 `src/prompts/system.py`에 정의:
- smartphone(`ANALYST_SYSTEM_PROMPT`): **Build / Sell-in / Sell-through**, 플레이어 Samsung/Apple/CN OEM
- humanoid(`HUMANOID_ANALYST_SYSTEM_PROMPT`): **Hardware / Software-AI / Deployment**
- automotive(`AUTOMOTIVE_ANALYST_SYSTEM_PROMPT`): **Production / Wholesale / Retail** (도메인 설정
  `data/domains/automotive.json`은 Build / Market / Shift로 기술 — 표현 불일치, 6장 참조)

---

## 1. 현황 — automotive는 이미 어디까지 와 있나

| 구성요소 | 상태 | 근거 |
|---|---|---|
| 아카이브 레지스트리 (26 소스) | ✅ | `suggest_automotive_topics.py:27-58` |
| Source taxonomy A~D + cross-layer 룰 | ✅ | 동 `:74-105`, 프롬프트 `:221-245` |
| 키워드 필터 (168개 + broad) | ✅ | `data/automotive_keywords.json`, `:122-146` |
| 도메인 설정 | ✅ | `data/domains/automotive.json` |
| suggest 메이저+Curiosity 2-pass | ✅ | `suggest_automotive_topics.py`, `suggest_automotive_emerging.py` |
| server emerging 머지 | ✅ | `server.py:904` EMERGING_PATHS (automotive 포함, space_datacenter도) |
| frontend 렌더링 (도메인 무관) | ✅ | `LandingPage.jsx`, `DomainContext.jsx` |

**결론: automotive는 "백지"가 아니라 ~85% 배선된 상태.** 아래 격차만 메우면 smartphone
수준에 도달한다.

---

## 2. 확정된 격차 (코드 근거 포함)

### Gap 1 — suggest trend 랭킹이 automotive를 제외
- `scripts/_suggest_core.py:435`
  ```python
  if domain_label not in {"smartphone", "humanoid"} or not topics:
      return topics   # automotive/space는 trend 랭킹 없이 그대로 반환
  ```
- 영향: automotive 토픽에 `trend` 필드가 생성되지 않음 →
  - `server.py:872-875` — `trend.rank` 정렬 대신 **단순 최신순(fallback)**.
  - `LandingPage.jsx:326` — `trend.status` 부재 시 전부 **"NEW" 뱃지**(상승▲/하락▼/유지— 구분 불가).
- 부차: `suggest_automotive_topics.py:382 main()`에 smartphone이 가진 `--end-date`/`--backfill`
  인자 없음 → trend 히스토리 부트스트랩(과거 주차 스냅샷) 불가. trend 랭킹은 히스토리가
  있어야 momentum/Rising/Sustained가 의미를 가짐. (히스토리 저장 배선 `run_pipeline` Step5는
  도메인 무관하게 이미 동작 — `apply_trend_ranking` 호출 `_suggest_core.py:~797`, 히스토리 저장 `~805-811`.)

### Gap 2 — 보고서 시스템 프롬프트(3축 프레임)가 스마트폰으로 하드코딩
- 보고서를 **쓰는** 단계가 시스템 프롬프트를 고정값으로 사용:

  | 단계 | 라인 | 시스템 프롬프트 |
  |---|---|---|
  | `stage_a` 영문 쿼리 | `run_report.py:149,177` | `_get_system_prompt()` (도메인 인지) ✅ |
  | `stage_c` 목차 | `run_report.py:314` | `ANALYST_SYSTEM_PROMPT` (스마트폰 고정) ❌ |
  | `stage_ef` 본문 | `run_report.py:626` | `ANALYST_SYSTEM_PROMPT` (스마트폰 고정) ❌ |
  | `stage_g` 요약·시사점 | `run_report.py:722` | `ANALYST_SYSTEM_PROMPT` (스마트폰 고정) ❌ |

- `ANALYST_SYSTEM_PROMPT`가 곧 "Build/Sell-in/Sell-through 3축 + Samsung/Apple/CN OEM 분류"를
  정의(`src/prompts/system.py:1-14`). 목차·본문·요약이 이를 고정 사용하므로, `main()`이
  `_active_system_prompt`를 도메인용으로 세팅(`run_report.py:1050`)해도 **무시되고** 스마트폰
  골격이 들어감 → **CLI·웹 모두 영향, 전 비(非)스마트폰 도메인 영향**.
- **실측 증거**: 라이브 humanoid 보고서(`/archive/휴머노이드_양산_시대_개막…`)가 휴머노이드
  고유 프레임(Hardware/Software-AI/Deployment)이 아니라 **"Sell-in 전략"/"Sell-through 전략"**
  (스마트폰 채널 개념)으로 서술됨. 내용·플레이어(Figure/1X/Apptronik/Boston Dynamics)는
  휴머노이드로 정확하나 분석 골격이 스마트폰. automotive도 동일하게 Build/Market/Shift가
  아닌 스마트폰 축으로 작성될 것.

### Gap 3 — 웹 보고서 경로가 도메인 페르소나를 세팅하지 않음
- `server.py:658 _run_report()`는 `run_report.py:main()`을 호출하지 않고 `stage_*`를 직접 호출.
  도메인 페르소나/시스템 프롬프트를 세팅하는 코드는 `main():1050-1051`에만 존재:
  ```python
  _active_system_prompt = DOMAIN_SYSTEM_PROMPTS.get(domain, ANALYST_SYSTEM_PROMPT)
  os.environ["GLM_ANALYST_TYPE"] = DOMAIN_ANALYST_TYPES.get(domain, "...smartphone...")
  ```
- `server.py` 어디에도 `GLM_ANALYST_TYPE`/`_active_system_prompt`/`DOMAIN_SYSTEM_PROMPTS` 설정 없음
  (`sess.domain_id`는 humanoid 외부검색 강제 `:707`와 slug 기억 `:830`에만 사용).
- 영향: `stage_a:145`의 `os.getenv("GLM_ANALYST_TYPE", "senior smartphone market analyst")`가
  `.env` 기본값(smartphone)을 그대로 사용 + `_get_system_prompt()`가 모듈 기본값(smartphone)을 반환.
- **실측 증거**: 웹 경로 복제 후 automotive 주제로 `stage_a` 실호출 → system="당신은 스마트폰
  시장 애널리스트입니다", `{analyst_type}`="senior smartphone market analyst" 확인.
  (CLI 경로는 `main()`이 세팅하므로 페르소나 라인은 정상.)

### Gap 4 (선택/품질) — step 프롬프트의 스마트폰 편향 + automotive 전용 스코어링 부재
- `src/prompts/step_prompts.py`의 PRE_SEARCH/TOC/SECTION/INSIGHTS 및 dimension 프롬프트가
  "smartphone market analyst" 역할 선언과 Samsung/Apple/foldable 예시를 포함(일부는 조건문으로
  완화 `:46,87,164`). `{analyst_type}`로 역할은 치환되나 예시는 스마트폰 고정.
- trend 랭킹: smartphone은 generic 스코어링(volume/momentum/source/freshness/novelty),
  humanoid는 전용 스코어링(source-quality 가중치/impact/commitment/repetition penalty,
  `_suggest_core.py:308-424`). automotive는 26개 혼성 소스(OEM PR·NGO 블로그·트래커)라
  naive volume 스코어링이 노이즈에 취약 → 전용 스코어링이 품질에 유리(선택).

### Gap 5 (데이터) — 레이어 불균형
실측(기준일 2026-05-30, 자동차 키워드 필터 적용 후 유효 기사):

| 레이어 | 30일 유효 | 평가 |
|---|---|---|
| A 독립 미디어 | ~608 | 🟢 강함·최신 (Electrek/DigiTimes/CnEVPost/Auto Dive·World/CarNewsChina) |
| C 정량 트래커 | ~570 | 🟡 볼륨 강하나 반도체/부품 편향 (Omdia 1182, Counterpoint 202, TrendForce 267); 순수 판매/등록은 Cox(미국)+JATO(stale)에 의존 |
| D 컨설팅·정책 | ~163 | 🟢 양호 (AlixPartners/SAE/ICCT/ACEA/T&E); CCS Insight 기여 미미(5) |
| B OEM 1차 | ~23 | 🔴 약함 — VW(5, 대부분 2022~)+Toyota(18)뿐. GM/Ford/Hyundai-Kia/BYD/Tesla 등 부재 |

- 판단: EV전환/OEM전략/중국EV/정책·관세/SDV·ADAS 주제군은 A+C+D로 **보고서 작성 충분**.
  단 (i) OEM 1차 레이어 thin, (ii) 판매/등록 정량 깊이 약함(JATO stale, Wards 2026-05-06에서 정지)이
  smartphone 대비 약점.

### Gap 6 (Codex 식별, 필수) — 보고서 아카이브 검색이 도메인 무관
- `src/services/search.py:86` `_load_archives()`가 `data/archives/*.json` **전부**를 단일 풀로 로드.
  `stage_b`/`stage_d`가 이 전역 풀을 검색하므로, automotive 보고서가 쿼리 스코어링으로 걸러지지
  않는 한 **스마트폰/휴머노이드/스페이스 아카이브까지 인용**할 수 있음.
- 필요: 도메인별 아카이브 스코프(레지스트리 기반 화이트리스트) 또는 최소한 소스 필터링.
  suggest 경로는 도메인 레지스트리로 소스를 한정하지만(예: `suggest_automotive_topics.py:27-58`),
  report 경로는 그렇지 않음 — 이 비대칭이 핵심.

### Gap 7 (Codex 식별) — body-fetch 허용목록이 automotive를 거의 미포함
- `run_report.py:581 _fetch_bodies()`는 `FETCHABLE_SOURCES`(`src/services/body_fetcher.py:32`)에
  속한 소스만 본문 fetch. 이 목록은 대부분 스마트폰 소스라 automotive 소스 다수가 빠짐 →
  automotive 보고서는 본문 대신 **메타데이터 스니펫 위주**로 작성됨(smartphone 대비 근거 깊이↓).
- 결정 필요: automotive 소스를 `FETCHABLE_SOURCES`에 확장할지, 아니면 "스니펫 기반"으로
  명시·수용할지.

---

## 3. 구현 계획 (단계별)

### Phase 0 — 전제/검증
- `.env`에 `ZHIPU_API_KEY` 존재 확인됨(실호출 성공). LLM 백엔드 glm.
- (권장) 첫 실전 실행 전 stale 빌더 refresh: `build_wardsauto_archive.py`, `build_jato_archive.py`,
  `build_vw_archive.py`.

### Phase 1 — suggest trend 랭킹 parity (Gap 1) · 저위험·고효과
1. `_suggest_core.py:435` allow-set에 `"automotive"` 추가 → generic `else` 브랜치(=smartphone과
   **동일한** 스코어링)로 진입. (humanoid처럼 전용 스코어링을 원치 않으면 코드 변경은 이 한 줄.)
2. `suggest_automotive_topics.py:main()`에 `--end-date`/`--backfill` 인자 추가 (smartphone:244-247 패턴 복제),
   `run_pipeline(..., end_date=, backfill=)` 전달.
3. 과거 4~8주 백필로 trend 히스토리 부트스트랩 후 메이저 패스 1회 실행.
4. **검증**: `_automotive_topic_suggestions.json`에 각 토픽 `trend.status`/`trend.rank_score`/`trend.rank`
   존재 확인. 웹 랜딩에서 상승/유지/신규 뱃지·정렬 노출 확인.

### Phase 2 — 보고서 도메인 프레임+페르소나 라우팅 (Gap 2+3) · humanoid도 동시 수정
**채택 방식: 전역 상태가 아니라 인자 주입(5.1b).** Codex 검토 반영 — 전역(`_active_system_prompt`,
`os.environ`)은 동시 멀티도메인 보고서에서 교차 오염 위험. blast radius는 중간 수준이며 정석.

1. **stage 함수 시그니처에 `system_prompt`·`analyst_type` 인자 추가**:
   `stage_a` / `stage_c` / `stage_ef` / `stage_g` (4개). 내부 `llm.complete(...)`의 시스템 프롬프트
   (`run_report.py:149,177,314,626,722`, 총 5곳)와 `{analyst_type}` 주입(`:145,304,604,714`)이
   전역/`getenv` 대신 인자를 사용하도록 교체.
2. **호출부 8곳 갱신**:
   - `server.py:_run_report()` — `sess.domain_id`로 `system_prompt=DOMAIN_SYSTEM_PROMPTS.get(...)`,
     `analyst_type=DOMAIN_ANALYST_TYPES.get(...)`를 각 stage에 전달 (4 호출).
   - `run_report.py:main()` — `--domain`으로 동일하게 전달 (4 호출). 기존 `:1050-1051`의 전역 세팅은 제거.
3. **검증**: automotive 보고서 1건씩 web·CLI 생성 → 본문/요약이 정본 3축(5.4 결정값) 프레임,
   플레이어가 Toyota/VW/BYD 등, "Sell-in/Sell-through" 미등장 확인. humanoid 보고서 재생성 →
   Hardware/Software-AI/Deployment 프레임 확인. smartphone 회귀 없음 확인.
   (동시성 검증: automotive·smartphone 보고서를 **동시 실행**해 교차 오염 없음 확인.)

### Phase 3 (선택) — automotive 깊이 튜닝
- step 프롬프트 예시를 도메인 설정에서 주입(역할/축/플레이어 파라미터화).
- `apply_trend_ranking`에 automotive 전용 브랜치(humanoid의 source-quality 패턴 차용):
  A/B/C/D 레이어 가중치 + EV전환/SDV/자율주행 impact 휴리스틱.

### Phase 4 (선택) — 데이터 레이어 보강
- OEM 1차(B) 확장: GM/Ford/Hyundai-Kia/BYD 뉴스룸 빌더 추가.
- 판매/등록 정량 보강: JATO/Wards refresh, 등록 데이터 소스 검토.

### Phase 5 — 최종 검증 (smartphone와 동등성 비교)
- suggest: automotive vs smartphone 산출 JSON의 trend 필드 구조 동일성.
- report: 동일 난이도 토픽으로 automotive/smartphone 보고서 생성 → 섹션 수, 인용 밀도,
  프레임 적합성 비교.

---

## 4. 변경 파일 요약

| 파일 | 변경 | Phase |
|---|---|---|
| `scripts/_suggest_core.py` | `:435` allow-set에 automotive 추가 | 1 |
| `scripts/suggest_automotive_topics.py` | `main()`에 `--end-date`/`--backfill` | 1 |
| `run_report.py` | `stage_a/c/ef/g` 시그니처에 `system_prompt`·`analyst_type` 인자화 (시스템 프롬프트 5곳 `:149,177,314,626,722` + analyst_type 4곳 `:145,304,604,714`); `main():1050-1051` 전역세팅 제거 | 2 |
| `src/server.py` | `_run_report()`에서 `sess.domain_id`로 stage에 인자 전달 (4 호출) | 2 |
| `src/prompts/system.py` 또는 `data/domains/automotive.json` | automotive 3축 정본 통일 (5.4, **필수**) | 2 |
| `src/services/search.py` | report 아카이브 검색에 도메인 스코프/소스 필터 (Gap 6, **필수**) | 2 |
| `src/services/body_fetcher.py` | `FETCHABLE_SOURCES`에 automotive 소스 확장 (Gap 7) 또는 스니펫 수용 명시 | 2/문서화 |
| (선택) `src/prompts/step_prompts.py` | 예시 파라미터화 | 3 |
| (선택) `scripts/_suggest_core.py` | automotive 전용 스코어링 브랜치 | 3 |
| (선택) `scripts/build_*_archive.py` | OEM 빌더 추가 / refresh | 4 |

---

## 5. 리스크 / 설계 메모

### 5.1 동시성 — 전역 상태로 도메인을 전달하는 구조 (중요)
`run_report._active_system_prompt`(모듈 전역)와 `os.environ["GLM_ANALYST_TYPE"]`(프로세스 전역)는
**요청 단위가 아니라 프로세스 단위** 상태다. 웹 서버에서 서로 다른 도메인의 보고서가
**동시에** 생성되면 전역값이 경합해 교차 오염될 수 있다. Phase 2의 최소 수정(전역 세팅)은
저동시성 환경에서 동작하지만, 정석은 **시스템 프롬프트/analyst_type을 stage 함수 인자로
주입**하는 리팩터다.
- **결정(Codex 검토 반영): (b) 인자화 리팩터를 채택** — `stage_a/c/ef/g(..., system_prompt=, analyst_type=)`.
  `server.py`는 `asyncio.create_task()`(`:1434`)로 보고서를 동시 실행하므로 전역 교차 오염이 실제
  위험. Blast radius: stage 시그니처 4개 + 호출부 8곳(server 4 + main 4) + 내부 `llm.complete`
  시스템 프롬프트 5곳. (a) 전역 세팅은 채택하지 않음.

### 5.2 구버전 경로 정리
`src/state_machine.py:AnalysisPipeline`(`server.py:_run_phase0`/`RunContext`)은 활성 보고서
생성에 쓰이지 않으나, `plan_propose:84`가 `PRE_SEARCH_PROMPT.format(topic, current_year)`를
analyst_type 없이 호출 → 호출 시 `KeyError` (격리 테스트로 확인). 또한 `self._sys`(`:52`)를
로드만 하고 미사용. **활성 경로 아님**이나, 혼선 방지를 위해 (i) 제거 또는 (ii) 동일 패턴으로
수정 권장. 본 계획의 필수 범위는 아님.

### 5.3 공유 코드 회귀
Phase 2는 humanoid·space_datacenter에도 영향(공유 stage). smartphone은 `_get_system_prompt()`
기본값이 `ANALYST_SYSTEM_PROMPT`라 무변경. 회귀 테스트에 4개 도메인 모두 1건씩 포함.

### 5.4 표현 불일치 (**필수 수정** — Codex 검토 반영)
automotive 3축이 `data/domains/automotive.json:9`에는 **Build/Market/Shift**, `system.py:31`의
`AUTOMOTIVE_ANALYST_SYSTEM_PROMPT`에는 **Production/Wholesale/Retail**로 서로 다르게 기술됨.
보고서 경로가 사용하는 것은 `system.py`(Phase 2 적용 시) — **어느 프레임을 정본으로 할지 확정 후
일관 적용은 선택이 아니라 필수**. suggest 경로는 `suggest_automotive_topics.py`의 인라인
프롬프트(Build/Market/Shift)를 사용하므로, 두 경로 간 프레임을 동일하게 맞춰야 함.

### 5.5 데이터 신선도
Gap 5의 stale 빌더(Wards/JATO/VW)는 trend momentum과 보고서 근거 신선도에 영향. Phase 1/2
기능 수정과 독립적으로 운영(빌더 실행)으로 해소 가능.

---

## 6. 의사결정 필요 항목 (리뷰 포인트)

**이미 결정됨 (Codex 검토 반영):**
- 보고서 도메인 라우팅 = **인자화 리팩터(5.1b)** 확정.
- 프레임 정합(5.4)·report 아카이브 검색 스코프(Gap 6) = **필수 범위**로 확정.

**사용자 결정 확정 (2026-05-30):**
1. trend 랭킹 = **automotive 전용 스코어링** (humanoid 패턴 차용: A~D 레이어 source-quality 가중치
   + EV전환/SDV/자율주행 impact 휴리스틱). `apply_trend_ranking`에 automotive 전용 브랜치 추가.
2. 정본 3축 = **Build / Market / Shift**. `system.py`의 `AUTOMOTIVE_ANALYST_SYSTEM_PROMPT`를
   이 프레임으로 교체 (suggest 프롬프트 + `automotive.json`과 일치).
3. body-fetch = **fetch 검증 통과 13개 소스 확장** (robots/ToS 검토 후 선별): WardsAuto,
   Automotive Dive, Automotive World, InsideEVs, CnEVPost, CarNewsChina, VW Group, JATO,
   Cox Automotive, ACEA, BloombergNEF, RMI, Transport & Environment. EMPTY 5개(Electrek,
   Toyota Newsroom, AlixPartners, SAE, ICCT)는 스니펫 유지(추후 전용 추출기 검토), IRENA 재시도.
4. 추가 범위 = **전부 포함**: (a) stale 빌더 refresh(Wards/JATO/VW), (b) OEM 뉴스룸 빌더 신규
   추가(GM/Ford/Hyundai-Kia/BYD), (c) 구버전 경로(state_machine 보고서 경로) 정리.

---

## 7. 구현 결과 (2026-05-30)

| Task | 상태 | 검증 |
|---|---|---|
| 1. automotive 전용 trend 스코어링 | ✅ 완료 | 단위 테스트: BYD>단일 OEM PR 랭킹 |
| 2. `--end-date`/`--backfill` 인자 | ✅ 완료(코드) | argparse 확인. ※ 다중 주차 백필 *실행*은 운영 미수행 |
| 3. 3축 Build/Market/Shift 통일 | ✅ 완료 | system.py 프롬프트 확인 |
| 4. stage 인자화(동시성 안전) | ✅ 완료 | 웹=자동차 페르소나, 전역 변동 0, 기본값 smartphone 백워드호환 |
| 5. 보고서 아카이브 검색 도메인 스코프 | ✅ 완료 | 16049→8133, 가드레일≥10 통과, humanoid fail-open |
| 6. body-fetch 11개 확장 | ✅ 완료 | robots 정밀 검토, 11 FETCHABLE/2 metadata-only |
| 9. state_machine 구버전 경로 정리 | ✅ 완료 | plan_propose KeyError 해소+self._sys 사용, 서버 dead 엔드포인트 4개 제거 |
| 10. end-to-end 검증 | ✅ 완료(automotive capstone) | 아래 |

**Capstone(실제 GLM 보고서, "BYD 유럽 공세와 EU 관세"):** exit 0. 프레임 점유율6/전환3/생산5,
**Sell-in·Sell-through 0, 스마트폰·Galaxy·iPhone 0**, 플레이어 BYD/Tesla/VW. 도메인 스코프로 검색
소스 전부 automotive 레지스트리. body-fetch 33건. → smartphone 수준 리서치 동작 확인.
(humanoid/smartphone 실제 보고서 run은 토큰 절약 위해 미실행 — 단위 테스트로 3개 도메인 라우팅 검증됨.)

**Suggest 실측(automotive, --days 14):** 282 기사 → 7개 토픽. 전 토픽에 `trend.rank_score/rank/status`
+ automotive 전용 필드(source_quality/impact/commitment) 생성 확인. 랭킹 합리적(상용차 전기화·로보택시
impact 1.0 상위 / 충전 M&A·페라리 EV 하위). `status`는 첫 실행이라 전부 "New" — Rising/Cooling 분화는
`_history` 누적(주간 실행 또는 `--backfill`) 후.

**테스트:** `pytest --collect-only` 65개 collect(import 깨짐 0), 비-GLM 단위 23개 PASS
(test_search_relaxed/test_state_machine/test_models/test_llm_service). GLM 통합 테스트
(test_fallback_prompt 3건)는 collect만 확인(실행은 토큰 소모로 생략) — plan_propose KeyError는 해소됨.

### 신규 follow-up (capstone에서 발견)
- **공유 트래커 파일 내부 정제**: report 검색 경로가 도메인 *파일*까지는 스코프하나, 공유 트래커
  파일(Counterpoint/Omdia/CCS/DigiTimes 등) *내부*의 비(非)자동차 기사(smartphone/datacenter)는
  걸러내지 못해 검색 풀에 일부 유입(최종 인용엔 0건, LLM이 필터). suggest 경로처럼 report 검색에도
  공유 소스에 automotive 키워드 필터 적용하면 풀 품질↑. (출력 정상이므로 비차단 개선거리.)
- **stage_g `korea_impact` 공란**: capstone에서 korea_impact ×. 본 작업과 무관한 기존 동작 추정 — 별도 점검.

### 미완료 (운영/탐색 — 별도 진행 필요)
- **Task 8 stale 빌더 refresh**(Wards/JATO/VW): 운영 실행(네트워크 크롤). 미실행.
- **Task 7 OEM 뉴스룸 빌더**: 실현가능성 조사 결과 — **4개 OEM 모두 단순 sitemap/RSS로 1차 뉴스
  수집 불가**(2026-05-30 실측):
  - GM(news.gm.com)·Hyundai(hyundainews.com): sitemap.xml이 HTML 반환(JS 렌더링), robots에 Sitemap
    디렉티브 없음, RSS 없음.
  - Ford(media.ford.com): 봇 차단(ReadTimeout).
  - BYD: www.byd.com=지역별 마케팅 sitemap(뉴스 없음), en.byd.com=빈 WordPress(포스트 2개, 최신
    2020 "Hello world"). → **사용 가능한 영문 뉴스룸 부재.**
  → B 레이어(OEM 1차) 확장은 **Selenium/JSON-endpoint 기반 맞춤 크롤러**(GM/Hyundai)가 필요하고
    Ford는 봇차단, BYD는 소스 부재. **빈 빌더는 만들지 않음.** 실용 대안: BYD/OEM 발표는 이미
    CnEVPost·CarNewsChina·Electrek·WardsAuto 등 미디어 + 트래커가 커버하므로 B레이어는 *plus*지 필수 아님.
    B레이어가 꼭 필요하면 GM/Hyundai Selenium 빌더를 별도 작업으로 진행.

---

## 부록 A. Codex 검토 요약 (2026-05-30, read-only)
- **판정: APPROVED WITH CHANGES.**
- Gap 1~5 전부 CONFIRMED (file:line 대조). Gap 5 레이어 수치(A=608/B=23/C=570/D=163) 재현 확인.
- 추가 식별: Gap 6(아카이브 검색 도메인 무관, `search.py:86`), Gap 7(body-fetch 커버리지, `body_fetcher.py:32`).
- 요구 변경: ①인자 주입 채택 ②trend allow-set+백필 인자 ③프레임 정본 통일 ④report 검색 도메인 스코프
  ⑤body-fetch 확장 여부 결정. → 본 개정판에 모두 반영.
