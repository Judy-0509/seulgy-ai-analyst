"""SQLite DB initialization and CRUD for MI news articles.

DB path: data/mi_news/market_dashboard.db
WAL mode for concurrent reads (scheduler writes, API reads).
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "mi_news" / "market_dashboard.db"

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Return a thread-local SQLite connection in WAL mode."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            url TEXT UNIQUE NOT NULL,
            source_name TEXT,
            source_type TEXT DEFAULT 'rss',
            language TEXT DEFAULT 'en',
            published_at TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            keywords TEXT,
            vendor_tags TEXT,
            issue_tags TEXT,
            area_tags TEXT,
            supply_chain_stage TEXT,
            ai_importance INTEGER DEFAULT 3,
            source_tier INTEGER DEFAULT 3,
            cluster_id TEXT,
            cluster_size INTEGER DEFAULT 1,
            importance REAL DEFAULT 0.0,
            summary_ko TEXT,
            summary_en TEXT,
            tag_status TEXT
        );

        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    logger.info(f"DB initialized at {DB_PATH}")


def insert_article(conn: sqlite3.Connection, article_dict: dict) -> bool:
    """INSERT OR IGNORE a single article. Returns True if inserted."""
    sql = """
        INSERT OR IGNORE INTO news_articles
            (title, description, url, source_name, source_type, language,
             published_at, keywords, source_tier)
        VALUES
            (:title, :description, :url, :source_name, :source_type, :language,
             :published_at, :keywords, :source_tier)
    """
    cur = conn.execute(sql, article_dict)
    conn.commit()
    return cur.rowcount > 0


def get_untagged_articles(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    """Return articles where vendor_tags IS NULL AND tag_status IS NULL."""
    cur = conn.execute(
        """
        SELECT id, title, description, url, source_name, source_tier
        FROM news_articles
        WHERE vendor_tags IS NULL AND tag_status IS NULL
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]


def update_article_tags(
    conn: sqlite3.Connection,
    article_id: int,
    tags_dict: dict,
) -> None:
    """Update AI-derived columns on an article."""
    conn.execute(
        """
        UPDATE news_articles SET
            vendor_tags        = :vendor_tags,
            issue_tags         = :issue_tags,
            area_tags          = :area_tags,
            supply_chain_stage = :supply_chain_stage,
            ai_importance      = :ai_importance,
            source_tier        = :source_tier,
            cluster_id         = :cluster_id,
            cluster_size       = :cluster_size,
            importance         = :importance,
            summary_ko         = :summary_ko,
            summary_en         = :summary_en,
            tag_status         = :tag_status
        WHERE id = :id
        """,
        {**tags_dict, "id": article_id},
    )
    conn.commit()
