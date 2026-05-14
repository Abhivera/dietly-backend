"""Select vision LLM implementation from settings."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings
from app.services.llm.base import VisionLLMProvider
from app.services.llm.bedrock import BedrockProvider
from app.services.llm.gemini import GeminiProvider
from app.services.llm.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


def _build_vision_llm() -> VisionLLMProvider:
    provider = (settings.llm_provider or "gemini").strip().lower()
    logger.info("Using LLM provider: %s", provider)

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            name="OpenAI",
            use_json_response_format=True,
        )

    if provider == "groq":
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return OpenAICompatibleProvider(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            model=settings.groq_model,
            name="Groq",
            use_json_response_format=False,
        )

    if provider == "bedrock":
        return BedrockProvider(
            region=settings.aws_region,
            model_id=settings.bedrock_model_id,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    if provider == "ollama":
        return OpenAICompatibleProvider(
            api_key=(settings.ollama_api_key or ""),
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            name="Ollama",
            use_json_response_format=False,
            require_api_key=False,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. Use gemini, openai, groq, bedrock, or ollama."
    )


@lru_cache(maxsize=1)
def get_vision_llm() -> VisionLLMProvider:
    return _build_vision_llm()
