"""Road to VR 아카이브 빌더 (smartglass) — Yoast sitemap (post 1-12).
실행: python scripts/build_roadtovr_archive.py
산출: data/archives/roadtovr.json
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _smartglass_research_helper import build_sitemap_archive  # noqa: E402

if __name__ == "__main__":
    asyncio.run(build_sitemap_archive(
        source_name="Road to VR",
        site_base="https://www.roadtovr.com",
        archive_filename="roadtovr.json",
        sitemap_index="https://www.roadtovr.com/sitemap_index.xml",
        sub_include="post-sitemap",
        tier=2,
    ))
