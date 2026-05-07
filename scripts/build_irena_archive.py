"""IRENA (International Renewable Energy Agency) Transport 아카이브 빌더.

전략: sitemap.xml에서 Transport·Mobility URL 필터 + 자동차 키워드.
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
        source_name="IRENA",
        site_base="https://www.irena.org",
        sitemap_url="https://www.irena.org/sitemap.xml",
        archive_path=ARCHIVE_DIR / "irena.json",
        url_includes=["/Transport", "/transport", "/mobility", "/Mobility",
                      "/news/", "/News/", "/publications/", "/Publications/"],
        url_excludes=["/About", "/Contact"],
        require_auto_keyword=True,
        max_articles=300,
        concurrency=5,
        tier=1,
    )


if __name__ == "__main__":
    asyncio.run(main())
