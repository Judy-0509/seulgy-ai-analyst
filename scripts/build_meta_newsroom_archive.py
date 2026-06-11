"""Meta Newsroom (about.fb.com) 아카이브 빌더 (smartglass).
전사 뉴스룸(통과율 5-10% 예상) — 키워드 필터 필수, /news/ 경로만 (로케일 제외).
실행: python scripts/build_meta_newsroom_archive.py
산출: data/archives/meta_newsroom.json
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _smartglass_research_helper import build_sitemap_archive  # noqa: E402

if __name__ == "__main__":
    asyncio.run(build_sitemap_archive(
        source_name="Meta Newsroom",
        site_base="https://about.fb.com",
        archive_filename="meta_newsroom.json",
        sitemap_index="https://about.fb.com/sitemap_index.xml",
        sub_include="post-sitemap",
        url_include_re=r"about\.fb\.com/news/",   # 로케일(/ja/news/ 등) 자동 배제
        tier=3,
    ))
