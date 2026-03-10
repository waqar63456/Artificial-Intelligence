"""
Unified LLM integration layer supporting OpenAI, DeepSeek, and Claude APIs.
Provides a single interface for all AI model interactions with automatic fallback.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from autodev.core.config import LLMConfig

logger = logging.getLogger("autodev")


class LLMResponse:
    """Standardized response from any LLM provider."""

    def __init__(
        self,
        content: str,
        model: str,
        provider: str,
        usage: dict[str, int] | None = None,
        raw_response: Any = None,
    ) -> None:
        self.content = content
        self.model = model
        self.provider = provider
        self.usage = usage or {}
        self.raw_response = raw_response

    def as_json(self) -> dict[str, Any] | None:
        """Try to parse content as JSON."""
        try:
            # Strip markdown code fences if present
            text = self.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first and last lines (code fences)
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Generate a structured (JSON) response from the LLM."""
        ...


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider (also works for DeepSeek via base_url)."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "openai package is required. Install with: pip install openai"
                )
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url or None,
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        client = self._get_client()
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )
        choice = response.choices[0]
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        return LLMResponse(
            content=choice.message.content or "",
            model=self.config.model,
            provider=self.config.provider,
            usage=usage,
            raw_response=response,
        )

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        format_instruction = (
            "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no code fences, no explanation."
        )
        return await self.generate(
            prompt=prompt + format_instruction,
            system_prompt=system_prompt,
            temperature=0.1,
        )


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError(
                    "anthropic package is required. Install with: pip install anthropic"
                )
            self._client = AsyncAnthropic(api_key=self.config.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if temperature is not None:
            kwargs["temperature"] = temperature
        else:
            kwargs["temperature"] = self.config.temperature

        response = await client.messages.create(**kwargs)
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
        usage = {
            "input_tokens": response.usage.input_tokens if response.usage else 0,
            "output_tokens": response.usage.output_tokens if response.usage else 0,
        }
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider="claude",
            usage=usage,
            raw_response=response,
        )

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        format_instruction = (
            "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no code fences, no explanation."
        )
        return await self.generate(
            prompt=prompt + format_instruction,
            system_prompt=system_prompt,
            temperature=0.1,
        )


def create_provider(config: LLMConfig) -> BaseLLMProvider:
    """Factory function to create an LLM provider from config."""
    if config.provider in ("openai", "deepseek"):
        return OpenAIProvider(config)
    elif config.provider == "claude":
        return ClaudeProvider(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")


class LLMManager:
    """
    Manages LLM providers with automatic fallback.
    Uses the primary provider first, then falls back to alternatives.
    """

    def __init__(self, primary: LLMConfig, fallbacks: list[LLMConfig] | None = None) -> None:
        self.primary = create_provider(primary)
        self.fallbacks = [create_provider(fb) for fb in (fallbacks or [])]
        self._providers = [self.primary] + self.fallbacks

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate a response, falling back to alternative providers on failure."""
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                logger.warning(
                    "Provider %s failed: %s. Trying next.",
                    provider.config.provider,
                    str(e),
                )
                last_error = e
        raise RuntimeError(
            f"All LLM providers failed. Last error: {last_error}"
        )

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str = "",
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Generate a structured response with fallback."""
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.generate_structured(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_format=response_format,
                )
            except Exception as e:
                logger.warning(
                    "Provider %s failed (structured): %s. Trying next.",
                    provider.config.provider,
                    str(e),
                )
                last_error = e
        raise RuntimeError(
            f"All LLM providers failed (structured). Last error: {last_error}"
        )
