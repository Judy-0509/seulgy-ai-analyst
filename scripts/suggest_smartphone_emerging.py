"""스마트폰 Emerging / Curiosity Pick 패스 — 주 1회 실행 권장.

메인 패스(suggest_smartphone_topics.py)와 분리된 별도 스크립트.
시장 메이저 합의 주제는 메인이 잡고, 본 스크립트는 "analyst가 흥미롭게 볼만한"
4가지 단발 신호 패턴을 좁은 윈도우(7일)로 surface한다:

  (a) 마이너 OEM의 strategic movement
  (b) 메이저 narrative와 반대되는 contrarian signal
  (e) 단발성 기술 fact / 부품 leak
  (g) 대형 OEM의 비주류 행동

출력 토픽은 모두 criteria="Criterion 3"으로 통일 → frontend의
"이번 주 새롭게 등장한 주제" 섹션에 자동 노출됨.

사용:
  python scripts/suggest_smartphone_emerging.py [--days 7]

출력: scripts/_topic_suggestions_emerging.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402
from suggest_smartphone_topics import (  # noqa: E402
    ARCHIVE_REGISTRY, SOURCE_LABEL, SOURCE_TAXONOMY, keyword_filter,
)


def _load_major_topic_titles() -> list[str]:
    """현재 메이저 패스 결과의 토픽 title 리스트.

    emerging 패스가 이를 'reject 대상'으로 받아 중복 surfacing을 방지.
    """
    p = ROOT / "scripts" / "_topic_suggestions.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [t["title"] for t in data.get("topics", []) if t.get("title")]
    except Exception:
        return []

# ── Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior smartphone market analyst preparing a weekly
"Curiosity Pick" digest. The mainstream consensus topics are already covered by
a separate 30-day major pass — DO NOT duplicate them.

Your task: surface 3 to 5 niche or off-trend signals that a sharp
analyst would find personally interesting in the last {days} days.

[CRITICAL OUTPUT RULES]
- TITLE LANGUAGE: every "title" field MUST be a Korean noun phrase. Never leave
  the title in English even if the source article is English. Translate the
  phenomenon into Korean.
- DUPLICATE REJECTION: the user prompt will list the major-pass topics that
  already exist. If your candidate signal is the SAME phenomenon (semantically),
  REJECT it and find a different angle or a different signal entirely. Picking
  a topic that the major pass already surfaces is a failure.

[What to LOOK FOR — 4 patterns, in priority order]

(e) STANDALONE technical fact / component leak  ⭐ SEEK FIRST
   1개 출처의 단발성 기술·부품 신호. 예시:
   - DigiTimes 단독 공급망 leak (HBM, 새 SoC 노드, 카메라 모듈, 배터리 셀)
   - Yole 단독 부품 분석 (패키징, 광학, 센서)
   - 메이저 트래커의 측면 코멘트 / 인터뷰 시리즈에서만 언급된 기술 fact
   다른 출처의 corroboration이 없어도 가치 있는 단독 기술 신호.

(g) MAJOR OEM의 OFF-TREND 행동  ⭐ HIGH PRIORITY
   Apple, Samsung, Huawei, Honor, Xiaomi, Vivo의 비주류 / 의외의 액션. 예시:
   - 인도·동남아·중남미 직접투자 / 현지 생산 확대
   - 자체 모뎀·SoC·OS 전환 같은 vertical integration leap
   - Tizen 부활, Tablet OS 분리, Carrier 직접 운영
   - 갑작스런 가격 정책 전환 / 신 segment 실험
   "왜 지금 굳이?"라는 질문이 떠오르는 종류의 액션.

(a) MINOR OEM movements
   Nothing, Realme, OnePlus, Motorola, Sony, ASUS, ZTE,
   Lenovo, HMD/Nokia, Sharp, Tecno, Infinix 등
   소형 OEM·부품사의 strategic pivot, 새 폼팩터 진입, 신 segment 진출.
   (e)·(g) 패턴에서 적합한 신호를 찾지 못한 경우에 한해 선택.

(b) CONTRARIAN signals
   메이저 narrative와 정반대 데이터/논평. 예시:
   - "AI 기능 실사용도 저조" (모두가 AI를 외칠 때 reality check)
   - "폴더블 회의론" (붐 분위기 속 냉정한 분석)
   - "온디바이스 AI 효용 의문"
   - "위성통신 도입 속도 둔화"
   - "프리미엄화의 한계 / 중저가 회복"
   (e)·(g) 패턴에서 적합한 신호를 찾지 못한 경우에 한해 선택.

[What to AVOID]
- 메이저 트래커들이 이미 합의하는 주류 주제 (그건 main pass 영역)
- 단순 정기 출하/점유율 데이터 업데이트
- 동일 주제의 재언급 / 후속 보도
- Tier-1 출처 외 일반 매체에서만 보도된 단순 루머

[SOURCE TAXONOMY — 7개 Tier-1 출처]
A. Trackers: Counterpoint Research, TrendForce, Omdia, IDC
C. Component: Yole
E. Asian supply chain: DigiTimes Asia
F. Carrier/EU consumer: CCS Insight"""

