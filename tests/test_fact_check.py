import json
from dataclasses import dataclass

import pytest

import run_report
from run_report import stage_ef
from src.models import SearchResult
from src.services.fact_check import (
    BulletVerdict,
    apply_verdicts,
    clip_evidence,
    deterministic_check,
    llm_check_bullets,
)


@dataclass
class FakeResponse:
    content: str


class FakeLLM:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    async def complete(self, system: str, user: str, **kwargs):
        self.calls.append((system, user, kwargs))
        payload = self.payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        if isinstance(payload, str):
            return FakeResponse(payload)
        return FakeResponse(json.dumps(payload, ensure_ascii=False))


async def _empty_bodies(_sections):
    return {}


def _result(content: str = "Evidence says verified quote and 1,200 units.") -> SearchResult:
    return SearchResult(
        source_url="https://example.com/a",
        final_url="https://example.com/a",
        content=content,
        tier=1,
        source_name="Example",
        article_title="Evidence title",
        pub_date="2026-01-01",
    )


def test_deterministic_check_verified_straight_and_curly_quotes():
    bullets = [
        '• "verified quote" — Evidence title [Example, 2026-01-01]',
        "• “curly quote” — Evidence title [Example, 2026-01-01]",
    ]
    verdicts, unresolved = deterministic_check(bullets, "A verified quote appears. A curly quote appears.")

    assert [v.status for v in verdicts] == ["verified", "verified"]
    assert [v.method for v in verdicts] == ["deterministic", "deterministic"]
    assert unresolved == []


def test_deterministic_check_miss_and_no_quote_unresolved():
    bullets = [
        '• "missing quote" — Evidence title [Example, 2026-01-01]',
        "• no quoted span — Evidence title [Example, 2026-01-01]",
    ]
    verdicts, unresolved = deterministic_check(bullets, "different evidence")

    assert [v.status for v in verdicts] == ["unverified", "unverified"]
    assert [v.method for v in verdicts] == ["deterministic", "no_quote"]
    assert unresolved == [0, 1]


def test_clip_evidence_keyword_window_and_cap():
    evidence = "a" * 100 + " distinctive_keyword " + "b" * 100
    clip = clip_evidence("bullet mentions distinctive_keyword", evidence, window=10, cap=35)

    assert "distinctive_keyword" in clip
    assert len(clip) <= 35


def test_clip_evidence_fallback_path_respects_cap():
    evidence = "abcdef" * 100

    assert clip_evidence("no matching token", evidence, cap=17) == evidence[:17]


@pytest.mark.asyncio
async def test_llm_check_bullets_normal_verdicts():
    llm = FakeLLM(
        [
            {
                "verdicts": [
                    {"id": 0, "verdict": "verified", "reason": "quote is present"},
                    {"id": 1, "verdict": "unsupported", "reason": "quote is absent"},
                ]
            }
        ]
    )

    result = await llm_check_bullets(
        llm,
        [
            {"index": 0, "bullet": "a", "evidence_clip": "a"},
            {"index": 1, "bullet": "b", "evidence_clip": "x"},
        ],
    )

    assert [(v.index, v.status, v.method) for v in result] == [
        (0, "verified", "llm"),
        (1, "unsupported", "llm"),
    ]
    assert llm.calls[0][2]["model"] == "glm-4.7-flashx"
    assert llm.calls[0][2]["temperature"] == 0.0


@pytest.mark.asyncio
async def test_llm_check_bullets_missing_id_unverified():
    llm = FakeLLM([{"verdicts": [{"id": 0, "verdict": "verified", "reason": "ok"}]}])

    result = await llm_check_bullets(
        llm,
        [
            {"index": 0, "bullet": "a", "evidence_clip": "a"},
            {"index": 1, "bullet": "b", "evidence_clip": "b"},
        ],
    )

    assert [v.status for v in result] == ["verified", "unverified"]
    assert result[1].reason == "checker response missing id"


@pytest.mark.asyncio
async def test_llm_check_bullets_invalid_json_all_unverified():
    llm = FakeLLM(["not json"])

    result = await llm_check_bullets(llm, [{"index": 3, "bullet": "a", "evidence_clip": "a"}])

    assert [(v.index, v.status) for v in result] == [(3, "unverified")]


