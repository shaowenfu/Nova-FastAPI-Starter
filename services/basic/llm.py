"""
Unified LLM Service Module.

This module provides a standardized interface for interacting with various Large Language Models (LLMs).
It strictly adheres to the OpenAI API specification for maximum compatibility and extensibility.

Key Components:
1. LLMProvider (Abstract Base Class): Defines the contract (complete/stream).
2. OpenAICompatibleProvider: A generic implementation using the `openai` SDK.
   - This single class supports DeepSeek, Moonshot, Qwen (DashScope), Doubao (Ark), and any other OpenAI-compatible APIs.
3. ModelService: The high-level facade used by the application to access LLM capabilities.

Architecture Decisions:
- **Unified SDK**: We use `AsyncOpenAI` for ALL providers. No manual HTTP requests.
- **Config Driven**: Switching providers is just a matter of changing env vars (BASE_URL, API_KEY).
- **Future Proof**: New models (Gemini, Claude) should be adapted to this interface, either via
  an OpenAI-compatible proxy (recommended) or by adding a specific adapter class here.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Optional, Literal

import structlog
from openai import AsyncOpenAI, APIError

from core.exceptions import LLMServiceError

logger = structlog.get_logger(__name__)


@dataclass
class LLMResponse:
    """Normalized response payload returned by each LLM provider."""

    content: str
    raw: Optional[Any] = None
    usage: Optional[Dict[str, Any]] = None


class LLMProvider(abc.ABC):
    """
    Abstract Base Class for LLM Providers.
    
    All implementations must return `LLMResponse` for completions and `AsyncGenerator[str]` for streams.
    """

    name: str

    @abc.abstractmethod
    async def complete(self, system_prompt: str, user_input: str) -> LLMResponse:
        """Send a non-streaming request to the LLM."""
        ...

    @abc.abstractmethod
    async def stream(self, system_prompt: str, user_input: str) -> AsyncGenerator[str, None]:
        """Send a streaming request to the LLM."""
        ...

    async def aclose(self) -> None:
        """Override when provider needs to release network resources."""
        return None


class OpenAICompatibleProvider(LLMProvider):
    """
    Generic provider for ANY service that supports the OpenAI API format.
    
    This includes:
    - Official OpenAI (GPT-3.5, GPT-4)
    - DeepSeek (deepseek-chat)
    - Aliyun DashScope (qwen-plus, etc. via compatible-mode)
    - Volcengine Ark (doubao, etc. via compatible-mode)
    - Moonshot (moonshot-v1)
    - Local LLMs (Ollama, vLLM, LM Studio)
    """

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model_name: str,
        timeout: float = 60.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.name = name
        self.model_name = model_name
        
        if not api_key:
             raise LLMServiceError(f"API key for {name} is missing.")

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            default_headers=extra_headers,
        )
        
        logger.info(
            "Initialized OpenAICompatibleProvider",
            name=self.name,
            model=self.model_name,
            base_url=base_url
        )

    async def aclose(self) -> None:
        await self._client.close()

    async def complete(self, system_prompt: str, user_input: str) -> LLMResponse:
        try:
            completion = await self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.7, # Default temperature, can be made configurable if needed
            )
        except APIError as exc:
            logger.error(f"{self.name} completion failed", error=str(exc))
            raise LLMServiceError(f"{self.name} completion failed: {exc.message}") from exc
        except Exception as exc:
            logger.error(f"{self.name} unknown error", error=str(exc))
            raise LLMServiceError(f"{self.name} failed with unknown error: {str(exc)}") from exc

        # Defensive programming: ensure content is always a string
        content = _coerce_openai_content(completion.choices[0].message.content)
        
        if not content:
            # Some models might return empty content for tool calls, but here we expect text
            logger.warning(f"{self.name} returned empty content")
            return LLMResponse(content="", raw=completion)

        return LLMResponse(
            content=content,
            raw=completion, # Keep the full object for debugging/logging
            usage=completion.usage.model_dump() if completion.usage else None
        )

    async def stream(self, system_prompt: str, user_input: str) -> AsyncGenerator[str, None]:
        try:
            stream = await self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.7,
                stream=True,
            )
        except APIError as exc:
            logger.error(f"{self.name} stream failed", error=str(exc))
            raise LLMServiceError(f"{self.name} stream failed: {exc.message}") from exc

        async for chunk in stream:
            if not chunk.choices:
                continue
                
            delta = chunk.choices[0].delta
            content = _coerce_openai_content(delta.content)
            
            if content:
                yield content


def _coerce_openai_content(content: Any) -> str:
    """
    Helper to ensure we always return a string, handling edge cases in various SDK versions
    or multi-modal responses.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Handle multi-modal content parts (e.g. GPT-4V)
        parts: list[str] = []
        for item in content:
            # item might be dict or object depending on SDK version/mode
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            
            if text:
                parts.append(text)
        return "".join(parts)
    return str(content)


