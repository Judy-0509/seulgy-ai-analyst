import asyncio
import os
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
LOCK_DIR = ROOT / "data" / "locks"
GLM_47_CONCURRENCY = int(os.getenv("GLM_47_CONCURRENCY", "2"))


class _FileSlot:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

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
            return True
        except OSError:
            self.close()
            return False

    def close(self) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def _acquire_slot() -> _FileSlot:
    while True:
        for idx in range(GLM_47_CONCURRENCY):
            slot = _FileSlot(LOCK_DIR / f"glm-4.7-{idx}.lock")
            if slot.try_acquire():
                return slot
        time.sleep(0.5)


@contextmanager
def glm47_slot():
    slot = _acquire_slot()
    try:
        yield
    finally:
        slot.close()


@asynccontextmanager
async def async_glm47_slot():
    slot = await asyncio.to_thread(_acquire_slot)
    try:
        yield
    finally:
        await asyncio.to_thread(slot.close)
