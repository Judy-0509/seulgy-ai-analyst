"""RSS feed collector — fetches all RSS_SOURCES from config and inserts into DB.

Uses feedparser for parsing. No keyword filtering (sources are curated).
Detects language from source name heuristic (Korean sources → 'ko').
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser

from src.config import RSS_SOURCES, SOURCE_TIER_MAP
from src.news_db import get_connection, insert_article

logger = logging.getLogger(__name__)

_KO_SOURCE_NAMES = {"thelec", "digitimes"}  # partial match for Korean/Asia sources that publish in KR context

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SparkBot/1.0; +https://github.com/spark)",
}


def _detect_language(source_name: str) -> str:
    """Heuristically detect language from source name."""
    name_lower = source_name.lower()
    if any(k in name_lower for k in ("korea", "한국", "thelec")):
        return "ko"
    return "en"


def _parse_date(date_str: str) -> Optional[str]:
    """Parse an RSS date string and return ISO 8601 UTC string, or None."""
    if not date_str:
        return None
    # RFC 2822
    try:
        dt = parsedate_to_datetime(date_str.strip())
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    # ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:19], fmt[:len(fmt)])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    return None


def _get_source_tier(source_name: str, source_url: str) -> int:
    """Look up tier from SOURCE_TIER_MAP by domain fragment."""
    from urllib.parse import urlparse
    try:
        domain = urlparse(source_url).netloc.lower().lstrip("www.")
    except Exception:
        domain = ""
    for key, tier in SOURCE_TIER_MAP.items():
        if key in domain:
            return tier
    return 3


def _fetch_feed(source: dict) -> tuple[int, int]:
    """Fetch one RSS source and insert into DB. Returns (inserted, skipped)."""
    name = source["name"]
    url = source["url"]
    tier = source.get("tier", 3)
    lang = _detect_language(name)

    inserted = skipped = 0
    try:
        # Build feedparser with User-Agent
        feed = feedparser.parse(url, agent=HEADERS["User-Agent"], request_headers=HEADERS)

        if feed.bozo and not feed.entries:
            logger.warning(f"RSS parse error [{name}]: {feed.bozo_exception}")
            return 0, 0

        conn = get_connection()
        for entry in feed.entries:
            title = (getattr(entry, "title", "") or "").strip()
            link = (getattr(entry, "link", "") or "").strip()
            if not title or not link:
                continue

            # Description: prefer summary, fall back to content
            description = ""
            if hasattr(entry, "summary") and entry.summary:
                description = re.sub(r"<[^>]+>", "", entry.summary).strip()
            elif hasattr(entry, "content") and entry.content:
                description = re.sub(r"<[^>]+>", "", entry.content[0].get("value", "")).strip()

            # Published date
            pub_str = None
            for attr in ("published", "updated", "created"):
                val = getattr(entry, attr, None)
                if val:
                    pub_str = _parse_date(val)
                    if pub_str:
                        break

            article = {
                "title": title,
                "description": description[:500] if description else None,
                "url": link,
                "source_name": name,
                "source_type": "rss",
                "language": lang,
                "published_at": pub_str,
                "keywords": None,
                "source_tier": tier,
            }

            if insert_article(conn, article):
                inserted += 1
            else:
                skipped += 1

    except Exception as e:
        logger.warning(f"RSS feed error [{name} | {url}]: {e}")

    return inserted, skipped


def fetch_rss_feeds() -> tuple[int, int]:
    """Collect all RSS_SOURCES. Returns (total_inserted, total_skipped)."""
    total_inserted = total_skipped = 0
    for source in RSS_SOURCES:
        ins, skp = _fetch_feed(source)
        total_inserted += ins
        total_skipped += skp
        if ins or skp:
            logger.debug(f"[{source['name']}] +{ins} inserted, {skp} skipped")
    logger.info(f"RSS collection done: +{total_inserted} inserted, {total_skipped} skipped")
    return total_inserted, total_skipped
