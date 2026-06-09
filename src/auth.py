from dotenv import load_dotenv
load_dotenv()

import os
import time

import httpx
from fastapi import HTTPException, Request


SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY")
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
}

_TOKEN_CACHE: dict[str, tuple[dict, float]] = {}
_TOKEN_CACHE_TTL_SECONDS = 60


async def verify_token(token: str) -> dict | None:
    try:
        now = time.time()
        cached = _TOKEN_CACHE.get(token)
        if cached:
            user, expiry = cached
            if expiry > now:
                return user
            _TOKEN_CACHE.pop(token, None)

        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {token}",
                },
            )
        if response.status_code != 200:
            return None
        user = response.json()
        _TOKEN_CACHE[token] = (user, now + _TOKEN_CACHE_TTL_SECONDS)
        return user
    except Exception:
        return None


def is_admin(user: dict) -> bool:
    email = (user.get("email") or "").lower()
    return email in ADMIN_EMAILS


async def require_member(request: Request) -> dict:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "로그인이 필요합니다")
    token = auth[7:].strip()
    user = await verify_token(token)
    if not user:
        raise HTTPException(401, "유효하지 않은 세션입니다")
    return user


async def require_admin_query(request: Request) -> dict:
    token = request.query_params.get("access_token")
    if not token:
        auth = request.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(401, "\ub85c\uadf8\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4")
    user = await verify_token(token)
    if not user:
        raise HTTPException(401, "\uc720\ud6a8\ud558\uc9c0 \uc54a\uc740 \uc138\uc158\uc785\ub2c8\ub2e4")
    if not is_admin(user):
        raise HTTPException(403, "\uad00\ub9ac\uc790 \uad8c\ud55c\uc774 \ud544\uc694\ud569\ub2c8\ub2e4")
    return user


async def require_admin(request: Request) -> dict:
    user = await require_member(request)
    if not is_admin(user):
        raise HTTPException(403, "관리자 권한이 필요합니다")
    return user


def require_page_access(page: str):
    """Factory: returns an async FastAPI dependency that allows admins and
    users who have been granted access to *page* via page_access.approve()."""
    async def _dep(request: Request) -> dict:
        user = await require_member(request)
        if is_admin(user):
            return user
        import src.page_access as _pa  # lazy to avoid cycles
        if _pa.has_access(user.get("email") or "", page):
            return user
        raise HTTPException(403, "이 페이지는 권한이 필요합니다")
    return _dep
