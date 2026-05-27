"""스마트폰 시장 주제 자동 선정 (옵션 B 정식 채택판).

10개 Tier-1 출처 + SOURCE_TAXONOMY (A~F 레이어) + cross-layer corroboration 룰.

2-pass 파이프라인:
  Pass 1 — 스마트폰 키워드 필터 → LLM → 초기 주제
  Pass 2 — 주제별 검색어 추출 → 전체 아카이브 탐색 → 추가 기사 발견 시 재작성
  + source_layers 자동 채움 (코드가 인용 출처에서 직접 도출)

사용법:
  python scripts/suggest_smartphone_topics.py [--days 30]
  python scripts/suggest_smartphone_topics.py [--days 7] [--with-existing]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402

# ── Archive registry (10 Tier-1 출처) ───────────────────────────────────────

ARCHIVE_REGISTRY = [
    ("Counterpoint Research", "counterpoint.json"),
    ("TrendForce",            "trendforce.json"),
    ("Omdia",                 "omdia.json"),
    ("IDC",                   "idc.json"),
    ("Yole",                  "yole.json"),
    ("DigiTimes Asia",        "digitimes.json"),
    ("CCS Insight",           "ccs_insight.json"),
]

SOURCE_LABEL = (
    "Counterpoint Research, TrendForce, Omdia, IDC, "
    "Yole, DigiTimes Asia, CCS Insight"
)

# ── Source taxonomy (post-process로 source_layers 자동 채움) ────────────────

SOURCE_TAXONOMY = {
    "Counterpoint Research": "A",  # Tracker
    "TrendForce":            "A",
    "Omdia":                 "A",
    "IDC":                   "A",
    "Yole":                  "C",  # Component
    "DigiTimes Asia":        "E",  # Asian supply chain
    "CCS Insight":           "F",  # Carrier / EU consumer
}

# ── Keyword filter ──────────────────────────────────────────────────────────

_KW_PATH = ROOT / "data" / "smartphone_keywords.json"
_KEYWORDS: list[str] = []

def _load_keywords() -> list[str]:
    global _KEYWORDS
    if not _KEYWORDS:
        _KEYWORDS = json.loads(_KW_PATH.read_text(encoding="utf-8")).get("keywords", [])
    return _KEYWORDS

def keyword_filter(entry: dict) -> bool:
    kw = _load_keywords()
    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
    return any(k in text for k in kw)

# ── Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior smartphone market intelligence analyst focused on OEM strategy
and brand-level competitive dynamics.
Your task is to identify research-worthy topics from a corpus of recent analyst reports.

[Core Principle]
Cluster articles by the MARKET PHENOMENON they describe, not by shared keywords.
Example: "Amazon acquires Globalstar" and "LEO satellite market inflection analysis"
are the SAME phenomenon (structural shift to always-on D2D satellite connectivity)
even though they share no keywords.

Prioritize signals at the OEM and brand level:
- A specific OEM achieving a competitive first (market share record, segment leadership, etc.)
- A brand entering a new product category or pivoting strategy
- Structural competitive advantage of one OEM over others becoming visible
- Divergence between OEM roadmaps and consumer adoption reality
- A brand's supply chain or technology self-sufficiency move (proprietary chips, vertical integration)

Also flag:
- Paradigm shifts in market structure that directly affect OEM strategy
- Technology transitions that change how OEMs differentiate their products

Do NOT flag:
- Routine periodic data tracker updates with no directional insight
- Semiconductor/memory supply chain signals with no direct OEM strategy implication
- Incremental updates to already well-documented trends

[SOURCE TAXONOMY — 본 corpus는 7개 Tier-1 출처로 구성, 각 출처의 관점이 다르다]

A. Market trackers (출하/점유율 정량 데이터, 다중 합의로 신뢰):
   Counterpoint Research, TrendForce, Omdia, IDC

C. Component specialist (반도체 패키징·광학 부품 — 기술적 사실 확정):
   Yole

E. Asian supply chain (대만/한국/중국 ODM·EMS·부품, 단독 leak이 잦음 — 보강 증거 필요):
   DigiTimes Asia

F. Carrier / EU consumer perspective (영국/유럽 통신사·소비자 행동):
   CCS Insight"""

