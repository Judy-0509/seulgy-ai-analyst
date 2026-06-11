"""Rokid (global.rokid.com) 아카이브 빌더 (smartglass) — Shopify blogs sitemap.
벤더 PR 100% smartglass → 키워드 필터 OFF. published_time 메타 없음 → sitemap lastmod 사용.
실행: python scripts/build_rokid_archive.py
산출: data/archives/rokid.json
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _smartglass_research_helper import build_sitemap_archive  # noqa: E402

if __name__ == "__main__":
    asyncio.run(build_sitemap_archive(
        source_name="Rokid",
        site_base="https://global.rokid.com",
        archive_filename="rokid.json",
        sitemaps=["https://global.rokid.com/sitemap_blogs_1.xml"],
        url_include_re=r"global\.rokid\.com/blogs/news/",  # 로케일 중복(/ja/ 등) 배제
        apply_keyword_filter=False,
        tier=3,
    ))