USER_PROMPT_TEMPLATE = """
[MAJOR-PASS TOPICS ALREADY COVERED — REJECT any candidate signal that overlaps semantically]
{existing_reports}

위 리스트에 있는 phenomenon (반도체 가격, 화웨이 점유율, 폴더블 시장, AI 글래스 메이저
narrative, 애플 파운드리 다변화, D2D 위성통신 메이저 narrative, 삼성 노조, iPhone 17e 등)을
다시 surface하면 이 디제스트의 가치가 사라진다. 같은 영역이라도 명확히 다른 angle을 잡거나,
완전히 다른 토픽을 선택하라.

[ARTICLE CORPUS — Tier-1 smartphone market articles, last {days} days]
Total: {total} articles | Sources: {source_label}

{articles}

---

[TASK]
Identify 3 to 5 "Curiosity Pick" topics. Prioritize patterns (e) and (g) —
prefer tech fact / component leaks and major OEM off-trend actions first.
Patterns (a) and (b) are fallback options only.
Single-source signals are ENCOURAGED. Do NOT require multi-source corroboration.

For each topic:
- Tag the dominant pattern with one of: "(e) tech fact" | "(g) off-trend" |
  "(a) minor OEM" | "(b) contrarian"
- Output criteria as "Criterion 3" (always — these are by definition emerging)
- Explain in rationale (Korean) WHY this is interesting beyond the obvious narrative

[OUTPUT — JSON array only]

[
  {{
    "title": "Topic title in Korean (noun phrase, 1 sentence max)",
    "criteria": "Criterion 3",
    "pattern": "(a) minor OEM | (b) contrarian | (e) tech fact | (g) off-trend",
    "institution_count": <integer>,
    "articles": [
      {{"date": "YYYY-MM-DD", "source": "<institution>", "title": "<original article title>"}}
    ],
    "key_data": [
      "<concrete data point with numbers/quotes>"
    ],
    "rationale": "왜 이 주제가 일반 분석가 시야에서는 놓치기 쉬운, 그러나 흥미로운 시그널인지 2~3문장. 어떤 pattern (a/b/e/g)인지 명시. 반드시 한국어."
  }}
]"""

ENRICH_SYSTEM = "You are a smartphone market analyst. Output only valid JSON."

ENRICH_TPL = """You previously identified the following Curiosity Pick topic:

TOPIC (KOREAN): {title}
PATTERN: (Crit 3 emerging — niche/contrarian signal)
CITED ARTICLES:
{existing_articles}
KEY DATA: {key_data}
RATIONALE: {rationale}

---

Additional articles:
{additional_articles}

---

If any of the additional articles GENUINELY support this same niche signal,
incorporate them. Otherwise discard. The signal must remain a "Curiosity Pick"
(niche/contrarian/single-source-tech/off-trend) — do NOT dilute it into a
mainstream Crit 2 multi-source consensus.

Output a single JSON object:

{{
  "title": "...",
  "criteria": "Criterion 3",
  "pattern": "(a) minor OEM | (b) contrarian | (e) tech fact | (g) off-trend",
  "institution_count": <integer>,
  "articles": [
    {{"date": "YYYY-MM-DD", "source": "<institution>", "title": "<article title>"}}
  ],
  "key_data": ["..."],
  "rationale": "2~3문장 한국어. 패턴 명시."
}}

Rules:
- Keep ALL original articles. Only add genuinely supporting ones.
- Even if institution_count rises to 2+, KEEP criteria as "Criterion 3" — this
  is a curiosity digest, not a consensus tracker.
- Preserve the niche framing of the title."""


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7,
                        help="윈도우 (default: 7일, 주 1회 실행 권장)")
    parser.add_argument("--out",  default="scripts/_topic_suggestions_emerging.json")
    args = parser.parse_args()

    major_titles = _load_major_topic_titles()
    if major_titles:
        print(f"[pre-step] Loaded {len(major_titles)} major-pass topics to reject as duplicates")

    run_pipeline(
        registry=ARCHIVE_REGISTRY,
        keyword_filter=keyword_filter,
        system_prompt=SYSTEM_PROMPT.format(days=args.days),
        user_prompt_template=USER_PROMPT_TEMPLATE,
        enrich_system=ENRICH_SYSTEM,
        enrich_tpl=ENRICH_TPL,
        out_path=args.out,
        domain_label="smartphone-emerging",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=False,
        source_taxonomy=SOURCE_TAXONOMY,
        extra_existing=major_titles,
    )


if __name__ == "__main__":
    main()
