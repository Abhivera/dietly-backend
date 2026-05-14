"""Abstract vision LLM used for food image analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VisionLLMProvider(ABC):
    """One implementation per vendor (Gemini, OpenAI, Groq, Bedrock, …)."""

    @abstractmethod
    async def analyze_image_bytes(
        self,
        image_content: bytes,
        content_type: str | None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Return the normalized food-analysis dict (same shape across providers)."""

    @abstractmethod
    async def analyze_image_path(
        self,
        image_path: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Analyze from a file on disk (e.g. public upload temp file)."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Lightweight connectivity check for ops / /test-llm."""
