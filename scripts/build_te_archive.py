"""Transport & Environment (T&E) 아카이브 빌더.

전략: sitemap_index → sub-sitemap 수집. EU 전동화·배출 advocacy NGO.
거의 모든 콘텐츠가 transport-related이지만 자동차 키워드 필터로 추가 정제.
"""
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _auto_research_helper import build_sitemap, ARCHIVE_DIR  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


async def main():
    await build_sitemap(
        source_name="Transport & Environment",
        site_base="https://www.transportenvironment.org",
        sitemap_url="https://www.transportenvironment.org/sitemap.xml",
        archive_path=ARCHIVE_DIR / "transport_environment.json",
        url_includes=["/discover/", "/news/", "/articles/", "/publications/", "/blog/"],
        url_excludes=["/about/", "/contact/", "/jobs/"],
        sub_include_keywords=None,
        require_auto_keyword=True,
        max_articles=300,
        concurrency=5,
        tier=2,
    )


if __name__ == "__main__":
    asyncio.run(main())
