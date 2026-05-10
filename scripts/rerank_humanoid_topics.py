"""Re-rank current humanoid topic suggestions using humanoid-specific evidence scoring."""
import json
from datetime import datetime
from pathlib import Path

from _suggest_core import ROOT, apply_trend_ranking


def main() -> None:
    rel_path = Path("scripts/_humanoid_topic_suggestions.json")
    path = ROOT / rel_path
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    generated_at = data.get("generated_at") or datetime.now().isoformat()
    data["topics"] = apply_trend_ranking(
        data.get("topics", []),
        out_path=rel_path,
        domain_label="humanoid",
        generated_at=generated_at,
    )
    data["ranking_method"] = {
        "version": "humanoid_trend_v1",
        "description": (
            "source quality + deployment/production/policy/technical impact + momentum "
            "+ source diversity + freshness; lower weight for arXiv/news-aggregator repetition"
        ),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    for topic in data["topics"]:
        trend = topic.get("trend", {})
        print(
            f"{trend.get('rank', '?')}. {topic.get('title', '')} "
            f"[{trend.get('status', '')}, score={trend.get('rank_score', '')}, "
            f"impact={trend.get('impact_score', '')}, commitment={trend.get('commitment_score', '')}, "
            f"quality={trend.get('source_quality_score', '')}, "
            f"articles={trend.get('current_article_count', '')}, "
            f"prev={trend.get('previous_article_count', '')}, "
            f"sources={trend.get('source_count', '')}, latest={trend.get('latest_article_date', '')}]"
        )


if __name__ == "__main__":
    main()
