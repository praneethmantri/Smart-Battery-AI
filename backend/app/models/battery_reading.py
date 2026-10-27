from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class BatteryReading(Base):
    """Stores high-frequency sensor readings (voltage, current, temperature, SoC)."""

    __tablename__ = "battery_readings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    voltage = Column(Float, nullable=False)
    current = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    battery_percent = Column(Float, nullable=False)

    # Time-series composite index for efficient user range queries
    __table_args__ = (
        Index("ix_battery_readings_user_timestamp", "user_id", "timestamp"),
    )

    # Relationships
    user = relationship("User", back_populates="battery_readings")

    def __repr__(self) -> str:
        return f"<BatteryReading(id={self.id}, user_id={self.user_id}, soc={self.battery_percent}%, temp={self.temperature}C)>"
