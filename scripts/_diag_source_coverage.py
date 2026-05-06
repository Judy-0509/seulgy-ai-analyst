"""B 코드 사용 시 각 소스의 30일 윈도우 커버리지 진단.

각 소스에 대해:
  - archive 총 entry 수
  - 최근 30일 내 entry 수
  - 키워드 필터 통과 entry 수 (B가 LLM에 실제 입력하는 양)

UBI/CCS/Yole/TechInsights/Morgan Stanley가 B 결과에서 0번 인용된 원인 파악용.
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

REGISTRY = [
    ("Counterpoint Research", "counterpoint.json"),
    ("TrendForce",            "trendforce.json"),
    ("Omdia",                 "omdia.json"),
    ("IDC",                   "idc.json"),
    ("Morgan Stanley",        "morgan_stanley.json"),
    ("Yole",                  "yole.json"),
    ("DigiTimes Asia",        "digitimes.json"),
    ("TechInsights",          "techinsights.json"),
    ("UBI Research",          "ubi_research.json"),
    ("CCS Insight",           "ccs_insight.json"),
]

KW = json.loads((ROOT / "data" / "smartphone_keywords.json").read_text(encoding="utf-8"))["keywords"]
cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)

def keyword_match(entry):
    text = (entry.get("title", "") + " " + entry.get("description", "")).lower()
    return any(k in text for k in KW)

def parse_dt(lm):
    try:
        dt = datetime.fromisoformat(lm.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

print(f"{'Source':<25}{'total':>8}{'last30d':>10}{'kw_pass':>10}  sample title")
print("-" * 100)
for source, fname in REGISTRY:
    p = ROOT / "data" / "archives" / fname
    if not p.exists():
        print(f"{source:<25}  NOT FOUND")
        continue
    entries = json.loads(p.read_text(encoding="utf-8")).get("entries", [])
    total = len(entries)
    recent = [e for e in entries if (dt := parse_dt(e.get("lastmod", ""))) and dt >= cutoff]
    kw_pass = [e for e in recent if keyword_match(e)]
    sample = ""
    if kw_pass:
        sample = kw_pass[0].get("title", "")[:55]
    elif recent:
        sample = "(none kw-pass) " + recent[0].get("title", "")[:40]
    print(f"{source:<25}{total:>8}{len(recent):>10}{len(kw_pass):>10}  {sample}")
