"""LLM Gateway: centralized LLM call orchestration with rate limiting."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from loguru import logger

from ..config import LlmConfig
from .rate_limiter import LLMRateLimiter


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]]) -> str:
        pass


class MockProvider(LLMProvider):
    """Offline mock provider for local development and testing."""

    async def generate(self, messages: list[dict[str, str]]) -> str:
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break

        return (
            f"[Mock LLM] I received your message: \"{last_user_msg}\". "
            "This is a mock response. "
            "Configure a real provider in stu.json to get actual LLM responses."
        )


class AISuiteProvider(LLMProvider):
    """Provider that routes through the aisuite library."""

    def __init__(self, config: LlmConfig):
        self.config = config

    async def generate(self, messages: list[dict[str, str]]) -> str:
        try:
            import aisuite as ai
        except ImportError as exc:
            raise RuntimeError(
                "aisuite is not installed. Install it with: uv add aisuite"
            ) from exc

        client = ai.Client()

        def _call() -> str:
            response = client.chat.completions.create(
                model=self.config.model,
                messages=messages,
            )
            return response.choices[0].message.content or ""

        return await asyncio.to_thread(_call)


class LLMGateway:
    """
    Centralized gateway for all LLM calls.
    Every call is rate-limited through the global LLMRateLimiter.
    """

    def __init__(self, config: LlmConfig, rate_limiter: LLMRateLimiter):
        self.config = config
        self.rate_limiter = rate_limiter
        self.provider = self._create_provider()
        logger.info(f"LLM Gateway initialized with provider: {config.provider}")

    def _create_provider(self) -> LLMProvider:
        if self.config.provider == "mock":
            return MockProvider()
        elif self.config.provider == "aisuite":
            return AISuiteProvider(self.config)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config.provider}")

    async def generate(self, messages: list[dict[str, str]]) -> str:
        async with self.rate_limiter.slot():
            logger.debug(f"LLM Gateway calling provider: {self.config.provider}")
            return await self.provider.generate(messages)
