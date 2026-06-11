"""UploadVR 아카이브 빌더 (smartglass) — Ghost CMS sitemap-posts.xml.
실행: python scripts/build_uploadvr_archive.py
산출: data/archives/uploadvr.json
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _smartglass_research_helper import build_sitemap_archive  # noqa: E402

if __name__ == "__main__":
    asyncio.run(build_sitemap_archive(
        source_name="UploadVR",
        site_base="https://www.uploadvr.com",
        archive_filename="uploadvr.json",
        sitemaps=["https://www.uploadvr.com/sitemap-posts.xml"],
        tier=2,
    ))
