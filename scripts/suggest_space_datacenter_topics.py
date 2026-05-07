"""스페이스 데이터센터 시장 주제 자동 선정.

8개 Tier-1 출처 + SOURCE_TAXONOMY (A~E 레이어) + cross-layer corroboration 룰.

2-pass 파이프라인:
  Pass 1 — space datacenter 키워드 필터 → LLM → 초기 주제
  Pass 2 — 주제별 검색어 추출 → 전체 아카이브 탐색 → 추가 기사 발견 시 재작성
  + source_layers 자동 채움 (코드가 인용 출처에서 직접 도출)

사용법:
  python scripts/suggest_space_datacenter_topics.py [--days 30]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402

# ── Archive registry ─────────────────────────────────────────────────────────

ARCHIVE_REGISTRY = [
    ("SpaceNews",             "spacenews.json"),
    ("Space.com",             "spacecom.json"),
    ("IEEE Spectrum",         "ieee_spectrum_space.json"),
    ("Data Center Knowledge", "datacenter_knowledge.json"),
    ("Data Center Frontier",  "datacenter_frontier.json"),
    ("TechCrunch",            "techcrunch_space.json"),
    ("NVIDIA",                "nvidia_news.json"),
    ("arXiv (cs.DC)",         "arxiv_space.json"),
]

SOURCE_LABEL = (
    "SpaceNews, Space.com, IEEE Spectrum, "
    "Data Center Knowledge, Data Center Frontier, TechCrunch, NVIDIA, arXiv (cs.DC)"
)

# ── Source taxonomy ──────────────────────────────────────────────────────────

SOURCE_TAXONOMY = {
    "SpaceNews":             "A",  # Space primary news (launch data, operator)
    "Space.com":             "A",  # Space broad coverage
    "IEEE Spectrum":         "B",  # Tech specialist (hardware, architecture)
    "arXiv (cs.DC)":         "B",  # Academic pre-prints
    "Data Center Knowledge": "C",  # DC industry economics
    "Data Center Frontier":  "C",  # DC industry analysis
    "TechCrunch":            "D",  # Venture/startup/funding
    "NVIDIA":                "E",  # Vendor official announcement
}

# ── Keyword filter ───────────────────────────────────────────────────────────

_KW_PATH = ROOT / "data" / "space_datacenter_keywords.json"
_KEYWORDS: list[str] = []


def _load_keywords() -> list[str]:
    global _KEYWORDS
    if not _KEYWORDS:
        _KEYWORDS = json.loads(_KW_PATH.read_text(encoding="utf-8")).get("keywords", [])
    return _KEYWORDS


def keyword_filter(entry: dict) -> bool:
    kw   = _load_keywords()
    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
    return any(k in text for k in kw)


# ── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior space datacenter infrastructure analyst focused on
orbital computing and space-based data infrastructure development.

Your task is to identify research-worthy topics from a corpus of recent articles and papers.

[Core Principle]
Cluster articles by the MARKET PHENOMENON they describe, not by shared keywords.
Example: "SpaceX files for million-satellite AI megaconstellation" and
"How orbital colocation changes hyperscaler economics" are the SAME phenomenon
(structural shift in compute economics driven by orbital deployment scale)
even if they share no keywords.

[3-Axis Analysis Framework — every topic must map to at least one axis]
- Launch & Deploy: satellite/module launches, orbital placement, launch costs/manifest,
  hardware reliability, rideshare economics, radiation hardening
- Compute & Connect: onboard GPU/NPU, inter-satellite optical links (ISL),
  ground station network, thermal management, power (solar, WPT)
- Enterprise & Cloud Adoption: hyperscaler strategy (SpaceX/Amazon/Microsoft/Google),
  contracts/investment, regulation, data sovereignty, latency use cases

Prioritize signals at the infrastructure and operator level:
- A hyperscaler or new entrant committing orbital compute strategy (launch manifest, contract)
- A technical barrier being overcome (thermal, power budget, radiation hardening, ISL bandwidth)
- A structural demand signal (why enterprises specifically need space compute over terrestrial)
- Divergence between vendor roadmaps and actual orbital deployment reality
- Academic research validating (or refuting) orbital compute economics

Also flag:
- Regulatory shifts that affect data sovereignty or spectrum access
- Supply chain bottlenecks for space-grade components (rad-hard chips, solar arrays, etc.)

Do NOT flag:
- Generic satellite communication news with no compute/datacenter angle
- Routine launch updates without infrastructure significance
- Incremental updates to already well-documented trends

[SOURCE TAXONOMY — 8개 Tier-1 출처]

A. Space primary news (launch data, operator announcements):
   SpaceNews, Space.com

B. Tech specialist / Academic (hardware architecture, peer-reviewed research):
   IEEE Spectrum, arXiv (cs.DC)

C. DC industry economics (cost modeling, enterprise adoption, market data):
   Data Center Knowledge, Data Center Frontier

D. Venture / startup / funding (deals, new entrants, ecosystem):
   TechCrunch

E. Vendor official (product launches, partnerships, roadmaps):
   NVIDIA"""

