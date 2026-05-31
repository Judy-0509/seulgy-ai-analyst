# Crawling and Robots Review

Date: 2026-05-07

This document records the current crawling/source policy for Research Helper. It is an operational risk note, not legal advice.

## Current Decision

The following sources are excluded from active smartphone archive collection, public archive listing, topic mining, and preferred external-search source hints:

- Reuters
- Nikkei Asia
- Gartner
- Bloomberg Technology

Existing local historical files or database rows may still exist, but the active code paths no longer include these sources.

## Why These Sources Were Excluded

| Source | Reason | Decision |
|---|---|---|
| Reuters | The archive has no descriptions, so topic quality is mostly title-only. Reuters also blocks many AI/data bots in `robots.txt`. | Exclude from active collection and topic workflows. |
| Nikkei Asia | RSS has title-only quality, with no useful description. Robots also signals broad AI/scraper restrictions. | Exclude from active collection and topic workflows. |
| Gartner | Terms prohibit scraper/robot/data-mining access without prior written consent and prohibit AI input/training/development use. Current smartphone relevance was 0. | Exclude from automated collection. |
| Bloomberg Technology | `robots.txt` blocks Python user agents and many AI/data bots. The RSS feed gives metadata, but policy risk is high and smartphone relevance was weak. | Exclude from active collection and topic workflows. |

## Scope Reviewed

The policy applies to source lists in:

- `scripts/build_all_archives.py`
- `src/server.py` `ARCHIVE_REGISTRY`
- `src/config.py` `RSS_SOURCES`
- `src/services/search.py` preferred publisher stop words / search hints
- `src/services/body_fetcher.py` body-fetch policy

## Baseline Policy

Use these defaults unless a source-specific policy says otherwise.

- Public pages should show only `title`, `source`, `date`, `url`, and short snippets.
- Do not publicly display original article bodies.
- Do not fetch, cache, or send paywalled/login-only content to an LLM.
- Prefer RSS, sitemap, or official APIs over page scraping.
- Follow `robots.txt`, `Crawl-delay`, and explicit site terms.
- Treat AI-specific robots blocks as a signal to avoid using that site's content as LLM input unless licensed or clearly permitted.
- Keep source links visible in reports and avoid long verbatim quotations.

## Active Smartphone Sources

These remain active in smartphone archive/status flows after the exclusion:

| Source | Policy |
|---|---|
| Counterpoint Research | **Body-fetch enabled** (FETCHABLE_SOURCES). robots 재점검 2026-05-30: 전면차단·AI봇차단 없음. Avoid `/api` paths. |
| TrendForce | **Body-fetch enabled** (FETCHABLE_SOURCES). robots 재점검 2026-05-30: clean (전면차단·AI봇차단 없음). Avoid auth/paid paths. |
| Omdia | Metadata only + Wayback 폴백(BLOCKED_SOURCES). 본문 직접 fetch 안 함(유료 firm). |
| IDC | **Body-fetch enabled** (FETCHABLE_SOURCES). robots 재점검 2026-05-30: clean. No paywalled/login content. |
| Yole | Public metadata only; recheck robots before expanding. |
| Morgan Stanley | Public pages only. Avoid blocked auth/content paths and body redistribution. |
| DigiTimes Asia | RSS metadata only. Do not body-fetch article pages. |
| TechInsights | Public metadata only. Treat as research-firm metadata source; no body fetch. |
| UBI Research | Public sitemap/metadata only. No body fetch. |
| CCS Insight | Public sitemap/metadata only. No body fetch. |

## Higher-Risk Sources Still Present In Other Domains

| Source | Recommendation |
|---|---|
| arXiv export | Do not scrape `export.arxiv.org` pages. Use official arXiv API and respect rate limits. |
| Automotive World | Metadata/link use only. Respect `Crawl-delay: 10`. Avoid AI/RAG body ingestion. |
| IEEE Spectrum | Metadata/link use only. Avoid PDF crawling and body ingestion. |
| TechCrunch | RSS metadata only. Avoid body cache and LLM ingestion. |
| MIT Technology Review | RSS/sitemap metadata only. Avoid body cache and LLM ingestion. |
| The Verge | RSS metadata only. Avoid body cache and LLM ingestion. |
| WardsAuto | **2026-05-30 갱신: FETCHABLE 전환** (robots에 AI봇 차단 없음; 단건 on-demand fetch로 Crawl-delay 취지 준수). 아래 "Automotive body-fetch review" 참조. |

## Implementation Notes

Changes made for the exclusion decision:

- Removed Reuters, Gartner, Nikkei Asia, and Bloomberg Technology from `scripts/build_all_archives.py`.
- Removed Reuters, Gartner, Nikkei Asia, and Bloomberg Technology from `src/server.py` `ARCHIVE_REGISTRY`.
- Removed Reuters and Nikkei Asia RSS feeds from `src/config.py`.
- Removed Reuters, Nikkei, Gartner, and Bloomberg publisher hints from `src/services/search.py`.
- Removed Reuters, Nikkei Asia, and Bloomberg Technology from body-fetch policy lists because they are now excluded rather than metadata-only active sources.

The existing files below are not deleted automatically:

- `data/archives/reuters.json`
- `data/archives/nikkei_asia.json`
- `data/archives/gartner.json`
- `data/archives/bloomberg.json`
- existing rows in `data/mi_news/market_dashboard.db`

Delete or archive those manually only if historical data removal is required.

## Suggested Next Step

Add a machine-readable source policy file such as `data/source_policy.json`:

