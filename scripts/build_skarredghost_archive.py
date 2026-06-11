"""The Ghost Howls (skarredghost.com) 아카이브 빌더 (smartglass) — Yoast sitemap.
실행: python scripts/build_skarredghost_archive.py
산출: data/archives/skarredghost.json
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _smartglass_research_helper import build_sitemap_archive  # noqa: E402

if __name__ == "__main__":
    asyncio.run(build_sitemap_archive(
        source_name="The Ghost Howls",
        site_base="https://skarredghost.com",
        archive_filename="skarredghost.json",
        sitemap_index="https://skarredghost.com/sitemap_index.xml",
        sub_include="post-sitemap",
        tier=2,
    ))
