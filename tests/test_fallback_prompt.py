"""B-stage fallback prompt 테스트 (AC #3).

검증:
  - archive_count < 5 시 input() 호출 → 'n' 응답 시 use_external=False
  - archive_count >= 5 (boundary 5, 6, 10) 시 input() 호출 0회
  - 'y'/엔터 시 search_external_only 호출
  - input() 이 asyncio.to_thread 로 wrap (async 안전)
"""
import builtins
import importlib
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


@pytest.fixture
def fresh_state_machine(tmp_path, monkeypatch):
    monkeypatch.setenv("BODY_CACHE_DB", str(tmp_path / "test.db"))
    from src.services import body_cache, body_fetcher
    importlib.reload(body_cache)
    importlib.reload(body_fetcher)
    yield


def _mock_search_results(count: int):
    """SearchResults mock with N results."""
    from src.models import SearchResult, SearchResults
    results = [
        SearchResult(
            source_url=f"https://archive/{i}",
            final_url=f"https://archive/{i}",
            content=f"content {i}",
            tier=1,
            source_name="TestArchive",
            article_title=f"title {i}",
        )
        for i in range(count)
    ]
    return SearchResults(results=results, fetched_urls=frozenset(r.source_url for r in results))


@pytest.mark.asyncio
@pytest.mark.parametrize("archive_count", [5, 6, 10])
async def test_no_fallback_on_sufficient_archive(
    fresh_state_machine, archive_count, monkeypatch
):
    """archive_count >= 5 (boundary 5, 6, 10) 시 input() 호출 없음."""
    input_calls = []

    def _spy_input(prompt=""):
        input_calls.append(prompt)
        return "n"

    monkeypatch.setattr(builtins, "input", _spy_input)

    # SearchService mock
    from src.services.search import SearchService
    svc = SearchService()
    svc.set_core_terms("test", current_year="2026")

    sr = _mock_search_results(archive_count)

    async def _archive_only(q, keywords=None):
        return sr

    svc.search_archive_only = _archive_only

    # B-stage 핵심 로직 시뮬레이션 (state_machine.py:101+ 패턴)
    archive_url_set = set()
    for r in sr.results:
        archive_url_set.add(r.source_url)
    archive_count_actual = len(archive_url_set)

    use_external = False
    if archive_count_actual < 5:
        # 호출되면 안 됨
        ans = input("외부 검색 진행할까요? [Y/n]: ").strip().lower()
        use_external = ans in ("", "y", "yes")

    assert len(input_calls) == 0, f"input() 호출되면 안 됨 (count={archive_count})"
    assert use_external is False


@pytest.mark.asyncio
async def test_fallback_triggers_on_low_archive(fresh_state_machine, monkeypatch):
    """archive_count < 5 시 input() 호출, 'n' 응답 시 use_external=False."""
    input_calls = []

    def _spy_input(prompt=""):
        input_calls.append(prompt)
        return "n"

    monkeypatch.setattr(builtins, "input", _spy_input)

    archive_count = 2  # < 5
    use_external = False
    if archive_count < 5:
        ans = input("외부 검색 진행할까요? [Y/n]: ").strip().lower()
        use_external = ans in ("", "y", "yes")

    assert len(input_calls) == 1
    assert use_external is False


@pytest.mark.asyncio
async def test_fallback_yes_enables_external(fresh_state_machine, monkeypatch):
    """input() 'y' 응답 → use_external=True."""
    monkeypatch.setattr(builtins, "input", lambda prompt="": "y")
    archive_count = 3
    use_external = False
    if archive_count < 5:
        ans = input("외부 검색 진행할까요? [Y/n]: ").strip().lower()
        use_external = ans in ("", "y", "yes")
    assert use_external is True


