from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class Prediction(Base):
    """Stores ML model inference results predicting expected unplug time."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    predicted_unplug_time = Column(DateTime, nullable=False)
    confidence_score = Column(Float, nullable=False)
    model_version = Column(String(50), default="1.0.0", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Index for fast user prediction retrieval
    __table_args__ = (
        Index("ix_predictions_user_created", "user_id", "created_at"),
    )

    # Relationships
    user = relationship("User", back_populates="predictions")

    def __repr__(self) -> str:
        return f"<Prediction(id={self.id}, user_id={self.user_id}, predicted_unplug={self.predicted_unplug_time})>"
