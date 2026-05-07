"""BCG (Boston Consulting Group) Auto/Mobility 아카이브 빌더.

전략: BCG sitemap_index.xml → sub-sitemap → /industries/automotive/ URL 필터.
2026년 발행 + 자동차 키워드 통과만 보존.
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
        source_name="BCG",
        site_base="https://www.bcg.com",
        sitemap_url="https://www.bcg.com/sitemap.xml",
        archive_path=ARCHIVE_DIR / "bcg.json",
        url_includes=["/industries/automotive", "/industries/mobility"],
        url_excludes=["/careers/", "/about/"],
        sub_include_keywords=None,  # all sub-sitemaps; URL filter does the work
        require_auto_keyword=True,
        max_articles=300,
        concurrency=5,
        tier=1,
    )


if __name__ == "__main__":
    asyncio.run(main())
