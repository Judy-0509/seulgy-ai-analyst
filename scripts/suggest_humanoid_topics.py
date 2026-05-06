"""휴머노이드 로봇 시장 주제 자동 선정.

2-pass 파이프라인:
  Pass 1 — 휴머노이드 키워드 필터 → LLM → 초기 주제
  Pass 2 — 주제별 검색어 추출 → 전체 아카이브 탐색 → 추가 기사 발견 시 재작성

사용법:
  python scripts/suggest_humanoid_topics.py [--days 30]
  python scripts/suggest_humanoid_topics.py [--days 7] [--with-existing]

산출:
  scripts/_humanoid_topic_suggestions.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402

# ── Archive registry ────────────────────────────────────────────────────────

ARCHIVE_REGISTRY = [
    # Tier A — independent media
    ("Robotics & Automation News", "robotics_automation_news.json"),
    ("TechCrunch Robotics",        "techcrunch_robotics.json"),
    ("IEEE Spectrum Robotics",     "ieee_spectrum_robotics.json"),
    ("The Robot Report",           "robot_report.json"),
    ("MIT Technology Review",      "mit_tech_review.json"),
    ("The Verge",                  "verge_robotics.json"),
    # Tier B — first-party OEM / supplier announcements
    ("Boston Dynamics",            "boston_dynamics.json"),
    ("Figure AI",                  "figure_ai.json"),
    ("Unitree",                    "unitree.json"),
    ("NVIDIA News",                "nvidia_news.json"),
    ("Apptronik",                  "apptronik.json"),
    ("Agility Robotics",           "agility_robotics.json"),
    ("1X Technologies",            "onex_technologies.json"),
    # Tier C — academic
    ("arXiv (cs.RO)",              "arxiv_robotics.json"),
    # Tier D — industry association
    ("IFR",                        "ifr.json"),
]

SOURCE_LABEL = (
    "Robotics & Automation News, TechCrunch Robotics, IEEE Spectrum, "
    "The Robot Report, MIT Technology Review, The Verge, "
    "Boston Dynamics, Figure AI, Unitree, NVIDIA, Apptronik, Agility Robotics, 1X, "
    "arXiv, IFR"
)

# ── Source taxonomy (post-process로 source_layers 자동 채움) ────────────────

SOURCE_TAXONOMY = {
    "Robotics & Automation News": "A",  # Independent media
    "TechCrunch Robotics":        "A",
    "IEEE Spectrum Robotics":     "A",
    "The Robot Report":           "A",
    "MIT Technology Review":      "A",
    "The Verge":                  "A",
    "Boston Dynamics":            "B",  # First-party OEM
    "Figure AI":                  "B",
    "Unitree":                    "B",
    "NVIDIA News":                "B",
    "Apptronik":                  "B",
    "Agility Robotics":           "B",
    "1X Technologies":            "B",
    "arXiv (cs.RO)":              "C",  # Academic
    "IFR":                        "D",  # Industry association
}

# ── Keyword filter ──────────────────────────────────────────────────────────
# Robotics & Automation News는 off-topic 기사(금융, SNS 등)를 포함하므로 가볍게 필터링.
# 나머지 소스는 이미 로보틱스 특화라 필터 불필요.

_KW_PATH = ROOT / "data" / "humanoid_keywords.json"
_KEYWORDS: list[str] = []
_BROAD_KEYWORDS = {
    "robot", "robotic", "humanoid", "autonomous", "automation",
    "actuator", "sensor", "locomotion", "manipulation", "embodied",
    "physical ai", "nvidia", "boston dynamics", "figure", "unitree",
    "warehouse", "industrial", "deployment", "arxiv",
}

def _load_keywords() -> list[str]:
    global _KEYWORDS
    if not _KEYWORDS:
        _KEYWORDS = json.loads(_KW_PATH.read_text(encoding="utf-8")).get("keywords", [])
    return _KEYWORDS

def keyword_filter(entry: dict) -> bool:
    # 소스가 이미 로보틱스 특화인 경우 통과 (1차 OEM, 학술, 로보틱스 전문 매체)
    source = entry.get("source", "")
    if source in (
        "arXiv (cs.RO)",
        "Boston Dynamics", "Figure AI", "Unitree", "Apptronik",
        "Agility Robotics", "1X Technologies",
        "TechCrunch Robotics", "IEEE Spectrum Robotics",
        "The Robot Report", "MIT Technology Review",
        "IFR",
    ):
        return True
    # 일반 매체(R&AN, Verge, NVIDIA blog)는 키워드 필터 적용
    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
    kw = _load_keywords()
    return any(k in text for k in kw) or any(k in text for k in _BROAD_KEYWORDS)

# ── Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior humanoid robotics market intelligence analyst focused on
commercialization strategy, technology readiness, and competitive dynamics.

[ROLE SPLIT — IMPORTANT]
This is the MAJOR pass. A separate "Curiosity Pick" emerging pass handles
single-source niche signals (minor OEM movements, contrarian data, standalone
technical leaks, major-OEM off-trend actions). DO NOT surface those here.
Focus this pass on phenomena with multi-source consensus or clear market-defining
significance.

[Core Principle]
Cluster articles by the MARKET PHENOMENON they describe, not by shared keywords.
Example: "Figure AI ramps production at BotQ" and "Schaeffler plans 1,000 Hexagon humanoids by 2032"
describe the SAME phenomenon (humanoid mass-production transition entering industrial deployment)
even though they mention different companies.

Prioritize signals at the company and technology level:
- A specific company achieving a commercial or production milestone (first fleet, factory scale-up, key funding)
- A company entering a new application sector (logistics, healthcare, aviation, consumer)
- Structural competitive advantage becoming visible (proprietary AI stack, actuator integration, manufacturing cost breakthrough)
- Divergence between company roadmap announcements and real-world deployment reality
- Supply chain signals (actuators, force sensors, AI chips, manufacturing partnerships)

Also flag:
- Paradigm shifts that change humanoid economics (labor cost parity, regulation, insurance, enterprise ROI)
- AI/software breakthroughs with near-term hardware deployment implications (VLA models, sim-to-real, whole-body control)
- Enterprise or government adoption signals indicating mainstream inflection

Do NOT flag:
- Routine product demos or video releases with no strategic signal
- Academic papers without clear near-term commercial application
- Incremental hardware spec updates with no market significance
- General automation or non-humanoid robotics topics
- Single-source niche/contrarian signals (delegated to the emerging pass)

[SOURCE TAXONOMY — 본 corpus는 4개 레이어로 구성, 각 레이어의 신호 강도가 다르다]

A. Independent media (저널리즘, 다중 합의로 신뢰):
   Robotics & Automation News, TechCrunch Robotics, IEEE Spectrum,
   The Robot Report, MIT Technology Review, The Verge

B. First-party OEM / supplier (1차 발표 — 기업 자체 announcement):
   Boston Dynamics, Figure AI, Unitree, NVIDIA News, Apptronik,
   Agility Robotics, 1X Technologies
   → Tier B 다수가 동일 시점 일제히 보도하면 "산업 전반 phase shift" 신호

C. Academic (arXiv) — 모델/기술 fact 확정용:
   arXiv (cs.RO)

D. Industry association — 산업 정량 지표 / 정책 동향:
   IFR (International Federation of Robotics)"""

