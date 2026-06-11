import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts.ab_test_report_pipeline import (
    footnote_url_validity,
    load_snapshot,
    number_support_rate,
    quote_match_rate,
    run_blind_judge,
    serialize_snapshot,
)
from src.models import SearchResult


def _result(url: str = "https://example.com/a", content: str = "content") -> SearchResult:
    return SearchResult(
        source_url=url,
        final_url=url,
        content=content,
        tier=1,
        source_name="Example",
        article_title="Example title",
        pub_date="2026-01-01",
        fetch_date="2026-06-11",
    )


def test_quote_match_rate_exact_and_normalized():
    report = {
        "bullets": [
            '근거는 "shipments reached 1,200 units"이다.',
            "다른 근거는 “AI/robot’s adoption”이다.",
        ]
    }
    evidence = ["Shipments reached 1,200 units. AI robot's adoption accelerated."]

    assert quote_match_rate(report, evidence) == (2, 2, 1.0)


def test_quote_match_rate_miss():
    report = {"bullets": ['근거는 "not in evidence"이다.']}

    assert quote_match_rate(report, ["different evidence"]) == (0, 1, 0.0)


def test_number_support_rate_commas_percentages_and_miss():
    report = {
        "headline": "출하량 1,200대와 점유율 35.7%",
        "narrative": "비용은 99달러지만 88은 누락",
    }
    evidence = ["shipments were 1200 units; share was 35.7%; price was 99 dollars"]

    assert number_support_rate(report, evidence) == (3, 4, 0.75)


def test_number_support_rate_no_numbers():
    assert number_support_rate({"headline": "증가", "narrative": "숫자 없음"}, ["evidence"]) == (0, 0, 1.0)


def test_footnote_url_validity_valid_and_miss():
    report = {
        "footnotes": [
            {"url": "https://example.com/a"},
            {"url": "https://example.com/missing"},
        ]
    }

    assert footnote_url_validity(report, ["https://example.com/a"]) == (1, 2, 0.5)


def test_snapshot_round_trip_reconstructs_search_results(tmp_path: Path):
    result = _result(content="Evidence 1,200 and 35.7%")
    sections = [
        {
            "title": "Section",
            "causal_role": "analysis",
            "angle": "angle",
            "queries": ["query"],
            "included": [True],
            "results": [result],
        }
    ]
    snapshot = serialize_snapshot(
        "토픽",
        "humanoid",
        "english topic",
        ["query"],
        [result],
        sections,
        created_at="2026-06-11T00:00:00",
    )
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    loaded = load_snapshot(path)

    assert isinstance(loaded["archive_results"][0], SearchResult)
    assert isinstance(loaded["sections"][0]["results"][0], SearchResult)
    assert loaded["archive_results"][0].model_dump() == result.model_dump()
    assert loaded["sections"][0]["results"][0].model_dump() == result.model_dump()


@dataclass
class FakeResponse:
    content: str


class FakeJudgeLLM:
    def __init__(self, payloads: list[dict]):
        self.payloads = payloads
        self.calls = []

    async def complete(self, system: str, user: str, **kwargs):
        self.calls.append((system, user, kwargs))
        return FakeResponse(json.dumps(self.payloads.pop(0), ensure_ascii=False))


def _variant(headline: str) -> dict:
    return {
        "sections": [
            {
                "title": "Section",
                "report": {
                    "headline": headline,
                    "narrative": "Narrative",
                    "bullets": [],
                    "footnotes": [],
                },
            }
        ],
        "meta": {"executive_summary": "Summary", "insights": []},
    }


@pytest.mark.asyncio
async def test_judge_position_bias_flagged_as_noise(monkeypatch):
    # 심판이 두 pass 모두 '슬롯 1'을 고르면(위치 편향) un-mapping 후 A/B가 갈려 noise 처리.
    monkeypatch.setattr("scripts.ab_test_report_pipeline.random.shuffle", lambda order: None)
    payload = {
        "overall": {"winner": "1", "reason": "better"},
        "증거 기반성": {"winner": "1", "reason": "better"},
    }
    llm = FakeJudgeLLM([payload, payload])

    result = await run_blind_judge(llm, "토픽", _variant("A"), _variant("B"))

    assert result["passes"][0]["mapping"] == {"1": "A", "2": "B"}
    assert result["passes"][1]["mapping"] == {"1": "B", "2": "A"}
    assert result["passes"][0]["unmapped"]["overall"]["winner"] == "A"
    assert result["passes"][1]["unmapped"]["overall"]["winner"] == "B"
    assert result["verdicts"]["overall"]["winner"] == "noise"


@pytest.mark.asyncio
async def test_judge_consistent_winner_survives_position_swap(monkeypatch):
    # 순서를 바꿔도 같은 variant(A)를 고르면 합의 → A 승리로 집계.
    monkeypatch.setattr("scripts.ab_test_report_pipeline.random.shuffle", lambda order: None)
    payloads = [
        {"overall": {"winner": "1", "reason": "first"}},
        {"overall": {"winner": "2", "reason": "second"}},
    ]
    llm = FakeJudgeLLM(payloads)

    result = await run_blind_judge(llm, "토픽", _variant("A"), _variant("B"))

    assert result["passes"][0]["unmapped"]["overall"]["winner"] == "A"
    assert result["passes"][1]["unmapped"]["overall"]["winner"] == "A"
    assert result["verdicts"]["overall"]["winner"] == "A"
