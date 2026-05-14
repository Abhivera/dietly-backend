"""MET-based estimates for calories burned (kcal) = MET * weight_kg * (duration_min / 60)."""

from __future__ import annotations

from typing import Final

# Compendium-style METs (approximate, moderate intensity).
_ACTIVITY_MET: Final[dict[str, float]] = {
    "walking": 3.5,
    "running": 9.0,
    "cycling": 6.0,
    "swimming": 6.0,
    "yoga": 2.5,
    "strength_training": 5.0,
}

_ACTIVITY_LABEL: Final[dict[str, str]] = {
    "walking": "Walking",
    "running": "Running",
    "cycling": "Cycling",
    "swimming": "Swimming",
    "yoga": "Yoga",
    "strength_training": "Strength training",
}


def activity_display_label(activity_key: str) -> str:
    return _ACTIVITY_LABEL.get(activity_key, activity_key.replace("_", " ").title())


def estimate_steps_kcal_burned(step_count: int, *, weight_kg: float | None, default_weight_kg: float = 70.0) -> int:
    """Rough kcal from steps using weight (kcal ≈ steps × 0.0005 × weight_kg)."""
    if step_count <= 0:
        return 0
    w = float(weight_kg) if weight_kg is not None and weight_kg > 0 else default_weight_kg
    return max(0, int(round(step_count * 0.0005 * w)))


def estimate_activity_calories(
    activity_key: str,
    duration_minutes: int,
    *,
    weight_kg: float | None,
    default_weight_kg: float = 70.0,
) -> int:
    met = _ACTIVITY_MET.get(activity_key)
    if met is None:
        raise ValueError(f"Unknown activity type: {activity_key}")
    w = float(weight_kg) if weight_kg is not None and weight_kg > 0 else default_weight_kg
    hours = duration_minutes / 60.0
    return max(0, int(round(met * w * hours)))
