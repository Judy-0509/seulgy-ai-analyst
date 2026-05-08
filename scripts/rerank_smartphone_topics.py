"""Re-rank current smartphone topic suggestions using trend history.

This does not call the LLM or fetch new data. It reads scripts/_topic_suggestions.json,
compares each topic against scripts/_history/smartphone_*.json, and writes the same
file with trend metadata and refreshed ordering.
"""
import json
from datetime import datetime
from pathlib import Path

from _suggest_core import ROOT, apply_trend_ranking


def main() -> None:
    rel_path = Path("scripts/_topic_suggestions.json")
    path = ROOT / rel_path
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    generated_at = data.get("generated_at") or datetime.now().isoformat()
    topics = data.get("topics", [])
    data["topics"] = apply_trend_ranking(
        topics,
        out_path=rel_path,
        domain_label="smartphone",
        generated_at=generated_at,
    )
    data["ranking_method"] = {
        "version": "smartphone_trend_v1",
        "description": "volume + momentum + source diversity + freshness + novelty - decline/stale penalties",
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    for topic in data["topics"]:
        trend = topic.get("trend", {})
        print(
            f"{trend.get('rank', '?')}. {topic.get('title', '')} "
            f"[{trend.get('status', '')}, score={trend.get('rank_score', '')}, "
            f"articles={trend.get('current_article_count', '')}, "
            f"prev={trend.get('previous_article_count', '')}, "
            f"sources={trend.get('source_count', '')}, latest={trend.get('latest_article_date', '')}]"
        )


if __name__ == "__main__":
    main()
