import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.llm import LLMService, GLMBackend, LLMResponse, TokenUsage


@pytest.mark.asyncio
async def test_glm_backend_complete_mock():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "테스트 응답"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 50

    backend = GLMBackend()
    with patch.object(backend.client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
        result = await backend.complete("system", "user query")

    assert result.content == "테스트 응답"
    assert result.backend == "glm"
    assert result.usage.completion_tokens == 50


@pytest.mark.asyncio
async def test_llm_service_default_backend():
    service = LLMService()
    assert isinstance(service.backend, GLMBackend)


@pytest.mark.asyncio
async def test_glm_backend_uses_min_2000_tokens():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "response"
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 200

    backend = GLMBackend()
    captured_kwargs = {}

    async def capture_create(**kwargs):
        captured_kwargs.update(kwargs)
        return mock_response

    with patch.object(backend.client.chat.completions, "create", new=capture_create):
        await backend.complete("sys", "user")

    assert captured_kwargs.get("max_tokens", 0) >= 2000
