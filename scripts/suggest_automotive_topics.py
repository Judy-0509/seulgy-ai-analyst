"""자동차 시장 주제 자동 선정.

2-pass 파이프라인:
  Pass 1 — Automotive 키워드 필터 → LLM → 초기 주제
  Pass 2 — 주제별 검색어 추출 → 전체 아카이브 탐색 → 추가 기사 발견 시 재작성

사용법:
  python scripts/suggest_automotive_topics.py [--days 30]
  python scripts/suggest_automotive_topics.py [--days 7] [--with-existing]

산출:
  scripts/_automotive_topic_suggestions.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402

# ── Archive registry ────────────────────────────────────────────────────────

ARCHIVE_REGISTRY = [
    ("WardsAuto",          "wardsauto.json"),
    ("Cox Automotive",     "cox_automotive.json"),
    ("AlixPartners",       "alixpartners.json"),
    ("SAE International",  "sae.json"),
    ("JATO Dynamics",      "jato.json"),
    ("Automotive Dive",    "automotive_dive.json"),
    ("Automotive World",   "automotive_world.json"),
    ("Electrek",           "electrek.json"),
    ("InsideEVs",          "insideevs.json"),
    ("VW Group",           "vw_group.json"),
    ("Toyota Newsroom",    "toyota.json"),
]

SOURCE_LABEL = (
    "WardsAuto, Cox Automotive, AlixPartners, SAE International, JATO Dynamics, "
    "Automotive Dive, Automotive World, Electrek, InsideEVs, VW Group, Toyota Newsroom"
)

# ── Keyword filter ──────────────────────────────────────────────────────────

_KW_PATH = ROOT / "data" / "automotive_keywords.json"
_KEYWORDS: list[str] = []

# OEM·미디어 전용 소스는 이미 자동차 특화 — 필터 면제
_DEDICATED_SOURCES = {
    "WardsAuto", "SAE International", "JATO Dynamics",
    "Automotive Dive", "Automotive World", "Electrek", "InsideEVs",
}

_BROAD_KEYWORDS = {
    "ev", "bev", "phev", "electric vehicle", "hybrid",
    "oem", "automaker", "automotive", "automobile", "vehicle",
    "toyota", "volkswagen", "byd", "gm", "stellantis",
    "hyundai", "ford", "tesla", "bmw", "mercedes",
    "rivian", "nio", "xpeng", "li auto",
    "adas", "autonomous", "self-driving", "battery",
    "charging", "infrastructure", "recall", "tariff",
    "factory", "production", "supply chain", "dealership",
}


def _load_keywords() -> list[str]:
    global _KEYWORDS
    if not _KEYWORDS:
        _KEYWORDS = json.loads(_KW_PATH.read_text(encoding="utf-8")).get("keywords", [])
    return _KEYWORDS


def keyword_filter(entry: dict) -> bool:
    if entry.get("source", "") in _DEDICATED_SOURCES:
        return True
    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
    kw = _load_keywords()
    return any(k in text for k in kw) or any(k in text for k in _BROAD_KEYWORDS)


# ── Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior automotive market intelligence analyst focused on
EV transition dynamics, OEM competitive strategy, and software-defined vehicle (SDV) economics.

[Core Principle]
Cluster articles by the MARKET PHENOMENON they describe, not by shared keywords.
Example: "Ford delays EV truck production ramp" and "GM restructures EV unit amid weak demand"
describe the SAME phenomenon (legacy OEM EV transition under profitability pressure) even
though they mention different companies and models.

[3-Axis Framework — Build / Market / Shift]
Evaluate every topic through the lens it primarily impacts:
- Build (생산): OEM production volumes, ADAS chip supply chain, battery cell procurement,
  plant utilization, retooling decisions, factory closures or openings
- Market (점유율): global OEM sales rankings, model-level competition, regional EV
  registration share, dealer inventory dynamics, pricing and incentive wars
- Shift (전환): EV adoption pace, SDV monetization, autonomous driving commercialization
  milestones, charging infrastructure rollout, regulation-driven powertrain transitions

Prioritize signals at the structural level:
- An OEM revising its EV production target or timeline (volume, model, plant)
- A battery supplier pricing shift or supply agreement change (CATL, LG, Samsung SDI)
- A tariff or trade policy materially changing OEM cost structure or market access
- BYD or a Chinese OEM gaining/losing ground in a key market
- A software or ADAS breakthrough crossing from R&D into commercial deployment
- An OEM posting unexpected EV profitability or margin data

Also flag:
- Regulatory changes (EU emission targets, US EV credits, China NEV mandates)
- Charging infrastructure capacity signals that change EV adoption trajectory
- Supply chain disruptions (rare earth, lithium, semiconductor shortages)
- Structural demand shifts (fleet electrification, ride-hailing EV transitions)

Do NOT flag:
- Routine model refreshes or concept reveals with no market share implication
- Minor spec updates or trim additions
- Brand advertising campaigns or design awards
- Incremental factory milestone press releases with no strategic signal"""

