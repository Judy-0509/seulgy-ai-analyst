from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import date


class Topic(BaseModel):
    title: str
    eng_title: str = ""  # English translation used for search queries
    date: str = Field(default_factory=lambda: date.today().isoformat())
    source_event: Optional[str] = None


class Citation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_name: str
    source_url: str
    source_tier: int
    excerpt: str
    access_date: str = Field(default_factory=lambda: date.today().isoformat())


class MarketData(BaseModel):
    metric: str
    value: str
    unit: str
    citation: Citation
    is_estimate: bool = False


class SearchResult(BaseModel):
    source_url: str
    final_url: str
    content: str
    tier: int
    source_name: str
    article_title: str = ""
    pub_date: str = ""
    fetch_date: str = Field(default_factory=lambda: date.today().isoformat())


class SearchResults(BaseModel):
    results: list[SearchResult]
    fetched_urls: frozenset[str] = frozenset()
    model_config = {"arbitrary_types_allowed": True}


class DimensionProposal(BaseModel):
    """C 단계 출력: 5개 차원 제안 (사용자 확인 전)."""
    analysis_rationale: str = ""
    eng_topic: str = ""
    pre_queries: list[str] = Field(default_factory=list)  # [REV4-M3] for Phase 1 anchoring
    proposed_dimensions: list[str] = Field(default_factory=list)
    dimension_rationale: dict[str, str] = Field(default_factory=dict)
    dimension_queries_grouped: list[list[str]] = Field(default_factory=list)
    # 사용자 피드백에서 추출된 제외 항목 (이후 F/G/H에서 강제)
    excluded_perspectives: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    analysis_rationale: str
    key_dimensions: list[str]
    dimension_rationale: dict[str, str] = Field(default_factory=dict)   # dim → why selected
    dimension_queries_grouped: list[list[str]] = Field(default_factory=list)  # parallel to key_dimensions, 3 ENG queries each
    pre_queries: list[str] = Field(default_factory=list)  # [REV4-M3] propagated from DimensionProposal
    # C 단계에서 사용자가 명시 제외한 항목 — F/G/H 모두에서 강제 적용
    excluded_perspectives: list[str] = Field(default_factory=list)
    excluded_topics: list[str] = Field(default_factory=list)


class PipelineState(BaseModel):
    topic: Optional[Topic] = None
    plan: Optional[ResearchPlan] = None
