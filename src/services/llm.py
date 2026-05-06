from dataclasses import dataclass
import asyncio
import os
from typing import Protocol, runtime_checkable

from dotenv import load_dotenv
from openai import APITimeoutError, AsyncOpenAI, RateLimitError

from src.services.glm_limiter import async_glm47_slot
from src.services.token_logger import log_usage, usage_counts

load_dotenv()

GLM_API_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
GLM_ANALYSIS_MODEL = "glm-4.7"
GLM_EXTRACTION_MODEL = "glm-4-flash"
GLM_REQUEST_TIMEOUT_SECONDS = float(os.getenv("GLM_REQUEST_TIMEOUT_SECONDS", "600"))


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class LLMResponse:
    content: str
    usage: TokenUsage
    backend: str
    reasoning: str = ""


@runtime_checkable
class LLMBackend(Protocol):
    async def complete(self, system: str, user: str, **kwargs) -> LLMResponse: ...
    async def extract(self, system: str, user: str, schema: dict) -> dict: ...


class GLMBackend:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("ZHIPU_API_KEY"),
            base_url=GLM_API_BASE_URL,
            timeout=GLM_REQUEST_TIMEOUT_SECONDS,
        )
        self.analysis_model = GLM_ANALYSIS_MODEL
        self.extraction_model = GLM_EXTRACTION_MODEL

    async def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        max_tokens = kwargs.get("max_tokens", 2000)
        params = {
            "model": self.analysis_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", 0.3),
        }
        if kwargs.get("response_format"):
            params["response_format"] = kwargs["response_format"]

        thinking = kwargs.get("thinking")
        if thinking is True or thinking == "enabled":
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        elif thinking is False or thinking == "disabled":
            params["extra_body"] = {"thinking": {"type": "disabled"}}

        response = await self._create_with_retries(params, use_glm47_limit=True)
        msg = response.choices[0].message
        reasoning = getattr(msg, "reasoning_content", None) or ""
        prompt_tokens, completion_tokens = usage_counts(getattr(response, "usage", None))
        log_usage(self.analysis_model, prompt_tokens, completion_tokens, "llm.complete")
        return LLMResponse(
            content=msg.content or "",
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
            backend="glm",
            reasoning=reasoning,
        )

    async def extract(self, system: str, user: str, schema: dict) -> dict:
        import json

        prompt = (
            f"{user}\n\n"
            "Return only a JSON object matching this schema:\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        response = await self._create_with_retries({
            "model": self.extraction_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        })
        msg = response.choices[0].message
        prompt_tokens, completion_tokens = usage_counts(getattr(response, "usage", None))
        log_usage(self.extraction_model, prompt_tokens, completion_tokens, "llm.extract")
        return json.loads(msg.content or "{}")

    async def _create_with_retries(self, params: dict, use_glm47_limit: bool = False):
        retry_delays = [30, 60, 120]
        last_err = None
        for attempt, delay in enumerate([0] + retry_delays):
            if delay:
                print(f"   [GLM retry] waiting {delay}s (attempt {attempt}/{len(retry_delays)})...")
                await asyncio.sleep(delay)
            try:
                if use_glm47_limit:
                    async with async_glm47_slot():
                        return await self.client.chat.completions.create(**params)
                return await self.client.chat.completions.create(**params)
            except (APITimeoutError, RateLimitError) as e:
                last_err = e
                if attempt == len(retry_delays):
                    break
                continue
        raise last_err


class LLMService:
    def __init__(self, backend: LLMBackend = None):
        self.backend = backend or GLMBackend()

    async def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        return await self.backend.complete(system, user, **kwargs)

    async def extract(self, system: str, user: str, schema: dict) -> dict:
        return await self.backend.extract(system, user, schema)