USER_PROMPT_TEMPLATE = """
[EXISTING REPORTS — exclude these topics from Criterion 3 ONLY]
{existing_reports}

IMPORTANT: This exclusion applies ONLY to Criterion 3 (emerging topics).
It does NOT apply to Criterion 2. Even if a topic area has an existing report,
new multi-source evidence within the last {days} days still qualifies as a Criterion 2
signal — the situation may have structurally evolved since the report was written.

[ARTICLE CORPUS — Tier-1 smartphone market articles, last {days} days]
Total: {total} articles | Sources: {source_label}

{articles}

---

[SELECTION CRITERIA — 7개 소스 / 4개 레이어]

Criterion 2 — Multi-Source Signal:
2 or more independent sources cover the SAME market phenomenon within a {days}-day window.
"Same phenomenon" is judged semantically, not by keyword overlap.

CROSS-LAYER 보강도 multi-source로 인정한다. 같은 현상에 대해 서로 다른 레이어의 증거가 동시에 등장하는 경우가 strong signal:
- Component layer (Yole 부품) + Tracker layer (Counterpoint/Omdia 출하)
  → "이 칩셋/부품이 실제 양산·출하되었음" 의 양면 확정
- Supply chain leak (DigiTimes) + Tracker confirmation (Counterpoint/Omdia/TrendForce)
  → 루머가 데이터로 corroborate 된 phenomenon
- Carrier/consumer behavior (CCS Insight) + Shipment data (Counterpoint/IDC)
  → 채널과 sell-through 의 일치/불일치 시그널

OPPOSING-DIRECTION 도 same phenomenon 으로 인정:
한 소스가 OEM의 supply-side 로드맵을 보도하고, 다른 소스가 demand-side 소비자 반응을 보도하면
이는 같은 구조적 신호의 양면이다.

[SOURCE WEIGHTING — 단독 출처 신호 처리]

Single-source (1개 출처만) 인 경우 신호 강도 차등:

- DigiTimes Asia 단독:
  공급망 leak 단독 인용 → 가능한 한 Criterion 3 (emerging) 으로 분류.
  다른 소스(특히 A·C·F 중 하나)의 corroboration 이 없으면 Criterion 2 부여 금지.

- Yole 단독 / CCS Insight 단독:
  Vertical specialist single-source → Criterion 3.

- Market tracker (A 그룹) 단독 1개 vs 같은 그룹 2개 이상 일치:
  A 그룹 2개 이상 일치 = 강한 Criterion 2 (시장 정량 합의).
  A 그룹 1개 단독 = Criterion 3.

Criterion 3 — Emerging Topic:
A topic that appears in the last {days} days and is NOT covered by any existing report above.
Single-institution articles qualify if the topic is genuinely new.

High-value Criterion 3 signals include:
- An OEM achieving a market first
- A brand's strategic pivot into a new segment or technology
- A specific OEM's competitive position shifting in a key market
- An OEM product launch that signals industry-wide direction change
- A teardown 또는 component 단독 신호 중 SoC 노드/배터리 셀 화학/카메라 모듈 등 OEM 차별화에 직결되는 기술 fact

---

[OUTPUT — JSON array only, no other text]
Identify 5 to 10 topics. For each topic output:

[
  {{
    "title": "Topic title in Korean (noun phrase capturing the core phenomenon)",
    "criteria": "Criterion 2" | "Criterion 3" | "Criterion 2+3",
    "institution_count": <integer>,
    "articles": [
      {{"date": "YYYY-MM-DD", "source": "<institution>", "title": "<original article title>"}}
    ],
    "key_data": [
      "<concrete data point with %, $, year, or volume figures>",
      "..."
    ],
    "rationale": "왜 이 주제가 일시적 트렌드가 아닌 구조적 신호인지 2~3문장으로 설명. 어떤 레이어들이 corroborate 했는지 명시. 반드시 한국어로 작성."
  }}
]"""

ENRICH_SYSTEM = "You are a smartphone market intelligence analyst. Output only valid JSON."

ENRICH_TPL = """You previously identified the following topic from a smartphone market corpus:

TOPIC (KOREAN): {title}
CRITERIA: {criteria}

CITED ARTICLES:
{existing_articles}

KEY DATA:
{key_data}

RATIONALE: {rationale}

---

Additional articles have now been found that were not in the original corpus but are
relevant to this same market phenomenon:

ADDITIONAL ARTICLES:
{additional_articles}

---

Update this topic to incorporate the additional articles where relevant.
Output a single JSON object only (no markdown, no other text):

{{
  "title": "...",
  "criteria": "Criterion 2" | "Criterion 3" | "Criterion 2+3",
  "institution_count": <count unique institutions across ALL articles>,
  "articles": [
    {{"date": "YYYY-MM-DD", "source": "<institution>", "title": "<article title>"}}
  ],
  "key_data": ["<updated data points — add new concrete figures if found>"],
  "rationale": "모든 기사를 반영한 2~3문장 선정 근거. 어떤 레이어가 추가 corroborate 했는지 명시. 반드시 한국어로 작성."
}}

Rules:
- Keep ALL original cited articles; add additional ones that genuinely support this phenomenon
- Discard additional articles that are not actually about this phenomenon
- Update institution_count to reflect unique institutions across all included articles
- If institution_count rises to 2+ AND cross-layer (다른 레이어 추가), upgrade to Criterion 2 or 2+3
- Single-source DigiTimes/Yole/CCS leaks → Criterion 3 유지
- Preserve the Korean title unless a better framing emerges from the new evidence"""


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",          type=int, default=14)
    parser.add_argument("--out",           default="scripts/_topic_suggestions.json")
    parser.add_argument("--with-existing", action="store_true")
    parser.add_argument("--end-date",      default=None, help="ISO date upper bound (e.g. 2026-05-21) for backfill")
    parser.add_argument("--backfill",      action="store_true", help="Skip trend ranking; save directly to --out as history snapshot")
    args = parser.parse_args()

    run_pipeline(
        registry=ARCHIVE_REGISTRY,
        keyword_filter=keyword_filter,
        system_prompt=SYSTEM_PROMPT,
        user_prompt_template=USER_PROMPT_TEMPLATE,
        enrich_system=ENRICH_SYSTEM,
        enrich_tpl=ENRICH_TPL,
        out_path=args.out,
        domain_label="smartphone",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=args.with_existing,
        source_taxonomy=SOURCE_TAXONOMY,
        end_date=args.end_date,
        backfill=args.backfill,
    )


if __name__ == "__main__":
    main()
