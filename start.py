"""
백엔드(uvicorn :8000) + 프론트엔드(Vite :5173) 동시 실행 스크립트.
사용법: python start.py
종료:   Ctrl+C
"""
import subprocess
import sys
import os
import re
import threading
import signal
import socket
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")


def _pids_on_port(port: int) -> list[int]:
    """지정 포트를 LISTENING 상태로 점유 중인 PID 목록 반환 (표준 라이브러리만)."""
    pids: set[int] = set()
    try:
        if sys.platform == "win32":
            # netstat -ano: Proto Local Foreign State PID
            out = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, timeout=5,
            ).stdout or ""
            pat = re.compile(rf":{port}\s+\S+\s+LISTENING\s+(\d+)")
            for line in out.splitlines():
                m = pat.search(line)
                if m:
                    pids.add(int(m.group(1)))
        else:
            # lsof -t -i :PORT -sTCP:LISTEN
            out = subprocess.run(
                ["lsof", "-t", "-i", f":{port}", "-sTCP:LISTEN"],
                capture_output=True, text=True, timeout=5,
            ).stdout or ""
            for tok in out.split():
                if tok.isdigit():
                    pids.add(int(tok))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    pids.discard(0)
    pids.discard(os.getpid())
    return sorted(pids)


def _kill_pid(pid: int, force: bool = False) -> bool:
    """PID 종료. force=True면 강제 종료. 성공 시 True."""
    try:
        if sys.platform == "win32":
            args = ["taskkill", "/PID", str(pid)]
            if force:
                args.append("/F")
            r = subprocess.run(args, capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        else:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
            return True
    except (FileNotFoundError, ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
        return False


def free_port(port: int, label: str) -> None:
    """포트가 점유돼 있으면 graceful 종료 → 1초 대기 → 강제 종료."""
    pids = _pids_on_port(port)
    if not pids:
        return
    print(f"\033[33m[{label}]\033[0m 포트 {port} 점유 PID {pids} → 정리 시도", flush=True)
    for pid in pids:
        _kill_pid(pid, force=False)
    # 종료 대기
    for _ in range(10):  # 최대 1초
        if not _pids_on_port(port):
            print(f"\033[33m[{label}]\033[0m 포트 {port} 정리 완료", flush=True)
            return
        time.sleep(0.1)
    # 여전히 살아 있으면 강제 종료
    remaining = _pids_on_port(port)
    if remaining:
        print(f"\033[33m[{label}]\033[0m 강제 종료 PID {remaining}", flush=True)
        for pid in remaining:
            _kill_pid(pid, force=True)
        time.sleep(0.3)


def stream(proc, prefix, color):
    """서브프로세스 출력을 prefix와 색상으로 실시간 출력."""
    reset = "\033[0m"
    for line in iter(proc.stdout.readline, b""):
        text = line.decode('utf-8', errors='replace').rstrip()
        try:
            print(f"{color}[{prefix}]{reset} {text}", flush=True)
        except UnicodeEncodeError:
            safe = text.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
            print(f"[{prefix}] {safe}", flush=True)


def wait_for_backend(host="127.0.0.1", port=8000, timeout=30):
    """백엔드 포트가 열릴 때까지 대기. timeout 초 초과 시 False 반환."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def main():
    print("\033[1m Research Helper 시작 중...\033[0m")
    print(" Backend  → http://localhost:8000")
    print(" Frontend → http://localhost:5173")
    print(" 종료: Ctrl+C\n")

    # 이전 실행에서 남은 프로세스가 8000/5173을 점유 중이면 정리
    free_port(8000, "BE")
    free_port(5173, "FE")

    backend_env = os.environ.copy()
    backend_env.setdefault("WATCHFILES_FORCE_POLLING", "true")

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.server:app",
         "--host", "127.0.0.1", "--port", "8000",
         "--reload", "--reload-dir", os.path.join(ROOT, "src"),
         "--reload-delay", "0.75"],
        cwd=ROOT,
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    t1 = threading.Thread(target=stream, args=(backend, "BE", "\033[36m"), daemon=True)
    t1.start()

    print("\033[36m[BE]\033[0m 백엔드 준비 대기 중...", flush=True)
    if not wait_for_backend():
        print("\033[31m[오류] 백엔드가 30초 내에 기동되지 않았습니다.\033[0m")
        backend.terminate()
        sys.exit(1)
    print("\033[36m[BE]\033[0m 백엔드 준비 완료 → 프론트엔드 시작\n", flush=True)

    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    frontend = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=FRONTEND,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    t2 = threading.Thread(target=stream, args=(frontend, "FE", "\033[35m"), daemon=True)
    t2.start()

    def shutdown(sig=None, frame=None):
        print("\n\033[1m 종료 중...\033[0m")
        backend.terminate()
        frontend.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 어느 한 프로세스라도 종료되면 같이 종료
    backend.wait()
    shutdown()


if __name__ == "__main__":
    main()
