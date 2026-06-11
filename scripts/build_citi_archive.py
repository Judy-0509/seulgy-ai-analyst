"""Citi Insights 아카이브 빌더 (smartglass) — IB 리서치 무료 요약.
/global/sitemap.xml → /global/insights/ prefix 필터. 날짜는 __NEXT_DATA__ publishDate.
WAF 주의 → concurrency=2 보수적 페이싱.
실행: python scripts/build_citi_archive.py
산출: data/archives/citi.json
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _smartglass_research_helper import build_sitemap_archive  # noqa: E402

if __name__ == "__main__":
    asyncio.run(build_sitemap_archive(
        source_name="Citi Research",
        site_base="https://www.citigroup.com",
        archive_filename="citi.json",
        sitemaps=["https://www.citigroup.com/global/sitemap.xml"],
        url_include_re=r"citigroup\.com/global/insights/",
        date_from_nextdata=True,
        concurrency=2,
        tier=1,
    ))
