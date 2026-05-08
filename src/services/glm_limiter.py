import asyncio
import os
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
LOCK_DIR = ROOT / "data" / "locks"

# ──────────────────────────────────────────────────────────────────────────
#  Zhipu 공식 concurrency 한도 (https://z.ai/manage-apikey/rate-limits)
#  각 모델별로 별도 limiter slot 운영 — 잘못 묶으면 capacity 손실.
# ──────────────────────────────────────────────────────────────────────────
GLM_47_CONCURRENCY        = int(os.getenv("GLM_47_CONCURRENCY",        "2"))   # GLM-4.7
GLM_FLASHX_CONCURRENCY    = int(os.getenv("GLM_FLASHX_CONCURRENCY",    "3"))   # GLM-4.7-FlashX
GLM_5_CONCURRENCY         = int(os.getenv("GLM_5_CONCURRENCY",         "2"))   # GLM-5
GLM_51_CONCURRENCY        = int(os.getenv("GLM_51_CONCURRENCY",       "10"))   # GLM-5.1 (높음)
GLM_5_TURBO_CONCURRENCY   = int(os.getenv("GLM_5_TURBO_CONCURRENCY",   "1"))   # GLM-5-Turbo (낮음)
GLM_45_AIR_CONCURRENCY    = int(os.getenv("GLM_45_AIR_CONCURRENCY",    "5"))   # GLM-4.5-Air
GLM_45_AIRX_CONCURRENCY   = int(os.getenv("GLM_45_AIRX_CONCURRENCY",   "5"))   # GLM-4.5-AirX
GLM_45_FLASH_CONCURRENCY  = int(os.getenv("GLM_45_FLASH_CONCURRENCY",  "2"))   # GLM-4.5-Flash
GLM_45_CONCURRENCY        = int(os.getenv("GLM_45_CONCURRENCY",       "10"))   # GLM-4.5
GLM_47_FLASH_CONCURRENCY  = int(os.getenv("GLM_47_FLASH_CONCURRENCY",  "1"))   # GLM-4.7-Flash
GLM_4_PLUS_CONCURRENCY    = int(os.getenv("GLM_4_PLUS_CONCURRENCY",   "20"))   # GLM-4-Plus
GLM_4_32B_CONCURRENCY     = int(os.getenv("GLM_4_32B_CONCURRENCY",    "15"))   # GLM-4-32B-0414-128K

# 알 수 없는 모델은 가장 보수적 기본값 사용
GLM_DEFAULT_CONCURRENCY = 1

# 모델 → (slot_prefix, concurrency) 명시적 매핑.
# Codex 권장: 문자열 substring 라우팅 대신 명시적 dict 사용.
MODEL_TO_SLOT: dict[str, tuple[str, int]] = {
    "glm-4.7":             ("glm-4.7",            GLM_47_CONCURRENCY),
    "glm-4.7-flashx":      ("glm-4.7-flashx",     GLM_FLASHX_CONCURRENCY),
    "glm-4.7-flash":       ("glm-4.7-flash",      GLM_47_FLASH_CONCURRENCY),
    "glm-5":               ("glm-5",              GLM_5_CONCURRENCY),
    "glm-5.1":             ("glm-5.1",            GLM_51_CONCURRENCY),
    "glm-5-turbo":         ("glm-5-turbo",        GLM_5_TURBO_CONCURRENCY),
    "glm-4.5":             ("glm-4.5",            GLM_45_CONCURRENCY),
    "glm-4.5-air":         ("glm-4.5-air",        GLM_45_AIR_CONCURRENCY),
    "glm-4.5-airx":        ("glm-4.5-airx",       GLM_45_AIRX_CONCURRENCY),
    "glm-4.5-flash":       ("glm-4.5-flash",      GLM_45_FLASH_CONCURRENCY),
    "glm-4-plus":          ("glm-4-plus",         GLM_4_PLUS_CONCURRENCY),
    "glm-4-32b-0414-128k": ("glm-4-32b",          GLM_4_32B_CONCURRENCY),
}


def slot_config_for(model: str) -> tuple[str, int]:
    """모델명 → (slot prefix, concurrency).

    명시되지 않은 모델은 보수적으로 (model_name, GLM_DEFAULT_CONCURRENCY=1) 반환.
    """
    if model in MODEL_TO_SLOT:
        return MODEL_TO_SLOT[model]
    return (model, GLM_DEFAULT_CONCURRENCY)


