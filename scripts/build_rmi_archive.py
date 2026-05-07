"""RMI (Rocky Mountain Institute) 아카이브 빌더.

전략: rmi.org/feed/ RSS — 자동차 키워드 통과 + 2026년만.
미국 EV 충전·depot 전환·전동화 정책 분석.
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
        source_name="RMI",
        site_base="https://rmi.org",
        rss_url="https://rmi.org/feed/",
        archive_path=ARCHIVE_DIR / "rmi.json",
        require_auto_keyword=True,
        tier=2,
    )


if __name__ == "__main__":
    asyncio.run(main())
