"""scripts/_suggest_core.py GLM 재시도 정책 회귀 테스트.

2026-07-20 장애: Zhipu 가 HTTP 502 를 반환했으나 재시도 판정이 에러 문자열
substring 매칭("429" / "1302" / "rate")이어서 502 는 어디에도 걸리지 않고
즉시 raise → set -euo pipefail 하에서 주간 파이프라인 16단계 전체가 중단.

네트워크 / 실제 sleep / lock 파일 없이 분류 로직만 검증한다.
"""
import contextlib

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

import scripts._suggest_core as sc


@contextlib.contextmanager
def _dummy_slot():
    """limiter slot 대체 — data/locks 에 파일을 만들지 않는다."""
    yield


@pytest.fixture
def slept(monkeypatch):
    """실제 대기 없이 요청된 대기 시간만 기록."""
    recorded: list[float] = []
    monkeypatch.setattr(sc._time, "sleep", recorded.append)
    monkeypatch.setattr(sc, "flashx_slot", _dummy_slot)
    monkeypatch.setattr(sc, "glm47_slot", _dummy_slot)
    return recorded


class _FakeCompletions:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def create(self, **params):
        self.calls += 1
        # outcomes 가 소진되면 마지막 항목을 계속 반복 (지속 장애 시나리오).
        outcome = self._outcomes[min(self.calls - 1, len(self._outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClient:
    """client.chat.completions.create 호출 횟수를 기록하는 최소 stub."""

    def __init__(self, outcomes):
        self.completions = _FakeCompletions(outcomes)
        self.chat = self

    @property
    def calls(self) -> int:
        return self.completions.calls


def _status_error(status_code: int, message: str = "boom", body_text: str = "") -> APIStatusError:
    request = httpx.Request("POST", "https://example.invalid/v4/chat/completions")
    response = httpx.Response(status_code=status_code, request=request, text=body_text)
    return APIStatusError(message, response=response, body=None)


def _call(client, slot=_dummy_slot):
    return sc.glm_create_with_retries(client, {"model": "glm-4.7"}, slot=slot)


# ── 1. 실제 장애 회귀 테스트 ────────────────────────────────────────────────

def test_http_502_retries_on_short_ladder(slept):
    """502 는 재시도되며, rate limit 이 아니라 짧은 ladder 로 대기한다."""
    sentinel = object()
    client = FakeClient([_status_error(502, body_text="<html>Bad Gateway</html>"), sentinel])

    result = _call(client)

    assert result is sentinel
    assert client.calls == 2
    assert len(slept) == 1
    # 5xx 를 rate limit 으로 오분류하면 60s 이상을 대기하게 된다.
    assert slept[0] < 60


# ── 2. 재시도 불가 status ───────────────────────────────────────────────────

def test_http_400_raises_without_retry(slept):
    client = FakeClient([_status_error(400, body_text="invalid request")])

    with pytest.raises(APIStatusError):
        _call(client)

    assert client.calls == 1
    assert slept == []


# ── 3. rate limit 은 긴 ladder ──────────────────────────────────────────────

def test_http_429_uses_long_ladder(slept):
    sentinel = object()
    client = FakeClient([_status_error(429, body_text="rate limit exceeded"), sentinel])

    assert _call(client) is sentinel
    assert client.calls == 2
    assert len(slept) == 1
    assert slept[0] >= 60


def test_zhipu_1302_body_refines_into_rate_limit(slept):
    """Zhipu 는 동시성 초과를 business code 1302 로 알린다 → 긴 ladder."""
    sentinel = object()
    client = FakeClient([
        _status_error(500, body_text='{"error":{"code":"1302"}}'),
        sentinel,
    ])

    assert _call(client) is sentinel
    assert slept[0] >= 60


def test_zhipu_1302_found_beyond_preview_truncation(slept):
    """1302 가 body 앞 120자를 넘어서 나와도 rate limit 으로 잡아야 한다."""
    sentinel = object()
    long_body = ("x" * 300) + '{"error":{"code":"1302"}}'
    client = FakeClient([_status_error(500, body_text=long_body), sentinel])

    assert _call(client) is sentinel
    assert slept[0] >= 60


# ── 4. "generate" substring 오분류 방지 ─────────────────────────────────────

def test_generate_in_message_is_not_a_rate_limit(slept):
    """'gene(rate)' 가 rate limit 으로 오인되어 재시도되면 안 된다."""
    client = FakeClient([
        _status_error(400, message="failed to generate completion",
                     body_text="the model could not generate a moderate response"),
    ])

    with pytest.raises(APIStatusError):
        _call(client)

    assert client.calls == 1
    assert slept == []


# ── 5. 지속 장애는 최종 예외 전파 ───────────────────────────────────────────

def test_persistent_502_propagates(slept):
    client = FakeClient([_status_error(502, body_text="Bad Gateway")])

    with pytest.raises(APIStatusError) as excinfo:
        _call(client)

    assert excinfo.value.status_code == 502
    assert client.calls == len(sc.TRANSIENT_DELAYS) + 1
    assert len(slept) == len(sc.TRANSIENT_DELAYS)
    assert all(s < 60 for s in slept)


# ── 부가: timeout / connection 오류도 짧은 ladder 로 재시도 ─────────────────

def test_timeout_and_connection_errors_retry(slept):
    request = httpx.Request("POST", "https://example.invalid/v4/chat/completions")
    sentinel = object()
    client = FakeClient([
        APITimeoutError(request=request),
        APIConnectionError(request=request),
        sentinel,
    ])

    assert _call(client) is sentinel
    assert client.calls == 3
    assert all(s < 60 for s in slept)


# ── enrich_topic 은 호출 실패 시 원본 토픽으로 강등 ─────────────────────────

def test_enrich_topic_degrades_gracefully_on_persistent_failure(slept):
    topic = {"title": "t", "criteria": "Criterion 1", "articles": [], "key_data": [],
             "rationale": "r"}
    client = FakeClient([_status_error(502, body_text="Bad Gateway")])

    result = sc.enrich_topic(topic, [{"source": "s", "date": "2026-07-01",
                                      "title": "a", "desc": ""}],
                             client, "sys", "{title}{criteria}{existing_articles}"
                                            "{key_data}{rationale}{additional_articles}")

    assert result is topic
