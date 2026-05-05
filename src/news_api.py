"""Read-only MI News API integrated from the standalone news app."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "mi_news" / "market_dashboard.db"

router = APIRouter(prefix="/api/news", tags=["news"])

VENDOR_GROUPS: dict[str, list[str]] = {
    "OPPO Group": ["OPPO", "OnePlus", "Realme"],
    "Motorola Group": ["Motorola", "Lenovo"],
    "Transsion": ["Transsion", "Tecno", "Infinix", "itel"],
    "CN Brands": [
        "Huawei",
        "OPPO",
        "OnePlus",
        "Realme",
        "vivo",
        "Xiaomi",
        "Honor",
        "Motorola",
        "Lenovo",
        "Transsion",
        "Tecno",
        "Infinix",
        "itel",
    ],
    "Others": ["Sony", "Nokia", "Others"],
}

ISSUE_LABELS: dict[str, str] = {
    "demand": "수요",
    "supply_chain": "공급망",
    "market_data": "시장 데이터",
    "pricing": "가격/ASP",
    "macro": "거시경제",
    "tech": "기술/스펙",
    "channel": "채널/유통",
    "regulation": "규제/정책",
    "competition": "경쟁/M&A",
    "earnings": "실적",
    "capacity": "CAPA/가동률",
    "process_node": "공정 노드",
    "packaging": "패키징",
    "ev_autonomous": "EV/자율주행",
    "robotics": "로봇/휴머노이드",
}

STANDALONE_BEFORE = ["Samsung", "Apple"]
STANDALONE_AFTER = ["Google"]
CN_BRANDS_DISPLAY = ["Huawei", "OPPO Group", "vivo", "Xiaomi", "Honor", "Motorola Group", "Transsion"]
OTHERS_CHILDREN = ["Sony", "Nokia"]


def _connect() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_tags(value) -> list[str]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            dt = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_to_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["vendor_tags"] = _parse_tags(item.get("vendor_tags"))
    item["issue_tags"] = _parse_tags(item.get("issue_tags"))
    item["area_tags"] = _parse_tags(item.get("area_tags"))
    return item


def _load_articles(search: Optional[str] = None) -> list[dict]:
    conn = _connect()
    if conn is None:
        return []
    where = []
    params: list[str] = []
    if search:
        where.append("(title LIKE ? OR description LIKE ? OR summary_ko LIKE ? OR summary_en LIKE ?)")
        q = f"%{search}%"
        params.extend([q, q, q, q])
    sql = """SELECT id, title, description, url, source_name, source_type, language,
                    published_at, summary_ko, summary_en, vendor_tags, issue_tags, area_tags,
                    ai_importance, source_tier, cluster_id, cluster_size, importance,
                    supply_chain_stage
             FROM news_articles"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def _latest_window_articles(days: int, search: Optional[str] = None) -> list[dict]:
    articles = _load_articles(search)
    dated = [(article, _parse_datetime(article.get("published_at"))) for article in articles]
    dated_values = [dt for _, dt in dated if dt]
    if not dated_values:
        return articles

    now_cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    latest_cutoff = max(dated_values) - timedelta(days=days)
    filtered = [article for article, dt in dated if dt is None or dt >= now_cutoff]
    if not filtered:
        filtered = [article for article, dt in dated if dt is None or dt >= latest_cutoff]
    return filtered


