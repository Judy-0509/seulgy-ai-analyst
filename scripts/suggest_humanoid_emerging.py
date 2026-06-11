"""휴머노이드 Emerging / Curiosity Pick 패스 — 주 1회 실행 권장.

메인 패스(suggest_humanoid_topics.py)와 분리된 별도 스크립트.
시장 메이저 합의 주제는 메인이 잡고, 본 스크립트는 "analyst가 흥미롭게 볼만한"
4가지 단발 신호 패턴을 좁은 윈도우(7일)로 surface한다:

  (a) 마이너/신규 휴머노이드 플레이어의 strategic movement
  (b) 메이저 narrative와 반대되는 contrarian signal
  (e) 단발성 기술 fact / 부품 leak / 단독 arXiv 논문
  (g) 메이저 4사(Tesla / Boston Dynamics / Figure / Unitree)의 비주류 행동

출력 토픽은 모두 criteria="Criterion 3"으로 통일 → frontend의
"이번 주 새롭게 등장한 주제" 섹션에 자동 노출됨.

사용:
  python scripts/suggest_humanoid_emerging.py [--days 7]

출력: scripts/_humanoid_topic_suggestions_emerging.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402
from suggest_humanoid_topics import (  # noqa: E402
    ARCHIVE_REGISTRY, SOURCE_LABEL, SOURCE_TAXONOMY, keyword_filter,
)


def _load_major_topic_titles() -> list[str]:
    """현재 메이저 패스 결과의 토픽 title 리스트.

    emerging 패스가 이를 'reject 대상'으로 받아 중복 surfacing을 방지.
    """
    p = ROOT / "scripts" / "_humanoid_topic_suggestions.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [t["title"] for t in data.get("topics", []) if t.get("title")]
    except Exception:
        return []

# ── Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior humanoid robotics market analyst preparing a
weekly "Curiosity Pick" digest. The mainstream consensus topics are already
covered by a separate 30-day major pass — DO NOT duplicate them.

Your task: surface 3 to 5 niche, contrarian, or off-trend signals that a sharp
humanoid analyst would find personally interesting in the last {days} days.

[CRITICAL OUTPUT RULES]
- TITLE LANGUAGE: every "title" field MUST be a Korean noun phrase. Never leave
  the title in English even if the source article is English. Translate the
  phenomenon into Korean.
- DUPLICATE REJECTION: the user prompt will list the major-pass topics that
  already exist. If your candidate signal is the SAME phenomenon (semantically),
  REJECT it and find a different angle or a different signal entirely. Picking
  a topic that the major pass already surfaces is a failure.

[What to LOOK FOR — 4 patterns, in priority order]

(a) MINOR / NEW humanoid players  ⭐ ACTIVELY SEEK THESE FIRST
   Apptronik, Agility Robotics, 1X Technologies, Sanctuary AI, AgiBot,
   Roze (SoftBank), UBTech, Kepler, Astribot, Pudu, Galbot,
   Xiaomi CyberOne, Disney robotics, Toyota Research Institute,
   Honda E2-DR, Sony, Lenovo robotics, Galaxy Robotics, NEURA,
   Pal Robotics, Sanctuary, Sereact, Physical Intelligence,
   Generalist AI, Skild, World Labs, K-scale Labs 등.
   메이저 4사(Tesla/BD/Figure/Unitree) 외 마이너~중위권 플레이어와
   신규 진입 스타트업·연구소의 strategic pivot, 첫 상용 계약,
   첫 양산 발표, 새 application 진입(헬스케어, 서비스, 항공, 농업),
   새 폼팩터·세그먼트, 자체 부품/AI 스택 발표.
   메이저 narrative에 묻혀버린 작은 플레이어의 움직임을 우선적으로 surface하라.
   이 패턴이 본 디제스트의 핵심이다.

(b) CONTRARIAN signals
   휴머노이드 메이저 narrative와 정반대 데이터/논평. 예시:
   - "휴머노이드 ROI 회의론 / 파일럿 실패 / 배치 철수"
   - "안전 사고 / 제품 결함 / 리콜 / 인명 사고 우려"
   - "노조·규제 반발 / 인력 대체 정치적 저항"
   - "데모 위주 마케팅 vs 실제 성능 격차" 같은 reality check
   - "시장 거품·과대평가" 분석
   - "비용 경제성 부정적 결과"
   주류와 반대 방향의 데이터 포인트가 핵심.

(e) STANDALONE technical fact / component leak / arXiv breakthrough
   1개 출처의 단발성 기술·부품·학술 신호. 예시:
   - arXiv 단독 VLA / world model / sim-to-real / dexterous manipulation
     논문 중 강한 수치(% 향상, 새 SOTA)
   - 부품 단독 leak: 새 actuator 기술, force sensor, AI 칩, 배터리 셀,
     gear/harmonic drive, 인공 근육, BMS, 방수·내구 요소
   - NVIDIA Isaac/Cosmos/GR00T 단독 기술 발표
   - 메이저 매체의 측면 코멘트에서만 언급된 기술 fact
   다른 출처의 corroboration이 없어도 가치 있는 단독 기술 신호.

(g) MAJOR humanoid OEM의 OFF-TREND 행동
   Tesla(Optimus), Boston Dynamics, Figure AI, Unitree의 비주류·의외의 액션.
   예시:
   - Optimus 가격·판매 정책 급변, 단가 하향 발표
   - Boston Dynamics가 산업 외 영역(소비자, 농업, 건설) 진출
   - Figure가 자동차 외 산업 진입(헬스케어, 호스피탈리티)
   - Unitree 미국·EU 직진출 / 가격 인상
   - 메이저 OEM의 vertical integration leap (자체 SoC, AI 칩, OS)
   - 메이저 OEM의 IPO·M&A·신규 펀딩 라운드 발표
   "왜 지금 굳이?"라는 질문이 떠오르는 종류의 액션.

[What to AVOID]
- 메이저 매체들이 이미 합의하는 주류 주제 (그건 main pass 영역)
- 단순 정기 데모 영상 / 기업 홍보 / 마케팅 재포장 보도
- 동일 주제의 재언급 / 후속 보도
- arXiv의 단순 incremental 논문 (강한 SOTA 수치 없는 경우)

[SOURCE TAXONOMY — 휴머노이드 4 레이어]
A. Independent media: R&AN, TechCrunch Robotics, IEEE Spectrum,
   The Robot Report, MIT Technology Review, Humanoids Daily,
   RoboticsTomorrow, The Verge
B. First-party OEM: Boston Dynamics, Figure AI, Unitree, NVIDIA,
   Apptronik, Agility Robotics, 1X Technologies
C. Technical Validation: arXiv (cs.RO)
D. Market / Industry Intelligence:
   IFR, Counterpoint Research, TrendForce, IDC, Omdia, IDTechEx, ABI Research, Yano Research,
   Goldman Sachs Research, Morgan Stanley Research, Barclays Research,
   Bank of America Institute, JPMorgan Research, Deutsche Bank Research"""

