"""search.py 매칭 완화 + Pydantic mutable 테스트 (AC #2 #9)."""
import pytest
from src.services.search import SearchService, classify_core_terms
from src.models import SearchResult


@pytest.fixture
def svc():
    return SearchService()


def test_classify_core_terms_no_general_bucket():
    """REV4: classify_core_terms은 required + anchor만 반환 (general 없음)."""
    result = classify_core_terms("HBM memory 2026", current_year="2026")
    assert "required" in result
    assert "anchor" in result
    assert "general" not in result  # plan invented general_terms — must not exist


def test_anchor_only_passes_floor(svc):
    """anchor 1개 매칭 (year-only) → score=0.5 → passes."""
    svc.core_terms = {"required": ["zzznoneseuq"], "anchor": ["2026"]}
    score, passes = svc._score_text("the year is 2026 with no required terms")
    assert score == 0.5
    assert passes is True


def test_zero_match_rejected(svc):
    """어떤 term도 매칭 안 되면 탈락."""
    svc.core_terms = {"required": ["xyz"], "anchor": ["abc"]}
    score, passes = svc._score_text("completely unrelated content")
    assert score == 0.0
    assert passes is False


def test_required_match_score_3x(svc):
    """required 가중치 3.0 보존."""
    svc.core_terms = {"required": ["hbm"], "anchor": []}
    score, passes = svc._score_text("HBM memory")
    # req=1, len(required)=1 → full match bonus 1.5x → 3.0 * 1.5 = 4.5
    assert score == 4.5
    assert passes is True


def test_full_match_bonus_preserved(svc):
    """모든 required 매칭 시 1.5x 보너스 유지."""
    svc.core_terms = {"required": ["hbm", "memory"], "anchor": []}
    score, passes = svc._score_text("HBM memory bandwidth analysis")
    # req=2, len(required)=2 → full match → (2*3.0 + 0) * 1.5 = 9.0
    assert score == 9.0


def test_anchor_weight_05(svc):
    """anchor 가중치 0.5 보존."""
    svc.core_terms = {"required": ["hbm"], "anchor": ["2026"]}
    score, passes = svc._score_text("HBM in 2026")
    # req=1, anc=1, full match → (3.0 + 0.5) * 1.5 = 5.25
    assert score == 5.25
    assert passes is True


def test_no_core_terms_passes(svc):
    """core_terms 미설정 시 (1.0, True) 반환."""
    svc.core_terms = None
    score, passes = svc._score_text("anything")
    assert score == 1.0
    assert passes is True


def test_empty_required_passes(svc):
    """required 빈 리스트면 (1.0, True)."""
    svc.core_terms = {"required": [], "anchor": []}
    score, passes = svc._score_text("anything")
    assert score == 1.0
    assert passes is True


def test_pydantic_content_assignable():
    """SearchResult.content 재할당 가능 (Pydantic v2 default mutable). AC #9."""
    sr = SearchResult(
        source_url="https://x/1",
        final_url="https://x/1",
        content="old content",
        tier=1,
        source_name="TestSrc",
    )
    sr.content = "new content"
    assert sr.content == "new content"


def test_match_count_increases_vs_baseline(svc):
    """완화 후 매칭 결과 ≥ 완화 전. (anchor 매칭 시 추가로 통과)."""
    svc.core_terms = {"required": ["hbm"], "anchor": ["2026"]}
    # anchor only (req=0, anc=1) — 구버전 룰(req>=1) 탈락, 신버전(score>=0.5) 통과
    _, passes_new = svc._score_text("the year 2026 in semiconductors")
    assert passes_new is True  # REV4 기준 통과
    # required match (req>=1) — 양쪽 모두 통과
    _, passes_full = svc._score_text("HBM in 2026")
    assert passes_full is True
