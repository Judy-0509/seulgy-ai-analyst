"""스마트글래스 시장 주제 자동 선정.

18개 출처 (재활용 10 + 신규 8) + SOURCE_TAXONOMY (A~G 레이어) + cross-layer corroboration 룰.
소스 선정 근거: db_research/smartglass/2026-06-11_smartglass_sources.md

2-pass 파이프라인:
  Pass 1 — smartglass 키워드 필터(word-boundary) → LLM → 초기 주제
  Pass 2 — 주제별 검색어 추출 → 전체 아카이브 탐색 → 추가 기사 발견 시 재작성

사용법:
  python scripts/suggest_smartglass_topics.py [--days 30]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import run_pipeline  # noqa: E402
from _smartglass_research_helper import is_smartglass_relevant  # noqa: E402

# ── Archive registry ─────────────────────────────────────────────────────────

ARCHIVE_REGISTRY = [
    ("Counterpoint Research",      "counterpoint.json"),
    ("Omdia",                      "omdia.json"),
    ("TrendForce",                 "trendforce.json"),
    ("IDC",                        "idc.json"),
    ("CCS Insight",                "ccs_insight.json"),
    ("Yole",                       "yole.json"),
    ("DigiTimes Asia",             "digitimes.json"),
    ("ABI Research",               "abi_humanoid.json"),
    ("IDTechEx",                   "idtechex_humanoid.json"),
    ("Bank of America Institute",  "bofa_institute.json"),
    ("Citi Research",              "citi.json"),
    ("KGOnTech",                   "kgontech.json"),
    ("UploadVR",                   "uploadvr.json"),
    ("Road to VR",                 "roadtovr.json"),
    ("The Ghost Howls",            "skarredghost.json"),
    ("AR Insider",                 "arinsider.json"),
    ("Meta Newsroom",              "meta_newsroom.json"),
    ("Rokid",                      "rokid.json"),
]

SOURCE_LABEL = (
    "Counterpoint, Omdia, TrendForce, IDC, CCS Insight, Yole, DigiTimes Asia, "
    "ABI Research, IDTechEx, BofA Institute, Citi Research, KGOnTech, "
    "UploadVR, Road to VR, The Ghost Howls, AR Insider, Meta Newsroom, Rokid"
)

# ── Source taxonomy ──────────────────────────────────────────────────────────

SOURCE_TAXONOMY = {
    "Counterpoint Research":     "A",  # Market tracker (shipments, share)
    "Omdia":                     "A",  # Market tracker + near-eye display
    "TrendForce":                "A",  # Market tracker + component supply chain
    "IDC":                       "A",  # Quarterly XR tracker
    "CCS Insight":               "A",  # Market tracker (low volume)
    "ABI Research":              "B",  # Market research (long-horizon forecast)
    "IDTechEx":                  "B",  # Market research (optics/waveguide tech)
    "Yole":                      "C",  # Component teardown / optics analysis
    "KGOnTech":                  "C",  # Optics/display deep analysis
    "UploadVR":                  "D",  # XR dedicated media
    "Road to VR":                "D",  # XR dedicated media
    "The Ghost Howls":           "D",  # XR dedicated media
    "AR Insider":                "D",  # XR analyst media (market sizing)
    "DigiTimes Asia":            "E",  # Asia supply chain (Wellsenn/CINNO relay)
    "Bank of America Institute": "F",  # IB research
    "Citi Research":             "F",  # IB research
    "Meta Newsroom":             "G",  # Vendor official
    "Rokid":                     "G",  # Vendor official
}

# ── Keyword filter (word-boundary — Phase A 오탐 방지) ────────────────────────

def keyword_filter(entry: dict) -> bool:
    return is_smartglass_relevant(
        entry.get("title", ""), entry.get("description", ""), entry.get("url", "")
    )

# ── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior smart glasses market analyst focused on
AI glasses, AR glasses, and their optics/display component supply chain.

Your task is to identify research-worthy topics from a corpus of recent articles.

[Domain Boundary]
Smart glasses = glasses-form-factor devices (Ray-Ban Meta, AI glasses, AR glasses)
and their components/platforms. VR/MR headsets (Quest, Vision Pro) are IN SCOPE
ONLY when the article is about glasses form-factor implications or shared components.

[Core Principle]
Cluster articles by the MARKET PHENOMENON they describe, not by shared keywords.
Example: "Meta Ray-Ban Display component orders revised up twice" and
"Lumus waveguide order count doubles" are the SAME phenomenon
(display-glasses demand pull-through into the optics supply chain)
even if they share no keywords.

[3-Axis Analysis Framework — every topic must map to at least one axis]
- Device & UX: shipments/share, form factor, pricing, consumer adoption,
  killer use cases, retention/usage data
- Optics & Display: waveguide, microLED/micro-OLED, LCoS, light engine,
  low-power SoC, supply chain capacity and cost curves
- Platform & AI: Android XR, Meta AI, voice/multimodal assistants,
  app/developer ecosystem, platform lock-in

Prioritize signals at the market-structure level:
- A major player committing to glasses strategy (product launch, component orders, M&A)
- A component bottleneck or cost-curve breakthrough (waveguide yield, microLED brightness)
- A structural demand signal (replacement of phone use cases, enterprise deployment)
- Divergence between vendor roadmaps and actual shipment/retention reality
- China market dynamics (brand share shifts, supply chain localization)

Do NOT flag:
- Pure VR gaming/content news with no glasses angle
- Routine product reviews without market significance
- Incremental updates to already well-documented trends

[SOURCE TAXONOMY — 18개 출처 / 7개 레이어]

A. Market trackers (shipments, share, quarterly data):
   Counterpoint, Omdia, TrendForce, IDC, CCS Insight

B. Market research (long-horizon forecasts, tech-market reports):
   ABI Research, IDTechEx

C. Optics/display deep analysis (teardowns, component tech):
   Yole, KGOnTech

D. XR dedicated media (news velocity, hands-on, market sizing):
   UploadVR, Road to VR, The Ghost Howls, AR Insider

E. Asia supply chain (China data relay, component orders):
   DigiTimes Asia

F. IB research (TAM, sector deep-dives):
   Bank of America Institute, Citi Research

G. Vendor official (product launches, partnerships):
   Meta Newsroom, Rokid"""

