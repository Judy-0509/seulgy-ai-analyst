import pytest
from src.state_machine import AnalysisPipeline


@pytest.mark.asyncio
async def test_pipeline_plan_returns_research_plan():
    """plan() returns a ResearchPlan with key_dimensions and dimension_queries_grouped."""
    from unittest.mock import AsyncMock, MagicMock
    from src.models import ResearchPlan
    from src.services.llm import LLMResponse, TokenUsage
    from src.services.search import SearchResults

    pipeline = AnalysisPipeline()

    # Mock search: return empty results
    pipeline.search.search = AsyncMock(return_value=SearchResults(
        results=[], fetched_urls=frozenset()
    ))
    pipeline.search.set_core_terms = MagicMock()

    # C단계가 차원 + 차원별 쿼리를 동시에 출력
    dim_json = (
        '{"analysis_rationale": "test", '
        '"key_dimensions": ["차원A", "차원B"], '
        '"dimension_rationale": {"차원A": "이유A", "차원B": "이유B"}, '
        '"dimension_queries_grouped": [["q1","q2","q3"],["q4","q5","q6"]]}'
    )

    pipeline.llm.complete = AsyncMock(side_effect=[
        LLMResponse(content='["iPhone foldable 2026", "foldable market"]',
                    usage=TokenUsage(prompt_tokens=10, completion_tokens=10), backend="glm"),
        LLMResponse(content=dim_json, reasoning="",
                    usage=TokenUsage(prompt_tokens=10, completion_tokens=10), backend="glm"),
    ])

    plan = await pipeline.plan("아이폰 폴더블 출시")

    assert isinstance(plan, ResearchPlan)
    assert len(plan.key_dimensions) == 2
    assert len(plan.dimension_queries_grouped) == 2
    assert plan.dimension_queries_grouped[0] == ["q1", "q2", "q3"]


def test_topic_slug():
    pipeline = AnalysisPipeline()
    slug = pipeline._topic_slug("EU 배터리 탈착식 규제!")
    assert "!" not in slug
    assert len(slug) <= 50


def test_state_path_returns_path():
    from pathlib import Path
    pipeline = AnalysisPipeline()
    p = pipeline._state_path("test_topic")
    assert isinstance(p, Path)
    assert p.name == "test_topic_state.json"
