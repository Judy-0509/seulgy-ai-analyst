"""APScheduler for MI news pipeline.

Three jobs at 07:00, 15:30, 23:00 KST:
  RSS collect → AI tag (untagged) → cluster → importance recalc
"""
from __future__ import annotations

import json
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _job_mi_news() -> None:
    """RSS collect → AI tag → cluster → importance recalc."""
    logger.info("MI News job start")

    # 1. RSS collection
    try:
        from src.collectors.rss_feeds import fetch_rss_feeds
        ins, skp = fetch_rss_feeds()
        logger.info(f"MI News RSS: +{ins} inserted, {skp} skipped")
    except Exception as e:
        logger.error(f"MI News RSS error: {e}")

    # 2. AI tagging
    try:
        from src.news_db import get_connection, get_untagged_articles, update_article_tags
        from src.collectors.ai_tagger import tag_article
        from src.collectors.importance_scorer import count_keyword_hits, compute_importance

        conn = get_connection()
        untagged = get_untagged_articles(conn, limit=100)
        for art in untagged:
            tags = tag_article(art["title"], art["description"] or "")
            tier = art.get("source_tier") or 3
            kw_hits = count_keyword_hits(art["title"], art["description"] or "")
            imp = compute_importance(
                source_tier=tier,
                cluster_size=1,
                keyword_hits=kw_hits,
                ai_score=tags["ai_importance"],
            )
            update_article_tags(conn, art["id"], {
                "vendor_tags":        json.dumps(tags["vendor_tags"]),
                "issue_tags":         json.dumps(tags["issue_tags"]),
                "area_tags":          json.dumps(tags.get("area_tags", [])),
                "supply_chain_stage": tags["supply_chain_stage"],
                "ai_importance":      tags["ai_importance"],
                "source_tier":        tier,
                "cluster_id":         None,
                "cluster_size":       1,
                "importance":         imp,
                "summary_ko":         tags["summary_ko"],
                "summary_en":         tags["summary_en"],
                "tag_status":         tags.get("tag_status", "failed"),
            })
        logger.info(f"AI tagging done: {len(untagged)} articles")
    except Exception as e:
        logger.error(f"AI tagging error: {e}")

    # 3. Clustering + importance recalc
    try:
        from src.news_db import get_connection
        from src.collectors.story_cluster import assign_clusters
        from src.collectors.importance_scorer import count_keyword_hits, compute_importance

        conn = get_connection()
        rows = conn.execute(
            """
            SELECT id, vendor_tags, published_at, ai_importance, source_tier,
                   title, description
            FROM news_articles
            WHERE created_at >= datetime('now', '-14 days')
            ORDER BY id DESC
            LIMIT 500
            """
        ).fetchall()
        articles = [dict(r) for r in rows]

        if articles:
            clustered = assign_clusters(articles)
            for art in clustered:
                orig = conn.execute(
                    "SELECT ai_importance, source_tier, title, description FROM news_articles WHERE id=?",
                    (art["id"],),
                ).fetchone()
                if not orig:
                    continue
                kw_hits = count_keyword_hits(orig["title"] or "", orig["description"] or "")
                imp = compute_importance(
                    source_tier=orig["source_tier"] or 3,
                    cluster_size=art["cluster_size"],
                    keyword_hits=kw_hits,
                    ai_score=orig["ai_importance"] or 3,
                )
                conn.execute(
                    "UPDATE news_articles SET cluster_id=?, cluster_size=?, importance=? WHERE id=?",
                    (str(art["cluster_id"]), art["cluster_size"], imp, art["id"]),
                )
            conn.commit()
            logger.info(f"Clustering done: {len(clustered)} articles")
    except Exception as e:
        logger.error(f"Clustering error: {e}")

    logger.info("MI News job complete")


def start_scheduler() -> None:
    """Start the background scheduler. Safe to call multiple times."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")

    for job_id, hour, minute in [
        ("mi_news_morning",   7,  0),
        ("mi_news_afternoon", 15, 30),
        ("mi_news_night",     23, 0),
    ]:
        _scheduler.add_job(
            _job_mi_news,
            trigger=CronTrigger(hour=hour, minute=minute, timezone="Asia/Seoul"),
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )

    _scheduler.start()
    logger.info("MI News scheduler started (07:00, 15:30, 23:00 KST)")


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler
