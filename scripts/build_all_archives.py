"""
9개 archive 빌더를 순차 실행하는 오케스트레이터.

각 빌더는 자체 incremental 로직을 갖고 있어서, 기존 JSON에 없는 URL만 새로 fetch한다.
즉 이 스크립트를 다시 돌릴수록 DB가 누적된다.

stdout으로 줄 단위 JSON 이벤트를 흘려보냄 → FastAPI SSE에서 그대로 사용 가능.

이벤트 종류:
  {"type":"start", "total":N, "ts":"..."}
  {"type":"builder_start", "idx":i, "name":..., "before":N}
  {"type":"builder_done",  "idx":i, "name":..., "ok":bool, "added":N, "elapsed_sec":S, "error":""}
  {"type":"complete", "summary":[...], "ts":"..."}

CLI 단독 실행:
  python scripts/build_all_archives.py
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT     = Path(__file__).parent.parent
SCRIPTS  = ROOT / "scripts"
ARCHIVES = ROOT / "data" / "archives"

# (UI 표시명, 빌더 스크립트, 산출 JSON 파일명)
BUILDERS = [
    ("Counterpoint Research", "build_counterpoint_archive.py",   "counterpoint.json"),
    ("TrendForce",            "build_trendforce_archive.py",     "trendforce.json"),
    ("Omdia",                 "build_omdia_archive.py",          "omdia.json"),
    ("IDC",                   "build_idc_archive.py",            "idc.json"),
    ("Reuters",               "build_reuters_archive.py",        "reuters.json"),
    ("Yole",                  "build_yole_archive.py",           "yole.json"),
    ("Gartner",               "build_gartner_archive.py",        "gartner.json"),
    ("Morgan Stanley",        "build_morgan_stanley_archive.py", "morgan_stanley.json"),
    ("Naver Research",        "build_naver_research_archive.py", "naver_research.json"),
]

PER_BUILDER_TIMEOUT_SEC = 900  # 빌더당 최대 15분


def emit(event: dict):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def count_entries(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        return len(json.loads(p.read_text(encoding="utf-8")).get("entries", []))
    except Exception:
        return 0


def run_builder(name: str, script: str, json_name: str, idx: int) -> dict:
    json_path = ARCHIVES / json_name
    before = count_entries(json_path)
    emit({"type": "builder_start", "idx": idx, "name": name, "before": before})

    t0 = time.time()
    ok = False
    err_tail = ""
    try:
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=PER_BUILDER_TIMEOUT_SEC,
            encoding="utf-8",
            errors="replace",
        )
        ok = (r.returncode == 0)
        if not ok:
            err_tail = (r.stderr or r.stdout or "")[-500:]
    except subprocess.TimeoutExpired:
        err_tail = f"TIMEOUT after {PER_BUILDER_TIMEOUT_SEC}s"
    except Exception as e:
        err_tail = f"{type(e).__name__}: {e}"

    after = count_entries(json_path)
    return {
        "type": "builder_done",
        "idx": idx,
        "name": name,
        "ok": ok,
        "before": before,
        "after": after,
        "added": max(0, after - before),
        "elapsed_sec": round(time.time() - t0, 1),
        "error": err_tail,
    }


def main():
    emit({"type": "start", "total": len(BUILDERS), "ts": datetime.now().isoformat()})
    summary = []
    for i, (name, script, json_name) in enumerate(BUILDERS, 1):
        result = run_builder(name, script, json_name, i)
        summary.append(result)
        emit(result)
    emit({
        "type": "complete",
        "summary": summary,
        "total_added": sum(s["added"] for s in summary),
        "succeeded":   sum(1 for s in summary if s["ok"]),
        "failed":      sum(1 for s in summary if not s["ok"]),
        "ts": datetime.now().isoformat(),
    })


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main()
