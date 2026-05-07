"""자동차 시장 주제 자동 선정 (옵션 B 정식 채택판).

11개 Tier-1 출처 + SOURCE_TAXONOMY (A~D 레이어) + cross-layer corroboration 룰.

2-pass 파이프라인:
  Pass 1 — Automotive 키워드 필터 → LLM → 초기 주제
  Pass 2 — 주제별 검색어 추출 → 전체 아카이브 탐색 → 추가 기사 발견 시 재작성
  + source_layers 자동 채움 (코드가 인용 출처에서 직접 도출)

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

# ── Archive registry (26 Tier-1 출처) ───────────────────────────────────────

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
    # 2026-05-07 추가 — 중국 EV 가시성 + EU 정책/통계 강화
    ("CnEVPost",           "cnevpost.json"),
    ("CarNewsChina",       "carnewschina.json"),
    ("ICCT",               "icct.json"),
    ("ACEA",               "acea.json"),
    # 2026-05-07 추가 — 스마트폰 트래커 자동차 practice 재활용
    # 자동차 키워드(168개) 필터로 auto-relevant 콘텐츠만 통과 → ADAS/반도체/배터리 갭 보강
    ("Counterpoint Research", "counterpoint.json"),
    ("TrendForce",            "trendforce.json"),
    ("Omdia",                 "omdia.json"),
    ("IDC",                   "idc.json"),
    ("Yole",                  "yole.json"),
    ("DigiTimes Asia",        "digitimes.json"),
    ("CCS Insight",           "ccs_insight.json"),
    # 2026-05-07 추가 — 컨설팅·EV/정책 무료 블로그
    ("BloombergNEF",          "bnef.json"),
    ("RMI",                   "rmi.json"),
    ("Transport & Environment", "transport_environment.json"),
    ("IRENA",                 "irena.json"),
]

SOURCE_LABEL = (
    "WardsAuto, Cox Automotive, AlixPartners, SAE International, JATO Dynamics, "
    "Automotive Dive, Automotive World, Electrek, InsideEVs, VW Group, Toyota Newsroom, "
    "CnEVPost, CarNewsChina, ICCT, ACEA, "
    "Counterpoint Research, TrendForce, Omdia, IDC, Yole, DigiTimes Asia, CCS Insight, "
    "BloombergNEF, RMI, Transport & Environment, IRENA"
)

# ── Source taxonomy (post-process로 source_layers 자동 채움) ────────────────
# A. Independent media — 자동차 산업 보도 매체 (편집권/논조 독립)
# B. First-party OEM — OEM 자체 PR/뉴스룸 (1차 official source)
# C. Quantitative trackers — 판매·등록·가격 정량 데이터 트래커
# D. Consultancy / industry association / policy research — 표준·정책·산업단체 리서치

SOURCE_TAXONOMY = {
    # A. Independent media
    "WardsAuto":          "A",
    "Automotive Dive":    "A",
    "Automotive World":   "A",
    "Electrek":           "A",
    "InsideEVs":          "A",
    "CnEVPost":           "A",  # 영문 중국 EV 매체
    "CarNewsChina":       "A",  # 영문 중국 자동차 매체
    "DigiTimes Asia":     "A",  # 아시아 공급망 매체 (자동차 반도체·OEM 부품 leak)
    # B. First-party OEM
    "VW Group":           "B",
    "Toyota Newsroom":    "B",
    # C. Quantitative trackers (스마트폰 트래커의 자동차 practice 포함)
    "JATO Dynamics":      "C",
    "Cox Automotive":     "C",
    "Counterpoint Research": "C",  # Robotaxi·L4 트래커, ADAS 시장 데이터
    "TrendForce":         "C",  # EV 칩·배터리 트래커
    "Omdia":              "C",  # Power Semiconductor in Automotive, 차량 image sensor 트래커
    "IDC":                "C",  # 분기 EV 시장 분석 (BYD vs Tesla 등)
    "Yole":               "C",  # 차량 GNSS·SiC·반도체 패키징 component 분석
    # D. Consultancy / industry association / policy research
    "AlixPartners":       "D",
    "SAE International":  "D",
    "ICCT":               "D",  # 정책·배출 리서치 (NGO)
    "ACEA":               "D",  # EU 자동차 제조사 협회
    "CCS Insight":        "D",  # 커넥티드카·satellite-to-car 컨설턴시
    "BloombergNEF":       "D",  # Bloomberg 에너지·EV 리서치 (무료 블로그)
    "RMI":                "D",  # Rocky Mountain Institute — 미국 EV/충전 NGO
    "Transport & Environment": "D",  # EU 교통·배출 advocacy NGO
    "IRENA":              "D",  # 국제재생에너지기구 (UN 산하)
}

# ── Keyword filter ──────────────────────────────────────────────────────────

_KW_PATH = ROOT / "data" / "automotive_keywords.json"
_KEYWORDS: list[str] = []

# OEM·미디어 전용 소스는 이미 자동차 특화 — 필터 면제
# (단, 빌드 시 require_auto_keyword=True 로 이미 1차 필터된 소스도 포함)
_DEDICATED_SOURCES = {
    "WardsAuto", "SAE International", "JATO Dynamics",
    "Automotive Dive", "Automotive World", "Electrek", "InsideEVs",
    "CnEVPost", "CarNewsChina", "ICCT", "ACEA",
    # 컨설팅·정책 — 빌더가 자동차 키워드로 1차 필터한 결과만 저장됨
    "BloombergNEF", "RMI", "Transport & Environment", "IRENA",
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

[CRITICAL — PHENOMENON-LEVEL DEDUPLICATION]
Supply-side and demand-side signals of the SAME phenomenon MUST be merged into ONE topic,
not split into two. Examples of supply/demand pairs that MUST be combined:
- "OEM EV production cuts / model cancellations" (supply) + "EV sales decline + dealer
  inventory buildup" (demand) = SAME phenomenon, ONE topic surfaced
- "Battery supplier capacity expansion" (supply) + "EV registrations surge in EU"
  (demand) = SAME phenomenon (battery-led EV adoption), ONE topic
- "Charging infrastructure rollout" (supply) + "EV adoption hitting tipping point in
  region X" (demand) = SAME phenomenon, ONE topic
If you have a candidate "supply-side" topic AND a candidate "demand-side" topic that
both describe market dynamics in the SAME segment within the SAME timeframe, you have
ONE topic, not two. Combine the evidence and surface the higher institution_count.

[CRITICAL — OEM VERTICAL INTEGRATION SIGNAL CLASSIFICATION]
When an automaker engages in vertical integration moves (own silicon, own foundry deals,
own OS, own AI stack, own battery cell joint ventures), classify these as AUTOMOTIVE
INDUSTRY STRUCTURE topics — NOT as semiconductor/tech topics. The phenomenon is the
restructuring of the auto industry value chain.

Specifically MUST be flagged as automotive structural topics (not pass to semiconductor):
- Tesla / GM / Ford / VW / Toyota / Hyundai / BYD CapEx for in-house chips, AI clusters,
  foundry partnerships (e.g., Tesla–Intel 14A, Tesla Terafab, BYD self-developed SoC)
- OEM joint ventures with Microsoft / Qualcomm / NVIDIA for SDV stacks
- OEM-led battery cell consortia (Ultium, PowerCo, Stellantis-CATL)
- OEM self-developed OS pivots (Mercedes MB.OS, VW SSP, BYD DiLink)

These signals represent SHIFTS IN INDUSTRY STRUCTURE — who owns what layer of the auto
value chain — and are research-priority topics even if they appear technical on the
surface. Cross-source evidence: a single OEM CapEx announcement (Layer A media) +
component analyst commentary (Layer C tracker — Counterpoint/TrendForce/Yole/Omdia)
qualifies as Criterion 2 multi-source.

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
- Incremental factory milestone press releases with no strategic signal

[SOURCE TAXONOMY — 본 corpus는 26개 Tier-1 출처로 구성, 각 출처의 관점이 다르다]

A. Independent media (자동차 산업 보도, 편집권 독립):
   WardsAuto, Automotive Dive, Automotive World, Electrek, InsideEVs,
   CnEVPost (영문 중국 EV), CarNewsChina (영문 중국 자동차),
   DigiTimes Asia (아시아 공급망·차량 반도체 leak)

B. First-party OEM (OEM 자체 PR/뉴스룸 — official statement, 자기 narrative):
   VW Group, Toyota Newsroom

C. Quantitative trackers (판매/등록/가격/부품 정량 데이터 — 다중 합의로 신뢰):
   JATO Dynamics, Cox Automotive,
   Counterpoint Research (Robotaxi·L4 트래커),
   TrendForce (EV 칩·배터리 트래커),
   Omdia (Power Semi·차량 Image Sensor 트래커),
   IDC (분기 EV 시장 분석),
   Yole (차량 GNSS·SiC·패키징 component 분석)

D. Consultancy / industry association / policy research (전략 컨설팅·산업단체·정책 리서치):
   AlixPartners, SAE International,
   ICCT (정책·배출 NGO), ACEA (EU 제조사 협회),
   CCS Insight (커넥티드카·satellite-to-car 컨설턴시),
   BloombergNEF (Bloomberg 에너지·EV 리서치),
   RMI (미국 EV/충전 NGO), Transport & Environment (EU 교통 NGO),
   IRENA (UN 재생에너지 기구)"""

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

