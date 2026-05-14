"""Shared vision prompt, MIME detection, and response normalization for all LLM providers."""

from __future__ import annotations

import base64
import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


def vision_json_instructions() -> str:
    return (
        "Analyze this image carefully and determine if it contains food items. "
        "Return ONLY a valid JSON object (no markdown) with these exact keys:\n"
        "- 'is_food': boolean (true if image contains any food items, false if not)\n"
        "- 'food_items': array of detected food item names as strings (empty array if no food)\n"
        "- 'food_items_details': array of objects, each with 'name' (string), 'count' (int), "
        "and 'per_item_calories' (int, estimated calories per item; 0 if unknown)\n"
        "- 'description': single sentence describing what's in the image\n"
        "- 'calories': estimated total calories as a number (0 if no food)\n"
        "- 'nutrients': object with keys 'protein', 'carbs', 'fat', 'sugar' (grams, numbers)\n"
        "- 'confidence': confidence score between 0 and 1\n"
        "- 'meal_name': short human-readable title for the meal or dish (e.g. 'Masala dosa breakfast'); "
        "empty string if not food\n"
        "- 'exercise_recommendations': object with keys 'steps' (int) and 'walking_km' (float)\n\n"
        "Example for food image:\n"
        '{"is_food":true,"food_items":["samosa","chutney"],"food_items_details":['
        '{"name":"samosa","count":5,"per_item_calories":300},{"name":"chutney","count":1,"per_item_calories":0}],'
        '"description":"Five samosas and chutney on a plate.","calories":1500,'
        '"nutrients":{"protein":30,"carbs":150,"fat":90,"sugar":15},"confidence":0.95,'
        '"meal_name":"Samosa plate with chutney",'
        '"exercise_recommendations":{"steps":30000,"walking_km":30.0}}\n\n'
        "Example for non-food image:\n"
        '{"is_food":false,"food_items":[],"food_items_details":[],"description":"A person sitting in a chair",'
        '"calories":0,"nutrients":{"protein":0,"carbs":0,"fat":0,"sugar":0},"confidence":0.90,'
        '"meal_name":"",'
        '"exercise_recommendations":{"steps":0,"walking_km":0.0}}'
    )


def build_vision_prompt(description: str | None) -> str:
    base = vision_json_instructions()
    if description:
        return (
            f"The user provided this description for context: '{description}'. "
            f"Use it if relevant.\n\n{base}"
        )
    return base


def get_mime_type(
    *,
    image_path: str | None = None,
    content_type: str | None = None,
    image_content: bytes | None = None,
) -> str:
    if content_type:
        ct = content_type.lower()
        if "jpeg" in ct or "jpg" in ct:
            return "image/jpeg"
        if "png" in ct:
            return "image/png"
        if "gif" in ct:
            return "image/gif"
        if "webp" in ct:
            return "image/webp"
    if image_path:
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_types.get(ext, "image/jpeg")
    if image_content:
        try:
            img = Image.open(BytesIO(image_content))
            fmt = (img.format or "JPEG").lower()
            if fmt == "jpeg":
                return "image/jpeg"
            if fmt == "png":
                return "image/png"
            if fmt == "gif":
                return "image/gif"
            if fmt == "webp":
                return "image/webp"
        except Exception as e:
            logger.warning("Could not detect image format from content: %s", e)
    return "image/jpeg"


def encode_image_bytes(image_content: bytes, content_type: str | None) -> tuple[str, str]:
    b64 = base64.b64encode(image_content).decode("utf-8")
    mime = get_mime_type(content_type=content_type, image_content=image_content)
    return b64, mime


def encode_image_path(image_path: str) -> tuple[str, str]:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    content = path.read_bytes()
    mime = get_mime_type(image_path=str(path), image_content=content)
    return base64.b64encode(content).decode("utf-8"), mime


def parse_json_object_from_model_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)


def validate_and_fix_result(result: dict[str, Any]) -> dict[str, Any]:
    required_keys = [
        "is_food",
        "food_items",
        "food_items_details",
        "description",
        "calories",
        "nutrients",
        "confidence",
        "meal_name",
        "exercise_recommendations",
    ]
    for key in required_keys:
        if key not in result:
            if key == "is_food":
                result[key] = False
            elif key == "food_items":
                result[key] = []
            elif key == "food_items_details":
                result[key] = []
            elif key == "description":
                result[key] = "Image analyzed"
            elif key == "calories":
                result[key] = 0
            elif key == "nutrients":
                result[key] = {"protein": 0, "carbs": 0, "fat": 0, "sugar": 0}
            elif key == "confidence":
                result[key] = 0.5
            elif key == "meal_name":
                result[key] = ""
            elif key == "exercise_recommendations":
                cals = result.get("calories", 0)
                result[key] = {"steps": int(cals * 20), "walking_km": round(cals / 50, 2)}

    if isinstance(result.get("nutrients"), dict):
        for nutrient in ("protein", "carbs", "fat", "sugar"):
            if nutrient not in result["nutrients"]:
                result["nutrients"][nutrient] = 0

    rec = result.get("exercise_recommendations")
    cals = result.get("calories", 0)
    if not isinstance(rec, dict):
        rec = {"steps": int(cals * 20), "walking_km": round(cals / 50, 2)}
    if "steps" not in rec:
        rec["steps"] = int(cals * 20)
    if "walking_km" not in rec:
        rec["walking_km"] = round(cals / 50, 2)
    result["exercise_recommendations"] = rec

    mn = result.get("meal_name")
    if mn is None:
        result["meal_name"] = ""
    elif not isinstance(mn, str):
        result["meal_name"] = str(mn).strip()[:255]
    else:
        result["meal_name"] = mn.strip()[:255]
    return result


def error_result(message: str) -> dict[str, Any]:
    return {
        "description": f"Error analyzing image: {message}",
        "is_food": False,
        "food_items": [],
        "food_items_details": [],
        "calories": 0,
        "nutrients": {"protein": 0, "carbs": 0, "fat": 0, "sugar": 0},
        "confidence": 0.0,
        "meal_name": "",
        "exercise_recommendations": {"steps": 0, "walking_km": 0.0},
    }


def bedrock_image_format(mime: str) -> str:
    m = mime.lower()
    if "png" in m:
        return "png"
    if "gif" in m:
        return "gif"
    if "webp" in m:
        return "webp"
    return "jpeg"
