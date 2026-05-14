from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DailySteps(Base):
    __tablename__ = "daily_steps"
    __table_args__ = (UniqueConstraint("user_id", "step_date", name="uq_daily_steps_user_step_date"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    step_date = Column(Date, nullable=False, index=True)
    step_count = Column(Integer, nullable=False, server_default="0")
    distance_km = Column(Float, nullable=True)
    kcal_burned = Column(Integer, nullable=False, server_default="0")
    source = Column(String(32), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="daily_steps")
