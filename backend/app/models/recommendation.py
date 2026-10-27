from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class Recommendation(Base):
    """Stores AI-generated charging plans and schedule recommendations."""

    __tablename__ = "charging_recommendations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("charging_sessions.id", ondelete="CASCADE"), nullable=True, index=True)

    # Core required fields
    predicted_unplug_time = Column(DateTime, nullable=False)
    recommended_start_time = Column(DateTime, nullable=False)
    target_soc = Column(Float, default=80.0, nullable=False)
    recommendation_message = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Optimization phase breakdown fields
    mode = Column(String(32), default="optimized_delayed", nullable=False)
    phase_1_fast_charge_until = Column(DateTime, nullable=True)
    hold_at_pct = Column(Float, default=80.0, nullable=False)
    phase_2_topoff_start = Column(DateTime, nullable=True)
    confidence_score = Column(Float, default=0.0, nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_recommendations_user_created", "user_id", "created_at"),
    )

    # Relationships
    user = relationship("User", back_populates="recommendations")
    session = relationship("ChargingSession", back_populates="recommendations")

    def __repr__(self) -> str:
        return f"<Recommendation(id={self.id}, user_id={self.user_id}, target_soc={self.target_soc}%)>"
