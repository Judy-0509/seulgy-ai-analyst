"""스마트폰 추천 주제 배치 레포트 생성.

suggest_smartphone_topics.py 결과를 읽어 각 주제별 레포트를 순차 생성.
GLM rate limit 방지를 위해 레포트 사이에 DELAY_BETWEEN 초 대기.

사용법:
  uv run python scripts/batch_report_gen.py
  uv run python scripts/batch_report_gen.py --domain humanoid
  uv run python scripts/batch_report_gen.py --delay 90
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
REPORTS_DIR = ROOT / "reports"

DOMAIN_TOPIC_FILES = {
    "smartphone":      "scripts/_topic_suggestions.json",
    "humanoid":        "scripts/_humanoid_topic_suggestions.json",
    "automotive":      "scripts/_automotive_topic_suggestions.json",
    "space_datacenter":"scripts/_space_datacenter_topic_suggestions.json",
    "smartglass":      "scripts/_smartglass_topic_suggestions.json",
}

DOMAIN_EMERGING_FILES = {
    "smartphone":      "scripts/_topic_suggestions_emerging.json",
    "humanoid":        "scripts/_humanoid_topic_suggestions_emerging.json",
    "automotive":      "scripts/_automotive_topic_suggestions_emerging.json",
    "space_datacenter":"scripts/_space_datacenter_topic_suggestions_emerging.json",
    "smartglass":      "scripts/_smartglass_topic_suggestions_emerging.json",
}


def _slug(topic: str) -> str:
    slug = re.sub(r"\s+", "_", topic.strip())
    slug = re.sub(r"[^\w가-힣]", "_", slug)
    return slug.strip("_")[:60]


def report_exists(topic: str) -> bool:
    return (REPORTS_DIR / f"{_slug(topic)}_report.md").exists()


def generate_report(topic: str, domain: str = "smartphone") -> bool:
    """run_report.py --auto 로 레포트 생성. 성공 여부 반환."""
    print(f"\n{'='*60}")
    print(f"  주제: {topic}")
    print(f"  슬러그: {_slug(topic)}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, str(ROOT / "run_report.py"), "--auto", "--domain", domain, topic],
        cwd=str(ROOT),
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="smartphone", choices=list(DOMAIN_TOPIC_FILES))
    parser.add_argument("--delay",  type=int, default=60, help="레포트 생성 간격(초)")
    parser.add_argument("--skip-existing", action="store_true", default=True)
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    parser.add_argument("--include-emerging", action="store_true", default=False,
                        help="이번 주 새롭게 등장한 주제(emerging) 포함 — 메이저 주제는 제외하고 emerging만 생성")
    args = parser.parse_args()

    if args.include_emerging:
        # emerging 파일에서 Crit 3 주제만 로드
        emerging_file = ROOT / DOMAIN_EMERGING_FILES[args.domain]
        if not emerging_file.exists():
            print(f"[!] Emerging 파일 없음: {emerging_file}")
            sys.exit(1)
        data = json.loads(emerging_file.read_text(encoding="utf-8"))
        topics = [t.get("title", "").strip() for t in data.get("topics", []) if t.get("title")]
    else:
        topics_file = ROOT / DOMAIN_TOPIC_FILES[args.domain]
        if not topics_file.exists():
            print(f"[!] 주제 파일 없음: {topics_file}")
            print("    suggest 스크립트를 먼저 실행하세요.")
            sys.exit(1)
        data = json.loads(topics_file.read_text(encoding="utf-8"))
        topics = [
            t.get("title", "").strip()
            for t in data.get("topics", [])
            if t.get("title")
        ]

    if not topics:
        print("[!] 추천 주제가 없습니다.")
        sys.exit(1)

    print(f"\n[배치 레포트 생성] 도메인: {args.domain}, 총 {len(topics)}개 주제")
    print(f"  레포트 간격: {args.delay}초\n")

    results = {"ok": [], "skip": [], "fail": []}

    for i, topic in enumerate(topics, 1):
        print(f"\n[{i}/{len(topics)}] {topic}")

        if args.skip_existing and report_exists(topic):
            print("  → 이미 생성됨, 건너뜀")
            results["skip"].append(topic)
            continue

        ok = generate_report(topic, domain=args.domain)
        if ok:
            results["ok"].append(topic)
            print(f"  → 완료: {_slug(topic)}_report.md")
        else:
            results["fail"].append(topic)
            print("  → 실패")

        if i < len(topics):
            print(f"\n  [대기] 다음 주제까지 {args.delay}초 대기 중...")
            time.sleep(args.delay)

    print(f"\n{'='*60}")
    print(f"  완료: {len(results['ok'])}개 | 건너뜀: {len(results['skip'])}개 | 실패: {len(results['fail'])}개")
    if results["fail"]:
        print("  실패 목록:")
        for t in results["fail"]:
            print(f"    - {t}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