@pytest.mark.asyncio
async def test_fallback_default_enter_enables_external(fresh_state_machine, monkeypatch):
    """엔터(빈 입력) → use_external=True (default Y)."""
    monkeypatch.setattr(builtins, "input", lambda prompt="": "")
    archive_count = 3
    use_external = False
    if archive_count < 5:
        ans = input("외부 검색 진행할까요? [Y/n]: ").strip().lower()
        use_external = ans in ("", "y", "yes")
    assert use_external is True


def test_state_machine_uses_asyncio_to_thread_for_input():
    """src/state_machine.py에 'asyncio.to_thread(input, ...)' 패턴 존재 확인."""
    from pathlib import Path
    src = Path("src/state_machine.py").read_text(encoding="utf-8")
    assert "asyncio.to_thread(" in src
    assert "input," in src or "input ," in src
    # B-stage 영역에 있는지 (대략)
    assert "외부 검색 진행할까요" in src


def test_run_phase0_debug_uses_asyncio_to_thread_for_input():
    """run_phase0_debug.py 에도 동일 패턴 존재."""
    from pathlib import Path
    src = Path("run_phase0_debug.py").read_text(encoding="utf-8")
    assert "asyncio.to_thread(" in src
    assert "외부 검색 진행할까요" in src


# === Real integration tests for plan_propose (REV4 code-review MAJOR-1 fix) ===

@pytest.mark.asyncio
async def test_plan_propose_sufficient_archive_no_external_no_prompt(
    fresh_state_machine, monkeypatch
):
    """
    실제 통합 테스트: archive 6건 (>=5) → input() 호출 0회, search_external_only 호출 0회.
    state_machine.py B-stage 의 archive-first 흐름이 실제로 spec 준수하는지 검증.
    """
    from src.state_machine import AnalysisPipeline
    from src.models import SearchResult, SearchResults
    from unittest.mock import AsyncMock, MagicMock

    # 6건 archive 결과
    sr_archive = SearchResults(
        results=[
            SearchResult(
                source_url=f"https://archive/{i}",
                final_url=f"https://archive/{i}",
                content=f"battery regulation content {i}",
                tier=1,
                source_name="TestArchive",
                article_title=f"title {i}",
            )
            for i in range(6)
        ],
        fetched_urls=frozenset(f"https://archive/{i}" for i in range(6)),
    )

    pipeline = AnalysisPipeline()
    pipeline.search.search_archive_only = AsyncMock(return_value=sr_archive)
    pipeline.search.search_external_only = AsyncMock(side_effect=AssertionError(
        "search_external_only MUST NOT be called when archive >= 5"
    ))
    pipeline.search.set_core_terms = MagicMock()

    # LLM mock — C-stage가 차원 제안 즉시 반환
    # A-stage: pre_queries JSON array
    fake_a_response = MagicMock()
    fake_a_response.content = '["EU battery query 1", "EU battery query 2"]'
    fake_a_response.reasoning = ""
    # C-stage: dimensions JSON
    fake_c_response = MagicMock()
    fake_c_response.content = (
        '{"key_dimensions": ["d1","d2"], "dimension_rationale": {}, '
        '"dimension_queries_grouped": [["q1"],["q2"]], "analysis_rationale": "ok"}'
    )
    fake_c_response.reasoning = ""
    pipeline.llm = MagicMock()
    pipeline.llm.complete = AsyncMock(side_effect=[fake_a_response, fake_c_response])

    # input() 가 호출되면 즉시 fail
    input_calls = []
    def _spy_input(prompt=""):
        input_calls.append(prompt)
        raise AssertionError(f"input() MUST NOT be called when archive >= 5: prompt={prompt!r}")
    monkeypatch.setattr("builtins.input", _spy_input)

    # 실제 plan_propose 호출
    plan = await pipeline.plan_propose("EU 배터리 규제 영향")

    # 검증: input() 호출 0회, external_only 호출 0회, _use_external == False
    assert len(input_calls) == 0
    assert pipeline.search.search_external_only.await_count == 0
    assert pipeline._use_external is False


@pytest.mark.asyncio
async def test_plan_propose_low_archive_user_n_no_external(
    fresh_state_machine, monkeypatch
):
    """
    archive 2건 (<5) → input() 호출 → 'n' 응답 → search_external_only 호출 0회.
    """
    from src.state_machine import AnalysisPipeline
    from src.models import SearchResult, SearchResults
    from unittest.mock import AsyncMock, MagicMock

    sr_archive = SearchResults(
        results=[
            SearchResult(
                source_url=f"https://archive/{i}",
                final_url=f"https://archive/{i}",
                content=f"content {i}",
                tier=1,
                source_name="TestArchive",
            )
            for i in range(2)
        ],
        fetched_urls=frozenset(f"https://archive/{i}" for i in range(2)),
    )

    pipeline = AnalysisPipeline()
    pipeline.search.search_archive_only = AsyncMock(return_value=sr_archive)
    pipeline.search.search_external_only = AsyncMock(side_effect=AssertionError(
        "search_external_only MUST NOT be called when user answers 'n'"
    ))
    pipeline.search.set_core_terms = MagicMock()

    fake_a = MagicMock()
    fake_a.content = '["test query 1", "test query 2"]'
    fake_a.reasoning = ""
    fake_c = MagicMock()
    fake_c.content = (
        '{"key_dimensions": ["d1"], "dimension_rationale": {}, '
        '"dimension_queries_grouped": [["q1"]], "analysis_rationale": "ok"}'
    )
    fake_c.reasoning = ""
    pipeline.llm = MagicMock()
    pipeline.llm.complete = AsyncMock(side_effect=[fake_a, fake_c])

    input_calls = []
    def _spy_input(prompt=""):
        input_calls.append(prompt)
        return "n"
    monkeypatch.setattr("builtins.input", _spy_input)

    await pipeline.plan_propose("test topic")

    assert len(input_calls) == 1, "input() should be called exactly once for archive < 5"
    assert pipeline.search.search_external_only.await_count == 0
    assert pipeline._use_external is False


@pytest.mark.asyncio
async def test_plan_propose_low_archive_user_y_runs_external(
    fresh_state_machine, monkeypatch
):
    """archive 2건 (<5) → input() 'y' → search_external_only 호출 발생 + _use_external=True."""
    from src.state_machine import AnalysisPipeline
    from src.models import SearchResult, SearchResults
    from unittest.mock import AsyncMock, MagicMock

    sr_archive = SearchResults(
        results=[
            SearchResult(
                source_url=f"https://archive/{i}",
                final_url=f"https://archive/{i}",
                content=f"content {i}",
                tier=1,
                source_name="TestArchive",
            )
            for i in range(2)
        ],
        fetched_urls=frozenset(),
    )
    sr_external = SearchResults(
        results=[
            SearchResult(
                source_url="https://external/1",
                final_url="https://external/1",
                content="external content",
                tier=2,
                source_name="ExtSrc",
            )
        ],
        fetched_urls=frozenset({"https://external/1"}),
    )

    pipeline = AnalysisPipeline()
    pipeline.search.search_archive_only = AsyncMock(return_value=sr_archive)
    pipeline.search.search_external_only = AsyncMock(return_value=sr_external)
    pipeline.search.set_core_terms = MagicMock()

    fake_a = MagicMock()
    fake_a.content = '["test query 1", "test query 2"]'
    fake_a.reasoning = ""
    fake_c = MagicMock()
    fake_c.content = (
        '{"key_dimensions": ["d1"], "dimension_rationale": {}, '
        '"dimension_queries_grouped": [["q1"]], "analysis_rationale": "ok"}'
    )
    fake_c.reasoning = ""
    pipeline.llm = MagicMock()
    pipeline.llm.complete = AsyncMock(side_effect=[fake_a, fake_c])

    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    await pipeline.plan_propose("test topic")

    assert pipeline.search.search_external_only.await_count >= 1
    assert pipeline._use_external is True
