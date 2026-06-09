import json
import threading
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).parent.parent
ROLES_PATH = ROOT / "data" / "roles.json"
_LOCK = threading.Lock()
_INITIAL_STATE = {"team": [], "requests": []}


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _ensure_file() -> None:
    ROLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ROLES_PATH.exists():
        ROLES_PATH.write_text(json.dumps(_INITIAL_STATE, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_state() -> dict:
    _ensure_file()
    try:
        data = json.loads(ROLES_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = dict(_INITIAL_STATE)
    return {
        "team": [
            {
                "email": _normalize_email(item.get("email", "")),
                "name": item.get("name", ""),
                "added_at": item.get("added_at", ""),
            }
            for item in data.get("team", [])
            if isinstance(item, dict) and _normalize_email(item.get("email", ""))
        ],
        "requests": [
            {
                "email": _normalize_email(item.get("email", "")),
                "name": item.get("name", ""),
                "status": item.get("status", "pending"),
                "ts": item.get("ts", ""),
            }
            for item in data.get("requests", [])
            if isinstance(item, dict) and _normalize_email(item.get("email", ""))
        ],
    }


def _write_state(data: dict) -> None:
    ROLES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_team(email: str) -> bool:
    email = _normalize_email(email)
    if not email:
        return False
    with _LOCK:
        return any(item["email"] == email for item in _read_state()["team"])


def is_requested(email: str) -> bool:
    email = _normalize_email(email)
    if not email:
        return False
    with _LOCK:
        return any(r["email"] == email and r["status"] == "pending" for r in _read_state()["requests"])


def add_team(email: str, name: str = "") -> str:
    email = _normalize_email(email)
    if not email:
        return "exists"
    with _LOCK:
        data = _read_state()
        for r in data["requests"]:
            if r["email"] == email and r["status"] == "pending":
                r["status"] = "approved"
        if any(item["email"] == email for item in data["team"]):
            _write_state(data)
            return "exists"
        data["team"].append({
            "email": email,
            "name": name or "",
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        _write_state(data)
        return "added"


def remove_team(email: str) -> bool:
    email = _normalize_email(email)
    with _LOCK:
        data = _read_state()
        before = len(data["team"])
        data["team"] = [item for item in data["team"] if item["email"] != email]
        if len(data["team"]) == before:
            return False
        _write_state(data)
        return True


def list_team() -> list[dict]:
    with _LOCK:
        return list(_read_state()["team"])


def request_team(email: str, name: str = "") -> str:
    """Record an analyst-access request. 'team' if already analyst, else 'requested'."""
    email = _normalize_email(email)
    if not email:
        return "requested"
    with _LOCK:
        data = _read_state()
        if any(item["email"] == email for item in data["team"]):
            return "team"
        for r in data["requests"]:
            if r["email"] == email and r["status"] == "pending":
                return "requested"
        data["requests"].append({
            "email": email,
            "name": name or "",
            "status": "pending",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        _write_state(data)
        return "requested"


def list_requests(status: str = "pending") -> list[dict]:
    with _LOCK:
        return [r for r in _read_state()["requests"] if r["status"] == status]


def approve_request(email: str) -> bool:
    email = _normalize_email(email)
    if not email:
        return False
    with _LOCK:
        data = _read_state()
        name = ""
        for r in data["requests"]:
            if r["email"] == email and r["status"] == "pending":
                r["status"] = "approved"
                name = r.get("name", "")
        if not any(item["email"] == email for item in data["team"]):
            data["team"].append({
                "email": email,
                "name": name,
                "added_at": datetime.now(timezone.utc).isoformat(),
            })
        _write_state(data)
        return True


def reject_request(email: str) -> bool:
    email = _normalize_email(email)
    with _LOCK:
        data = _read_state()
        found = False
        for r in data["requests"]:
            if r["email"] == email and r["status"] == "pending":
                r["status"] = "rejected"
                found = True
        if found:
            _write_state(data)
        return found


def role_of(user: dict) -> str:
    from src.auth import is_admin  # lazy to avoid circular import
    if is_admin(user):
        return "admin"
    email = _normalize_email(user.get("email") or "")
    if email and is_team(email):
        return "team"
    return "other"
