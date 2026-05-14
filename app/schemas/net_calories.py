from datetime import date

from pydantic import BaseModel


class NetCaloriesResponse(BaseModel):
    """Eaten (meal images) minus manual activity burns and optional step-derived kcal."""

    date: date
    calories_eaten: int
    calories_burned_manual: int
    calories_burned_steps: int
    calories_burned_total: int
    net_calories: int
