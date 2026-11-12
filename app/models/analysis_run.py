from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.analysis_explanation import AnalysisExplanation
    from app.models.change_request import ChangeRequest
    from app.models.recommendation import Recommendation


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    change_request_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("change_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    change_request: Mapped[Optional["ChangeRequest"]] = relationship(
        "ChangeRequest",
        back_populates="analysis_runs",
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        order_by="Recommendation.rank",
    )
    explanation: Mapped[Optional["AnalysisExplanation"]] = relationship(
        "AnalysisExplanation",
        back_populates="analysis_run",
        uselist=False,
        cascade="all, delete-orphan",
    )

