"""GLM API token usage logger.

data/token_usage.jsonl 에 한 줄씩 append.
thread-safe (sync/async 모두 사용 가능).
"""
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).parent.parent.parent
LOG_FILE = ROOT / "data" / "token_usage.jsonl"
LOCK_FILE = ROOT / "data" / "token_usage.lock"

_lock = Lock()

# ── 단가 (CNY / 1K tokens) ── 지푸AI 공식 가격 기준, 변경 시 여기만 수정
# https://open.bigmodel.cn/pricing
PRICING: dict[str, dict] = {
    "glm-4.7":       {"input": 0.007, "output": 0.028},
    "glm-4-flash":   {"input": 0.0001, "output": 0.0001},
    "glm-4-plus":    {"input": 0.01,  "output": 0.01},
    "glm-4":         {"input": 0.01,  "output": 0.01},
}


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def usage_counts(usage) -> tuple[int, int]:
    """Return prompt/completion token counts from OpenAI-compatible usage objects."""
    if usage is None:
        return 0, 0
    if isinstance(usage, dict):
        return (
            _as_int(usage.get("prompt_tokens", 0)),
            _as_int(usage.get("completion_tokens", 0)),
        )
    return (
        _as_int(getattr(usage, "prompt_tokens", 0)),
        _as_int(getattr(usage, "completion_tokens", 0)),
    )


def _price_for(model: str) -> dict:
    if model in PRICING:
        return PRICING[model]
    for prefix, price in PRICING.items():
        if model.startswith(prefix):
            return price
    return {"input": 0, "output": 0}


@contextmanager
def _process_file_lock():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with LOCK_FILE.open("a+b") as f:
            f.seek(0)
            if not f.read(1):
                f.write(b"0")
                f.flush()
            try:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def log_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    caller: str = "",
) -> dict:
    model = str(model or "unknown")
    prompt_tokens = _as_int(prompt_tokens)
    completion_tokens = _as_int(completion_tokens)
    price = _price_for(model)
    cost = (prompt_tokens * price["input"] + completion_tokens * price["output"]) / 1000
    entry = {
        "ts":                datetime.now().isoformat(),
        "model":             model,
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens":      prompt_tokens + completion_tokens,
        "cost_cny":          round(cost, 6),
        "caller":            caller,
    }
    with _process_file_lock():
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_all() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries
