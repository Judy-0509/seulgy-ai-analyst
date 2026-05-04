import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURE = Path(__file__).parent / "fixtures" / "golden_mindmap.json"


@pytest.fixture
def golden_mindmap():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def mock_llm():
    """Mock LLMService that returns canned responses based on prompt content."""
    mock = AsyncMock()

    async def fake_complete(system, user, **kwargs):
        from src.services.llm import LLMResponse, TokenUsage
        # Detect prompt type by keyword presence
        if "kept_question_ids" in user:
            content = json.dumps({
                "kept_question_ids": ["Q1", "Q2", "Q3", "Q4", "Q5"],
                "merge_groups": [],
                "excluded_question_ids": [],
                "excluded_topics_ko": [],
                "excluded_topics_en": ["supply chain"],
            })
        elif "[s1]" in user:
            # Answer prompt — return a valid 3-sentence paragraph
            content = json.dumps({
                "paragraph": "[s1] 첫 문장. [s2] 둘째 문장. [s3] 셋째 문장.",
                "sentence_count": 3,
                "source_urls": ["https://example-test-1.test", "https://example-test-2.test"],
            })
        elif "queries" in user:
            content = json.dumps({"queries": ["iPhone foldable price 2026"]})
        else:
            content = "{}"
        return LLMResponse(
            content=content,
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50),
            backend="mock",
        )

    mock.complete = fake_complete
    return mock


@pytest.fixture
def mock_search():
    """Mock SearchService that returns no extra results."""
    mock = MagicMock()
    mock.core_terms = {"required": ["iphone", "foldable"], "anchor": ["2026"]}

    async def fake_search(q):
        from src.models import SearchResults
        return SearchResults(results=[], fetched_urls=frozenset())

    mock.search = fake_search
    mock.set_core_terms = MagicMock()
    return mock


def test_phase1_integration_happy_path(tmp_path, golden_mindmap, mock_llm, mock_search, monkeypatch):
    """End-to-end: load fixture, simulate user pressing Enter, verify outputs.

    NOTE: mock_llm returns source_urls=['https://example-test-1.test', 'https://example-test-2.test'].
    These URLs MUST appear in golden_mindmap fixture's evidence so they pass the registry whitelist.
    If you change the fixture, also update mock_llm in this test.
    """
    import run_phase1_debug as p1

    # Assert the linkage explicitly — fail fast if fixture/mock drift apart.
    fixture_blob = json.dumps(golden_mindmap)
    assert "https://example-test-1.test" in fixture_blob
    assert "https://example-test-2.test" in fixture_blob

    # Stage fixture as the latest mindmap
    reports = tmp_path / "reports"
    reports.mkdir()
    mindmap_path = reports / "test_topic_mindmap.json"
    mindmap_path.write_text(json.dumps(golden_mindmap, ensure_ascii=False), encoding="utf-8")

    # Patch services + reports dir + input()
    monkeypatch.setattr(p1, "REPORTS_DIR", reports)
    monkeypatch.setattr(p1, "LLMService", lambda: mock_llm)
    monkeypatch.setattr(p1, "SearchService", lambda: mock_search)

    # Simulate: Enter at finalize round (approve all 5), then Enter for each of 5 answers (OK)
    inputs = iter(["", "", "", "", "", ""])  # 1 finalize approve + 5 answer OKs
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))

    asyncio.run(p1.main(slug="test_topic"))

    # Verify output files exist
    out_path = reports / "test_topic_phase1.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data["answers"]) == 5
    assert all(a["final_status"] == "ok" for a in data["answers"])

    html_path = reports / "phase1_debug.html"
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "Phase 1 Debug" in html or "phase1" in html.lower()


def test_phase1_no_answer_when_urls_filtered_out(tmp_path, golden_mindmap, mock_search, monkeypatch):
    """If LLM returns hallucinated URLs not in registry, status should be no_answer."""
    import run_phase1_debug as p1
    from src.services.llm import LLMResponse, TokenUsage

    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "test_topic_mindmap.json").write_text(
        json.dumps(golden_mindmap, ensure_ascii=False), encoding="utf-8"
    )

    # Mock LLM: finalize narrows to Q1 only, answer returns hallucinated URL
    bad_llm = AsyncMock()

    async def bad_complete(system, user, **kwargs):
        if "kept_question_ids" in user:
            return LLMResponse(
                content=json.dumps({
                    "kept_question_ids": ["Q1"],
                    "merge_groups": [],
                    "excluded_question_ids": ["Q2", "Q3", "Q4", "Q5"],
                    "excluded_topics_ko": [],
                    "excluded_topics_en": [],
                }),
                usage=TokenUsage(prompt_tokens=50, completion_tokens=30),
                backend="mock",
            )
        if "[s1]" in user:
            return LLMResponse(
                content=json.dumps({
                    "paragraph": "[s1] One. [s2] Two. [s3] Three.",
                    "sentence_count": 3,
                    "source_urls": ["https://hallucinated-not-in-registry.test"],
                }),
                usage=TokenUsage(prompt_tokens=100, completion_tokens=50),
                backend="mock",
            )
        return LLMResponse(
            content="{}",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10),
            backend="mock",
        )

    bad_llm.complete = bad_complete

    monkeypatch.setattr(p1, "REPORTS_DIR", reports)
    monkeypatch.setattr(p1, "LLMService", lambda: bad_llm)
    monkeypatch.setattr(p1, "SearchService", lambda: mock_search)

    # Flow:
    # 1. First input is non-empty feedback -> triggers finalize LLM (narrows to Q1)
    # 2. Second input "" -> approves the narrowed Q1 list
    # 3. Q1 answer loop: LLM returns no_answer (hallucinated URL)
    #    - "" (Enter) is rejected because no_answer can't be OK'd -> loop continues
    #    - "s" -> skip Q1
    inputs = iter(["Q1만 남겨줘", "", "", "s"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))

    asyncio.run(p1.main(slug="test_topic"))

    out = json.loads((reports / "test_topic_phase1.json").read_text(encoding="utf-8"))
    assert len(out["answers"]) == 1  # only Q1 kept
    answer = out["answers"][0]
    assert answer["final_status"] == "skipped"
    # The first attempt should have candidate_status == "no_answer"
    assert any(a.get("candidate_status") == "no_answer" for a in answer["attempt_history"])


def test_phase1_anchor_error_when_no_eng_topic(tmp_path, monkeypatch):
    """Mindmap without eng_topic AND without pre_queries raises Phase1AnchorError."""
    import run_phase1_debug as p1

    reports = tmp_path / "reports"
    reports.mkdir()
    bad_mindmap = {
        "topic": "한국어만",
        "eng_topic": "",   # empty
        "pre_queries": [],  # empty
        "key_questions": [],
        "dimensions": [],
    }
    (reports / "korean_only_mindmap.json").write_text(
        json.dumps(bad_mindmap, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(p1, "REPORTS_DIR", reports)
    # Patch LLMService and SearchService to avoid network init side effects
    from unittest.mock import MagicMock, AsyncMock
    mock_search_instance = MagicMock()
    mock_search_instance.set_core_terms = MagicMock()
    mock_search_instance.core_terms = None  # empty core_terms triggers the error

    monkeypatch.setattr(p1, "LLMService", lambda: AsyncMock())
    monkeypatch.setattr(p1, "SearchService", lambda: mock_search_instance)

    with pytest.raises(p1.Phase1AnchorError):
        asyncio.run(p1.main(slug="korean_only"))
