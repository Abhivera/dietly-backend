from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


def total_burned_from_json(calories_burned: list | None) -> int:
    if not calories_burned:
        return 0
    total = 0
    for activity in calories_burned:
        try:
            total += int(activity.get("calories", 0))
        except (ValueError, TypeError):
            continue
    return total


class UserCalories(Base):
    __tablename__ = "user_calories"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_date", name="uq_user_calories_user_activity_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_date = Column(Date, nullable=False, index=True)
    calories_burned = Column(JSON, nullable=False)
    total_burned = Column(Integer, nullable=False, server_default="0")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="user_calories")

    def __repr__(self) -> str:
        return f"<UserCalories(id={self.id}, user_id={self.user_id}, activity_date='{self.activity_date}')>"