USER_PROMPT_TEMPLATE = """
[EXISTING REPORTS — exclude these topics from Criterion 3 ONLY]
{existing_reports}

IMPORTANT: This exclusion applies ONLY to Criterion 3 (emerging topics).
It does NOT apply to Criterion 2. Even if a topic area has an existing report,
new multi-source evidence within the last {days} days still qualifies as a Criterion 2
signal — the situation may have structurally evolved since the report was written.

[ARTICLE CORPUS — Tier-1 smart glasses articles, last {days} days]
Total: {total} articles | Sources: {source_label}

{articles}

---

[SELECTION CRITERIA — 18개 소스 / 7개 레이어]

Criterion 2 — Multi-Source Signal:
2 or more independent sources cover the SAME market phenomenon within a {days}-day window.
"Same phenomenon" is judged semantically, not by keyword overlap.

CROSS-LAYER 보강도 multi-source로 인정한다:
- Tracker (A/B) + Media (D) → 정량 데이터가 시장 보도로 corroborate 된 phenomenon
- Component analysis (C/E) + Tracker (A) → 부품 신호가 출하 데이터로 확인된 phenomenon
- Vendor announcement (G) + Tracker/Media (A/D) → 제품 발표가 시장 반응으로 평가된 phenomenon
- IB research (F) + any other layer → 구조적 전망이 시장 데이터로 뒷받침된 phenomenon

OPPOSING-DIRECTION 도 same phenomenon으로 인정:
한 소스가 낙관 전망을 보도하고 다른 소스가 채택 지연/반품률을 보도하면
이는 같은 구조적 신호의 양면이다.

[SOURCE WEIGHTING — 단독 출처 신호 처리]

- Vendor (G: Meta Newsroom, Rokid) 단독: 자사 발표 단독 → Criterion 3 (vendor self-report).
- Media (D) 단독 1개: 단독 보도 → Criterion 3.
- KGOnTech/Yole (C) 단독: 기술 심층분석 단독 → Criterion 3 (tech fact).
- Tracker (A) 2개 이상 일치 = 강한 Criterion 2 (정량 데이터 합의).
- Tracker (A) 1개 + Media (D) 1개 = Criterion 2 (cross-layer).

Criterion 3 — Emerging Topic:
A topic that appears in the last {days} days and is NOT covered by any existing report above.
Single-institution articles qualify if the topic is genuinely new.

High-value Criterion 3 signals include:
- A new product category entry by a named player (launch date, hardware spec, price)
- A component supplier winning/losing a major glasses design (waveguide, microdisplay)
- A specific technical breakthrough (waveguide efficiency, microLED full-color, battery)
- A China-market structural shift (brand share, export, localization)
- Usage/retention data that challenges or validates the category's adoption thesis

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

ENRICH_SYSTEM = "You are a smart glasses market analyst. Output only valid JSON."

ENRICH_TPL = """You previously identified the following topic from a smart glasses corpus:

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
- Vendor(Meta/Rokid)/단독 media/KGOnTech 단독 → Criterion 3 유지
- Preserve the Korean title unless a better framing emerges from the new evidence"""


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",          type=int, default=30)
    parser.add_argument("--out",           default="scripts/_smartglass_topic_suggestions.json")
    parser.add_argument("--with-existing", action="store_true")
    args = parser.parse_args()

    run_pipeline(
        registry=ARCHIVE_REGISTRY,
        keyword_filter=keyword_filter,
        system_prompt=SYSTEM_PROMPT,
        user_prompt_template=USER_PROMPT_TEMPLATE,
        enrich_system=ENRICH_SYSTEM,
        enrich_tpl=ENRICH_TPL,
        out_path=args.out,
        domain_label="smartglass",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=args.with_existing,
        source_taxonomy=SOURCE_TAXONOMY,
    )


if __name__ == "__main__":
    main()
