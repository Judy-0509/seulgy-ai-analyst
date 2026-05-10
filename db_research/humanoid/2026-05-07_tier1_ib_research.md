# 휴머노이드 Tier-1 IB 리서치 소스 추가 조사

- **도메인**: humanoid
- **조사일**: 2026-05-07
- **조사자**: Claude (Opus 4.7)
- **트리거**: 사용자 질문 — "휴머노이드도 스마트폰처럼 Tier-1 조사기관이 있는 것이 좋지 않을까?"

---

## 1. 현재 아카이브 상태 (2026-05-07 기준)

휴머노이드 도메인은 23개 소스 전부 활성 상태:

| 레이어 | 소스 | 기사 수 |
|---|---|---|
| A — Independent Media | Robotics & Automation News, TechCrunch Robotics, IEEE Spectrum, The Robot Report, MIT Tech Review, Humanoids Daily, RoboticsTomorrow, The Verge | 1034 / 50 / 32 / 22 / 15 / 699 / 800 / 1 |
| B — First-Party OEM | Boston Dynamics, Figure AI, Unitree, NVIDIA, Apptronik, Agility, 1X | 12 / 16 / 8 / 2 / 15 / 12 / 11 |
| C — Academic | arXiv (cs.RO) | 1411 |
| D — Market Intelligence | IFR, Counterpoint(공유), TrendForce(공유), IDC(공유), IDTechEx, ABI Research, Yano Research | 120 / 267 / 461 / 185 / 2 / 11 / 1 |

### 진단

- **강점**: A/B/C 레이어는 풍부 — 미디어 1,000+건, OEM 공식 발표 76건, arXiv 1,411편
- **Gap**: D (Market Intelligence) 중 IDTechEx/ABI/Yano 가 거의 비어 있음 (1~11건). **스마트폰의 Counterpoint·TrendForce·Omdia·IDC 같은 정량 트래커 합의 부재**

---

## 2. Gap 식별 근거

스마트폰 도메인은 Counterpoint·TrendForce·Omdia·IDC 4개 Tier-1 트래커가 분기별 출하량/점유율 합의 데이터를 제공. 4개 기관 합의 = 최고 신뢰도.

휴머노이드는:
- 시장이 너무 초기 → 전용 정량 트래커 미성숙
- 그러나 **TAM forecast / unit shipment 인용 시 거의 항상 등장하는 firm 3곳이 존재** → 글로벌 인용 빈도 압도적
- 현재 보유: 0건

---

## 3. 후보 소스 조사 (web search 기반)

### Tier-1 — Investment Bank Research (인용 빈도 최상위)

| 소스 | 대표 forecast | 인용 패턴 | 보유 |
|---|---|---|---|
| Morgan Stanley Research | $5T by 2050 · 13M units by 2035 · chip TAM $305B by 2045 | 모든 메이저 매체가 long-term TAM 인용 시 1순위 | ❌ |
| Goldman Sachs Research | $38B by 2035 · 1.4M units · 50K-100K in 2026 | "Goldman Sachs predicts..." 패턴 | ❌ |
| Bank of America Institute | 3B units by 2060 · $35K → $17K cost decline | content cost 분석 빈번 인용 | ❌ |
| Citi Research | 648M units by 2050 | BofA와 묶여 인용 | ❌ (paywall) |

### Tier-2 — 시장조사 firm (이미 보유 또는 빈약)

| 소스 | 보유 | 비고 |
|---|---|---|
| TrendForce (2026 commercialization 50K units) | ✅ 461건 | 강력 |
| Counterpoint (256K units by 2030) | ✅ 267건 | 강력 |
| IDC (18K units 2025, 508% YoY) | ✅ 185건 | 강력 |
| IDTechEx ($30B by 2035) | ✅ 2건 | 강화 필요 |
| ABI Research ($6.5B by 2030) | ✅ 11건 | 강화 필요 |
| MarketsandMarkets ($15.26B by 2030) | ❌ | 후보 |
| Grand View / Fortune Business Insights | ❌ | 보조 |

---

## 4. robots.txt 검토 (2026-05-07 fetch)

### Goldman Sachs (`https://www.goldmansachs.com/robots.txt`)
```
User-agent: *
Disallow: /materials/

User-agent: GPTBot
Disallow: /alumni/
Disallow: /what-we-do/ayco/insights/
Disallow: /insights/top-of-mind/
Disallow: /materials/
Disallow: /what-we-do/research/
...

User-agent: ChatGPT-User
(GPTBot과 동일)

Sitemap: https://www.goldmansachs.com/sitemap.xml
```
- ✅ User-agent: * 는 `/materials/` 만 차단
- ✅ `/insights/articles/` 및 `/insights/goldman-sachs-research/` 허용
- 주의: GPTBot/ChatGPT-User 식별자 사용 금지 → 일반 Mozilla UA 사용

### Morgan Stanley (`https://www.morganstanley.com/robots.txt`)
```
User-agent: *
Sitemap: https://www.morganstanley.com/sitemapindex.xml
Allow: /pub/content/dam/msdotcom/
Disallow: /auth/
Disallow: /pub/
Disallow: /content/
Disallow: /etc/
... (다수 client/auth 경로)
```
- ✅ `/insights/`, `/ideas/` 허용 (disallow 목록에 없음)
- `/content/` 차단되지만 우리 대상 경로에는 영향 없음

