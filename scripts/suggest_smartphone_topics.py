"""스마트폰 시장 주제 자동 선정 (구 suggest_topics.py).

2-pass 파이프라인:
  Pass 1 — 스마트폰 키워드 필터 → LLM → 초기 주제
  Pass 2 — 주제별 검색어 추출 → 전체 아카이브 탐색 → 추가 기사 발견 시 재작성

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

# ── Archive registry ────────────────────────────────────────────────────────

ARCHIVE_REGISTRY = [
    ("Counterpoint Research", "counterpoint.json"),
    ("TrendForce",            "trendforce.json"),
    ("Omdia",                 "omdia.json"),
    ("IDC",                   "idc.json"),
    ("Morgan Stanley",        "morgan_stanley.json"),
]

SOURCE_LABEL = "Counterpoint Research, TrendForce, Omdia, IDC, Morgan Stanley"

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
- Incremental updates to already well-documented trends"""

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

[SELECTION CRITERIA]

Criterion 2 — Multi-Source Signal:
2 or more independent research institutions covered the SAME market phenomenon
within a {days}-day window. Institutions must be drawn from the Tier-1 list above.
"Same phenomenon" is judged semantically, not by keyword overlap.

OEM-level signals qualify: if 2+ institutions independently confirm the same brand's
strategic shift, competitive milestone, or structural advantage — even from different
angles — that counts as one multi-source signal.

CRITICAL — Opposing-direction articles can be the SAME phenomenon:
If one institution reports what OEMs are building or planning (supply-side roadmap)
while another reports how consumers are actually responding (demand-side reality),
these are TWO SIDES OF THE SAME STRUCTURAL SIGNAL.

Criterion 3 — Emerging Topic:
A topic that appears in the last {days} days and is NOT covered by any existing report above.
Single-institution articles qualify if the topic is genuinely new.

High-value Criterion 3 signals include:
- An OEM achieving a market first
- A brand's strategic pivot into a new segment or technology
- A specific OEM's competitive position shifting in a key market
- An OEM product launch that signals industry-wide direction change

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
    "rationale": "왜 이 주제가 일시적 트렌드가 아닌 구조적 신호인지 2~3문장으로 설명. 구체적 기사 근거 포함. 반드시 한국어로 작성."
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
  "rationale": "모든 기사를 반영한 2~3문장 선정 근거. 반드시 한국어로 작성."
}}

Rules:
- Keep ALL original cited articles; add additional ones that genuinely support this phenomenon
- Discard additional articles that are not actually about this phenomenon
- Update institution_count to reflect unique institutions across all included articles
- If institution_count rises to 2+, upgrade single-source Criterion 3 to Criterion 2 or 2+3
- Preserve the Korean title unless a better framing emerges from the new evidence"""


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",          type=int, default=30)
    parser.add_argument("--out",           default="scripts/_topic_suggestions.json")
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
        domain_label="smartphone",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=args.with_existing,
    )


if __name__ == "__main__":
    main()
