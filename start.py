"""
백엔드(uvicorn :8000) + 프론트엔드(Vite :5173) 동시 실행 스크립트.
사용법: python start.py
종료:   Ctrl+C
"""
import subprocess
import sys
import os
import threading
import signal
import socket
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")


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

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.server:app",
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=ROOT,
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
