"""SQLite 기반 article 본문 캐시.

스키마: bodies(url PK, body, source, char_count, status, extractor, fetched_at)
status: 'ok' | 'blocked' | 'empty' | 'error'

DB 경로: 기본 `data/article_bodies.db`. `BODY_CACHE_DB` 환경변수로 override (테스트용).
WAL 모드로 reader/writer 동시성 확보. autocommit (isolation_level=None).
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("BODY_CACHE_DB", "data/article_bodies.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bodies (
  url TEXT PRIMARY KEY,
  body TEXT NOT NULL DEFAULT '',
  source TEXT,
  char_count INTEGER,
  status TEXT NOT NULL,
  extractor TEXT,
  fetched_at TEXT NOT NULL
)
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_SCHEMA)
    return conn


def get_body(url: str) -> dict | None:
    """캐시 row 반환. 없으면 None."""
    with _conn() as c:
        row = c.execute(
            "SELECT url, body, source, char_count, status, extractor, fetched_at "
            "FROM bodies WHERE url=?",
            (url,),
        ).fetchone()
    if not row:
        return None
    return dict(zip(
        ["url", "body", "source", "char_count", "status", "extractor", "fetched_at"],
        row,
    ))


def put_body(url: str, body: str, source: str, status: str, extractor: str) -> None:
    """upsert. 같은 URL 재호출 시 row 1건 유지."""
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO bodies "
            "(url, body, source, char_count, status, extractor, fetched_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                url,
                body or "",
                source,
                len(body or ""),
                status,
                extractor,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def has_body(url: str) -> bool:
    return get_body(url) is not None


def is_blocked(url: str) -> bool:
    """status='blocked' 여부 (재시도 차단용)."""
    row = get_body(url)
    return bool(row and row["status"] == "blocked")


def stats() -> dict:
    """집계: total, by_source, by_status, total_chars."""
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM bodies").fetchone()[0]
        by_source = dict(
            c.execute("SELECT source, COUNT(*) FROM bodies GROUP BY source").fetchall()
        )
        by_status = dict(
            c.execute("SELECT status, COUNT(*) FROM bodies GROUP BY status").fetchall()
        )
        total_chars = c.execute("SELECT SUM(char_count) FROM bodies").fetchone()[0] or 0
    return {
        "total": total,
        "by_source": by_source,
        "by_status": by_status,
        "total_chars": total_chars,
    }


def clear(url: str | None = None, source: str | None = None) -> int:
    """일치 행 삭제. url 우선, 그 다음 source, 둘 다 없으면 전체.
    반환: 삭제된 행 수."""
    with _conn() as c:
        if url:
            cur = c.execute("DELETE FROM bodies WHERE url=?", (url,))
        elif source:
            cur = c.execute("DELETE FROM bodies WHERE source=?", (source,))
        else:
            cur = c.execute("DELETE FROM bodies")
        return cur.rowcount
