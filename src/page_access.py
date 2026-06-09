"""Page-level access control store.

Persists to data/page_access.json.  All writes are atomic read-modify-write.
Reads never create or touch the file (side-effect-free).

Shape:
    {
        "grants":   {"<email>": ["db", "keywords"]},
        "requests": [{"email", "page", "status": "pending"|"approved", "ts"}]
    }
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

VALID_PAGES: frozenset[str] = frozenset({"db", "keywords"})

# Module-level path so tests can monkeypatch: monkeypatch.setattr("src.page_access.STORE_PATH", ...)
STORE_PATH: Path = Path(__file__).parent.parent / "data" / "page_access.json"

_EMPTY: dict = {"grants": {}, "requests": []}


def _load() -> dict:
    """Return the store contents.  Returns empty defaults if file is missing — never writes."""
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"grants": {}, "requests": []}
    except Exception:
        return {"grants": {}, "requests": []}


def _save(data: dict) -> None:
    """Persist store to disk, creating the file if needed."""
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Public API ────────────────────────────────────────────────────────────────

def has_access(email: str, page: str) -> bool:
    """Return True if email has been granted access to page."""
    email = email.strip().lower()
    data = _load()
    return page in data.get("grants", {}).get(email, [])


def granted_pages(email: str) -> list[str]:
    """Return the list of pages granted to email."""
    email = email.strip().lower()
    data = _load()
    return list(data.get("grants", {}).get(email, []))


def request_access(email: str, page: str) -> None:
    """Record an access request.  No-op if already pending or granted."""
    if page not in VALID_PAGES:
        raise ValueError(f"Invalid page: {page!r}. Must be one of {sorted(VALID_PAGES)}")
    email = email.strip().lower()
    data = _load()

    # Already granted → no-op
    if page in data.get("grants", {}).get(email, []):
        return

    # Already has a pending request → no-op
    for req in data.get("requests", []):
        if req.get("email") == email and req.get("page") == page and req.get("status") == "pending":
            return

    data.setdefault("requests", []).append({
        "email": email,
        "page": page,
        "status": "pending",
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    _save(data)


def list_requests(status: str = "pending") -> list[dict]:
    """Return all requests matching status."""
    data = _load()
    return [r for r in data.get("requests", []) if r.get("status") == status]


def approve(email: str, page: str) -> None:
    """Grant page access to email and mark any matching pending request approved."""
    if page not in VALID_PAGES:
        raise ValueError(f"Invalid page: {page!r}. Must be one of {sorted(VALID_PAGES)}")
    email = email.strip().lower()
    data = _load()

    # Add to grants
    grants = data.setdefault("grants", {})
    pages_list = grants.setdefault(email, [])
    if page not in pages_list:
        pages_list.append(page)

    # Mark any pending request as approved
    for req in data.get("requests", []):
        if req.get("email") == email and req.get("page") == page and req.get("status") == "pending":
            req["status"] = "approved"

    _save(data)
