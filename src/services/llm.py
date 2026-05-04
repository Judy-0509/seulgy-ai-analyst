from typing import Protocol, runtime_checkable
from dataclasses import dataclass
import asyncio
import os
from openai import AsyncOpenAI, RateLimitError
from dotenv import load_dotenv

load_dotenv()


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
            base_url="https://open.bigmodel.cn/api/paas/v4/"
        )
        self.analysis_model = "glm-4.7"
        self.extraction_model = "glm-4-flash"

    async def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        max_tokens = kwargs.get("max_tokens", 2000)  # GLM-4.7 reasoning needs >=2000
        params = dict(
            model=self.analysis_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=kwargs.get("temperature", 0.3),
        )
        if kwargs.get("response_format"):
            params["response_format"] = kwargs["response_format"]
        thinking = kwargs.get("thinking")
        if thinking is True or thinking == "enabled":
            params["extra_body"] = {"thinking": {"type": "enabled"}}
        elif thinking is False or thinking == "disabled":
            params["extra_body"] = {"thinking": {"type": "disabled"}}

        # 429 Rate Limit 재시도: 30s → 60s → 120s
        retry_delays = [30, 60, 120]
        last_err = None
        for attempt, delay in enumerate([0] + retry_delays):
            if delay:
                print(f"   [Rate Limit] {delay}초 대기 후 재시도 (시도 {attempt}/{len(retry_delays)})...")
                await asyncio.sleep(delay)
            try:
                response = await self.client.chat.completions.create(**params)
                msg = response.choices[0].message
                reasoning = getattr(msg, "reasoning_content", None) or ""
                return LLMResponse(
                    content=msg.content or "",
                    usage=TokenUsage(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                    ),
                    backend="glm",
                    reasoning=reasoning,
                )
            except RateLimitError as e:
                last_err = e
                if attempt == len(retry_delays):
                    break
                continue
        raise last_err

    async def extract(self, system: str, user: str, schema: dict) -> dict:
        import json
        prompt = f"{user}\n\n반드시 다음 JSON 스키마에 맞게 응답하세요:\n{json.dumps(schema, ensure_ascii=False)}"
        response = await self.client.chat.completions.create(
            model=self.extraction_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        msg = response.choices[0].message
        return json.loads(msg.content or "{}")


class LLMService:
    def __init__(self, backend: LLMBackend = None):
        if backend is None:
            backend_name = os.getenv("LLM_BACKEND", "glm")
            if backend_name == "glm":
                backend = GLMBackend()
            else:
                raise ValueError(f"Unknown LLM backend: {backend_name}. Only 'glm' is supported.")
        self.backend = backend

    async def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        return await self.backend.complete(system, user, **kwargs)

    async def extract(self, system: str, user: str, schema: dict) -> dict:
        return await self.backend.extract(system, user, schema)