USER_PROMPT_TEMPLATE = """
[EXISTING REPORTS — exclude these topics from Criterion 3 ONLY]
{existing_reports}

IMPORTANT: This exclusion applies ONLY to Criterion 3 (emerging topics).
It does NOT apply to Criterion 2. Even if a topic has an existing report,
new multi-source evidence within the last {days} days still qualifies as a Criterion 2
signal — the market situation may have structurally evolved since the report was written.

[ARTICLE CORPUS — Automotive market articles, last {days} days]
Total: {total} articles | Sources: {source_label}

{articles}

---

[SELECTION CRITERIA]

Criterion 2 — Multi-Source Signal:
2 or more independent sources covered the SAME market phenomenon within a {days}-day window.
"Same phenomenon" is judged semantically, not by keyword overlap.

Source independence tiers for automotive:
- Tier A (independent media / research): WardsAuto, Cox Automotive, AlixPartners,
  SAE International, JATO Dynamics, Automotive Dive, Automotive World,
  Electrek, InsideEVs — each counts as a distinct independent source
- Tier B (OEM signals): VW Group, Toyota Newsroom and other OEM press releases
  — all OEM blogs/newsrooms together count as ONE source type

Criterion 2 requires 2+ Tier A sources, OR 1 Tier A + 1 Tier B covering the same phenomenon.

CRITICAL — Opposing-direction articles can be the SAME phenomenon:
If one source reports OEM EV expansion plans while another reports dealer inventory
buildup and weak retail demand, these are TWO SIDES OF THE SAME STRUCTURAL SIGNAL
— the gap between supply-side push and demand-side pull IS the market insight.

Criterion 3 — Emerging Topic:
A topic that appears in the last {days} days and is NOT covered by any existing report.
Single-source articles qualify if the topic is genuinely new to the automotive market.

High-value Criterion 3 signals include:
- An OEM announcing a material change to its EV production ramp or model timeline
- A new battery chemistry, ADAS platform, or SDV software stack entering volume production
- A trade policy (tariff, subsidy, mandate) creating a new competitive asymmetry
- A Chinese OEM entering or exiting a new geographic market at scale
- A charging network or grid constraint becoming a measurable adoption bottleneck

---

[OUTPUT — JSON array only, no other text]
Identify 5 to 10 topics. For each topic output:

[
  {{
    "title": "Topic title in Korean (noun phrase capturing the core phenomenon)",
    "criteria": "Criterion 2" | "Criterion 3" | "Criterion 2+3",
    "institution_count": <integer>,
    "articles": [
      {{"date": "YYYY-MM-DD", "source": "<source>", "title": "<original article title>"}}
    ],
    "key_data": [
      "<concrete data point with %, $, units, timeline, or volume figures>",
      "..."
    ],
    "rationale": "왜 이 주제가 일시적 트렌드가 아닌 구조적 신호인지 2~3문장으로 설명. 구체적 기사 근거 포함. 반드시 한국어로 작성."
  }}
]"""

ENRICH_SYSTEM = "You are an automotive market intelligence analyst. Output only valid JSON."

ENRICH_TPL = """You previously identified the following topic from an automotive market corpus:

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
  "institution_count": <count unique sources across ALL articles>,
  "articles": [
    {{"date": "YYYY-MM-DD", "source": "<source>", "title": "<article title>"}}
  ],
  "key_data": ["<updated data points — add new concrete figures if found>"],
  "rationale": "모든 기사를 반영한 2~3문장 선정 근거. 반드시 한국어로 작성."
}}

Rules:
- Keep ALL original cited articles; add additional ones that genuinely support this phenomenon
- Discard additional articles that are not actually about this phenomenon
- Update institution_count to reflect unique sources across all included articles
- If institution_count rises to 2+, upgrade single-source Criterion 3 to Criterion 2 or 2+3
- Preserve the Korean title unless a better framing emerges from the new evidence"""


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",          type=int, default=30)
    parser.add_argument("--out",           default="scripts/_automotive_topic_suggestions.json")
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
        domain_label="automotive",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=args.with_existing,
    )


if __name__ == "__main__":
    main()