USER_PROMPT_TEMPLATE = """
[EXISTING REPORTS — exclude these topics from Criterion 3 ONLY]
{existing_reports}

IMPORTANT: This exclusion applies ONLY to Criterion 3 (emerging topics).
It does NOT apply to Criterion 2. Even if a topic has an existing report,
new multi-source evidence within the last {days} days still qualifies as a Criterion 2
signal — the situation may have structurally evolved since the report was written.

[ARTICLE CORPUS — Humanoid robotics articles, last {days} days]
Total: {total} articles | Sources: {source_label}

{articles}

---

[SELECTION CRITERIA]

Criterion 2 — Multi-Source Signal:
2 or more independent sources covered the SAME market phenomenon within a {days}-day window.
"Same phenomenon" is judged semantically, not by keyword overlap.

Source independence tiers for humanoid robotics:
- Tier A (independent media): Robotics & Automation News, TechCrunch Robotics,
  IEEE Spectrum, The Robot Report, MIT Technology Review, The Verge
  — each Tier-A outlet counts as a distinct independent source
- Tier B (first-party OEM/supplier): Boston Dynamics, Figure AI, Unitree, NVIDIA,
  Apptronik, Agility Robotics, 1X — each company is its own first-party source.
  Two distinct OEMs = TWO independent sources (different companies, different
  strategic positions). Same company multiple posts = ONE source.
- Tier C (academic): arXiv papers — papers from different research groups count
  as distinct sources; multiple papers from the same group = ONE source.
- Tier D (industry association): IFR — counts as one source type.

Criterion 2 requires 2+ sources covering the same phenomenon, where:
- 2+ Tier A outlets, OR
- 2+ Tier B OEMs (cross-company convergence is itself a strong market signal), OR
- 1 Tier A + 1 Tier B/C/D, OR
- 1 Tier B + 1 Tier C (e.g., OEM announces capability + arXiv paper validates approach)

CROSS-LAYER 보강이 strong signal:
- Tier B (OEM 발표) + Tier A (독립 매체 검증) → 양면 확정
- Tier C (arXiv 모델) + Tier B (OEM 적용 발표) → 학술→상용 전이 신호
- Tier D (IFR 통계) + Tier A (사례 보도) → 산업 차원 vs 개별 사례 일치

CRITICAL — Opposing-direction articles can be the SAME phenomenon:
If one source reports what companies are building (technology roadmap) while another
reports deployment reality or adoption barriers, these are TWO SIDES OF THE SAME
STRUCTURAL SIGNAL — the gap between them IS the market insight.

Criterion 3 — Emerging Topic:
A topic that appears in the last {days} days and is NOT covered by any existing report.
Single-source articles qualify if the topic is genuinely new to the humanoid market.

High-value Criterion 3 signals include:
- A company achieving a humanoid production or deployment milestone
- A new application sector opening for humanoids (new industry partnership, pilot)
- A technology breakthrough enabling new humanoid capabilities
- A new major entrant or strategic pivot into humanoids
- Economic or regulatory dynamics that change the adoption timeline

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
      "<concrete data point with %, $, year, unit volume, or timeline figures>",
      "..."
    ],
    "rationale": "왜 이 주제가 일시적 트렌드가 아닌 구조적 신호인지 2~3문장으로 설명. 구체적 기사 근거 포함. 반드시 한국어로 작성."
  }}
]"""

ENRICH_SYSTEM = "You are a humanoid robotics market intelligence analyst. Output only valid JSON."

ENRICH_TPL = """You previously identified the following topic from a humanoid robotics market corpus:

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
    parser.add_argument("--out",           default="scripts/_humanoid_topic_suggestions.json")
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
        domain_label="humanoid",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=args.with_existing,
        source_taxonomy=SOURCE_TAXONOMY,
    )


if __name__ == "__main__":
    main()