```json
{
  "Reuters": {
    "active": false,
    "allow_metadata": false,
    "allow_body_fetch": false,
    "allow_llm_input": false,
    "reason": "Excluded due to title-only quality and AI/data bot restrictions"
  }
}
```

Then make archive builders and search pipelines consult that policy before fetching or ranking sources.

## Reference URLs

- Reuters robots: https://www.reuters.com/robots.txt
- Gartner Terms: https://www.gartner.com/en/about/policies/terms-of-use

---

## Automotive body-fetch review (2026-05-30)

Automotive 도메인을 smartphone 수준으로 끌어올리며 automotive 소스의 본문 fetch 가능성과
robots.txt를 정밀 점검했다. 모든 후보가 200 OK로 본문 추출에 성공(403/페이월 0건). robots의
AI 크롤러 규칙 + Crawl-delay + 매체 성격(ToS)을 함께 적용해 결정했다.

### robots.txt 점검 결과 (2026-05-30)

| Source | 도메인 | Crawl-delay | AI 크롤러 규칙 | 결정 |
|---|---|---|---|---|
| WardsAuto | www.wardsauto.com | 5~30 | AI봇 차단 없음 (omgili만 차단) | **FETCHABLE** |
| Automotive Dive | (URL=wardsauto.com) | 위와 동일 | 위와 동일 | **FETCHABLE** |
| InsideEVs | insideevs.com | 없음 | 없음 | **FETCHABLE** |
| CnEVPost | cnevpost.com | 없음 | GPTBot/ClaudeBot/anthropic-ai 명시 허용, CCBot/diffbot/omgili만 차단 | **FETCHABLE** |
| CarNewsChina | carnewschina.com | 없음 | 없음 | **FETCHABLE** |
| VW Group | volkswagen-group.com | 없음 | 없음 (OEM PR) | **FETCHABLE** |
| JATO Dynamics | jato.com | 없음 | 없음 | **FETCHABLE** |
| Cox Automotive | coxautoinc.com | 없음 | 없음 | **FETCHABLE** |
| ACEA | acea.auto | 없음 | 없음 (산업협회) | **FETCHABLE** |
| BloombergNEF | about.bnef.com | 없음 | 없음 (무료 블로그) | **FETCHABLE** |
| RMI | rmi.org | 없음 | 없음 (NGO) | **FETCHABLE** |
| Automotive World | automotiveworld.com | 10~600 | **GPTBot/ClaudeBot/CCBot/Google-Extended/Bytespider/Amazonbot/Applebot-Extended 전면 차단** | **metadata-only** |
| Transport & Environment | transportenvironment.org | 없음 | **GPTBot/Google-Extended 차단** | **metadata-only** |

→ 총 11개 FETCHABLE 추가, 2개 metadata-only 유지. `src/services/body_fetcher.py` 반영.

신규 미디어 소스 body-fetch 검토 (2026-05-30):
- **Motor1** (motor1.com): robots clean(전면·AI봇·Crawl-delay 모두 없음), 본문 5000+자 추출 → **FETCHABLE**.
- **Autocar** (autocar.co.uk): robots에 **GPTBot Disallow**(AI 크롤러 차단) + 본문 추출 thin(~400자, JS 렌더링 추정) → **metadata-only**.

### WardsAuto 재검토 (기존 metadata-only → FETCHABLE)

2026-05-07 검토는 WardsAuto/Automotive World를 "metadata/link only"로 두었다. 재검토 결과
WardsAuto의 사유는 robots의 AI 차단이 **아니라** Crawl-delay(5~30) + 트레이드 매체 ToS에 대한
보수적 baseline이었다. robots.txt가 GPTBot/ClaudeBot을 차단하지 않고, 본 도구는 인용 기사를
1건씩 on-demand로 가져오며(대량 크롤링 아님, 5000자 cap, 출처 링크 유지) Crawl-delay 취지에
어긋나지 않으므로 FETCHABLE로 전환한다. 잔여 ToS 리스크(Informa계열 재배포 제한)는 인지하되
"인용·분석 목적 단건 fetch + 출처 표기" 범위로 한정해 수용한다. 반면 Automotive World는 robots가
주요 AI 봇을 명시 차단하므로 metadata-only를 유지한다 (위 표의 "Higher-Risk Sources" 항목과 일치).

### 미해결 / 후속

1. **선행 불일치 — 해결(2026-05-30)**: 문서(2026-05-07)는 Counterpoint/TrendForce/IDC를 "metadata only"로
   적었으나 `body_fetcher.py FETCHABLE_SOURCES`엔 셋 다 포함돼 있었다(코드↔문서 불일치). robots 재점검 결과
   셋 다 **전면차단·AI봇차단 없음** → 코드(body-fetch)가 robots상 타당. 위 "Active Smartphone Sources" 표를
   코드 실제(body-fetch enabled)에 맞춰 갱신함. (Omdia만 유료 firm이라 metadata-only/Wayback 유지.)
2. **데이터 품질**: `automotive_dive.json`의 기사 URL이 전부 `www.wardsauto.com`이다 —
   `build_automotive_dive_archive.py`가 잘못된 도메인을 수집 중일 수 있음(별도 이슈, task #7 점검 시 확인).
- Bloomberg robots: https://www.bloomberg.com/robots.txt
- Omdia robots: https://omdia.tech.informa.com/robots.txt
- Omdia Terms: https://omdia.tech.informa.com/terms-and-conditions
- Google robots.txt explanation: https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt
- EU database protection overview: https://digital-strategy.ec.europa.eu/en/policies/protection-databases
- U.S. Copyright Office Fair Use: https://copyright.gov/fair-use/
