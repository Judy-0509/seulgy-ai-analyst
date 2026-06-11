"""스마트글래스 Emerging / Curiosity Pick 패스 — 주 1회 실행 권장.

메인 패스(suggest_smartglass_topics.py)와 분리된 별도 스크립트.
출력 토픽은 모두 criteria="Criterion 3" → frontend "이번 주 새롭게 등장한 주제" 섹션 노출.

사용:
  python scripts/suggest_smartglass_emerging.py [--days 7]

출력: scripts/_smartglass_topic_suggestions_emerging.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402
from suggest_smartglass_topics import (  # noqa: E402
    ARCHIVE_REGISTRY, SOURCE_LABEL, SOURCE_TAXONOMY, keyword_filter,
)


def _load_major_topic_titles() -> list[str]:
    p = ROOT / "scripts" / "_smartglass_topic_suggestions.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [t["title"] for t in data.get("topics", []) if t.get("title")]
    except Exception:
        return []


SYSTEM_PROMPT = """You are a senior smart glasses analyst preparing a weekly
"Curiosity Pick" digest. The mainstream consensus topics are already covered by
a separate 30-day major pass — DO NOT duplicate them.

Your task: surface 3 to 5 niche, contrarian, or off-trend signals that a sharp
analyst would find personally interesting in the last {days} days.

[CRITICAL OUTPUT RULES]
- TITLE LANGUAGE: every "title" field MUST be a Korean noun phrase. Never leave
  the title in English even if the source article is English.
- DUPLICATE REJECTION: if your candidate signal is the SAME phenomenon as a
  major-pass topic (semantically), REJECT it and find a different angle entirely.

[What to LOOK FOR — 4 patterns, in priority order]

(a) NEW ENTRANT / CHALLENGER movements  ⭐ ACTIVELY SEEK THESE FIRST
   Meta/Google/Samsung 메이저 narrative에 묻힌 도전자들의 전략적 움직임:
   중국 브랜드(RayNeo, Rokid, Xreal, INMO), 신생 스타트업(Even Realities,
   Halliday, Brilliant Labs), 부품 신규 진입자(waveguide/microLED 스타트업),
   신규 계약·자금 조달·기술 시연. 이 패턴이 핵심이다.

(b) CONTRARIAN signals
   메이저 narrative와 정반대 데이터/논평. 예시:
   - "AI 글래스 반품률/사용 중단율 데이터" (열광 속 냉정한 신호)
   - "디스플레이 글래스의 BOM 원가 구조상 가격 장벽"
   - "프라이버시 규제가 카메라 글래스 보급의 실질 제약"
   - "스마트폰 대체론에 대한 회의적 사용 데이터"

(c) STANDALONE technical fact / component signal
   1개 출처의 단발성 기술·부품 신호. 예시:
   - KGOnTech/Yole 단독 광학 teardown (waveguide 효율, microLED 풀컬러)
   - 부품사 단독 발표 (JBD 신규 microdisplay spec, Lumus 수율 개선)
   - 단독 리포트에서만 언급된 BOM 원가 / 수율 수치

(d) DELAY / SETBACK / BARRIER signal
   출시 지연, 기술 장벽 재부상, 규제 난항. 예시:
   - 발표 제품의 출하 지연과 기술적 원인 (배터리, 발열, 수율)
   - 프라이버시/안전 규제 이슈
   - 예상 대비 판매 부진 데이터

[What to AVOID]
- 메이저 플레이어들이 이미 합의하는 주류 로드맵 주제 (main pass 영역)
- VR 게임/콘텐츠 뉴스 (글래스 폼팩터 각도 없는 것)
- 동일 주제의 재언급 / 후속 보도

[SOURCE TAXONOMY — 18개 출처]
A. Trackers: Counterpoint, Omdia, TrendForce, IDC, CCS Insight
B. Market research: ABI Research, IDTechEx
C. Optics analysis: Yole, KGOnTech
D. XR media: UploadVR, Road to VR, The Ghost Howls, AR Insider
E. Asia supply chain: DigiTimes Asia
F. IB: Bank of America Institute, Citi Research
G. Vendor: Meta Newsroom, Rokid"""

USER_PROMPT_TEMPLATE = """
[MAJOR-PASS TOPICS ALREADY COVERED — REJECT any candidate signal that overlaps semantically]
{existing_reports}

위 리스트에 있는 phenomenon을 다시 surface하면 이 디제스트의 가치가 사라진다.
같은 영역이라도 명확히 다른 angle을 잡거나, 완전히 다른 토픽을 선택하라.

[ARTICLE CORPUS — Tier-1 smart glasses articles, last {days} days]
Total: {total} articles | Sources: {source_label}

{articles}

---

[TASK]
Identify 3 to 5 "Curiosity Pick" topics matching one of the 4 patterns (a/b/c/d)
described in the system prompt. Single-source signals are ENCOURAGED — that is
the whole point of this digest. Do NOT require multi-source corroboration.

For each topic:
- Tag the dominant pattern with one of:
  "(a) new entrant" | "(b) contrarian" | "(c) tech fact" | "(d) setback"
- Output criteria as "Criterion 3" (always — these are by definition emerging)
- Explain in rationale (Korean) WHY this is interesting beyond the obvious narrative

[OUTPUT — JSON array only]

[
  {{
    "title": "Topic title in Korean (noun phrase, 1 sentence max)",
    "criteria": "Criterion 3",
    "pattern": "(a) new entrant | (b) contrarian | (c) tech fact | (d) setback",
    "institution_count": <integer>,
    "articles": [
      {{"date": "YYYY-MM-DD", "source": "<institution>", "title": "<original article title>"}}
    ],
    "key_data": [
      "<concrete data point with numbers/quotes>"
    ],
    "rationale": "왜 이 주제가 일반 분석가 시야에서는 놓치기 쉬운, 그러나 흥미로운 시그널인지 2~3문장. 어떤 pattern (a/b/c/d)인지 명시. 반드시 한국어."
  }}
]"""

ENRICH_SYSTEM = "You are a smart glasses market analyst. Output only valid JSON."

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
(niche/contrarian/single-source/setback) — do NOT dilute it into a
mainstream Crit 2 multi-source consensus.

Output a single JSON object:

{{
  "title": "...",
  "criteria": "Criterion 3",
  "pattern": "(a) new entrant | (b) contrarian | (c) tech fact | (d) setback",
  "institution_count": <integer>,
  "articles": [
    {{"date": "YYYY-MM-DD", "source": "<institution>", "title": "<article title>"}}
  ],
  "key_data": ["..."],
  "rationale": "2~3문장 한국어. 패턴 명시."
}}

Rules:
- Keep ALL original articles. Only add genuinely supporting ones.
- Even if institution_count rises to 2+, KEEP criteria as "Criterion 3".
- Preserve the niche framing of the title."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7,
                        help="윈도우 (default: 7일, 주 1회 실행 권장)")
    parser.add_argument("--out",  default="scripts/_smartglass_topic_suggestions_emerging.json")
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
        domain_label="smartglass-emerging",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=False,
        source_taxonomy=SOURCE_TAXONOMY,
        extra_existing=major_titles,
    )


if __name__ == "__main__":
    main()
