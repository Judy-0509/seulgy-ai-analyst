"""scripts/clear_body_cache.py CLI 테스트 (AC #6).

subprocess 호출은 BODY_CACHE_DB env var로 isolation.
"""
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(tmp_path, args):
    """subprocess 환경변수로 BODY_CACHE_DB 격리."""
    env = {**os.environ, "BODY_CACHE_DB": str(tmp_path / "test.db")}
    return subprocess.run(
        [sys.executable, "-m", "scripts.clear_body_cache"] + args,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        encoding="utf-8",
        errors="replace",
    )


@pytest.fixture
def cache_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BODY_CACHE_DB", str(tmp_path / "test.db"))
    from src.services import body_cache
    importlib.reload(body_cache)
    yield body_cache


def test_cli_clear_all(cache_env, tmp_path):
    """--all: 모든 row 삭제."""
    cache_env.put_body("https://x/1", "a", "S", "ok", "httpx")
    cache_env.put_body("https://x/2", "b", "S", "ok", "httpx")
    assert cache_env.stats()["total"] == 2

    result = _run_cli(tmp_path, ["--all"])
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "삭제 2건" in result.stdout

    # parent reload to verify
    from src.services import body_cache
    importlib.reload(body_cache)
    assert body_cache.stats()["total"] == 0


def test_cli_clear_url(cache_env, tmp_path):
    """--url: 특정 URL만 삭제."""
    cache_env.put_body("https://x/1", "a", "S", "ok", "httpx")
    cache_env.put_body("https://x/2", "b", "S", "ok", "httpx")

    result = _run_cli(tmp_path, ["--url", "https://x/1"])
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "삭제 1건" in result.stdout

    from src.services import body_cache
    importlib.reload(body_cache)
    assert body_cache.stats()["total"] == 1


def test_cli_clear_source(cache_env, tmp_path):
    """--source: source별 삭제."""
    cache_env.put_body("https://a/1", "a", "SrcA", "ok", "httpx")
    cache_env.put_body("https://a/2", "a2", "SrcA", "ok", "httpx")
    cache_env.put_body("https://b/1", "b", "SrcB", "ok", "httpx")

    result = _run_cli(tmp_path, ["--source", "SrcA"])
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "삭제 2건" in result.stdout

    from src.services import body_cache
    importlib.reload(body_cache)
    assert body_cache.stats()["total"] == 1


def test_cli_invalid_args_rejected(tmp_path):
    """인자 없이 호출 시 argparse error."""
    result = _run_cli(tmp_path, [])
    assert result.returncode != 0


def test_cli_mutually_exclusive(tmp_path):
    """--all 과 --url 동시 사용 시 에러."""
    result = _run_cli(tmp_path, ["--all", "--url", "https://x"])
    assert result.returncode != 0
