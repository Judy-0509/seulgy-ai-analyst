"""주제 추천 JSON에 등록된 모든 토픽에 대해 run_report.py --auto 일괄 실행.

GLM 동시성 제약(2개)을 고려해 순차 실행. 각 토픽 평균 10~15분.
이미 동일 slug 레포트(.md)가 있는 경우 스킵.

사용:
  python scripts/_batch_generate_reports.py                          # 메이저 + emerging 둘 다
  python scripts/_batch_generate_reports.py --source major           # 메이저만
  python scripts/_batch_generate_reports.py --source emerging        # emerging만
  python scripts/_batch_generate_reports.py --file scripts/foo.json  # 특정 파일
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
SUGG_MAJOR    = ROOT / "scripts" / "_topic_suggestions.json"
SUGG_EMERGING = ROOT / "scripts" / "_topic_suggestions_emerging.json"
REPORTS = ROOT / "reports"


def slug(topic: str) -> str:
    s = re.sub(r"\s+", "_", topic.strip())
    s = re.sub(r"[^\w가-힣]", "_", s)
    return s.strip("_")[:60]


def _load_titles(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return [t["title"] for t in d.get("topics", []) if t.get("title")]
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["major", "emerging", "all"], default="all")
    parser.add_argument("--file",   help="특정 JSON 파일 직접 지정 (override)")
    args = parser.parse_args()

    if args.file:
        topics = _load_titles(Path(args.file))
        label = Path(args.file).name
    elif args.source == "major":
        topics = _load_titles(SUGG_MAJOR)
        label = "major"
    elif args.source == "emerging":
        topics = _load_titles(SUGG_EMERGING)
        label = "emerging"
    else:
        topics = _load_titles(SUGG_MAJOR) + _load_titles(SUGG_EMERGING)
        label = "major + emerging"

    if not topics:
        print(f"no topics found for source={args.source}")
        sys.exit(1)

    print("=" * 70)
    print(f"  Batch report generation [{label}] — {len(topics)} topics")
    print(f"  started: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 70)

    skipped = 0
    succeeded = 0
    failed = 0
    for i, title in enumerate(topics, 1):
        s = slug(title)
        md = REPORTS / f"{s}_report.md"
        print(f"\n[{i}/{len(topics)}] {title}")
        if md.exists():
            print(f"  → SKIP (exists: {md.name})")
            skipped += 1
            continue

        t0 = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, "run_report.py", "--auto", title],
                cwd=str(ROOT),
                timeout=1800,  # 30 min hard cap per report
                capture_output=False,
            )
            elapsed = time.time() - t0
            ok = proc.returncode == 0 and md.exists()
            print(f"  → exit={proc.returncode}  elapsed={elapsed:.1f}s  md_exists={md.exists()}")
            if ok:
                succeeded += 1
            else:
                failed += 1
        except subprocess.TimeoutExpired:
            print("  → TIMEOUT after 1800s")
            failed += 1
        except Exception as e:
            print(f"  → ERROR: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"  Done. ok={succeeded}  skipped={skipped}  failed={failed}")
    print(f"  finished: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
