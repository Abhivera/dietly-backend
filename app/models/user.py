from sqlalchemy import Column, DateTime, Integer, String, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    role = Column(String(20), nullable=False, server_default=text("'user'"), index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    gender = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    weight = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    goal_weight = Column(Integer, nullable=True)
    step_goal = Column(Integer, nullable=False, server_default=text("8000"))

    images = relationship("Image", back_populates="owner", cascade="all, delete-orphan")
    user_calories = relationship("UserCalories", back_populates="user", cascade="all, delete-orphan")
    daily_steps = relationship("DailySteps", back_populates="user", cascade="all, delete-orphan")
    streak_row = relationship(
        "UserStreak",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