@pytest.mark.asyncio
async def test_llm_check_bullets_exception_all_unverified():
    llm = FakeLLM([RuntimeError("boom")])

    result = await llm_check_bullets(llm, [{"index": 2, "bullet": "a", "evidence_clip": "a"}])

    assert [(v.index, v.status) for v in result] == [(2, "unverified")]


def test_apply_verdicts_drops_only_unsupported_and_counts():
    report = {"bullets": ["a", "b", "c"], "headline": "h", "narrative": "n", "footnotes": []}
    summary = apply_verdicts(
        report,
        [
            BulletVerdict(0, "a", "verified", "deterministic", "ok"),
            BulletVerdict(1, "b", "unsupported", "llm", "absent"),
            BulletVerdict(2, "c", "unverified", "llm", "failed"),
        ],
    )

    assert report["bullets"] == ["a", "c"]
    assert summary["total"] == 3
    assert summary["verified"] == 1
    assert summary["unsupported_dropped"] == 1
    assert summary["unverified_kept"] == 1
    assert len(summary["verdicts"]) == 3


def test_apply_verdicts_can_leave_empty_bullets_without_marking_insufficient():
    report = {"bullets": ["a"], "headline": "h", "narrative": "n", "footnotes": []}
    summary = apply_verdicts(report, [BulletVerdict(0, "a", "unsupported", "llm", "absent")])

    assert report["bullets"] == []
    assert "insufficient_evidence" not in report
    assert summary["unsupported_dropped"] == 1


@pytest.mark.asyncio
async def test_stage_ef_factcheck_enabled_drops_unsupported(monkeypatch):
    monkeypatch.setenv("REPORT_FACTCHECK", "1")
    monkeypatch.setattr(run_report, "_fetch_bodies", _empty_bodies)
    llm = FakeLLM(
        [
            {
                "headline": "Headline",
                "narrative": "Narrative",
                "bullets": ['• "absent quote" — Evidence title [Example, 2026-01-01]'],
                "footnotes": [],
            },
            {"verdicts": [{"id": 0, "verdict": "unsupported", "reason": "not in clip"}]},
            {
                "headline": "Second headline",
                "narrative": "Second narrative",
                "bullets": ['• "verified quote" — Evidence title [Example, 2026-01-01]'],
                "footnotes": [],
            },
        ]
    )
    sections = [
        {
            "title": "Section",
            "angle": "",
            "causal_role": "analysis",
            "results": [_result("Evidence has different text.")],
        },
        {
            "title": "Second section",
            "angle": "",
            "causal_role": "analysis",
            "results": [_result("Evidence has verified quote.")],
        },
    ]

    result = await stage_ef(llm, "Topic", sections)

    assert result[0]["report"]["bullets"] == []
    assert result[0]["fact_check"]["total"] == 1
    assert result[0]["fact_check"]["unsupported_dropped"] == 1


@pytest.mark.asyncio
async def test_stage_ef_factcheck_unset_skips(monkeypatch):
    monkeypatch.delenv("REPORT_FACTCHECK", raising=False)
    monkeypatch.setattr(run_report, "_fetch_bodies", _empty_bodies)
    llm = FakeLLM(
        [
            {
                "headline": "Headline",
                "narrative": "Narrative",
                "bullets": ['• "absent quote" — Evidence title [Example, 2026-01-01]'],
                "footnotes": [],
            },
            {
                "headline": "Second headline",
                "narrative": "Second narrative",
                "bullets": ['• "verified quote" — Evidence title [Example, 2026-01-01]'],
                "footnotes": [],
            }
        ]
    )
    sections = [
        {
            "title": "Section",
            "angle": "",
            "causal_role": "analysis",
            "results": [_result("Evidence has different text.")],
        },
        {
            "title": "Second section",
            "angle": "",
            "causal_role": "analysis",
            "results": [_result("Evidence has verified quote.")],
        },
    ]

    result = await stage_ef(llm, "Topic", sections)

    assert result[0]["report"]["bullets"]
    assert "fact_check" not in result[0]
