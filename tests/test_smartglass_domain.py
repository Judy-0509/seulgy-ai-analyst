# tests/test_smartglass_domain.py
"""Smartglass 도메인 등록 일관성 테스트 — 설정/레지스트리 drift 방지."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def test_load_domain_smartglass():
    from src.domains import load_domain
    cfg = load_domain("smartglass")
    assert cfg["id"] == "smartglass"
    assert cfg["theme"]["accent"] == "#0891b2"
    assert cfg["suggested_path"] == "scripts/_smartglass_topic_suggestions.json"
    assert len(cfg["keywords"]) >= 40


def test_smartglass_system_prompt_registered():
    from src.prompts.system import DOMAIN_SYSTEM_PROMPTS, DOMAIN_ANALYST_TYPES
    assert "smartglass" in DOMAIN_SYSTEM_PROMPTS
    assert "스마트글래스" in DOMAIN_SYSTEM_PROMPTS["smartglass"]
    assert DOMAIN_ANALYST_TYPES["smartglass"] == "senior smart glasses market analyst"


def test_detect_domain_accepts_smartglass():
    from src.server import _detect_domain
    assert _detect_domain({"domain": "smartglass"}) == "smartglass"
