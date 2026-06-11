# tests/test_smartglass_keywords.py
"""word-boundary 키워드 매처 테스트 — Phase A에서 발견된 오탐 케이스 회귀 방지."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _smartglass_research_helper import is_smartglass_relevant  # noqa: E402


def test_positive_title_matches():
    assert is_smartglass_relevant("Global Smart Glasses Shipments Grew 139% YoY")
    assert is_smartglass_relevant("Huawei launches AI glasses with ecosystem integration")
    assert is_smartglass_relevant("JBD microdisplay breakthrough for AR")
    assert is_smartglass_relevant("Micro LED gains focus as Seoul Semi plans AR investment")  # "micro-led" ~ "micro led"


def test_url_slug_matches():
    assert is_smartglass_relevant("", url="https://example.com/ai-glasses-market-2026/")
    assert is_smartglass_relevant("", url="https://about.fb.com/news/ray-ban-meta-update/")


def test_word_boundary_blocks_false_positives():
    # Phase A 실측 오탐 패턴: 부분문자열 매칭 금지
    assert not is_smartglass_relevant("Buick Envision production begins in 2026")
    assert not is_smartglass_relevant("Mozilla Thunderbird email update")
    assert not is_smartglass_relevant("The inmost circle of advisors")   # "inmo" 차단
    assert not is_smartglass_relevant("Rokidding around")                # "rokid" + 접미사 차단