[SELECTION CRITERIA — 26개 소스 / 4개 레이어]

Criterion 2 — Multi-Source Signal:
2 or more independent sources cover the SAME market phenomenon within a {days}-day window.
"Same phenomenon" is judged semantically, not by keyword overlap.

CROSS-LAYER 보강도 multi-source로 인정한다. 같은 현상에 대해 서로 다른 레이어의 증거가 동시에 등장하는 경우가 strong signal:
- Quant tracker (JATO/Cox 판매·등록 데이터) + Independent media (Wards/Automotive Dive 등 보도)
  → "판매 수치와 시장 narrative 양면 확정"
- OEM official (VW Group/Toyota Newsroom) + Independent media corroboration
  → 1차 발표가 외부에서 검증·맥락화 된 phenomenon
- Consultancy framework (AlixPartners/SAE) + 실제 데이터 (JATO/Cox)
  → 전략 가설이 실측치로 confirm 된 신호

OPPOSING-DIRECTION 도 same phenomenon 으로 인정:
한 소스가 OEM의 supply-side EV 로드맵 발표를 보도하고, 다른 소스가 demand-side 딜러 재고
누적과 retail 약세를 보도하면 이는 같은 구조적 신호의 양면이다 (push vs pull 격차 = 시장 insight).

[SOURCE WEIGHTING — 단독 출처 신호 처리]

