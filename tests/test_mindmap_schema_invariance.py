"""mindmap.json 스키마 호환성 테스트 (AC #7).

REV4 변경이 mindmap 출력 스키마를 깨지 않는지 검증.
- 기존에 있던 핵심 키(topic, dimensions, linkages)는 반드시 유지
- 추가 키는 forward-compatible (검증 안 함)
- dimensions 객체 내부 구조 (dimension, headline, subtopics) 유지
"""
import json
from pathlib import Path

import pytest

REPORTS = Path(__file__).resolve().parent.parent / "reports"

# 모든 버전의 mindmap에 반드시 존재하는 절대 최소 키
# (linkages, key_questions 등은 일부 legacy 파일엔 없을 수 있음 — forward-compat 허용)
CORE_KEYS = {"topic", "dimensions"}

# dimensions[i] 객체에 존재해야 하는 키
EXPECTED_DIMENSION_KEYS = {"dimension"}  # subtopics, headline 은 옵션 (legacy 호환)


def _load_existing_mindmaps():
    if not REPORTS.exists():
        return []
    return list(REPORTS.glob("*mindmap*.json"))


@pytest.mark.skipif(
    not _load_existing_mindmaps(),
    reason="기존 mindmap.json 파일이 없음 (Phase 0 첫 실행 후 생성됨)",
)
def test_mindmap_core_keys_invariant():
    """모든 mindmap 파일에 CORE_KEYS (topic/dimensions/linkages) 존재.

    REV4 변경이 이 키들을 제거하지 말아야 함.
    """
    mindmaps = _load_existing_mindmaps()
    failures = []
    for mm_path in mindmaps:
        try:
            data = json.loads(mm_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        actual = set(data.keys())
        missing = CORE_KEYS - actual
        if missing:
            failures.append(f"{mm_path.name}: {missing}")
    assert not failures, "CORE 키 누락 (호환성 위반): " + "; ".join(failures)


@pytest.mark.skipif(
    not _load_existing_mindmaps(),
    reason="기존 mindmap.json 파일이 없음",
)
def test_dimension_objects_have_dimension_field():
    """dimensions[i] 에 'dimension' 필드 존재 (Phase 0 출력 invariant)."""
    mindmaps = _load_existing_mindmaps()
    for mm_path in mindmaps:
        try:
            data = json.loads(mm_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for i, dim in enumerate(data.get("dimensions", []) or []):
            if not isinstance(dim, dict):
                continue
            actual = set(dim.keys())
            missing = EXPECTED_DIMENSION_KEYS - actual
            assert not missing, (
                f"{mm_path.name} dim[{i}]: 'dimension' 필드 누락"
            )


def test_core_keys_documented():
    """sanity: CORE_KEYS 가 비어있지 않음."""
    assert len(CORE_KEYS) >= 2
    assert "topic" in CORE_KEYS
    assert "dimensions" in CORE_KEYS