class _FileSlot:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None
        self._acquired = False  # acquire 성공 여부 — close 시 unlock 결정

    def try_acquire(self) -> bool:
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            self.handle.seek(0)
            if not self.handle.read(1):
                self.handle.write(b"0")
                self.handle.flush()
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._acquired = True
            return True
        except OSError:
            # acquire 실패 → unlock 시도하지 않고 handle 만 닫음 (msvcrt LK_UNLCK 가
            # 잡지 않은 영역에 호출되면 Errno 13 Permission denied 로 터짐).
            try:
                if self.handle is not None:
                    self.handle.close()
            except Exception:
                pass
            self.handle = None
            return False

    def close(self) -> None:
        if self.handle is None:
            return
        try:
            if self._acquired:
                if os.name == "nt":
                    import msvcrt
                    self.handle.seek(0)
                    try:
                        msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass  # already unlocked / handle invalid — 안전 무시
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            try:
                self.handle.close()
            except Exception:
                pass
            self.handle = None
            self._acquired = False


def _acquire_named_slot(prefix: str, concurrency: int) -> _FileSlot:
    while True:
        for idx in range(concurrency):
            slot = _FileSlot(LOCK_DIR / f"{prefix}-{idx}.lock")
            if slot.try_acquire():
                return slot
        time.sleep(0.5)


def _acquire_slot() -> _FileSlot:
    return _acquire_named_slot("glm-4.7", GLM_47_CONCURRENCY)


def _acquire_for_model(model: str) -> _FileSlot:
    """모델 → slot 명시적 매핑 (slot_config_for 사용). 알 수 없는 모델은 보수적 default."""
    prefix, concurrency = slot_config_for(model)
    return _acquire_named_slot(prefix, concurrency)


# ──────────────────────────────────────────────────────────────────────────
#  Model-aware unified slot — 신규 호출자는 가급적 이쪽 사용 권장.
# ──────────────────────────────────────────────────────────────────────────
@contextmanager
def model_slot(model: str):
    """모델별 한도에 맞춰 자동으로 slot 획득 / 해제."""
    slot = _acquire_for_model(model)
    try:
        yield
    finally:
        slot.close()


@asynccontextmanager
async def async_model_slot(model: str):
    slot = await asyncio.to_thread(_acquire_for_model, model)
    try:
        yield
    finally:
        await asyncio.to_thread(slot.close)


# ──────────────────────────────────────────────────────────────────────────
#  Legacy / 명시 모델 helper — 기존 호출자 호환 유지.
# ──────────────────────────────────────────────────────────────────────────
@contextmanager
def glm47_slot():
    with model_slot("glm-4.7"):
        yield


@contextmanager
def flashx_slot():
    """GLM-4.7-FlashX (concurrency=3, ~10x 저렴, JSON 재작성용)."""
    with model_slot("glm-4.7-flashx"):
        yield


@contextmanager
def glm5_slot():
    """GLM-5 (concurrency=2)."""
    with model_slot("glm-5"):
        yield


@contextmanager
def glm51_slot():
    """GLM-5.1 (concurrency=10) — 최종 보고서·시사점에 적합."""
    with model_slot("glm-5.1"):
        yield


@contextmanager
def air_slot():
    """GLM-4.5-Air (concurrency=5)."""
    with model_slot("glm-4.5-air"):
        yield


@contextmanager
def flash_slot():
    """GLM-4.5-Flash (concurrency=2, FREE) — 추출·태깅 대량용."""
    with model_slot("glm-4.5-flash"):
        yield


@asynccontextmanager
async def async_glm47_slot():
    async with async_model_slot("glm-4.7"):
        yield


@asynccontextmanager
async def async_flashx_slot():
    async with async_model_slot("glm-4.7-flashx"):
        yield


@asynccontextmanager
async def async_glm5_slot():
    async with async_model_slot("glm-5"):
        yield


@asynccontextmanager
async def async_glm51_slot():
    async with async_model_slot("glm-5.1"):
        yield


@asynccontextmanager
async def async_flash_slot():
    async with async_model_slot("glm-4.5-flash"):
        yield