Single-source (1개 출처만) 인 경우 신호 강도 차등:

- OEM official (B 그룹: VW Group, Toyota Newsroom) 단독:
  자사 발표 단독 인용 → Criterion 3 (emerging) 으로 분류.
  외부 (A·C·D) 보강 없이는 Criterion 2 부여 금지 (자사 narrative 편향 우려).

- Consultancy single-source (AlixPartners/SAE 단독):
  Strategic framework 단독 → Criterion 3.

- Quant tracker (C 그룹) 단독 1개 vs 같은 그룹 2개 일치:
  JATO + Cox 합의 = 강한 Criterion 2 (시장 정량 합의).
  C 그룹 1개 단독 = Criterion 3 가능.

- Independent media (A 그룹) 2개 이상 일치:
  편집권 독립 매체 다수 합의 = Criterion 2 부여 가능.
  A 그룹 1개 단독 = Criterion 3.

Criterion 3 — Emerging Topic:
A topic that appears in the last {days} days and is NOT covered by any existing report above.
Single-source articles qualify if the topic is genuinely new.

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
    "rationale": "왜 이 주제가 일시적 트렌드가 아닌 구조적 신호인지 2~3문장으로 설명. 어떤 레이어들이 corroborate 했는지 명시. 반드시 한국어로 작성."
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
  "rationale": "모든 기사를 반영한 2~3문장 선정 근거. 어떤 레이어가 추가 corroborate 했는지 명시. 반드시 한국어로 작성."
}}

Rules:
- Keep ALL original cited articles; add additional ones that genuinely support this phenomenon
- Discard additional articles that are not actually about this phenomenon
- Update institution_count to reflect unique sources across all included articles
- If institution_count rises to 2+ AND cross-layer (다른 레이어 추가), upgrade to Criterion 2 or 2+3
- OEM (B) 단독 / Consultancy (D) 단독 / Quant tracker (C) 1개 단독 → Criterion 3 유지
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
        source_taxonomy=SOURCE_TAXONOMY,
    )


if __name__ == "__main__":
    main()
