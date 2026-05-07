"""BloombergNEF (BNEF) 무료 블로그 아카이브 빌더.

전략: about.bnef.com/feed/ RSS — 자동차 키워드 통과 + 2026년만.
"""
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _auto_research_helper import build_rss_only, ARCHIVE_DIR  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


async def main():
    await build_rss_only(
        source_name="BloombergNEF",
        site_base="https://about.bnef.com",
        rss_url="https://about.bnef.com/feed/",
        archive_path=ARCHIVE_DIR / "bnef.json",
        require_auto_keyword=True,
        tier=1,
    )


if __name__ == "__main__":
    asyncio.run(main())
