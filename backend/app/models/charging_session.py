from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class ChargingSession(Base):
    """Stores historical and active charging session events."""

    __tablename__ = "charging_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    start_time = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    end_time = Column(DateTime, nullable=True)
    start_battery_percent = Column(Float, nullable=False)
    end_battery_percent = Column(Float, nullable=True)
    average_temperature = Column(Float, nullable=True)
    charging_duration_minutes = Column(Float, nullable=True)
    charger_type = Column(String(50), default="standard_ac", nullable=False)
    screen_usage_minutes = Column(Float, default=0.0, nullable=True)
    idle_usage_minutes = Column(Float, default=0.0, nullable=True)
    previous_day_usage_minutes = Column(Float, default=0.0, nullable=True)
    day_of_week = Column(Integer, nullable=True)  # 0 = Monday, 6 = Sunday
    data_source = Column(String(30), default="SYNTHETIC", nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Composite index for filtering user sessions by start_time
    __table_args__ = (
        Index("ix_charging_sessions_user_start", "user_id", "start_time"),
    )

    # Relationships
    user = relationship("User", back_populates="charging_sessions")
    recommendations = relationship("Recommendation", back_populates="session", cascade="all, delete-orphan")

    # Backward compatibility properties
    @property
    def plug_time(self):
        return self.start_time

    @plug_time.setter
    def plug_time(self, val):
        self.start_time = val

    @property
    def unplug_time(self):
        return self.end_time

    @unplug_time.setter
    def unplug_time(self, val):
        self.end_time = val

    @property
    def start_battery_pct(self):
        return self.start_battery_percent

    @start_battery_pct.setter
    def start_battery_pct(self, val):
        self.start_battery_percent = val

    @property
    def end_battery_pct(self):
        return self.end_battery_percent

    @end_battery_pct.setter
    def end_battery_pct(self, val):
        self.end_battery_percent = val

    @property
    def duration_minutes(self):
        return self.charging_duration_minutes

    @duration_minutes.setter
    def duration_minutes(self, val):
        self.charging_duration_minutes = val

    def __repr__(self) -> str:
        return f"<ChargingSession(id={self.id}, user_id={self.user_id}, start_time={self.start_time})>"
