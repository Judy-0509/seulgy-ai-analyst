"""휴머노이드 소스 가중치 A/B 테스트 — 애널리스트 제안 가중치 시뮬레이션.

배경 (2026-06-11 애널리스트 피드백):
  "OEM 발표 / 투자은행 가중치 상, 리서치들은 가중치 중, 나머지는 가중치 하"
  → 현행 _HUMANOID_SOURCE_WEIGHTS 는 리서치 기관이 최상위(IFR 0.98 등),
    IB는 테이블 누락으로 기본값 0.60. 제안은 사실상 서열 역전이라
    반영 전 동일 토픽셋으로 순위 변화를 비교한다.

방법:
  suggest_humanoid_topics.py 실행 결과(_humanoid_topic_suggestions.json)를 입력으로,
  rank_score 에서 가중치 의존 항(0.24 × source_quality)만 교체해 재채점.
    rank_score_B = rank_score_A + 0.24 × (sq_B − sq_A)
  repetition_penalty 등 나머지 항은 동결(가중치 단일 변수 통제).

실행:
  python scripts/ab_test_humanoid_weights.py

산출:
  scripts/_ab_humanoid_weights.json  (토픽별 A/B 점수·순위)
  stdout 비교 테이블
"""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _suggest_core import ROOT, _HUMANOID_SOURCE_WEIGHTS  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

INPUT_PATH  = ROOT / "scripts" / "_humanoid_topic_suggestions.json"
OUTPUT_PATH = ROOT / "scripts" / "_ab_humanoid_weights.json"

SQ_COEFF = 0.24  # apply_trend_ranking 의 source_quality 계수와 동일해야 함

# ── Variant B: 애널리스트 제안 (상 0.95 / 중 0.78 / 하 0.55) ────────────────

_TIER_HIGH = 0.95   # OEM 1차 발표 + 투자은행
_TIER_MID  = 0.78   # 시장조사 리서치
_TIER_LOW  = 0.55   # 나머지 (독립 미디어·학술)

PROPOSED_WEIGHTS = {
    # OEM / 플랫폼 1차 발표 — 상
    "Boston Dynamics":            _TIER_HIGH,
    "Figure AI":                  _TIER_HIGH,
    "1X Technologies":            _TIER_HIGH,
    "Apptronik":                  _TIER_HIGH,
    "Agility Robotics":           _TIER_HIGH,
    "Unitree":                    _TIER_HIGH,
    "Unitree Robotics":           _TIER_HIGH,
    "NVIDIA News":                _TIER_HIGH,
    "NVIDIA":                     _TIER_HIGH,
    # 투자은행 — 상
    "Goldman Sachs Research":     _TIER_HIGH,
    "Morgan Stanley Research":    _TIER_HIGH,
    "Barclays Research":          _TIER_HIGH,
    "Bank of America Institute":  _TIER_HIGH,
    "JPMorgan Research":          _TIER_HIGH,
    "Deutsche Bank Research":     _TIER_HIGH,
    # 시장조사 리서치 — 중
    "IFR":                        _TIER_MID,
    "ABI Research":               _TIER_MID,
    "IDTechEx":                   _TIER_MID,
    "Yano Research":              _TIER_MID,
    "Counterpoint Research":      _TIER_MID,
    "TrendForce":                 _TIER_MID,
    "IDC":                        _TIER_MID,
    "Omdia":                      _TIER_MID,
    # 나머지(독립 미디어·학술) — 하
    "The Robot Report":           _TIER_LOW,
    "IEEE Spectrum Robotics":     _TIER_LOW,
    "IEEE Spectrum":              _TIER_LOW,
    "TechCrunch Robotics":        _TIER_LOW,
    "MIT Technology Review":      _TIER_LOW,
    "Robotics & Automation News": _TIER_LOW,
    "RoboticsTomorrow":           _TIER_LOW,
    "The Verge":                  _TIER_LOW,
    "Humanoids Daily":            _TIER_LOW,
    "arXiv (cs.RO)":              _TIER_LOW,
}
PROPOSED_DEFAULT = _TIER_LOW
CURRENT_DEFAULT  = 0.60  # _humanoid_source_quality 의 기본값


def source_quality(topic: dict, weights: dict, default: float) -> float:
    sources = {a.get("source") for a in topic.get("articles", []) if a.get("source")}
    if not sources:
        return 0.0
    return sum(weights.get(s, default) for s in sources) / len(sources)


def main() -> None:
    if not INPUT_PATH.exists():
        sys.exit(f"입력 없음: {INPUT_PATH} — 먼저 suggest_humanoid_topics.py 를 실행하세요.")
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    topics = data.get("topics", [])
    if not topics:
        sys.exit("토픽이 비어 있습니다.")

    rows = []
    for t in topics:
        trend = t.get("trend", {})
        score_a = trend.get("rank_score", 0.0)
        sq_a = source_quality(t, _HUMANOID_SOURCE_WEIGHTS, CURRENT_DEFAULT)
        sq_b = source_quality(t, PROPOSED_WEIGHTS, PROPOSED_DEFAULT)
        score_b = score_a + SQ_COEFF * (sq_b - sq_a)
        sources = sorted({a.get("source", "") for a in t.get("articles", [])})
        rows.append({
            "title": t.get("title", ""),
            "sources": sources,
            "rank_a": trend.get("rank", 0),
            "score_a": round(score_a, 4),
            "sq_a": round(sq_a, 3),
            "score_b": round(score_b, 4),
            "sq_b": round(sq_b, 3),
        })

    rows_b = sorted(rows, key=lambda r: r["score_b"], reverse=True)
    for i, r in enumerate(rows_b, 1):
        r["rank_b"] = i
        r["rank_delta"] = r["rank_a"] - i  # +면 상승

    out = {
        "generated_at": data.get("generated_at", ""),
        "input": str(INPUT_PATH.name),
        "method": "rank_score_B = rank_score_A + 0.24 * (sq_B - sq_A); repetition penalty 동결",
        "variant_a": "_HUMANOID_SOURCE_WEIGHTS (현행)",
        "variant_b": f"애널리스트 제안 — OEM/IB {_TIER_HIGH} / 리서치 {_TIER_MID} / 나머지 {_TIER_LOW}",
        "topics": rows_b,
    }
    OUTPUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'A':>3} {'B':>3} {'Δ':>4}  {'score A':>8} {'score B':>8}  title / sources")
    print("-" * 100)
    for r in rows_b:
        delta = f"{r['rank_delta']:+d}" if r["rank_delta"] else "·"
        print(f"{r['rank_a']:>3} {r['rank_b']:>3} {delta:>4}  "
              f"{r['score_a']:>8.4f} {r['score_b']:>8.4f}  {r['title'][:60]}")
        print(f"{'':>32}{', '.join(r['sources'])[:80]}")
    print(f"\n→ {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
