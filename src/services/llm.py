from dataclasses import dataclass
import asyncio
import os
from typing import Protocol, runtime_checkable

from dotenv import load_dotenv
from openai import APITimeoutError, AsyncOpenAI, RateLimitError

from src.services.glm_limiter import async_glm47_slot, async_model_slot
from src.services.token_logger import log_usage, usage_counts

load_dotenv()

GLM_API_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
GLM_ANALYSIS_MODEL = os.getenv("GLM_ANALYSIS_MODEL", "glm-4.7")
# glm-4-flash 는 2026-05 기준 deprecated (Zhipu API err 1211).
# 무료·구조화 추출 용도는 glm-4.5-flash 로 교체.
GLM_EXTRACTION_MODEL = os.getenv("GLM_EXTRACTION_MODEL", "glm-4.5-flash")
# 시사점 / 결론 등 품질 우선 단계에서 override 시 사용.
GLM_FINAL_MODEL = os.getenv("GLM_FINAL_MODEL", "glm-5.1")
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
        _key = os.getenv("ZHIPU_API_KEY")
        if not _key:
            raise RuntimeError(
                "ZHIPU_API_KEY is not set — add it to your .env (LLM_BACKEND=glm)."
            )
        self.client = AsyncOpenAI(
            api_key=_key,
            base_url=GLM_API_BASE_URL,
            timeout=GLM_REQUEST_TIMEOUT_SECONDS,
        )
        self.analysis_model = GLM_ANALYSIS_MODEL
        self.extraction_model = GLM_EXTRACTION_MODEL

    async def complete(self, system: str, user: str, **kwargs) -> LLMResponse:
        max_tokens = kwargs.get("max_tokens", 2000)
        # 호출자가 model 명시 시 override (e.g. 시사점 단계는 GLM-5.1 사용)
        chosen_model = kwargs.get("model") or self.analysis_model
        params = {
            "model": chosen_model,
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

        response = await self._create_with_retries(params, model=chosen_model)
        msg = response.choices[0].message
        reasoning = getattr(msg, "reasoning_content", None) or ""
        prompt_tokens, completion_tokens = usage_counts(getattr(response, "usage", None))
        log_usage(chosen_model, prompt_tokens, completion_tokens, "llm.complete")
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
        # extract 도 모델별 limiter 적용 (glm-4.5-flash 는 concurrency=2)
        response = await self._create_with_retries({
            "model": self.extraction_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }, model=self.extraction_model)
        msg = response.choices[0].message
        prompt_tokens, completion_tokens = usage_counts(getattr(response, "usage", None))
        log_usage(self.extraction_model, prompt_tokens, completion_tokens, "llm.extract")
        return json.loads(msg.content or "{}")

    async def _create_with_retries(self, params: dict, model: str = "", use_limit: bool = True,
                                   use_glm47_limit: bool = False):
        """모델별 limiter 자동 적용.

        - `use_limit=True` (기본): glm_limiter 의 명시 mapping 으로 모델별 slot 획득.
          알 수 없는 모델은 보수적 default (concurrency=1) slot.
        - `use_glm47_limit`: legacy 호환 — 모델 인자 없이 4.7 slot 강제 시 사용.
        """
        retry_delays = [30, 60, 120]
        last_err = None
        for attempt, delay in enumerate([0] + retry_delays):
            if delay:
                print(f"   [GLM retry] waiting {delay}s (attempt {attempt}/{len(retry_delays)})...")
                await asyncio.sleep(delay)
            try:
                if use_glm47_limit and not model:
                    async with async_glm47_slot():
                        return await self.client.chat.completions.create(**params)
                if use_limit and model:
                    async with async_model_slot(model):
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
