"""body_cache 부분/전체 비우기.

사용:
  python -m scripts.clear_body_cache --all
  python -m scripts.clear_body_cache --url https://example.com/article
  python -m scripts.clear_body_cache --source "Morgan Stanley"

또는 (sys.path fallback 포함, 직접 호출):
  python scripts/clear_body_cache.py --all
"""
import argparse
import io
import sys
from pathlib import Path

# Direct invocation fallback (project root에서 호출 안 한 경우)
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services import body_cache  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    p = argparse.ArgumentParser(
        description="body_cache.db에서 항목을 삭제."
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="모든 항목 삭제")
    g.add_argument("--url", type=str, help="특정 URL 삭제")
    g.add_argument("--source", type=str, help="해당 source의 모든 항목 삭제")
    args = p.parse_args()

    if args.all:
        n = body_cache.clear()
    elif args.url:
        n = body_cache.clear(url=args.url)
    else:
        n = body_cache.clear(source=args.source)

    print(f"  → 삭제 {n}건")
    print(f"  → 현재 stats: {body_cache.stats()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
