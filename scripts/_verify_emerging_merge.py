"""api_topics_suggested 응답 시뮬레이션 — emerging merge 검증."""
import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.server import api_topics_suggested  # noqa: E402

async def run():
    resp = await api_topics_suggested(domain="smartphone")
    topics = resp["topics"]
    major = [t for t in topics if "Criterion 2" in str(t.get("criteria", ""))]
    emerg = [t for t in topics if str(t.get("criteria", "")) == "Criterion 3"]
    print(f"total: {len(topics)}  major(Crit2/2+3): {len(major)}  emerging(Crit3): {len(emerg)}")
    print()
    print("-- MAJOR (이번주 핵심 주제 섹션) --")
    for t in major:
        slug = "[have report]" if t.get("report_slug") else "[no report]"
        print(f"  {slug} {t['title'][:60]}  [{t.get('criteria')}]")
    print()
    print("-- EMERGING (이번주 새롭게 등장한 주제 섹션) --")
    for t in emerg:
        slug = "[have report]" if t.get("report_slug") else "[no report]"
        pat = t.get("pattern", "?")
        print(f"  {slug} {t['title'][:60]}  pattern={pat}")

asyncio.run(run())
