import logging
from collections.abc import AsyncGenerator

import httpx
from apps.api.src.core.config import settings
from apps.api.src.core.exceptions import AppException
from apps.api.src.llm.base import BaseLLMProvider, ChatMessage
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

logger = logging.getLogger("ai_knowledge_assistant.llm.openai")


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI Large Language Model provider implementation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
    ):
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or settings.LLM_MODEL
        self._default_temp = (
            default_temperature if default_temperature is not None else settings.LLM_TEMPERATURE
        )
        self._default_max_tokens = default_max_tokens or settings.LLM_MAX_TOKENS

        if not self._api_key:
            logger.warning("OPENAI_API_KEY is not set. Real OpenAI requests will fail.")

        self._client = AsyncOpenAI(
            api_key=self._api_key or "sk-dummy-key",
            timeout=httpx.Timeout(60.0, connect=10.0),
            max_retries=2,
        )

    @property
    def model_name(self) -> str:
        return self._model

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def generate(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate full non-streamed text completion."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=self._convert_messages(messages),
                temperature=temperature if temperature is not None else self._default_temp,
                max_tokens=max_tokens or self._default_max_tokens,
                stream=False,
            )
            content = response.choices[0].message.content
            return content or ""
        except RateLimitError:
            logger.error("OpenAI rate limit encountered.")
            raise AppException(
                "LLM provider rate limit exceeded. Please retry shortly.", status_code=429
            ) from None
        except APIStatusError as e:
            logger.error(f"OpenAI API status error: {e.status_code}")
            if e.status_code == 401:
                raise AppException(
                    "LLM provider authentication failed. Check API key configuration.",
                    status_code=500,
                ) from None
            raise AppException("LLM provider service error.", status_code=502) from None
        except APIConnectionError as e:
            logger.error(f"OpenAI network connection error: {e}")
            raise AppException(
                "Unable to reach LLM provider. Check network connectivity.", status_code=503
            ) from None
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI chat completion: {e}")
            raise AppException(
                "An unexpected error occurred during AI generation.", status_code=500
            ) from None

    async def stream(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream generated tokens asynchronously from OpenAI."""
        try:
            stream_resp = await self._client.chat.completions.create(
                model=self._model,
                messages=self._convert_messages(messages),
                temperature=temperature if temperature is not None else self._default_temp,
                max_tokens=max_tokens or self._default_max_tokens,
                stream=True,
            )
            async for chunk in stream_resp:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except RateLimitError:
            logger.error("OpenAI rate limit during stream.")
            raise AppException(
                "LLM rate limit exceeded. Please try again shortly.", status_code=429
            ) from None
        except APIStatusError as e:
            logger.error(f"OpenAI API status error during stream: {e.status_code}")
            raise AppException(
                "LLM provider error during response streaming.", status_code=502
            ) from None
        except APIConnectionError as e:
            logger.error(f"OpenAI connection error during stream: {e}")
            raise AppException("Network connection to LLM interrupted.", status_code=503) from None
        except Exception as e:
            logger.error(f"Unexpected streaming failure: {e}")
            raise AppException(
                "Response streaming encountered an internal failure.", status_code=500
            ) from None
