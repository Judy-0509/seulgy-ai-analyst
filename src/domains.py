"""Domain config loader — one JSON per domain in data/domains/."""
import json
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_DOMAINS_DIR = _ROOT / "data" / "domains"


@lru_cache(maxsize=8)
def load_domain(domain_id: str = "smartphone") -> dict:
    path = _DOMAINS_DIR / f"{domain_id}.json"
    if not path.exists():
        path = _DOMAINS_DIR / "smartphone.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    kw_path = _ROOT / cfg["keywords_file"]
    cfg["keywords"] = json.loads(kw_path.read_text(encoding="utf-8")).get("keywords", []) if kw_path.exists() else []
    return cfg


def list_domains() -> list[dict]:
    out = []
    for p in sorted(_DOMAINS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": d["id"], "label": d["label"], "icon": d.get("icon", ""), "theme": d.get("theme", {})})
        except Exception:
            continue
    return out
