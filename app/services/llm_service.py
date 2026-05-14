"""Food vision analysis — delegates to the configured LLM provider (see `app.services.llm`)."""

from __future__ import annotations

from typing import Any

from app.services.llm.factory import get_vision_llm


class LLMService:
    """Stable import path for the rest of the app (`ImageService`, public analyze, tests)."""

    def __init__(self) -> None:
        self._llm = get_vision_llm()

    async def analyze_image(self, image_path: str, description: str | None = None) -> dict[str, Any]:
        return await self._llm.analyze_image_path(image_path, description=description)

    async def analyze_image_content(
        self,
        image_content: bytes,
        content_type: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        return await self._llm.analyze_image_bytes(
            image_content, content_type, description=description
        )

    async def test_api_connection(self) -> bool:
        return await self._llm.health_check()
