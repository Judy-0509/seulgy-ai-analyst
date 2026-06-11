"""AR Insider 아카이브 빌더 (smartglass) — Yoast sitemap.
robots.txt에 Crawl-delay: 10 명시 → delay_sec=10, 직렬 fetch.
실행: python scripts/build_arinsider_archive.py
산출: data/archives/arinsider.json
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _smartglass_research_helper import build_sitemap_archive  # noqa: E402

if __name__ == "__main__":
    asyncio.run(build_sitemap_archive(
        source_name="AR Insider",
        site_base="https://arinsider.co",
        archive_filename="arinsider.json",
        sitemap_index="https://arinsider.co/sitemap_index.xml",
        sub_include="post-sitemap",
        delay_sec=10.0,
        tier=2,
    ))
