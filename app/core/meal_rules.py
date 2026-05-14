"""Rules for auto-flagging meal images (user can still override via PATCH)."""

from __future__ import annotations

MEAL_AUTO_CONFIDENCE_MIN = 0.8
MEAL_AUTO_MIN_FOOD_ITEMS = 2


def infer_is_meal(is_food: bool | None, confidence: float | None, food_items: list | None) -> bool:
    if not is_food:
        return False
    items = food_items or []
    c = float(confidence) if confidence is not None else 0.0
    return c >= MEAL_AUTO_CONFIDENCE_MIN and len(items) >= MEAL_AUTO_MIN_FOOD_ITEMS
