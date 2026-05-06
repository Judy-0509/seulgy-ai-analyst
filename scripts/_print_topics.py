import json
from pathlib import Path

files = [
    ("scripts/_topic_suggestions.json", "SMARTPHONE"),
    ("scripts/_humanoid_topic_suggestions.json", "HUMANOID"),
    ("scripts/_automotive_topic_suggestions.json", "AUTOMOTIVE"),
]
ROOT = Path(__file__).parent.parent
for fname, label in files:
    p = ROOT / fname
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"=== {label} ({d['generated_at'][:10]}, {len(d['topics'])}개) ===")
    for i, t in enumerate(d["topics"], 1):
        print(f"  [{i}] [{t['criteria']}] {t['title']}")
    print()
