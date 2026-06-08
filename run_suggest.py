"""
주제 추천 → 레포트 생성 진입점

최근 1개월 내 작성된 레포트 주제를 분석하여 후속 분석 주제를 추천.
사용자가 주제를 선택하면 run_report.py 파이프라인을 실행.

사용법:
  python run_suggest.py
"""
import asyncio
import sys
import json
from datetime import date, datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from src.services.llm import LLMService
from src.prompts.system import ANALYST_SYSTEM_PROMPT
from run_report import main as run_report_main

REPORTS_DIR = Path("reports")

SUGGEST_PROMPT = """You are a smartphone market analyst assistant.

The user has recently analyzed the following topics (most recent first):
{past_topics}

Today's date: {today}

Suggest 6 NEW report topics the user would likely want to analyze next.

Rules:
- Each topic must be DIFFERENT from the past topics above
- Topics must be relevant to the smartphone market (OEM strategy, market dynamics, technology, regional trends, competitive landscape)
- Topics should feel like natural follow-ups or adjacent angles to the past topics — e.g. if they analyzed foldable market impact, suggest Apple vs Samsung foldable competitive strategy, or China foldable OEM response
- Each topic should be specific and researchable — concrete enough to generate a 3-section report
- Topic titles in Korean (same style as the past topics: "X에 따른 Y 영향성" or "X의 Y 전략" etc.)
- Rationale in Korean, 1 sentence max

Respond ONLY with a valid JSON array (no markdown):
[
  {{"topic": "<Korean topic title>", "rationale": "<why this is worth analyzing now, 1 sentence>"}},
  ...
]
"""


def _get_recent_topics(days: int = 30) -> list[dict]:
    """최근 N일 내 생성된 _report.md 파일에서 주제 추출."""
    cutoff = datetime.now() - timedelta(days=days)
    reports = []
    for path in sorted(REPORTS_DIR.glob("*_report.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
            continue
        # 파일 첫 줄에서 주제 추출 (# 제목)
        try:
            first_line = path.read_text(encoding="utf-8").splitlines()[0]
            topic = first_line.lstrip("# ").strip()
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
            reports.append({"topic": topic, "date": mtime})
        except Exception:
            continue
    return reports


async def suggest(llm: LLMService) -> list[dict]:
    """최근 레포트 기반 후속 주제 추천."""
    recent = _get_recent_topics(days=30)

    if not recent:
        print("[!] 최근 1개월 내 레포트가 없습니다. 전체 레포트를 검색합니다.")
        recent = _get_recent_topics(days=365)

    if not recent:
        print("[!] 레포트 기록이 없습니다. 기본 주제로 추천합니다.")
        past_topics_str = "없음 (첫 번째 분석)"
    else:
        past_topics_str = "\n".join(f"- [{r['date']}] {r['topic']}" for r in recent)

    print(f"\n최근 분석 주제 {len(recent)}건 기반으로 추천 생성 중...\n")

    prompt = SUGGEST_PROMPT.format(
        past_topics=past_topics_str,
        today=date.today().isoformat(),
    )
    resp = await llm.complete(
        ANALYST_SYSTEM_PROMPT, prompt,
        max_tokens=1500, temperature=0.7,
        response_format={"type": "json_object"},
        thinking="disabled",
    )

    raw = resp.content.strip()

    def _clean(lst):
        return [s for s in lst if isinstance(s, dict) and s.get("topic")]

    # JSON object로 감싸진 경우 처리
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return _clean(parsed)
        # {"suggestions": [...]} 형태 처리
        for v in parsed.values():
            if isinstance(v, list):
                return _clean(v)
    except Exception:
        pass

    # fallback: json array 추출 시도
    import re
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        try:
            return _clean(json.loads(m.group()))
        except Exception:
            pass

    return []


def _print_suggestions(suggestions: list[dict], recent: list[dict]):
    print("=" * 60)
    print("  📊 분석 주제 추천")
    print("=" * 60)
    if recent:
        print("\n  [최근 분석 이력]")
        for r in recent[:3]:
            print(f"  • [{r['date']}] {r['topic']}")
    print()
    print("  [추천 주제]")
    for i, s in enumerate(suggestions, 1):
        print(f"\n  {i}. {s.get('topic', '')}")
        print(f"     → {s.get('rationale', '')}")
    print()
    print("=" * 60)


async def main():
    llm = LLMService()
    recent = _get_recent_topics(days=30) or _get_recent_topics(days=365)
    suggestions = await suggest(llm)

    if not suggestions:
        print("[!] 추천 주제 생성에 실패했습니다.")
        sys.exit(1)

    _print_suggestions(suggestions, recent)

    print("  번호를 입력하여 주제를 선택하세요 (직접 입력도 가능, q=종료):")
    print("  예) 2  또는  '직접 입력할 주제'")
    print()

    choice = input("  > ").strip()

    if choice.lower() in ("q", "quit", "exit", "0", ""):
        print("  종료합니다.")
        sys.exit(0)

    # 번호 선택
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(suggestions):
            selected_topic = suggestions[idx]["topic"]
        else:
            print("[!] 올바른 번호를 입력하세요.")
            sys.exit(1)
    else:
        # 직접 입력
        selected_topic = choice.strip("'\"")

    if not selected_topic:
        print("[!] 주제가 비어 있습니다.")
        sys.exit(1)

    print(f"\n  선택된 주제: {selected_topic}")
    print("  레포트 생성을 시작합니다...\n")

    await run_report_main(selected_topic)


if __name__ == "__main__":
    asyncio.run(main())
