"""하위 호환 shim — suggest_smartphone_topics.py 로 위임.

직접 실행 시 suggest_smartphone_topics.py 와 동일하게 동작합니다.
새 코드에서는 suggest_smartphone_topics.py 를 직접 사용하세요.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from suggest_smartphone_topics import main  # noqa: E402

if __name__ == "__main__":
    main()