### BofA Institute (`https://institute.bankofamerica.com/robots.txt`)
```
User-agent: *
Sitemap: https://institute.bankofamerica.com/content/institute/bank-of-america-institute.sitemap.xml
Disallow: /cgi-bin/
Disallow: /tmp/
```
- ✅ 거의 모든 경로 허용
- `/transformation/` 의 humanoid/physical-ai 페이지 무료 공개

---

## 5. sitemap 구조 / URL 패턴

| 사이트 | sitemap 형태 | 총 URL | humanoid/robot URL |
|---|---|---|---|
| Goldman Sachs | sitemap.xml → sitemap-1.xml (단일) | 6,760 | 9 (insights/articles/, insights/goldman-sachs-research/) |
| Morgan Stanley | sitemapindex.xml → 5개 분할 (main: sitemap.xml) | 4,488 | 10 (insights/articles/, insights/podcasts/, ideas/) |
| BofA Institute | 단일 sitemap.xml | 156 | 5 (transformation/) |

URL 키워드 필터: `humanoid / robot / robotics / physical-ai / automation / embodied / ai-accelerant`

---

## 6. 결정

| 후보 | 결정 | 이유 |
|---|---|---|
| Goldman Sachs Research | **선정** | TAM 인용 1순위, sitemap 안정, 무료 공개 |
| Morgan Stanley Research | **선정** | Adam Jonas 휴머노이드 시리즈, $5T forecast 빈번 인용 |
| Bank of America Institute | **선정** | Physical AI 시리즈 + Humanoid 전용 페이지, 무료 공개 풍부 |
| Citi Research | 보류 | 무료 공개 페이지 부족, robots.txt 추가 검증 필요 |
| MarketsandMarkets / Grand View / Fortune Business Insights | 보류 | press release 위주, 메타데이터 빈약, 다음 라운드에서 재검토 |
| IDTechEx / ABI / Yano 강화 | 별도 작업 | 빌더 robust 재작성 필요 — 본 조사와 분리 |

---

## 7. 빌더 구현 메모

### 작성된 빌더

| 빌더 | 산출 | 첫 빌드 결과 |
|---|---|---|
| `scripts/build_goldman_sachs_archive.py` | `data/archives/goldman_sachs.json` | 7건 |
| `scripts/build_morgan_stanley_archive.py` | `data/archives/morgan_stanley.json` | 7건 |
| `scripts/build_bofa_institute_archive.py` | `data/archives/bofa_institute.json` | 5건 |

### 등록 완료

- [x] `scripts/build_all_archives.py` BUILDERS
- [x] `src/server.py` ARCHIVE_REGISTRY
- [x] `scripts/suggest_humanoid_topics.py` ARCHIVE_REGISTRY / SOURCE_LABEL / SOURCE_TAXONOMY (모두 D 레이어) / keyword_filter (소스 특화 통과 목록)
- [x] `CLAUDE.md`

### 첫 빌드 샘플 데이터 (검증)

**Goldman Sachs**:
- Robotaxis Are Forecast to Become a $400 Billion Market in 2035 (2026-04-30)
- Humanoid robot: The AI accelerant (2025-12-08)
- The global market for humanoid robots could reach $38 billion by 2035

**Morgan Stanley**:
- The Rise of the Humanoid Economy — Adam Jonas & Sheng Zhong (2025-07-10)
- The Robots Are Coming (2025-09-26)
- AI Fuels Tech IPO Revival (2025-11-24)

**Bank of America Institute**:
- Physical AI, part 1: The basics (2026-03-25)
- Physical AI, part 2: Humanoid robots (2026-03-25)
- Physical AI, part 3: The future of mobility (2026-04-01)

---

## 8. 후속 작업

### 검증 항목
- [ ] `suggest_humanoid_topics.py --days 30` 재실행해서 새 소스가 Crit 2 교차에 기여하는지 확인
- [ ] 프론트엔드 LandingPage에서 humanoid 도메인 주제 카드에 새 소스 표시 확인

### 다음 라운드 조사 후보
- IDTechEx / ABI / Yano 빌더 robust 재작성 (메타데이터 수집 강화)
- Citi Research 무료 공개 콘텐츠 재탐색
- Bloomberg Intelligence Robotics 무료 hub 페이지 존재 여부 확인
- Yole Développement 휴머노이드 부품 분석 추가 가능성 (반도체 패키징 외)
- KOTRA / 산업통상자원부 휴머노이드 보고서 (한국 시장)

### 적용 패턴 (다른 도메인에 재사용)
이 조사는 **Tier-1 IB Research를 sitemap-key word 필터로 수집하는 패턴**의 첫 적용 사례.
다른 도메인에도 동일 패턴 사용 가능:
- Smartphone: Goldman Sachs / Morgan Stanley smartphone TAM 리포트
- Automotive: Goldman Sachs auto research, BofA mobility transformation
- Space Datacenter: Morgan Stanley space economy, Goldman Sachs space report
