"""SQLite 기반 사용자 피드백 저장소.

스키마: feedback(id, user_id, email, name, domain, target_type, target_ref, message, status, created_at)
status: 'new' | 'reviewed' | 'applied' | 'dismissed'
target_type: 'general' | 'keyword' | 'source' | 'report'

DB 경로: 기본 `data/feedback.db`. `FEEDBACK_DB` 환경변수로 override (테스트용).
WAL 모드로 reader/writer 동시성 확보. autocommit (isolation_level=None).
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("FEEDBACK_DB", "data/feedback.db"))

ALLOWED_STATUS = {"new", "reviewed", "applied", "dismissed"}
ALLOWED_TARGET_TYPE = {"general", "keyword", "source", "report"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT,
  email TEXT NOT NULL,
  name TEXT,
  domain TEXT,
  target_type TEXT,
  target_ref TEXT,
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL
)
"""

_COLUMNS = ["id", "user_id", "email", "name", "domain", "target_type", "target_ref", "message", "status", "created_at"]


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), isolation_level=None, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_SCHEMA)
    return conn


def _row_to_dict(row: tuple) -> dict:
    return dict(zip(_COLUMNS, row))


def add_feedback(
    user_id: str,
    email: str,
    name: str,
    domain: str,
    target_type: str,
    target_ref: str,
    message: str,
) -> dict:
    """피드백 행 추가, 생성된 전체 row 반환."""
    created_at = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO feedback "
            "(user_id, email, name, domain, target_type, target_ref, message, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,'new',?)",
            (
                user_id or "",
                email or "",
                name or "",
                domain or "",
                target_type or "general",
                target_ref or "",
                message,
                created_at,
            ),
        )
        row_id = cur.lastrowid
        row = c.execute(
            "SELECT id, user_id, email, name, domain, target_type, target_ref, message, status, created_at "
            "FROM feedback WHERE id=?",
            (row_id,),
        ).fetchone()
    return _row_to_dict(row)


def list_mine(email: str) -> list[dict]:
    """특정 이메일의 피드백 목록 (최신 순)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, user_id, email, name, domain, target_type, target_ref, message, status, created_at "
            "FROM feedback WHERE email=? ORDER BY id DESC",
            (email or "",),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_all(domain: str | None = None, status: str | None = None) -> list[dict]:
    """전체 피드백 목록 (최신 순). domain/status 선택 필터."""
    clauses = []
    params: list = []
    if domain:
        clauses.append("domain=?")
        params.append(domain)
    if status:
        clauses.append("status=?")
        params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as c:
        rows = c.execute(
            f"SELECT id, user_id, email, name, domain, target_type, target_ref, message, status, created_at "
            f"FROM feedback {where} ORDER BY id DESC",
            params,
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_status(fid: int, status: str) -> bool:
    """status 업데이트. 유효하지 않은 status이거나 row 없으면 False."""
    if status not in ALLOWED_STATUS:
        return False
    with _conn() as c:
        cur = c.execute(
            "UPDATE feedback SET status=? WHERE id=?",
            (status, fid),
        )
        return cur.rowcount > 0
