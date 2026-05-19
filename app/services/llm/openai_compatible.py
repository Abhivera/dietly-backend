"""OpenAI-compatible Chat Completions API (OpenAI + Groq) with vision."""

from __future__ import annotations

import logging
from typing import Any

from pathlib import Path

import httpx

from app.services.llm.base import VisionLLMProvider
from app.services.llm import shared

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(VisionLLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        name: str,
        use_json_response_format: bool = True,
        require_api_key: bool = True,
    ) -> None:
        if require_api_key and not api_key:
            raise ValueError(f"{name} API key is not configured")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._name = name
        self._use_json = use_json_response_format
        if name == "Groq":
            err = shared.groq_vision_model_error(model)
            if err:
                raise ValueError(err)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _chat(
        self, messages: list[dict[str, Any]], extra: dict[str, Any] | None = None
    ) -> str:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.1,
        }
        if self._use_json:
            body["response_format"] = {"type": "json_object"}
        if extra:
            body.update(extra)
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            )
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = r.json().get("error", {}).get("message", str(e))
            except Exception:
                detail = r.text or str(e)
            raise RuntimeError(f"{self._name} HTTP {r.status_code}: {detail}") from e
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"{self._name}: empty choices")
        msg = choices[0].get("message") or {}
        return (msg.get("content") or "").strip()

    async def analyze_image_bytes(
        self,
        image_content: bytes,
        content_type: str | None,
        description: str | None = None,
    ) -> dict[str, Any]:
        if self._name == "Groq":
            err = shared.groq_vision_model_error(self._model)
            if err:
                return shared.error_result(err)
        try:
            b64, mime = shared.encode_image_bytes(image_content, content_type)
            prompt = shared.build_vision_prompt(description)
            data_uri = f"data:{mime};base64,{b64}"
            text = await self._chat(
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": data_uri},
                            },
                        ],
                    }
                ],
            )
            result = shared.parse_json_object_from_model_text(text)
            return shared.validate_and_fix_result(result)
        except Exception as e:
            logger.exception("%s analyze_image_bytes failed", self._name)
            return shared.error_result(str(e))

    async def analyze_image_path(
        self, image_path: str, description: str | None = None
    ) -> dict[str, Any]:
        try:
            content = Path(image_path).read_bytes()
            mime = shared.get_mime_type(image_path=image_path, image_content=content)
            return await self.analyze_image_bytes(content, mime, description)
        except Exception as e:
            logger.exception("%s analyze_image_path failed", self._name)
            return shared.error_result(str(e))

    async def health_check(self) -> bool:
        try:
            text = await self._chat(
                [{"role": "user", "content": "Reply with JSON only: {\"ok\": true}"}],
            )
            shared.parse_json_object_from_model_text(text)
            return True
        except Exception as e:
            logger.error("%s health_check failed: %s", self._name, e)
            return False
