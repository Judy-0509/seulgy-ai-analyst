import json
import sys
import re
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_phase1_debug as p1


def test_derive_core_terms_uses_eng_topic():
    mm = {"eng_topic": "iPhone foldable launch", "pre_queries": ["x y z"], "topic": "한국어"}
    eng, pq = p1._derive_core_terms(mm)
    assert eng == "iPhone foldable launch"
    assert pq == ["x y z"]


def test_derive_core_terms_falls_back_to_pre_queries():
    mm = {"pre_queries": ["iPhone foldable 2026 launch market data"], "topic": "한국어"}
    eng, _ = p1._derive_core_terms(mm)
    # First 6 tokens
    assert eng == "iPhone foldable 2026 launch market data"


def test_derive_core_terms_falls_back_to_korean_topic_with_warning(capsys):
    mm = {"topic": "한국어 토픽만 있음"}
    eng, _ = p1._derive_core_terms(mm)
    assert eng == "한국어 토픽만 있음"
    captured = capsys.readouterr()
    assert "WARNING" in captured.out


def test_build_merged_question_collapses_perspective_to_composite():
    sources = [
        {"id": "Q1", "question": "q1", "perspective": "sell_in", "related_dimensions": ["A"], "related_linkages": []},
        {"id": "Q5", "question": "q5", "perspective": "sell_through", "related_dimensions": ["B"], "related_linkages": ["L1"]},
    ]
    merged = p1._build_merged_question(sources, "Q1+5")
    assert merged["id"] == "Q1+5"
    assert merged["perspective"] == "composite"
    assert merged["source_perspective_breakdown"] == {"Q1": "sell_in", "Q5": "sell_through"}
    assert set(merged["related_dimensions"]) == {"A", "B"}
    assert merged["related_linkages"] == ["L1"]
    assert merged["_merged_from"] == ["Q1", "Q5"]


def test_marker_count_extraction():
    # Helper for tests — replicate inline regex used in main
    paragraph = "[s1] First. [s2] Second. [s3] Third."
    assert len(re.findall(r"\[s\d+\]", paragraph)) == 3


def test_strip_markers_for_display():
    p = "[s1] 첫문장. [s2] 둘째문장."
    cleaned = re.sub(r"\[s\d+\]\s*", "", p)
    assert cleaned == "첫문장. 둘째문장."
