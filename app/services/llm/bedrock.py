"""AWS Bedrock Converse API (vision + text)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from functools import partial

import boto3

from app.services.llm.base import VisionLLMProvider
from app.services.llm import shared

logger = logging.getLogger(__name__)


class BedrockProvider(VisionLLMProvider):
    def __init__(
        self,
        *,
        region: str,
        model_id: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
    ) -> None:
        if not aws_access_key_id or not aws_secret_access_key:
            raise ValueError("AWS credentials are required for Bedrock")
        self._model_id = model_id
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    def _converse_sync(
        self,
        messages: list[dict[str, Any]],
        inference_config: dict[str, Any],
    ) -> str:
        resp = self._client.converse(
            modelId=self._model_id,
            messages=messages,
            inferenceConfig=inference_config,
        )
        blocks = (resp.get("output") or {}).get("message", {}).get("content") or []
        parts: list[str] = []
        for block in blocks:
            if "text" in block:
                parts.append(block["text"])
        return "\n".join(parts).strip()

    async def analyze_image_bytes(
        self,
        image_content: bytes,
        content_type: str | None,
        description: str | None = None,
    ) -> dict[str, Any]:
        try:
            _, mime = shared.encode_image_bytes(image_content, content_type)
            fmt = shared.bedrock_image_format(mime)
            prompt = shared.build_vision_prompt(description)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt},
                        {"image": {"format": fmt, "source": {"bytes": image_content}}},
                    ],
                }
            ]
            inference = {"maxTokens": 1024, "temperature": 0.1}
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                partial(self._converse_sync, messages, inference),
            )
            result = shared.parse_json_object_from_model_text(text)
            return shared.validate_and_fix_result(result)
        except json.JSONDecodeError as e:
            logger.exception("Bedrock JSON parse failed")
            return shared.error_result(str(e))
        except Exception as e:
            logger.exception("Bedrock analyze_image_bytes failed")
            return shared.error_result(str(e))

    async def analyze_image_path(
        self, image_path: str, description: str | None = None
    ) -> dict[str, Any]:
        from pathlib import Path

        path = Path(image_path)
        content = path.read_bytes()
        mime = shared.get_mime_type(image_path=str(path), image_content=content)
        return await self.analyze_image_bytes(content, mime, description)

    async def health_check(self) -> bool:
        try:
            messages = [
                {
                    "role": "user",
                    "content": [{"text": 'Reply with JSON only: {"ok": true}'}],
                }
            ]
            inference = {"maxTokens": 64, "temperature": 0.0}
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                partial(self._converse_sync, messages, inference),
            )
            shared.parse_json_object_from_model_text(text)
            return True
        except Exception as e:
            logger.error("Bedrock health_check failed: %s", e)
            return False