class ModelService:
    """
    Facade for interacting with the configured LLM provider.
    Application code should use this class, not the providers directly.
    """

    def __init__(self, config) -> None:
        self.config = config
        self.provider_name = (config.DEFAULT_MODEL_PROVIDER or "openai").lower()
        self._provider = self._create_provider()
        logger.info("LLM Service Initialized", provider=self.provider_name)

    def _create_provider(self) -> LLMProvider:
        """
        Factory method to instantiate the correct provider based on configuration.
        """
        
        # Generic OpenAI Compatible Provider (Preferred)
        # Works for: OpenAI, DeepSeek, DashScope, Moonshot, LocalAI, vLLM, etc.
        # Just set LLM_BASE_URL and LLM_API_KEY in your env.
        if self.provider_name in ["openai", "custom", "deepseek", "dashscope", "ark", "moonshot"]:
             return OpenAICompatibleProvider(
                name=self.provider_name,
                api_key=self.config.LLM_API_KEY,
                base_url=self.config.LLM_BASE_URL,
                model_name=self.config.LLM_MODEL,
            )

        raise LLMServiceError(f"Unsupported LLM provider: {self.provider_name}")

    async def aclose(self) -> None:
        if self._provider:
            await self._provider.aclose()

    # -------------------------------------------------------------------------
    # Public API Methods
    # -------------------------------------------------------------------------

    async def generate_response(
        self,
        system_prompt: str,
        user_input: str,
        *,
        include_memory: bool = False,
        memory_query: Optional[str] = None,
        memory_user_id: Optional[str] = None,
        memory_agent_id: Optional[str] = None,
    ) -> str:
        """Simple text generation, returning the content string directly."""
        prompt = self._prepare_prompt(
            system_prompt,
            include_memory=include_memory,
            memory_query=memory_query or user_input,
            memory_user_id=memory_user_id,
            memory_agent_id=memory_agent_id,
        )
        response = await self._provider.complete(prompt, user_input)
        return response.content

    async def generate_response_with_metadata(
        self,
        system_prompt: str,
        user_input: str,
        *,
        include_memory: bool = False,
        memory_query: Optional[str] = None,
        memory_user_id: Optional[str] = None,
        memory_agent_id: Optional[str] = None,
    ) -> LLMResponse:
        """Full text generation, returning content + usage + raw response."""
        prompt = self._prepare_prompt(
            system_prompt,
            include_memory=include_memory,
            memory_query=memory_query or user_input,
            memory_user_id=memory_user_id,
            memory_agent_id=memory_agent_id,
        )
        return await self._provider.complete(prompt, user_input)

    async def generate_response_stream(
        self,
        system_prompt: str,
        user_input: str,
        *,
        include_memory: bool = False,
        memory_query: Optional[str] = None,
        memory_user_id: Optional[str] = None,
        memory_agent_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming text generation."""
        prompt = self._prepare_prompt(
            system_prompt,
            include_memory=include_memory,
            memory_query=memory_query or user_input,
            memory_user_id=memory_user_id,
            memory_agent_id=memory_agent_id,
        )
        async for chunk in self._provider.stream(prompt, user_input):
            yield chunk

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _prepare_prompt(
        self,
        system_prompt: str,
        *,
        include_memory: bool,
        memory_query: Optional[str],
        memory_user_id: Optional[str],
        memory_agent_id: Optional[str],
    ) -> str:
        """Injects memory context into the system prompt if enabled."""
        if not include_memory or not memory_query:
            return system_prompt
            
        # Lazy import to avoid circular dependencies if any
        from core.memory_adapter import build_memory_block, is_memory_enabled
        
        if not is_memory_enabled():
            # Soft warning or error depending on policy. Here we error to be explicit.
            raise LLMServiceError("Memory requested but memory adapter is disabled.")

        memory_block = build_memory_block(
            query=memory_query,
            user_id=memory_user_id,
            agent_id=memory_agent_id,
            header="Relevant Context / Memories:",
        )
        
        if not memory_block:
            return system_prompt
            
        return f"{system_prompt}\n\n{memory_block}"


# -------------------------------------------------------------------------
# Developer Guide: How to Add New Models
# -------------------------------------------------------------------------
#
# Case 1: The new model supports OpenAI-compatible API (Most common)
# ----------------------------------------------------------------
# Examples: Moonshot, MiniMax, DeepSeek, Local LLMs (Ollama)
#
# 1. Add configuration in `core/config.py` (e.g., MOONSHOT_API_KEY).
# 2. In `_create_provider` above, add a new `if`:
#    if self.provider_name == "moonshot":
#        return OpenAICompatibleProvider(
#            name="moonshot",
#            api_key=self.config.MOONSHOT_API_KEY,
#            base_url="https://api.moonshot.cn/v1",
#            model_name="moonshot-v1-8k"
#        )
#
# Case 2: The new model has a completely different API (e.g., Google Gemini Native)
# -------------------------------------------------------------------------------
# Option A (Recommended): Use a proxy like OneAPI to convert it to OpenAI format.
# Option B (If native features are needed):
# 1. Create a new class inheriting from `LLMProvider`:
#    class GeminiProvider(LLMProvider):
#        def __init__(self, api_key): ...
#        async def complete(self, ...): ...
# 2. Register it in `_create_provider`.
