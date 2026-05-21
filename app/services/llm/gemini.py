"""Google Gemini vision (REST v1beta generateContent)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests

from app.services.llm.base import VisionLLMProvider
from app.services.llm import shared as llm_shared

logger = logging.getLogger(__name__)


class GeminiProvider(VisionLLMProvider):
    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("Gemini API key is not configured")
        self._api_key = api_key
        self._model = model
        self._url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )

    def _post(self, payload: dict[str, Any]) -> requests.Response:
        headers = {"Content-Type": "application/json", "User-Agent": "Calovia/1.0"}
        url = f"{self._url}?key={self._api_key}"
        return requests.post(url, headers=headers, json=payload, timeout=120)

    def _parse_generate_content(self, response: requests.Response) -> dict[str, Any]:
        response.raise_for_status()
        content = response.json()
        if "error" in content:
            msg = content["error"].get("message", "Unknown API error")
            raise RuntimeError(msg)
        candidates = content.get("candidates") or []
        if not candidates:
            raise RuntimeError("No candidates in response")
        candidate = candidates[0]
        if candidate.get("finishReason") == "SAFETY":
            raise RuntimeError("Content was blocked by safety filters")
        parts = candidate.get("content", {}).get("parts") or []
        if not parts:
            raise RuntimeError("No content parts in response")
        text = parts[0].get("text") or ""
        return llm_shared.parse_json_object_from_model_text(text)

    async def _vision_payload(
        self, b64: str, mime: str, description: str | None
    ) -> dict[str, Any]:
        prompt = llm_shared.build_vision_prompt(description)
        return {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": b64}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": 1024,
            },
        }

    async def analyze_image_bytes(
        self,
        image_content: bytes,
        content_type: str | None,
        description: str | None = None,
    ) -> dict[str, Any]:
        try:
            b64, mime = llm_shared.encode_image_bytes(image_content, content_type)
            payload = await self._vision_payload(b64, mime, description)
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, self._post, payload)
            result = self._parse_generate_content(resp)
            return llm_shared.validate_and_fix_result(result)
        except Exception as e:
            logger.exception("Gemini analyze_image_bytes failed")
            return llm_shared.error_result(str(e))

    async def analyze_image_path(
        self, image_path: str, description: str | None = None
    ) -> dict[str, Any]:
        try:
            b64, mime = llm_shared.encode_image_path(image_path)
            payload = await self._vision_payload(b64, mime, description)
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, self._post, payload)
            result = self._parse_generate_content(resp)
            return llm_shared.validate_and_fix_result(result)
        except Exception as e:
            logger.exception("Gemini analyze_image_path failed")
            return llm_shared.error_result(str(e))

    async def health_check(self) -> bool:
        try:
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": 'Reply with JSON only: {"ok": true}',
                            }
                        ]
                    }
                ],
                "generationConfig": {"maxOutputTokens": 64, "temperature": 0},
            }
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, self._post, payload)
            self._parse_generate_content(resp)
            return True
        except Exception as e:
            logger.error("Gemini health_check failed: %s", e)
            return False
