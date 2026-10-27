from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, Boolean, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class TelemetrySample(Base):
    """
    Stores periodic local host battery telemetry samples and user activity states.
    Collected by the background Windows telemetry service at configurable intervals
    (e.g. 2-5 minutes) without recording sensitive user content.
    """

    __tablename__ = "telemetry_samples"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    battery_percent = Column(Float, nullable=False)
    is_plugged_in = Column(Boolean, nullable=False)
    seconds_left = Column(Integer, nullable=True)
    is_user_active = Column(Boolean, default=True, nullable=False)
    idle_duration_seconds = Column(Float, default=0.0, nullable=False)
    sleep_gap_seconds = Column(Float, default=0.0, nullable=False)
    source = Column(String(30), default="REAL_WINDOWS", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_telemetry_samples_user_time", "user_id", "timestamp"),
    )

    user = relationship("User", backref="telemetry_samples")

    def __repr__(self) -> str:
        return (
            f"<TelemetrySample(id={self.id}, user_id={self.user_id}, "
            f"soc={self.battery_percent}%, plugged={self.is_plugged_in}, active={self.is_user_active})>"
        )
