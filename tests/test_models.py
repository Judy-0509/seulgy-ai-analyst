import pytest
from src.models import (
    Topic, Citation, MarketData,
    PipelineState, SearchResult, SearchResults,
    ResearchPlan,
)


def test_topic_defaults():
    t = Topic(title="EU 배터리 규제")
    assert t.title == "EU 배터리 규제"
    assert t.date  # should be today's date


def test_citation_auto_id():
    c = Citation(source_name="Reuters", source_url="https://reuters.com/x", source_tier=2, excerpt="test")
    assert len(c.id) == 8


def test_pipeline_state_defaults():
    state = PipelineState()
    assert state.topic is None
    assert state.plan is None


def test_search_results_frozenset():
    sr = SearchResults(results=[], fetched_urls=frozenset(["https://a.com", "https://b.com"]))
    assert "https://a.com" in sr.fetched_urls


def test_market_data():
    c = Citation(source_name="IDC", source_url="https://idc.com/x", source_tier=1, excerpt="market share data")
    md = MarketData(metric="market_share", value="23.5", unit="%", citation=c)
    assert md.is_estimate is False


def test_research_plan_fields():
    plan = ResearchPlan(
        analysis_rationale="test rationale",
        key_dimensions=["차원A", "차원B"],
        dimension_rationale={"차원A": "이유1", "차원B": "이유2"},
        dimension_queries_grouped=[
            ["q1a", "q1b", "q1c"],
            ["q2a", "q2b", "q2c"],
        ],
    )
    assert len(plan.key_dimensions) == 2
    assert len(plan.dimension_queries_grouped) == 2
    assert plan.dimension_rationale["차원A"] == "이유1"


def test_research_plan_minimal_defaults():
    plan = ResearchPlan(analysis_rationale="r", key_dimensions=["X"])
    assert plan.dimension_rationale == {}
    assert plan.dimension_queries_grouped == []
