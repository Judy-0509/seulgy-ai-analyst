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


def test_archive_files_mirror_suggest_registry():
    """domain json의 archive_files ↔ suggest 스크립트 ARCHIVE_REGISTRY drift 방지."""
    from src.domains import load_domain
    import suggest_smartglass_topics as sst
    cfg_files = set(load_domain("smartglass")["archive_files"])
    reg_files = {f for _, f in sst.ARCHIVE_REGISTRY}
    assert cfg_files == reg_files


def test_suggest_registry_taxonomy_complete():
    import suggest_smartglass_topics as sst
    names = {n for n, _ in sst.ARCHIVE_REGISTRY}
    assert names == set(sst.SOURCE_TAXONOMY.keys())
    assert len(sst.ARCHIVE_REGISTRY) == 18