def _sort_articles(articles: list[dict], limit: int) -> list[dict]:
    return sorted(
        articles,
        key=lambda a: (
            float(a.get("importance") or 0),
            _parse_datetime(a.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )[:limit]


def _count_tags(tag_name: str, days: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in _latest_window_articles(days):
        for tag in article.get(tag_name, []):
            counts[tag] = counts.get(tag, 0) + 1
    return counts


@router.get("")
def list_news(
    vendor: list[str] = Query(default=[]),
    issue: list[str] = Query(default=[]),
    vendor_mode: str = Query(default="or"),
    issue_mode: str = Query(default="or"),
    tier3_only: bool = Query(default=False),
    days: int = Query(7, ge=1, le=90),
    lang: Optional[str] = Query(None),
    area: list[str] = Query(default=[]),
    search: str = Query(default=""),
    limit: int = Query(200, ge=1, le=2000),
):
    articles = _latest_window_articles(days, search or None)

    if vendor:
        selections = [set(VENDOR_GROUPS[v]) if v in VENDOR_GROUPS else {v} for v in vendor]
        if vendor_mode == "and":
            articles = [a for a in articles if all(sel & set(a["vendor_tags"]) for sel in selections)]
        else:
            all_brands = set().union(*selections)
            articles = [a for a in articles if all_brands & set(a["vendor_tags"])]

    if issue:
        if issue_mode == "and":
            articles = [a for a in articles if all(i in a["issue_tags"] for i in issue)]
        else:
            issue_set = set(issue)
            articles = [a for a in articles if issue_set & set(a["issue_tags"])]

    if area:
        area_set = set(area)
        articles = [a for a in articles if area_set & set(a.get("area_tags", []))]

    if tier3_only:
        articles = [a for a in articles if a.get("source_tier") == 3]

    if lang:
        articles = [a for a in articles if a.get("language") == lang]

    total = len(articles)
    return {"total": total, "articles": _sort_articles(articles, limit)}


@router.get("/meta")
def get_news_meta():
    conn = _connect()
    if conn is None:
        return {"last_collected_at": None, "next_update_at": None, "schedule": ["07:00", "15:30"]}
    row = conn.execute("SELECT MAX(created_at) as last_collected FROM news_articles").fetchone()
    last_collected = row["last_collected"] if row and row["last_collected"] else None

    kst_now = datetime.now(timezone.utc) + timedelta(hours=9)
    next_update = None
    for hour, minute in [(7, 0), (15, 30)]:
        candidate = kst_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > kst_now:
            next_update = candidate
            break
    if next_update is None:
        tomorrow = kst_now + timedelta(days=1)
        next_update = tomorrow.replace(hour=7, minute=0, second=0, microsecond=0)

    return {
        "last_collected_at": last_collected.replace(" ", "T") + "Z" if last_collected else None,
        "next_update_at": (next_update - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schedule": ["07:00", "15:30"],
    }


@router.get("/vendors")
def get_vendors(days: int = Query(7, ge=1, le=90)):
    brand_counts = _count_tags("vendor_tags", days)
    result = []

    for brand in STANDALONE_BEFORE:
        count = brand_counts.get(brand, 0)
        if count:
            result.append({"id": brand, "label": brand, "count": count, "children": []})

    cn_children = []
    for item in CN_BRANDS_DISPLAY:
        if item in VENDOR_GROUPS:
            children = [
                {"id": member, "label": member, "count": brand_counts.get(member, 0), "children": []}
                for member in VENDOR_GROUPS[item]
                if brand_counts.get(member, 0) > 0
            ]
            count = sum(child["count"] for child in children)
            if count:
                cn_children.append({"id": item, "label": item, "count": count, "children": children})
        else:
            count = brand_counts.get(item, 0)
            if count:
                cn_children.append({"id": item, "label": item, "count": count, "children": []})
    cn_count = sum(child["count"] for child in cn_children)
    if cn_count:
        result.append({"id": "CN Brands", "label": "CN Brands", "count": cn_count, "children": cn_children})

    for brand in STANDALONE_AFTER:
        count = brand_counts.get(brand, 0)
        if count:
            result.append({"id": brand, "label": brand, "count": count, "children": []})

    others_children = [
        {"id": member, "label": member, "count": brand_counts.get(member, 0), "children": []}
        for member in OTHERS_CHILDREN
        if brand_counts.get(member, 0) > 0
    ]
    others_count = sum(child["count"] for child in others_children) + brand_counts.get("Others", 0)
    if others_count:
        result.append({"id": "Others", "label": "Others", "count": others_count, "children": others_children})

    return result


@router.get("/issues")
def get_issues(days: int = Query(7, ge=1, le=90)):
    counts = _count_tags("issue_tags", days)
    return [
        {"id": key, "label": ISSUE_LABELS.get(key, key), "count": count}
        for key, count in sorted(counts.items(), key=lambda item: -item[1])
    ]
