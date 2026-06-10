"""기존 보고서에 EN 요약 사이드카(`{slug}.en.json`)를 백필.

핵심요약 + 제목만 glm-4.7로 번역(본문 제외). 멱등 — 이미 사이드카가 있으면 건너뜀.
유료 LLM 호출이므로 비용 인지 후 실행할 것.

    python scripts/backfill_en_summary.py            # 사이드카 없는 것만
    python scripts/backfill_en_summary.py --limit 5  # 5건만 (시험)
    python scripts/backfill_en_summary.py --force     # 전부 재생성
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.en_summary import ensure_en_summary, load_en_summary  # noqa: E402
from src.services.llm import LLMService  # noqa: E402

REPORTS_DIR = ROOT / "reports"


def _parse_md(md: str) -> tuple[str, str]:
    """(topic, executive_summary) 추출 — _build_markdown 포맷 기준."""
    topic = ""
    lines = md.splitlines()
    for ln in lines:
        if ln.startswith("# ") and not ln.startswith("## "):
            topic = ln[2:].strip()
            break
    summary_lines: list[str] = []
    capturing = False
    for ln in lines:
        if ln.strip().lower() == "## executive summary":
            capturing = True
            continue
        if capturing:
            if ln.strip() == "---" or ln.startswith("## "):
                break
            summary_lines.append(ln)
    return topic, "\n".join(summary_lines).strip()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="최대 처리 건수 (0=무제한)")
    ap.add_argument("--force", action="store_true", help="기존 사이드카도 재생성")
    args = ap.parse_args()

    md_paths = sorted(REPORTS_DIR.glob("*_report.md"))
    llm = LLMService()
    done = skipped = failed = 0

    for md_path in md_paths:
        slug = md_path.name.removesuffix("_report.md")
        if not args.force and load_en_summary(REPORTS_DIR, slug):
            skipped += 1
            continue
        if args.limit and done >= args.limit:
            break
        topic, summary = _parse_md(md_path.read_text(encoding="utf-8"))
        if not summary:
            print(f"  [skip-empty] {slug}")
            skipped += 1
            continue
        try:
            data = await ensure_en_summary(
                REPORTS_DIR, slug, topic, summary, llm, force=args.force
            )
            ok = bool(data and data.get("executive_summary_en"))
            done += 1
            print(f"  [{'ok' if ok else 'empty'}] {slug}  →  {(data or {}).get('executive_summary_en','')[:60]}...")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  [FAIL] {slug}: {e}")

    print(f"\n완료: 생성 {done} · 건너뜀 {skipped} · 실패 {failed} (총 {len(md_paths)}건)")


if __name__ == "__main__":
    asyncio.run(main())
