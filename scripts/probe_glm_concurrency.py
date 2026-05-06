"""GLM-4.7 동시성 상한 실측 프로브.

전략:
  - 동일 API 키로 N개 동시 요청을 발사
  - 각 요청은 최소 토큰 (max_tokens=8) 으로 TPM 영향 최소화
  - 429 / 1302 / rate / concurrent 에러를 카운트
  - N을 1, 2, 4, 8, 16, 24, 32 단계로 증가시키며 임계점 탐색

사용:
  python scripts/probe_glm_concurrency.py
  python scripts/probe_glm_concurrency.py --steps 1,2,4,8,16,32,48
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# .env 로드
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("ZHIPU_API_KEY")
if not API_KEY:
    print("ERR: ZHIPU_API_KEY not set")
    sys.exit(1)

URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4.7"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
PAYLOAD = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "say 'hi'"}],
    "max_tokens": 8,
    "temperature": 0,
}


async def one_call(client: httpx.AsyncClient, idx: int) -> dict:
    t0 = time.time()
    try:
        r = await client.post(URL, json=PAYLOAD, timeout=120)
        elapsed = round(time.time() - t0, 2)
        body = r.text[:200]
        return {
            "idx": idx,
            "status": r.status_code,
            "elapsed": elapsed,
            "ok": r.status_code == 200,
            "body": body,
        }
    except Exception as e:
        return {
            "idx": idx,
            "status": 0,
            "elapsed": round(time.time() - t0, 2),
            "ok": False,
            "body": f"{type(e).__name__}: {e}",
        }


def classify(result: dict) -> str:
    if result["ok"]:
        return "ok"
    body = result["body"].lower()
    if "1302" in body or "rate" in body or "concurrent" in body or "frequent" in body:
        return "rate_limited"
    if result["status"] == 429:
        return "rate_limited"
    if result["status"] in (502, 503, 504):
        return "server_error"
    return "other_error"


async def probe(n: int) -> dict:
    print(f"\n=== N={n} 동시 요청 ===")
    t0 = time.time()
    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [one_call(client, i) for i in range(n)]
        results = await asyncio.gather(*tasks)
    total = round(time.time() - t0, 2)

    counts = {"ok": 0, "rate_limited": 0, "server_error": 0, "other_error": 0}
    statuses: dict[int, int] = {}
    elapsed_ok: list[float] = []
    sample_errs: list[str] = []
    for r in results:
        c = classify(r)
        counts[c] += 1
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        if r["ok"]:
            elapsed_ok.append(r["elapsed"])
        elif len(sample_errs) < 2:
            sample_errs.append(f"  err[{r['idx']}] status={r['status']} elapsed={r['elapsed']}s body={r['body'][:140]}")

    avg_ok = round(sum(elapsed_ok) / len(elapsed_ok), 2) if elapsed_ok else 0
    print(f"  total wall: {total}s | per-request avg(ok): {avg_ok}s")
    print(f"  status 분포: {statuses}")
    print(f"  분류: {counts}")
    if sample_errs:
        print("  에러 샘플:")
        for e in sample_errs:
            print(e)

    return {
        "n": n,
        "wall": total,
        "avg_ok": avg_ok,
        "counts": counts,
        "statuses": statuses,
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", default="1,2,4,8,16,24,32",
                        help="comma-separated concurrency levels to test")
    parser.add_argument("--cooldown", type=int, default=15,
                        help="seconds to wait between probes (rate-limit recovery)")
    args = parser.parse_args()

    levels = [int(s) for s in args.steps.split(",") if s.strip()]
    print(f"=== GLM-4.7 동시성 프로브 ===")
    print(f"  API key: {API_KEY[:10]}...{API_KEY[-4:]}")
    print(f"  steps: {levels}, cooldown: {args.cooldown}s")

    summary = []
    for n in levels:
        r = await probe(n)
        summary.append(r)
        # 다음 단계 전에 쿨다운 (rate window 회복)
        if n != levels[-1]:
            print(f"  쿨다운 {args.cooldown}s ...")
            await asyncio.sleep(args.cooldown)

    print("\n" + "=" * 60)
    print("  요약")
    print("=" * 60)
    print(f"{'N':>4} | {'ok':>3} | {'rate':>4} | {'srv_err':>7} | {'other':>5} | wall(s) | avg_ok(s)")
    print("-" * 60)
    for r in summary:
        c = r["counts"]
        print(f"{r['n']:>4} | {c['ok']:>3} | {c['rate_limited']:>4} | {c['server_error']:>7} | {c['other_error']:>5} | {r['wall']:>7} | {r['avg_ok']:>9}")

    # 최대 안전 동시성 추정
    safe = [r["n"] for r in summary if r["counts"]["rate_limited"] == 0 and r["counts"]["ok"] == r["n"]]
    if safe:
        print(f"\n  → 100% 성공 최대값: {max(safe)} (이 값 이하로 GLM_47_CONCURRENCY 권장)")
    else:
        print(f"\n  → 모든 단계에서 일부 실패 — 결과를 보고 수동 판단")


if __name__ == "__main__":
    asyncio.run(main())
