from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserStreak(Base):
    """One row per user; recomputed when meals are logged or step data is synced."""

    __tablename__ = "streaks"
    __table_args__ = (UniqueConstraint("user_id", name="uq_streaks_user_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    current_streak = Column(Integer, nullable=False, server_default="0")
    longest_streak = Column(Integer, nullable=False, server_default="0")
    last_logged_date = Column(Date, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="streak_row", uselist=False)
