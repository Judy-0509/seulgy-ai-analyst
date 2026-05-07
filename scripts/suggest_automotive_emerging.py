"""자동차 Emerging / Curiosity Pick 패스 — 주 1회 실행 권장.

메인 패스(suggest_automotive_topics.py)와 분리된 별도 스크립트.
시장 메이저 합의 주제는 메인이 잡고, 본 스크립트는 "analyst가 흥미롭게 볼만한"
4가지 단발 신호 패턴을 좁은 윈도우(7일)로 surface한다:

  (a) 마이너/신규 OEM·부품사의 strategic movement
  (b) 메이저 narrative와 반대되는 contrarian signal
  (e) 단발성 기술 fact / 부품 leak / 단독 데이터
  (g) 메이저 OEM(Tesla / Toyota / VW / GM / Ford / Stellantis / Hyundai-Kia / BYD)의
      비주류 행동

출력 토픽은 모두 criteria="Criterion 3"으로 통일 → frontend의
"이번 주 새롭게 등장한 주제" 섹션에 자동 노출됨.

사용:
  python scripts/suggest_automotive_emerging.py [--days 7]

출력: scripts/_automotive_topic_suggestions_emerging.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402
from suggest_automotive_topics import (  # noqa: E402
    ARCHIVE_REGISTRY, SOURCE_LABEL, SOURCE_TAXONOMY, keyword_filter,
)


def _load_major_topic_titles() -> list[str]:
    """현재 메이저 패스 결과의 토픽 title 리스트.

    emerging 패스가 이를 'reject 대상'으로 받아 중복 surfacing을 방지.
    """
    p = ROOT / "scripts" / "_automotive_topic_suggestions.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [t["title"] for t in data.get("topics", []) if t.get("title")]
    except Exception:
        return []

# ── Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior automotive market analyst preparing a weekly
"Curiosity Pick" digest. The mainstream consensus topics are already covered by
a separate 30-day major pass — DO NOT duplicate them.

Your task: surface 3 to 5 niche, contrarian, or off-trend signals that a sharp
automotive analyst would find personally interesting in the last {days} days.

[CRITICAL OUTPUT RULES]
- TITLE LANGUAGE: every "title" field MUST be a Korean noun phrase. Never leave
  the title in English even if the source article is English. Translate the
  phenomenon into Korean.
- DUPLICATE REJECTION: the user prompt will list the major-pass topics that
  already exist. If your candidate signal is the SAME phenomenon (semantically),
  REJECT it and find a different angle or a different signal entirely. Picking
  a topic that the major pass already surfaces is a failure.

[What to LOOK FOR — 4 patterns, in priority order]

(a) MINOR / NEW automotive players  ⭐ ACTIVELY SEEK THESE FIRST
   Polestar, Lucid, Rivian, VinFast, Fisker, Slate Auto, Lordstown, Canoo,
   Sono Motors, Aiways, Nio Neta, Leapmotor, Xpeng (해외 진출 단계),
   Lynk & Co, Zeekr, GAC, Chery (글로벌 expansion 신단계),
   Tata Motors EV, Mahindra Born Electric, Maruti Suzuki EV,
   Mazda BEV, Subaru Solterra, Mitsubishi PHEV, Suzuki India EV,
   Sony-Honda Afeela, Foxconn Foxtron, Ola Electric (인도),
   부품사 신호: Mobileye 단독 win, Wayve, Aurora, Plus.ai, 자율주행 트럭 스타트업,
   배터리 스타트업 (QuantumScape, SES, Solid Power, Sila, Group14),
   충전 신규 사업자 (EVgo, ChargePoint 변동, IONITY EU 확장,
   인도/동남아 충전 사업자), 라이다 회사 (Luminar, Innoviz, Hesai).
   메이저 6사(Tesla/Toyota/VW/GM/Ford/Stellantis) 외 마이너~중위권 플레이어와
   신규 진입 스타트업의 strategic pivot, 첫 양산, 첫 흑자, 새 segment 진입,
   해외시장 진출, 자체 부품 발표. 메이저 narrative에 묻혀버린 작은 플레이어의
   움직임을 우선적으로 surface하라. 이 패턴이 본 디제스트의 핵심이다.

(b) CONTRARIAN signals
   자동차 메이저 narrative와 정반대 데이터/논평. 예시:
   - "EV 둔화 / EV 수요 약세 / 딜러 재고 누적" (붐 narrative 속 reality check)
   - "하이브리드 부활" (BEV 일변도 narrative 속 PHEV/HEV 회복)
   - "ICE 회귀 / EV 모델 단종" (전동화 narrative 속 역행 신호)
   - "EV 잔존가치 폭락 / 보험료 급등" (소유 경제성 부정)
   - "충전 인프라 한계 / 그리드 제약" (인프라 낙관론 반박)
   - "자율주행 deployment 좌초" (Cruise 철수 같은)
   - "관세 retaliation 역방향 흐름" (한쪽 보호주의 반사 효과)
   - "중국 EV 가격경쟁의 글로벌 디플레이션 압력"
   - "SDV 수익화 실패 / OTA 구독 거부"
   주류와 반대 방향의 데이터 포인트가 핵심.

(e) STANDALONE technical fact / supplier leak / 단독 데이터
   1개 출처의 단발성 기술·부품·정량 신호. 예시:
   - 솔리드스테이트 / 나트륨이온 / 실리콘 음극 단독 진전 발표
   - 배터리 셀 단독 테스트 결과 (사이클 수명, 에너지밀도)
   - 새 SDV 플랫폼·OS 단독 공개 (Rivian R2 unboxed, VW SSP 변경)
   - 단독 Mobileye / Nvidia DRIVE / Snapdragon Ride win
   - 라이다 신모델 단독 채택
   - 자율주행 milestone (특정 robotaxi 도시 진입)
   - JATO 또는 Cox 단독 정량 데이터 (특정 segment·국가)
   - SAE 단독 표준 발표
   다른 출처의 corroboration이 없어도 가치 있는 단독 신호.

(g) MAJOR automotive OEM의 OFF-TREND 행동
   Tesla, Toyota, Volkswagen, GM, Ford, Stellantis, Hyundai-Kia, BYD,
   Mercedes, BMW의 비주류·의외의 액션. 예시:
   - Tesla 가격 정책 급변 / Cybertruck 단종 / FSD 구독 모델 변경
   - Toyota 갑작스런 BEV 가속 (수년간 HEV 위주 후 전환)
   - VW 대형 reset / 공장 폐쇄 / 중국 합작 재편
   - GM의 Cruise 처분 / EV 라인 통폐합
   - Ford의 EV 공장 일시 중단 / F-150 Lightning 정책 변화
   - Stellantis의 특정 시장 철수 / 브랜드 통폐합
   - Hyundai-Kia의 비EV 전략 다변화 (수소·합성연료)
   - BYD의 EU 직접 진출 가속 / 미국 우회 진입
   - Mercedes / BMW의 EV 목표 재조정 (연도 후퇴)
   - 메이저 OEM의 IPO·M&A·신규 합작 발표
   "왜 지금 굳이?"라는 질문이 떠오르는 종류의 액션.

[What to AVOID]
- 메이저 매체들이 이미 합의하는 주류 주제 (그건 main pass 영역)
- 단순 정기 판매 데이터 / 분기 실적 발표 그 자체
- 동일 주제의 재언급 / 후속 보도
- 단순 모델 페이스리프트 / 연식 변경

[SOURCE TAXONOMY — 자동차 4 레이어 / 26 소스]
A. Independent media: WardsAuto, Automotive Dive, Automotive World,
   Electrek, InsideEVs, CnEVPost, CarNewsChina, DigiTimes Asia
B. First-party OEM: VW Group, Toyota Newsroom
C. Quantitative trackers: JATO Dynamics, Cox Automotive,
   Counterpoint Research, TrendForce, Omdia, IDC, Yole
D. Consultancy / association / policy: AlixPartners, SAE International,
   ICCT, ACEA, CCS Insight, BloombergNEF, RMI,
   Transport & Environment, IRENA"""

USER_PROMPT_TEMPLATE = """
[MAJOR-PASS TOPICS ALREADY COVERED — REJECT any candidate signal that overlaps semantically]
{existing_reports}

위 리스트에 있는 phenomenon (BYD 글로벌 점유율 메이저 narrative, Tesla 가격 인하 메이저
narrative, EU CO2 규제 메이저 narrative, IRA EV credit 메이저 narrative 등)을 다시
surface하면 이 디제스트의 가치가 사라진다. 같은 영역이라도 명확히 다른 angle을 잡거나,
완전히 다른 토픽을 선택하라.

[ARTICLE CORPUS — Tier-1 automotive market articles, last {days} days]
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

ENRICH_SYSTEM = "You are an automotive market analyst. Output only valid JSON."

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
    parser.add_argument("--out",  default="scripts/_automotive_topic_suggestions_emerging.json")
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
        domain_label="automotive-emerging",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=False,
        source_taxonomy=SOURCE_TAXONOMY,
        extra_existing=major_titles,
    )


if __name__ == "__main__":
    main()
