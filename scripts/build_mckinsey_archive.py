"""McKinsey Auto/Mobility 아카이브 빌더.

전략: McKinsey sitemap.xml에서 자동차/모빌리티 URL 패턴 필터.
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
        source_name="McKinsey",
        site_base="https://www.mckinsey.com",
        sitemap_url="https://www.mckinsey.com/sitemap.xml",
        archive_path=ARCHIVE_DIR / "mckinsey.json",
        url_includes=[
            "/industries/automotive-and-assembly/",
            "/featured-insights/future-mobility/",
            "/industries/oil-and-gas/our-insights/",
        ],
        url_excludes=["/careers/", "/about-us/", "/contact-us/"],
        require_auto_keyword=True,
        max_articles=300,
        concurrency=5,
        tier=1,
    )


if __name__ == "__main__":
    asyncio.run(main())
