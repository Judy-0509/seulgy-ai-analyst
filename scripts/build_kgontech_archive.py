"""KGOnTech (kguttag.com) 아카이브 빌더 (smartglass) — 광학/디스플레이 심층분석.
월 1건 저빈도 — 주 1회 빌드면 충분.
실행: python scripts/build_kgontech_archive.py
산출: data/archives/kgontech.json
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _smartglass_research_helper import build_sitemap_archive  # noqa: E402

if __name__ == "__main__":
    asyncio.run(build_sitemap_archive(
        source_name="KGOnTech",
        site_base="https://kguttag.com",
        archive_filename="kgontech.json",
        sitemap_index="https://kguttag.com/sitemap.xml",
        tier=2,
    ))
