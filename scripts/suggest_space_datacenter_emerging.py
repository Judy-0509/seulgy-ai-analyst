"""스페이스 데이터센터 Emerging / Curiosity Pick 패스 — 주 1회 실행 권장.

메인 패스(suggest_space_datacenter_topics.py)와 분리된 별도 스크립트.
시장 메이저 합의 주제는 메인이 잡고, 본 스크립트는 "analyst가 흥미롭게 볼만한"
4가지 단발 신호 패턴을 좁은 윈도우(7일)로 surface한다:

  (a) 신규 진입자/스타트업의 전략적 movement
  (b) 메이저 narrative와 반대되는 contrarian signal
  (c) 단발성 기술 fact / 부품·아키텍처 신호
  (d) 배포 지연·기술 장벽·setback 신호

출력 토픽은 모두 criteria="Criterion 3"으로 통일 → frontend의
"이번 주 새롭게 등장한 주제" 섹션에 자동 노출됨.

사용:
  python scripts/suggest_space_datacenter_emerging.py [--days 7]

출력: scripts/_space_datacenter_topic_suggestions_emerging.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, run_pipeline  # noqa: E402
from suggest_space_datacenter_topics import (  # noqa: E402
    ARCHIVE_REGISTRY, SOURCE_LABEL, SOURCE_TAXONOMY, keyword_filter,
)


def _load_major_topic_titles() -> list[str]:
    p = ROOT / "scripts" / "_space_datacenter_topic_suggestions.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [t["title"] for t in data.get("topics", []) if t.get("title")]
    except Exception:
        return []


# ── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior space datacenter analyst preparing a weekly
"Curiosity Pick" digest. The mainstream consensus topics are already covered by
a separate 30-day major pass — DO NOT duplicate them.

Your task: surface 3 to 5 niche, contrarian, or off-trend signals that a sharp
analyst would find personally interesting in the last {{days}} days.

[CRITICAL OUTPUT RULES]
- TITLE LANGUAGE: every "title" field MUST be a Korean noun phrase. Never leave
  the title in English even if the source article is English.
- DUPLICATE REJECTION: if your candidate signal is the SAME phenomenon as a
  major-pass topic (semantically), REJECT it and find a different angle entirely.

[What to LOOK FOR — 4 patterns, in priority order]

(a) NEW ENTRANT / STARTUP movements  ⭐ ACTIVELY SEEK THESE FIRST
   소규모 스타트업, 비메이저 플레이어(Lumen Orbit, Axiom, Relativity Space 등)의
   전략적 발표, 신규 계약, 기술 시연, 파트너십, 자금 조달.
   SpaceX/Amazon/Microsoft/Google 메이저 4사 위주 narrative에서 묻혀버린
   작은 플레이어의 움직임을 우선적으로 surface하라. 이 패턴이 핵심이다.

(b) CONTRARIAN signals
   메이저 narrative와 정반대 데이터/논평. 예시:
   - "궤도 데이터센터의 경제성 회의론" (열광적 분위기 속 냉정한 분석)
   - "지상 데이터센터 대비 space의 실제 비용 우위 부재"
   - "방사선 내성 문제 미해결 → 하드웨어 수명 과대평가"
   - "지상국 병목으로 인한 latency 이점 상쇄"
   주류와 반대 방향의 데이터 포인트가 핵심.

(c) STANDALONE technical fact / component signal
   1개 출처의 단발성 기술·부품·아키텍처 신호. 예시:
   - IEEE/arXiv 단독 논문 (새로운 열 관리 솔루션, ISL 대역폭 기록)
   - Vendor 단독 발표 (NVIDIA space-grade GPU spec, rad-hard 새 칩셋)
   - 단독 리포트에서만 언급된 전력 예산 / WPT 효율 수치
   다른 출처의 corroboration이 없어도 가치 있는 단독 기술 신호.

(d) DELAY / SETBACK / BARRIER signal
   예상보다 늦어지는 배포 일정, 기술적 장벽 재부상, 규제 난항. 예시:
   - 발사 지연 및 그 기술적 원인
   - 열 관리 / 전력 예산 목표 미달 보고
   - 스펙트럼 할당 규제 지연
   - 예상 비용 대비 실제 비용 초과 보고
   낙관론 속 현실 점검 신호.

[What to AVOID]
- 메이저 플레이어들이 이미 합의하는 주류 로드맵 주제 (그건 main pass 영역)
- 단순 위성 통신 뉴스 (compute/datacenter 각도 없는 것)
- 동일 주제의 재언급 / 후속 보도
- 관련성 없는 일반 우주 탐사 뉴스

[SOURCE TAXONOMY — 8개 Tier-1 출처]
A. Space primary: SpaceNews, Space.com
B. Tech/Academic: IEEE Spectrum, arXiv (cs.DC)
C. DC industry: Data Center Knowledge, Data Center Frontier
D. Venture/startup: TechCrunch
E. Vendor: NVIDIA"""

USER_PROMPT_TEMPLATE = """
[MAJOR-PASS TOPICS ALREADY COVERED — REJECT any candidate signal that overlaps semantically]
{existing_reports}

위 리스트에 있는 phenomenon을 다시 surface하면 이 디제스트의 가치가 사라진다.
같은 영역이라도 명확히 다른 angle을 잡거나, 완전히 다른 토픽을 선택하라.

[ARTICLE CORPUS — Tier-1 space datacenter articles & papers, last {days} days]
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

ENRICH_SYSTEM = "You are a space datacenter analyst. Output only valid JSON."

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


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7,
                        help="윈도우 (default: 7일, 주 1회 실행 권장)")
    parser.add_argument("--out",  default="scripts/_space_datacenter_topic_suggestions_emerging.json")
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
        domain_label="space_datacenter-emerging",
        source_label=SOURCE_LABEL,
        days=args.days,
        with_existing=False,
        source_taxonomy=SOURCE_TAXONOMY,
        extra_existing=major_titles,
    )


if __name__ == "__main__":
    main()