USER_PROMPT_TEMPLATE = """
[EXISTING REPORTS — exclude these topics from Criterion 3 ONLY]
{existing_reports}

IMPORTANT: This exclusion applies ONLY to Criterion 3 (emerging topics).
It does NOT apply to Criterion 2. Even if a topic area has an existing report,
new multi-source evidence within the last {days} days still qualifies as a Criterion 2
signal — the situation may have structurally evolved since the report was written.

[ARTICLE CORPUS — Tier-1 space datacenter articles & papers, last {days} days]
Total: {total} articles | Sources: {source_label}

{articles}

---

[SELECTION CRITERIA — 8개 소스 / 5개 레이어]

Criterion 2 — Multi-Source Signal:
2 or more independent sources cover the SAME market phenomenon within a {days}-day window.
"Same phenomenon" is judged semantically, not by keyword overlap.

CROSS-LAYER 보강도 multi-source로 인정한다:
- Academic (arXiv/IEEE) + Industry news (SpaceNews/DC Knowledge)
  → 연구 결과가 실제 시장 움직임으로 corroborate 된 phenomenon
- Vendor announcement (NVIDIA) + Industry analysis (DC Frontier/DC Knowledge)
  → 제품 출시가 시장 파급력으로 평가된 phenomenon
- Startup/funding (TechCrunch) + Space news (SpaceNews)
  → 신규 플레이어 등장이 업계 반응으로 확인된 phenomenon
- Technical barrier reporting (IEEE/arXiv) + Commercial deployment (SpaceNews/Space.com)
  → 기술 장벽 극복이 실제 배포로 이어진 phenomenon

OPPOSING-DIRECTION 도 same phenomenon으로 인정:
한 소스가 기술 로드맵 발표를 보도하고, 다른 소스가 실제 배포 지연/성과를 보도하면
이는 같은 구조적 신호의 양면이다.

[SOURCE WEIGHTING — 단독 출처 신호 처리]

- arXiv 단독: 학술 pre-print 단독 → Criterion 3.
  IEEE Spectrum 등 검증 소스의 corroboration이 없으면 Criterion 2 부여 금지.

- TechCrunch 단독: 펀딩/스타트업 소식 단독 → Criterion 3.
  운영·기술 corroboration 없이 Criterion 2 부여 금지.

- NVIDIA 단독: 자사 블로그 발표 단독 → Criterion 3 (vendor self-report).

- Space news (A 그룹) 2개 이상 일치 = 강한 Criterion 2 (운영 데이터 합의).
  A 그룹 1개 단독 = Criterion 3.

Criterion 3 — Emerging Topic:
A topic that appears in the last {days} days and is NOT covered by any existing report above.
Single-institution articles qualify if the topic is genuinely new.

High-value Criterion 3 signals include:
- First orbital compute deployment by a named operator (launch date, hardware spec)
- A new entrant or startup targeting orbital datacenter market
- A specific technical breakthrough (ISL bandwidth record, thermal solution, rad-hard chip)
- A regulatory filing or spectrum allocation that enables new orbital compute use case
- An academic proof-of-concept that directly challenges or validates orbital datacenter economics

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

ENRICH_SYSTEM = "You are a space datacenter infrastructure analyst. Output only valid JSON."

ENRICH_TPL = """You previously identified the following topic from a space datacenter corpus:

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
- arXiv/TechCrunch/NVIDIA 단독 → Criterion 3 유지
- Preserve the Korean title unless a better framing emerges from the new evidence"""


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",          type=int, default=30)
    parser.add_argument("--out",           default="scripts/_space_datacenter_topic_suggestions.json")
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
        domain_label="space_datacenter",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=args.with_existing,
        source_taxonomy=SOURCE_TAXONOMY,
    )


if __name__ == "__main__":
    main()
