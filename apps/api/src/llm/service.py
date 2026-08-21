import logging
from collections.abc import AsyncGenerator

from apps.api.src.core.config import settings
from apps.api.src.llm.base import BaseLLMProvider, ChatMessage
from apps.api.src.llm.mock import MockLLMProvider
from apps.api.src.llm.openai import OpenAILLMProvider

logger = logging.getLogger("ai_knowledge_assistant.llm.service")


class LLMService:
    """Orchestration service providing a single interface for LLM completions and streaming."""

    def __init__(self, provider: BaseLLMProvider | None = None):
        is_placeholder_key = not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith(
            "your_openai_api_key"
        )
        if provider:
            self._provider = provider
        elif settings.LLM_PROVIDER.lower() == "mock" or (
            is_placeholder_key and settings.ENVIRONMENT == "development"
        ):
            logger.info("Using MockLLMProvider for deterministic offline AI generation.")
            self._provider = MockLLMProvider()
        else:
            logger.info(f"Using OpenAILLMProvider (model={settings.LLM_MODEL}).")
            self._provider = OpenAILLMProvider()

    @property
    def provider(self) -> BaseLLMProvider:
        return self._provider

    async def generate(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return await self._provider.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        async for token in self._provider.stream(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield token


_llm_service_instance: LLMService | None = None


def get_llm_service() -> LLMService:
    """Dependency / singleton provider for LLMService."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