USER_PROMPT_TEMPLATE = """
[MAJOR-PASS TOPICS ALREADY COVERED — REJECT any candidate signal that overlaps semantically]
{existing_reports}

위 리스트에 있는 phenomenon (Schaeffler-Hexagon 1,000대, Figure BotQ 양산,
Physical Intelligence/Generalist AI 범용 모델, 휴머노이드 시장 inflection 메이저
narrative 등)을 다시 surface하면 이 디제스트의 가치가 사라진다. 같은 영역이라도
명확히 다른 angle을 잡거나, 완전히 다른 토픽을 선택하라.

[ARTICLE CORPUS — Tier-1 humanoid robotics articles, last {days} days]
Total: {total} articles | Sources: {source_label}

{articles}

---

[TASK]
Identify 3 to 5 "Curiosity Pick" topics matching one of the 4 patterns (a/b/e/g)
described in the system prompt. Single-source signals are ENCOURAGED — that is
the whole point of this digest. Do NOT require multi-source corroboration.

For each topic:
- Tag the dominant pattern with one of: "(a) minor OEM" | "(b) contrarian" |
  "(e) tech fact" | "(g) off-trend"
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
      {{"date": "YYYY-MM-DD", "source": "<source>", "title": "<original article title>"}}
    ],
    "key_data": [
      "<concrete data point with numbers/quotes>"
    ],
    "rationale": "왜 이 주제가 일반 분석가 시야에서는 놓치기 쉬운, 그러나 흥미로운 시그널인지 2~3문장. 어떤 pattern (a/b/e/g)인지 명시. 반드시 한국어."
  }}
]"""

ENRICH_SYSTEM = "You are a humanoid robotics market analyst. Output only valid JSON."

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
    {{"date": "YYYY-MM-DD", "source": "<source>", "title": "<article title>"}}
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
    parser.add_argument("--out",  default="scripts/_humanoid_topic_suggestions_emerging.json")
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
        domain_label="humanoid-emerging",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=False,
        source_taxonomy=SOURCE_TAXONOMY,
        extra_existing=major_titles,
    )


if __name__ == "__main__":
    main()
